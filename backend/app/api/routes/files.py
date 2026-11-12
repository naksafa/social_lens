import uuid

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_project_service
from app.core.enums import Platform
from app.db.session import get_db
from app.ingestion.canonical import canonical_fields
from app.integrations.sources import SOURCES
from app.schemas.file import (
    CanonicalFieldRead,
    FilePreview,
    FileRead,
    MappingConfirmRequest,
    MappingDetectRequest,
    NormalizeRequest,
    NormalizeResponse,
)
from app.services.file_service import FileService
from app.services.normalization_service import NormalizationService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}", tags=["data ingestion"])
meta_router = APIRouter(prefix="/meta", tags=["meta"])


@router.post("/files", response_model=list[FileRead], status_code=status.HTTP_201_CREATED)
def upload_files(
    project_id: uuid.UUID,
    files: list[UploadFile] = File(..., description="One or more CSV/XLSX exports"),
    platform: Platform | None = Form(default=None, description="Platform for all files (optional)"),
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> list[FileRead]:
    project = projects.get(project_id)
    service = FileService(db)
    return [
        FileRead.model_validate(service.upload(project, f.filename or "upload.csv", f.file, platform)) for f in files
    ]


@router.get("/files", response_model=list[FileRead])
def list_files(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[FileRead]:
    return [FileRead.model_validate(f) for f in FileService(db).list_files(project_id)]


@router.get("/files/{file_id}", response_model=FileRead)
def get_file(project_id: uuid.UUID, file_id: uuid.UUID, db: Session = Depends(get_db)) -> FileRead:
    return FileRead.model_validate(FileService(db).get(project_id, file_id))


@router.get("/files/{file_id}/preview", response_model=FilePreview)
def preview_file(
    project_id: uuid.UUID, file_id: uuid.UUID, limit: int = 20, db: Session = Depends(get_db)
) -> FilePreview:
    return FileService(db).preview(project_id, file_id, min(max(limit, 1), 100))


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_file(project_id: uuid.UUID, file_id: uuid.UUID, db: Session = Depends(get_db)) -> Response:
    FileService(db).delete(project_id, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/files/{file_id}/mapping/detect", response_model=FileRead)
def detect_mapping(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    body: MappingDetectRequest | None = None,
    db: Session = Depends(get_db),
) -> FileRead:
    platform = body.platform if body else None
    return FileRead.model_validate(FileService(db).detect_mappings(project_id, file_id, platform))


@router.post("/files/{file_id}/mapping/confirm", response_model=FileRead)
def confirm_mapping(
    project_id: uuid.UUID,
    file_id: uuid.UUID,
    body: MappingConfirmRequest,
    db: Session = Depends(get_db),
) -> FileRead:
    return FileRead.model_validate(FileService(db).confirm_mappings(project_id, file_id, body.platform, body.mappings))


@router.post("/normalize", response_model=NormalizeResponse)
def normalize(
    project_id: uuid.UUID,
    body: NormalizeRequest | None = None,
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> NormalizeResponse:
    project = projects.get(project_id)
    return NormalizationService(db).normalize(project, body.file_ids if body else None)


@meta_router.get("/canonical-fields", response_model=list[CanonicalFieldRead])
def list_canonical_fields() -> list[CanonicalFieldRead]:
    return [
        CanonicalFieldRead(name=f.name, label=f.label, type=f.type, required=f.required)
        for f in canonical_fields().values()
    ]


@meta_router.get("/integrations")
def list_integrations() -> list[dict]:
    """Status of direct platform API integrations (planned; uploads are used in the MVP)."""
    return [
        {"platform": st.platform.value, "available": st.available, "reason": st.reason,
         "required_scopes": st.required_scopes, "docs_url": st.docs_url}
        for st in (src.status() for src in SOURCES.values())
    ]  # fmt: skip
