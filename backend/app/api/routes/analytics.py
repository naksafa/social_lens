import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_project_service
from app.core.enums import Platform
from app.db.session import get_db
from app.models import AnalyticsRun, Insight, SocialPost
from app.schemas.analytics import (
    AnalyticsRead,
    AnalyticsRunRead,
    AnalyzeRequest,
    InsightList,
    InsightRead,
    PostPage,
    PostRead,
)
from app.services.analysis_pipeline import AnalysisPipeline, get_run, load_sections
from app.services.jobs import TaskRunner, get_task_runner
from app.services.project_service import ProjectService
from app.utils.csv_export import to_csv

router = APIRouter(prefix="/projects/{project_id}", tags=["analytics"])

SectionName = Literal["overview", "platforms", "overall", "cross_platform", "scoring", "post_metrics", "findings"]


@router.post("/analyze", response_model=AnalyticsRunRead)
def analyze(
    project_id: uuid.UUID,
    body: AnalyzeRequest | None = None,
    projects: ProjectService = Depends(get_project_service),
    runner: TaskRunner = Depends(get_task_runner),
    db: Session = Depends(get_db),
) -> AnalyticsRunRead:
    """Run the full analytics pipeline and store a new, versioned analysis."""
    project = projects.get(project_id)
    job = runner.submit(AnalysisPipeline(db).run, project, body.weight_overrides if body else None)
    return AnalyticsRunRead.model_validate(job.result)


@router.get("/analytics/runs", response_model=list[AnalyticsRunRead])
def list_runs(project_id: uuid.UUID, db: Session = Depends(get_db)) -> list[AnalyticsRunRead]:
    runs = db.scalars(
        select(AnalyticsRun).where(AnalyticsRun.project_id == project_id).order_by(AnalyticsRun.analysis_version.desc())
    )
    return [AnalyticsRunRead.model_validate(r) for r in runs]


@router.get("/analytics", response_model=AnalyticsRead)
def get_analytics(
    project_id: uuid.UUID,
    version: int | None = None,
    sections: list[SectionName] | None = Query(default=None, description="Subset of sections to return"),
    db: Session = Depends(get_db),
) -> AnalyticsRead:
    run = get_run(db, project_id, version)
    return AnalyticsRead(
        run=AnalyticsRunRead.model_validate(run),
        sections=load_sections(db, run.id, tuple(sections) if sections else None),
    )


@router.get("/insights", response_model=InsightList)
def get_insights(
    project_id: uuid.UUID,
    version: int | None = None,
    platform: Platform | None = None,
    db: Session = Depends(get_db),
) -> InsightList:
    run = get_run(db, project_id, version)
    stmt = select(Insight).where(Insight.run_id == run.id)
    if platform:
        stmt = stmt.where(Insight.platform == platform.value)
    severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
    items = sorted(db.scalars(stmt), key=lambda i: (severity_rank.get(i.severity, 9), i.sentiment != "negative"))
    return InsightList(analysis_version=run.analysis_version, insights=[InsightRead.model_validate(i) for i in items])


_SORTABLE = {"published_at", "reach", "views", "impressions", "likes", "comments", "shares", "saves", "clicks"}


@router.get("/posts", response_model=PostPage)
def list_posts(
    project_id: uuid.UUID,
    platform: Platform | None = None,
    sort: str = "published_at",
    descending: bool = True,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> PostPage:
    base = select(SocialPost).where(SocialPost.project_id == project_id)
    if platform:
        base = base.where(SocialPost.platform == platform)
    total = db.scalar(select(func.count()).select_from(base.subquery())) or 0
    col = getattr(SocialPost, sort if sort in _SORTABLE else "published_at")
    order = col.desc().nulls_last() if descending else col.asc().nulls_last()
    items = db.scalars(base.order_by(order).limit(limit).offset(offset))
    return PostPage(total=total, items=[PostRead.model_validate(p) for p in items])


_EXPORT_COLUMNS = ["platform", "external_post_id", "published_at", "content_format", "content_pillar", "content_topic",
                   "cta_type", "hook_type", "caption", "likes", "comments", "shares", "saves", "views", "reach",
                   "impressions", "clicks", "followers_gained", "completion_rate", "permalink"]  # fmt: skip


@router.get("/export/posts.csv", response_class=Response)
def export_posts_csv(
    project_id: uuid.UUID,
    projects: ProjectService = Depends(get_project_service),
    db: Session = Depends(get_db),
) -> Response:
    """Normalized posts as CSV (formula-injection safe)."""
    project = projects.get(project_id)
    posts = db.scalars(select(SocialPost).where(SocialPost.project_id == project_id).order_by(SocialPost.published_at))
    rows = [
        [getattr(p, c).value if hasattr(getattr(p, c), "value") else getattr(p, c) for c in _EXPORT_COLUMNS]
        for p in posts
    ]
    filename = f"{project.name[:40].replace(' ', '_') or 'project'}_posts.csv"
    return Response(
        content=to_csv(_EXPORT_COLUMNS, rows),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
