import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import FileStatus, MappingMethod, Platform


class ColumnMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_column: str
    target_field: str | None
    confidence: float
    method: MappingMethod
    needs_review: bool
    confirmed: bool
    alternatives: list[dict[str, Any]]


class FileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    original_filename: str
    file_type: str
    size_bytes: int
    status: FileStatus
    row_count: int | None
    column_count: int | None
    header_row: int
    sheet_name: str | None
    columns: list[dict[str, Any]]
    platform: Platform | None
    detected_platform: Platform | None
    detection_confidence: float | None
    validation: dict[str, Any]
    posts_imported: int | None
    created_at: datetime
    mappings: list[ColumnMappingRead]


class FilePreview(BaseModel):
    columns: list[str]
    rows: list[dict[str, Any]]
    total_rows: int


class MappingDetectRequest(BaseModel):
    platform: Platform | None = Field(
        default=None, description="Override the detected platform before re-detecting mappings."
    )


class MappingItem(BaseModel):
    source_column: str
    target_field: str | None


class MappingConfirmRequest(BaseModel):
    platform: Platform
    mappings: list[MappingItem]


class NormalizeRequest(BaseModel):
    file_ids: list[uuid.UUID] | None = Field(
        default=None, description="Files to normalize; defaults to every mapped file."
    )


class FileNormalizationResult(BaseModel):
    file_id: uuid.UUID
    filename: str
    platform: Platform | None
    status: FileStatus
    posts_imported: int
    validation: dict[str, Any]


class NormalizeResponse(BaseModel):
    files: list[FileNormalizationResult]
    total_posts: int


class CanonicalFieldRead(BaseModel):
    name: str
    label: str
    type: str
    required: bool
