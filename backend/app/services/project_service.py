import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.core.enums import Platform
from app.core.exceptions import NotFoundError
from app.core.logging import get_logger
from app.models import (
    AIAudit,
    AnalyticsRun,
    BusinessProfile,
    MarketingStrategy,
    Project,
    SocialPost,
    UploadedFile,
)
from app.schemas.project import (
    LatestRunSummary,
    ProjectCreate,
    ProjectFileSummary,
    ProjectListItem,
    ProjectRead,
    ProjectUpdate,
)
from app.storage import get_storage

logger = get_logger(__name__)


class ProjectService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, project_id: uuid.UUID) -> Project:
        project = self.db.scalar(
            select(Project).where(Project.id == project_id).options(selectinload(Project.business_profile))
        )
        if project is None:
            raise NotFoundError("Project not found.", {"project_id": str(project_id)})
        return project

    def create(self, data: ProjectCreate, *, is_demo: bool = False) -> Project:
        project = Project(
            name=data.name,
            description=data.description,
            platforms=[p.value for p in data.platforms],
            timezone=data.timezone,
            is_demo=is_demo,
        )
        project.business_profile = BusinessProfile(
            **data.business_profile.model_dump(mode="json", exclude={"monthly_budget"}),
            monthly_budget=data.business_profile.monthly_budget,
        )
        self.db.add(project)
        self.db.commit()
        logger.info("project.created", extra={"project_id": str(project.id), "demo": is_demo})
        return self.get(project.id)

    def update(self, project_id: uuid.UUID, data: ProjectUpdate) -> Project:
        project = self.get(project_id)
        fields = data.model_dump(exclude_unset=True, exclude={"business_profile"}, mode="json")
        for key, value in fields.items():
            setattr(project, key, value)
        if data.business_profile is not None:
            values = data.business_profile.model_dump(mode="json", exclude={"monthly_budget"})
            values["monthly_budget"] = data.business_profile.monthly_budget
            if project.business_profile is None:
                project.business_profile = BusinessProfile(**values)
            else:
                for key, value in values.items():
                    setattr(project.business_profile, key, value)
        self.db.commit()
        return self.get(project_id)

    def delete(self, project_id: uuid.UUID) -> None:
        project = self.get(project_id)
        storage = get_storage()
        for f in project.files:
            storage.delete(f.storage_key)
        self.db.delete(project)
        self.db.commit()
        logger.info("project.deleted", extra={"project_id": str(project_id)})

    def list_projects(self) -> list[ProjectListItem]:
        projects = self.db.scalars(
            select(Project)
            .options(selectinload(Project.business_profile), selectinload(Project.files))
            .order_by(Project.created_at.desc())
        ).all()
        if not projects:
            return []
        ids = [p.id for p in projects]

        post_counts = dict(
            self.db.execute(
                select(SocialPost.project_id, func.count())
                .where(SocialPost.project_id.in_(ids))
                .group_by(SocialPost.project_id)
            ).all()
        )
        latest_runs: dict[uuid.UUID, AnalyticsRun] = {}
        for run in self.db.scalars(
            select(AnalyticsRun).where(AnalyticsRun.project_id.in_(ids)).order_by(AnalyticsRun.analysis_version.desc())
        ):
            latest_runs.setdefault(run.project_id, run)
        audited = set(self.db.scalars(select(AIAudit.project_id).where(AIAudit.project_id.in_(ids))))
        strategized = set(
            self.db.scalars(select(MarketingStrategy.project_id).where(MarketingStrategy.project_id.in_(ids)))
        )

        items = []
        for p in projects:
            run = latest_runs.get(p.id)
            items.append(
                ProjectListItem(
                    **ProjectRead.model_validate(p).model_dump(),
                    files=_file_summary(p.files),
                    post_count=post_counts.get(p.id, 0),
                    latest_run=(
                        LatestRunSummary(
                            id=run.id,
                            analysis_version=run.analysis_version,
                            status=run.status,
                            finished_at=run.finished_at,
                            post_count=run.post_count,
                            headline=run.summary.get("headline", {}) if run.summary else {},
                        )
                        if run
                        else None
                    ),
                    has_audit=p.id in audited,
                    has_strategy=p.id in strategized,
                )
            )
        return items


def _file_summary(files: list[UploadedFile]) -> ProjectFileSummary:
    platforms = sorted({Platform(f.platform) for f in files if f.platform})
    return ProjectFileSummary(count=len(files), platforms=platforms)
