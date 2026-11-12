"""Upload handling: validate, store, profile, detect platform and suggest mappings."""

import io
import uuid
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.core.enums import FileStatus, MappingMethod, Platform, ProjectStatus
from app.core.exceptions import ConflictError, MappingError, NotFoundError, UnsupportedFileTypeError
from app.core.logging import get_logger
from app.ingestion.canonical import canonical_fields
from app.ingestion.mapping import missing_required, suggest_mappings
from app.ingestion.platform_detection import detect_platform
from app.ingestion.profiling import profile_table
from app.ingestion.readers import RawTable, read_table
from app.models import ColumnMapping, Project, UploadedFile
from app.schemas.file import FilePreview, MappingItem
from app.storage import get_storage
from app.utils.files import file_extension, sanitize_filename

logger = get_logger(__name__)


class FileService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.storage = get_storage()
        self.settings = get_settings()

    # ------------------------------------------------------------------ queries
    def list_files(self, project_id: uuid.UUID) -> list[UploadedFile]:
        return list(
            self.db.scalars(
                select(UploadedFile)
                .where(UploadedFile.project_id == project_id)
                .options(selectinload(UploadedFile.mappings))
                .order_by(UploadedFile.created_at)
            )
        )

    def get(self, project_id: uuid.UUID, file_id: uuid.UUID) -> UploadedFile:
        f = self.db.scalar(
            select(UploadedFile)
            .where(UploadedFile.id == file_id, UploadedFile.project_id == project_id)
            .options(selectinload(UploadedFile.mappings))
        )
        if f is None:
            raise NotFoundError("File not found.", {"file_id": str(file_id)})
        return f

    def load_raw(self, f: UploadedFile) -> RawTable:
        return read_table(self.storage.read_bytes(f.storage_key), f.file_type)

    def preview(self, project_id: uuid.UUID, file_id: uuid.UUID, limit: int = 20) -> FilePreview:
        table = self.load_raw(self.get(project_id, file_id))
        head = table.df.head(limit).astype(object).where(table.df.head(limit).notna(), None)
        rows = [{str(k): (None if v is None else str(v)) for k, v in r.items()} for r in head.to_dict("records")]
        return FilePreview(columns=[str(c) for c in table.df.columns], rows=rows, total_rows=len(table.df))

    # ------------------------------------------------------------------ upload
    def upload(
        self,
        project: Project,
        filename: str,
        stream: BinaryIO,
        platform_hint: Platform | None = None,
    ) -> UploadedFile:
        ext = file_extension(filename)
        if ext not in self.settings.allowed_upload_extensions:
            raise UnsupportedFileTypeError(
                f"'{filename}' is not a supported file. Upload CSV or XLSX exports.",
                {"allowed": self.settings.allowed_upload_extensions},
            )
        safe_name = sanitize_filename(filename)
        file_id = uuid.uuid4()
        key = f"projects/{project.id}/uploads/{file_id}_{safe_name}"
        stored = self.storage.save(key, stream, max_bytes=self.settings.max_upload_bytes)

        duplicate = self.db.scalar(
            select(UploadedFile).where(UploadedFile.project_id == project.id, UploadedFile.sha256 == stored.sha256)
        )
        if duplicate is not None:
            self.storage.delete(key)
            raise ConflictError(
                f"'{filename}' was already uploaded to this project.",
                {"existing_file_id": str(duplicate.id)},
            )

        try:
            table = read_table(self.storage.read_bytes(key), ext)
        except Exception:
            self.storage.delete(key)
            raise

        f = UploadedFile(
            id=file_id,
            project_id=project.id,
            original_filename=safe_name,
            storage_key=key,
            file_type=ext,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
        )
        self._analyze_structure(f, table, safe_name, platform_hint)
        self.db.add(f)
        if project.status == ProjectStatus.DRAFT:
            project.status = ProjectStatus.DATA_UPLOADED
        self.db.commit()
        logger.info(
            "file.imported",
            extra={
                "project_id": str(project.id),
                "file_id": str(file_id),
                "rows": f.row_count,
                "columns": f.column_count,
                "platform": f.platform,
                "detection_confidence": f.detection_confidence,
            },
        )
        return self.get(project.id, file_id)

    def upload_bytes(
        self, project: Project, filename: str, content: bytes, platform: Platform | None = None
    ) -> UploadedFile:
        return self.upload(project, filename, io.BytesIO(content), platform)

    def delete(self, project_id: uuid.UUID, file_id: uuid.UUID) -> None:
        f = self.get(project_id, file_id)
        self.storage.delete(f.storage_key)
        self.db.delete(f)
        self.db.commit()

    # ------------------------------------------------------------------ mapping
    def detect_mappings(
        self, project_id: uuid.UUID, file_id: uuid.UUID, platform: Platform | None = None
    ) -> UploadedFile:
        f = self.get(project_id, file_id)
        table = self.load_raw(f)
        self._analyze_structure(f, table, f.original_filename, platform or f.platform)
        f.status = FileStatus.UPLOADED
        self.db.commit()
        logger.info("mapping.detected", extra={"file_id": str(file_id), "platform": f.platform})
        return self.get(project_id, file_id)

    def confirm_mappings(
        self,
        project_id: uuid.UUID,
        file_id: uuid.UUID,
        platform: Platform,
        items: list[MappingItem],
    ) -> UploadedFile:
        f = self.get(project_id, file_id)
        fields = canonical_fields()
        by_source = {m.source_column: m for m in f.mappings}

        unknown_cols = [i.source_column for i in items if i.source_column not in by_source]
        if unknown_cols:
            raise MappingError("Unknown source column(s).", {"columns": unknown_cols})
        unknown_fields = [i.target_field for i in items if i.target_field and i.target_field not in fields]
        if unknown_fields:
            raise MappingError("Unknown target field(s).", {"fields": unknown_fields})
        # Validate the *resulting* mapping (existing rows overridden by submitted items)
        # before mutating anything.
        final = {m.source_column: m.target_field for m in f.mappings}
        final.update({i.source_column: i.target_field for i in items})
        targets = [t for t in final.values() if t]
        dupes = sorted({t for t in targets if targets.count(t) > 1})
        if dupes:
            raise MappingError("Each field can only be mapped from one column.", {"duplicate_fields": dupes})
        mapped = set(targets)
        missing = missing_required(mapped)
        if missing:
            raise MappingError(
                "Required field(s) are not mapped.",
                {"missing": [fields[n].label for n in missing]},
            )
        if not any(fields[t].is_numeric for t in mapped):
            raise MappingError("Map at least one performance metric (likes, reach, views...).")

        for m in f.mappings:
            target = final[m.source_column]
            if m.target_field != target:
                m.method = MappingMethod.MANUAL if target else MappingMethod.UNMAPPED
                m.confidence = 1.0 if target else 0.0
            m.target_field = target
            m.needs_review = False
            m.confirmed = True

        f.platform = platform
        f.status = FileStatus.MAPPED
        self.db.commit()
        logger.info("mapping.confirmed", extra={"file_id": str(file_id), "mapped_fields": len(mapped)})
        return self.get(project_id, file_id)

    # ------------------------------------------------------------------ internals
    def _analyze_structure(
        self,
        f: UploadedFile,
        table: RawTable,
        filename: str,
        platform_hint: Platform | None,
    ) -> None:
        profiles = profile_table(table.df)
        detection = detect_platform(table.df, filename)
        f.row_count = len(table.df)
        f.column_count = len(table.df.columns)
        f.header_row = table.header_row
        f.sheet_name = table.sheet_name
        f.columns = [p.to_dict() for p in profiles]
        f.detected_platform = detection.platform
        f.detection_confidence = detection.confidence
        f.platform = platform_hint or detection.platform

        issues = []
        if table.duplicate_columns:
            issues.append(
                {
                    "code": "duplicate_columns",
                    "severity": "warning",
                    "message": "Duplicate column names were renamed: " + ", ".join(table.duplicate_columns),
                    "column": None,
                    "count": len(table.duplicate_columns),
                    "examples": table.duplicate_columns[:5],
                }
            )
        if f.platform is None:
            issues.append(
                {
                    "code": "platform_undetected",
                    "severity": "warning",
                    "message": "Could not detect the platform. Select it before confirming the mapping.",
                    "column": None,
                    "count": 0,
                    "examples": [],
                }
            )
        f.validation = {
            "stage": "structure",
            "is_valid": True,
            "detection_scores": detection.scores,
            "issues": issues,
        }
        f.mappings.clear()
        self.db.flush()
        for pos, s in enumerate(suggest_mappings(profiles, f.platform)):
            f.mappings.append(
                ColumnMapping(
                    position=pos,
                    source_column=s.source_column,
                    target_field=s.target_field,
                    confidence=s.confidence,
                    method=s.method,
                    needs_review=s.needs_review,
                    confirmed=False,
                    alternatives=s.alternatives,
                )
            )

    def auto_confirm(self, project_id: uuid.UUID, file_id: uuid.UUID) -> UploadedFile:
        """Accept the suggested mapping as-is (used by demo mode)."""
        f = self.get(project_id, file_id)
        if f.platform is None:
            raise MappingError("Platform could not be detected; confirm the mapping manually.")
        items = [MappingItem(source_column=m.source_column, target_field=m.target_field) for m in f.mappings]
        return self.confirm_mappings(project_id, file_id, Platform(f.platform), items)
