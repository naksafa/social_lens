import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import FileStatus, MappingMethod, Platform
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, str_enum
from app.models.project import Project


class UploadedFile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "uploaded_files"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    original_filename: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512))
    file_type: Mapped[str] = mapped_column(String(10))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    status: Mapped[FileStatus] = mapped_column(str_enum(FileStatus), default=FileStatus.UPLOADED)

    row_count: Mapped[int | None] = mapped_column(Integer)
    column_count: Mapped[int | None] = mapped_column(Integer)
    # Column profiles: [{name, dtype, null_pct, sample_values}, ...]
    columns: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)
    header_row: Mapped[int] = mapped_column(Integer, default=0)
    sheet_name: Mapped[str | None] = mapped_column(String(120))

    # Platform chosen by the user, else the detected one.
    platform: Mapped[Platform | None] = mapped_column(str_enum(Platform))
    detected_platform: Mapped[Platform | None] = mapped_column(str_enum(Platform, name="detected_platform"))
    detection_confidence: Mapped[float | None] = mapped_column(Float)

    # ValidationReport as JSON ({"is_valid", "issues": [...], "stats": {...}}).
    validation: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    posts_imported: Mapped[int | None] = mapped_column(Integer)

    project: Mapped[Project] = relationship(back_populates="files")
    mappings: Mapped[list["ColumnMapping"]] = relationship(
        back_populates="file", cascade="all, delete-orphan", order_by="ColumnMapping.position"
    )


class ColumnMapping(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Mapping of one source column in a file to one canonical field (or none)."""

    __tablename__ = "column_mappings"
    __table_args__ = (UniqueConstraint("file_id", "source_column"),)

    file_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("uploaded_files.id", ondelete="CASCADE"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)
    source_column: Mapped[str] = mapped_column(String(255))
    target_field: Mapped[str | None] = mapped_column(String(64))
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    method: Mapped[MappingMethod] = mapped_column(str_enum(MappingMethod), default=MappingMethod.UNMAPPED)
    needs_review: Mapped[bool] = mapped_column(default=False)
    confirmed: Mapped[bool] = mapped_column(default=False)
    alternatives: Mapped[list[dict[str, Any]]] = mapped_column(JSONType, default=list)

    file: Mapped[UploadedFile] = relationship(back_populates="mappings")
