"""AnalysisPipeline: load posts -> run AnalysisEngine -> persist a versioned AnalyticsRun.

Steps 1-8 of the processing pipeline (load, validate, detect, map, normalize, clean)
happen at ingestion time; this service covers features -> KPIs -> group analyses ->
trends -> statistical tests -> rule-based insights -> storage. AI generation is a
separate step that reads a stored run.
"""

import hashlib
import time
import uuid
from datetime import UTC, datetime

import pandas as pd
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analytics.engine import AnalysisContext, AnalysisEngine
from app.core.enums import ClassificationSource, ProjectStatus, RunStatus
from app.core.exceptions import AnalysisError, InvalidDatasetError, NotFoundError
from app.core.logging import get_logger
from app.models import AnalyticsResult, AnalyticsRun, Insight, Project, SocialPost
from app.services.posts import load_posts_frame

logger = get_logger(__name__)

SECTIONS = ("overview", "platforms", "overall", "cross_platform", "scoring", "post_metrics", "findings")


def _input_hash(df: pd.DataFrame, params: dict) -> str:
    cols = [c for c in ("external_post_id", "platform", "published_at", "reach", "views", "impressions",
                        "likes", "comments", "shares", "saves", "clicks", "caption") if c in df]  # fmt: skip
    body = pd.util.hash_pandas_object(df[cols].astype(str), index=False).values.tobytes()
    return hashlib.sha256(body + repr(sorted(params.items())).encode()).hexdigest()


class AnalysisPipeline:
    def __init__(self, db: Session) -> None:
        self.db = db

    def run(self, project: Project, weight_overrides: dict[str, float] | None = None) -> AnalyticsRun:
        posts = load_posts_frame(self.db, project.id)
        if posts.empty:
            raise InvalidDatasetError("This project has no normalized posts yet. Upload and normalize data first.")

        objectives = project.business_profile.marketing_objectives if project.business_profile else []
        version = (
            self.db.scalar(select(func.max(AnalyticsRun.analysis_version)).where(AnalyticsRun.project_id == project.id))
            or 0
        ) + 1
        run = AnalyticsRun(
            project_id=project.id,
            analysis_version=version,
            status=RunStatus.RUNNING,
            started_at=datetime.now(UTC),
            post_count=len(posts),
            input_hash=_input_hash(posts, {"objectives": tuple(objectives), "tz": project.timezone}),
        )
        self.db.add(run)
        self.db.commit()
        logger.info("analysis.started", extra={"project_id": str(project.id), "version": version, "posts": len(posts)})

        started = time.perf_counter()
        try:
            output = AnalysisEngine(
                AnalysisContext(
                    objectives=list(objectives), timezone=project.timezone, weight_overrides=weight_overrides
                )
            ).run(posts)
        except Exception as exc:
            run.status = RunStatus.FAILED
            run.error = str(exc)[:2000]
            run.finished_at = datetime.now(UTC)
            self.db.commit()
            logger.exception("analysis.failed", extra={"project_id": str(project.id), "version": version})
            if isinstance(exc, AnalysisError):
                raise
            raise AnalysisError("The analysis failed unexpectedly.", {"run_id": str(run.id)}) from exc

        for name in SECTIONS:
            payload = output.findings if name == "findings" else output.sections[name]
            self.db.add(AnalyticsResult(run_id=run.id, section=name, payload=payload))
        for ins in output.insights:
            self.db.add(Insight(run_id=run.id, **ins.to_dict()))
        self._persist_classifications(output.classifications)

        run.status = RunStatus.COMPLETED
        run.finished_at = datetime.now(UTC)
        run.duration_ms = int((time.perf_counter() - started) * 1000)
        run.period_start = output.period[0].to_pydatetime()
        run.period_end = output.period[1].to_pydatetime()
        run.parameters = output.parameters
        run.summary = {"headline": output.headline}
        if project.status in (ProjectStatus.DRAFT, ProjectStatus.DATA_UPLOADED, ProjectStatus.NORMALIZED):
            project.status = ProjectStatus.ANALYZED
        self.db.commit()
        logger.info(
            "analysis.completed",
            extra={
                "project_id": str(project.id),
                "version": version,
                "duration_ms": run.duration_ms,
                "findings": len(output.findings),
                "insights": len(output.insights),
            },
        )
        return run

    def _persist_classifications(self, classes: pd.DataFrame) -> None:
        """Store keyword classifications on posts (never overwriting source/AI/manual labels)."""
        rows = classes[classes["topic_source"] == ClassificationSource.KEYWORD.value]
        self.db.bulk_update_mappings(
            SocialPost,  # type: ignore[arg-type]
            [
                {
                    "id": r.id,
                    "content_topic": r.content_topic,
                    "content_pillar": r.content_pillar,
                    "topic_confidence": float(r.topic_confidence) if pd.notna(r.topic_confidence) else None,
                    "topic_source": ClassificationSource.KEYWORD,
                    "cta_type": r.cta_type,
                    "hook_type": r.hook_type,
                }
                for r in rows.itertuples(index=False)
            ],
        )


def get_run(db: Session, project_id: uuid.UUID, version: int | None = None) -> AnalyticsRun:
    stmt = select(AnalyticsRun).where(AnalyticsRun.project_id == project_id, AnalyticsRun.status == RunStatus.COMPLETED)
    stmt = (
        stmt.where(AnalyticsRun.analysis_version == version)
        if version
        else stmt.order_by(AnalyticsRun.analysis_version.desc())
    )
    run = db.scalars(stmt.limit(1)).first()
    if run is None:
        raise NotFoundError(
            "No completed analysis found for this project."
            if version is None
            else f"Analysis version {version} not found.",
            {"project_id": str(project_id), "version": version},
        )
    return run


def load_sections(db: Session, run_id: uuid.UUID, sections: tuple[str, ...] | None = None) -> dict:
    stmt = select(AnalyticsResult.section, AnalyticsResult.payload).where(AnalyticsResult.run_id == run_id)
    if sections:
        stmt = stmt.where(AnalyticsResult.section.in_(sections))
    return dict(db.execute(stmt).all())
