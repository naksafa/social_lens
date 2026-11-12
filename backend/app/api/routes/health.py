from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.config import Settings, get_settings
from app.db.session import check_database, get_db
from app.schemas.common import ComponentStatus, HealthResponse

router = APIRouter(tags=["system"])


def _dialect(db: Session) -> str:
    name = db.get_bind().dialect.name
    return {"postgresql": "PostgreSQL", "sqlite": "SQLite"}.get(name, name)


@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)) -> HealthResponse:
    db_ok = check_database(db)
    ai_status = (
        ComponentStatus(status="ok", detail=settings.ai_provider)
        if settings.ai_configured
        else ComponentStatus(
            status="not_configured",
            detail="AI features disabled until an API key is set; analytics still work.",
        )
    )
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        app=settings.app_name,
        version=settings.app_version,
        environment=settings.environment,
        database=ComponentStatus(status="ok" if db_ok else "error", detail=_dialect(db)),
        ai=ai_status,
    )
