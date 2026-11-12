import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_project_service
from app.db.session import get_db
from app.models import AIAudit, ContentPlan, MarketingStrategy
from app.schemas.ai import AIOutputRead, AuditRequest, ClassifyResponse, ContentPlanRequest, GenerateRequest
from app.services.ai_service import AIService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}", tags=["ai"])


@router.post("/audit", response_model=AIOutputRead, status_code=201)
def generate_audit(
    project_id: uuid.UUID,
    body: AuditRequest | None = None,
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> AIOutputRead:
    """Generate a new audit version from a stored analytics run (LLM, or rule-based without an API key)."""
    body = body or AuditRequest()
    service = AIService(db, use_provider=body.use_ai)
    return AIOutputRead.model_validate(
        service.generate_audit(projects.get(project_id), body.instructions, body.analysis_version)
    )


@router.get("/audit", response_model=AIOutputRead)
def get_audit(project_id: uuid.UUID, version: int | None = None, db: Session = Depends(get_db)) -> AIOutputRead:
    return AIOutputRead.model_validate(AIService(db, use_provider=False).latest(AIAudit, project_id, version))


@router.post("/strategy", response_model=AIOutputRead, status_code=201)
def generate_strategy(
    project_id: uuid.UUID,
    body: GenerateRequest | None = None,
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> AIOutputRead:
    body = body or GenerateRequest()
    service = AIService(db, use_provider=body.use_ai)
    return AIOutputRead.model_validate(service.generate_strategy(projects.get(project_id), body.instructions))


@router.get("/strategy", response_model=AIOutputRead)
def get_strategy(project_id: uuid.UUID, version: int | None = None, db: Session = Depends(get_db)) -> AIOutputRead:
    return AIOutputRead.model_validate(AIService(db, use_provider=False).latest(MarketingStrategy, project_id, version))


@router.post("/content-plan", response_model=AIOutputRead, status_code=201)
def generate_content_plan(
    project_id: uuid.UUID,
    body: ContentPlanRequest | None = None,
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> AIOutputRead:
    body = body or ContentPlanRequest()
    service = AIService(db, use_provider=body.use_ai)
    return AIOutputRead.model_validate(
        service.generate_content_plan(projects.get(project_id), body.instructions, body.start_date)
    )


@router.get("/content-plan", response_model=AIOutputRead)
def get_content_plan(project_id: uuid.UUID, version: int | None = None, db: Session = Depends(get_db)) -> AIOutputRead:
    return AIOutputRead.model_validate(AIService(db, use_provider=False).latest(ContentPlan, project_id, version))


@router.post("/classify", response_model=ClassifyResponse)
def classify_with_ai(
    project_id: uuid.UUID,
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> ClassifyResponse:
    """Re-classify low-confidence posts with the LLM (cached per caption). Re-run analysis afterwards."""
    return ClassifyResponse(**AIService(db).classify_posts(projects.get(project_id)))
