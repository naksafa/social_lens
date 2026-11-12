import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session

from app.api.deps import get_project_service
from app.db.session import get_db
from app.reporting.report_service import ReportService
from app.services.project_service import ProjectService

router = APIRouter(prefix="/projects/{project_id}", tags=["report"])


@router.get("/report", response_class=HTMLResponse)
def get_report(
    project_id: uuid.UUID,
    format: Literal["html", "pdf"] = "html",
    download: bool = False,
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> Response:
    """Full audit report built from stored analytics, audit, strategy and content plan."""
    project = projects.get(project_id)
    service = ReportService(db)
    slug = "".join(c if c.isalnum() else "_" for c in project.name)[:50] or "report"
    if format == "pdf":
        return Response(
            content=service.render_pdf(project),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{slug}_audit.pdf"'},
        )
    headers = {"Content-Disposition": f'attachment; filename="{slug}_audit.html"'} if download else {}
    return HTMLResponse(content=service.render_html(project), headers=headers)
