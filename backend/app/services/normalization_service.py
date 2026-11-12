"""Turn mapped uploads into canonical SocialPost / MetricSnapshot rows.

Re-normalizing a file replaces only the posts that came from that file, so files
can be corrected and re-imported independently.
"""

import uuid

import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.enums import ClassificationSource, FileStatus, Platform, ProjectStatus
from app.core.exceptions import InvalidDatasetError
from app.core.logging import get_logger
from app.ingestion.normalizer import normalize_table
from app.models import MetricSnapshot, PlatformAccount, Project, SocialPost, UploadedFile
from app.schemas.file import FileNormalizationResult, NormalizeResponse
from app.services.file_service import FileService
from app.utils.serialization import records

logger = get_logger(__name__)

_POST_COLUMNS = {c.key for c in SocialPost.__table__.columns}


class NormalizationService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.files = FileService(db)

    def normalize(self, project: Project, file_ids: list[uuid.UUID] | None = None) -> NormalizeResponse:
        files = self.files.list_files(project.id)
        if file_ids:
            wanted = set(file_ids)
            files = [f for f in files if f.id in wanted]
        candidates = [f for f in files if f.status in (FileStatus.MAPPED, FileStatus.NORMALIZED, FileStatus.FAILED)]
        candidates = [f for f in candidates if any(m.confirmed for m in f.mappings)]
        if not candidates:
            raise InvalidDatasetError("No files with a confirmed column mapping. Confirm mappings before normalizing.")

        results = [self._normalize_file(project, f) for f in candidates]
        if any(r.status == FileStatus.NORMALIZED for r in results):
            project.status = ProjectStatus.NORMALIZED
            self._sync_platforms(project)
        self.db.commit()

        total = self.db.query(SocialPost).filter(SocialPost.project_id == project.id).count()
        return NormalizeResponse(files=results, total_posts=total)

    def _normalize_file(self, project: Project, f: UploadedFile) -> FileNormalizationResult:
        platform = Platform(f.platform)
        mapping = {m.source_column: m.target_field for m in f.mappings if m.target_field}
        table = self.files.load_raw(f)
        result = normalize_table(table.df, mapping, platform, project.timezone)
        report = result.report

        # Replace this file's previous import.
        self.db.execute(delete(SocialPost).where(SocialPost.source_file_id == f.id))
        self.db.execute(delete(MetricSnapshot).where(MetricSnapshot.source_file_id == f.id))

        imported = 0
        if report.is_valid and not result.posts.empty:
            posts = result.posts
            # Skip posts already imported from another file of this project (overlapping exports).
            existing = set(
                self.db.scalars(
                    select(SocialPost.external_post_id).where(
                        SocialPost.project_id == project.id,
                        SocialPost.platform == platform,
                    )
                )
            )
            overlap = posts["external_post_id"].isin(existing)
            if overlap.any():
                report.add(
                    "overlapping_posts",
                    "warning",
                    f"{int(overlap.sum())} post(s) were already imported from another file and were skipped.",
                    "external_post_id",
                    int(overlap.sum()),
                )
                posts = posts[~overlap]
            report.rows_valid = len(posts)

            rows = []
            for rec in records(posts):
                row = {k: v for k, v in rec.items() if k in _POST_COLUMNS}
                row.update(project_id=project.id, source_file_id=f.id, platform=platform)
                if row.get("content_topic"):
                    row["topic_source"] = ClassificationSource.SOURCE
                    row["topic_confidence"] = 1.0
                rows.append(row)
            self.db.bulk_insert_mappings(SocialPost, rows)  # type: ignore[arg-type]
            imported = len(rows)
            self._store_snapshots(project, platform, f, result.snapshots)

        f.validation = {"stage": "normalization", **report.to_dict()}
        f.posts_imported = imported
        f.status = FileStatus.NORMALIZED if report.is_valid and imported else FileStatus.FAILED
        logger.info(
            "normalization.file_completed",
            extra={
                "file_id": str(f.id),
                "platform": platform.value,
                "posts": imported,
                "warnings": sum(i.severity == "warning" for i in report.issues),
                "errors": sum(i.severity == "error" for i in report.issues),
            },
        )
        return FileNormalizationResult(
            file_id=f.id,
            filename=f.original_filename,
            platform=platform,
            status=f.status,
            posts_imported=imported,
            validation=f.validation,
        )

    def _store_snapshots(self, project: Project, platform: Platform, f: UploadedFile, snaps: pd.DataFrame) -> None:
        if snaps is None or snaps.empty:
            return
        dates = list(snaps["snapshot_date"])
        self.db.execute(
            delete(MetricSnapshot).where(
                MetricSnapshot.project_id == project.id,
                MetricSnapshot.platform == platform,
                MetricSnapshot.snapshot_date.in_(dates),
            )
        )
        self.db.bulk_insert_mappings(
            MetricSnapshot,  # type: ignore[arg-type]
            [
                {
                    "id": uuid.uuid4(),
                    "project_id": project.id,
                    "platform": platform,
                    "snapshot_date": r["snapshot_date"],
                    "followers": r["followers"],
                    "source_file_id": f.id,
                }
                for r in records(snaps)
            ],
        )

    def _sync_platforms(self, project: Project) -> None:
        present = set(
            self.db.scalars(select(SocialPost.platform).where(SocialPost.project_id == project.id).distinct())
        )
        known = {a.platform for a in project.platform_accounts}
        for p in present - known:
            project.platform_accounts.append(PlatformAccount(platform=p, source="upload"))
        merged = list(dict.fromkeys([*project.platforms, *[Platform(p).value for p in present]]))
        project.platforms = merged
