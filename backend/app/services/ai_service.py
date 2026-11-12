"""Orchestrates AI generation: audit -> strategy -> content plan (+ AI classification).

Each output is versioned per project and linked to the analytics run it was built
from; earlier versions are kept. Every LLM call is recorded in AIRequestLog (prompt
hash + sizes + tokens + latency; never the raw prompt or keys).
"""

import hashlib
import uuid
from datetime import date, timedelta

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.ai.agents import (
    AgentContext,
    AgentResult,
    AuditAgent,
    ContentClassificationAgent,
    ContentPlanAgent,
    StrategyAgent,
)
from app.ai.base_provider import LLMProvider
from app.ai.factory import get_provider
from app.ai.prompt_builder import build_analytics_summary, business_context
from app.analytics.classification import TAXONOMY_VERSION, TOPIC_TO_PILLAR
from app.core.enums import ClassificationSource, ContentPillar, GeneratedBy, ProjectStatus
from app.core.exceptions import AINotConfiguredError, AIProviderError, NotFoundError
from app.core.logging import get_logger
from app.models import (
    AIAudit,
    AIRequestLog,
    AnalyticsRun,
    ContentClassification,
    ContentPlan,
    Insight,
    MarketingStrategy,
    Project,
    SocialPost,
)
from app.services.analysis_pipeline import get_run, load_sections

logger = get_logger(__name__)
OutputModel = type[AIAudit] | type[MarketingStrategy] | type[ContentPlan]


class AIService:
    def __init__(self, db: Session, provider: LLMProvider | None = None, use_provider: bool = True) -> None:
        self.db = db
        self.provider = provider if provider is not None else (get_provider() if use_provider else None)

    # ------------------------------------------------------------------ context
    def _context(self, project: Project, run: AnalyticsRun, instructions: str | None) -> AgentContext:
        sections = load_sections(self.db, run.id)
        insights = [
            {
                "id": str(i.id),
                "rule_id": i.rule_id,
                "category": i.category,
                "platform": i.platform,
                "title": i.title,
                "description": i.description,
                "metric": i.metric,
                "evidence": i.evidence,
                "confidence": i.confidence.value if hasattr(i.confidence, "value") else i.confidence,
                "severity": i.severity.value if hasattr(i.severity, "value") else i.severity,
                "sentiment": i.sentiment,
                "recommendation_hint": i.recommendation_hint,
            }
            for i in self.db.scalars(select(Insight).where(Insight.run_id == run.id))
        ]
        severity_rank = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
        insights.sort(key=lambda i: (severity_rank.get(i["severity"], 9), i["sentiment"] != "negative"))
        merged = "\n".join(
            x
            for x in (
                project.business_profile.additional_instructions if project.business_profile else None,
                instructions,
            )
            if x
        )
        return AgentContext(
            business=business_context(project),
            summary=build_analytics_summary(sections, insights, {"analysis_version": run.analysis_version}),
            sections=sections,
            insights=insights,
            instructions=merged or None,
        )

    def _next_version(self, model: OutputModel, project_id: uuid.UUID) -> int:
        return (self.db.scalar(select(func.max(model.version)).where(model.project_id == project_id)) or 0) + 1

    def _log(
        self, project_id: uuid.UUID, agent: str, result: AgentResult | None, error: Exception | None = None
    ) -> None:
        if self.provider is None:
            return
        llm = result.llm if result else None
        self.db.add(
            AIRequestLog(
                project_id=project_id,
                agent=agent,
                provider=self.provider.name,
                model=self.provider.model,
                prompt_hash=llm.prompt_hash if llm else "",
                prompt_chars=llm.prompt_chars if llm else 0,
                input_tokens=llm.usage.input_tokens if llm else None,
                output_tokens=llm.usage.output_tokens if llm else None,
                latency_ms=llm.latency_ms if llm else None,
                attempts=llm.attempts if llm else 1,
                success=error is None,
                error_code=getattr(error, "code", type(error).__name__) if error else None,
            )
        )

    def _run_agent(self, project: Project, agent_name: str, fn) -> AgentResult:  # type: ignore[no-untyped-def]
        try:
            result = fn()
        except AIProviderError as exc:
            self._log(project.id, agent_name, None, exc)
            self.db.commit()
            logger.error("ai.failed", extra={"agent": agent_name, "project_id": str(project.id), "code": exc.code})
            raise
        self._log(project.id, agent_name, result)
        return result

    # ------------------------------------------------------------------ generation
    def generate_audit(self, project: Project, instructions: str | None, version: int | None = None) -> AIAudit:
        run = get_run(self.db, project.id, version)
        ctx = self._context(project, run, instructions)
        result = self._run_agent(project, "audit", lambda: AuditAgent().run(ctx, self.provider))
        row = AIAudit(
            project_id=project.id, analytics_run_id=run.id, version=self._next_version(AIAudit, project.id),
            generated_by=result.generated_by, provider=result.provider, model=result.model,
            user_instructions=instructions, content=result.content(),
        )  # fmt: skip
        self.db.add(row)
        if project.status in (ProjectStatus.ANALYZED, ProjectStatus.NORMALIZED):
            project.status = ProjectStatus.AUDITED
        self.db.commit()
        return row

    def generate_strategy(self, project: Project, instructions: str | None) -> MarketingStrategy:
        audit = self.latest(AIAudit, project.id)
        run = self.db.get(AnalyticsRun, audit.analytics_run_id)
        ctx = self._context(project, run, instructions)  # type: ignore[arg-type]
        result = self._run_agent(project, "strategy", lambda: StrategyAgent().run(ctx, self.provider, audit.content))
        row = MarketingStrategy(
            project_id=project.id, analytics_run_id=run.id, audit_id=audit.id,  # type: ignore[union-attr]
            version=self._next_version(MarketingStrategy, project.id), generated_by=result.generated_by,
            provider=result.provider, model=result.model, user_instructions=instructions, content=result.content(),
        )  # fmt: skip
        self.db.add(row)
        project.status = ProjectStatus.STRATEGY_READY
        self.db.commit()
        return row

    def generate_content_plan(self, project: Project, instructions: str | None, start: date | None) -> ContentPlan:
        strategy = self.latest(MarketingStrategy, project.id)
        run = self.db.get(AnalyticsRun, strategy.analytics_run_id)
        ctx = self._context(project, run, instructions)  # type: ignore[arg-type]
        start = start or (date.today() + timedelta(days=1))
        result = self._run_agent(
            project, "content_plan", lambda: ContentPlanAgent().run(ctx, self.provider, strategy.content, start)
        )
        row = ContentPlan(
            project_id=project.id, analytics_run_id=run.id, strategy_id=strategy.id,  # type: ignore[union-attr]
            version=self._next_version(ContentPlan, project.id), generated_by=result.generated_by,
            provider=result.provider, model=result.model, user_instructions=instructions,
            content={**result.content(), "start_date": start.isoformat()},
        )  # fmt: skip
        self.db.add(row)
        self.db.commit()
        return row

    def latest(self, model: OutputModel, project_id: uuid.UUID, version: int | None = None):  # type: ignore[no-untyped-def]
        stmt = select(model).where(model.project_id == project_id)
        stmt = stmt.where(model.version == version) if version else stmt.order_by(model.version.desc())
        row = self.db.scalars(stmt.limit(1)).first()
        if row is None:
            names = {AIAudit: "audit", MarketingStrategy: "strategy", ContentPlan: "content plan"}
            prereq = {AIAudit: "Run an analysis, then generate the audit.",
                      MarketingStrategy: "Generate the audit first.",
                      ContentPlan: "Generate the strategy first."}  # fmt: skip
            raise NotFoundError(f"No {names[model]} found. {prereq[model]}", {"project_id": str(project_id)})
        return row

    # ------------------------------------------------------------------ AI classification
    def classify_posts(self, project: Project, min_keyword_confidence: float = 0.5, limit: int = 400) -> dict:
        """Re-classify low-confidence keyword posts with the LLM, using a cache keyed by
        (caption hash, taxonomy version, model) so no caption is ever classified twice."""
        if self.provider is None:
            raise AINotConfiguredError(
                "AI classification needs an AI provider (set ANTHROPIC_API_KEY or OPENAI_API_KEY)."
            )
        posts = list(
            self.db.scalars(
                select(SocialPost)
                .where(
                    SocialPost.project_id == project.id,
                    SocialPost.caption.is_not(None),
                    (SocialPost.topic_source.is_(None))
                    | ((SocialPost.topic_source == ClassificationSource.KEYWORD) & (func.coalesce(SocialPost.topic_confidence, 0) < min_keyword_confidence)),
                )
                .limit(limit)
            )
        )  # fmt: skip
        model = self.provider.model
        hashes = {p.id: hashlib.sha256(p.caption.strip().lower().encode()).hexdigest() for p in posts}  # type: ignore[union-attr]
        cached = {
            c.caption_hash: c
            for c in self.db.scalars(
                select(ContentClassification).where(
                    ContentClassification.caption_hash.in_(set(hashes.values())),
                    ContentClassification.taxonomy_version == TAXONOMY_VERSION,
                    ContentClassification.model == model,
                )
            )
        }
        todo = [p for p in posts if hashes[p.id] not in cached]
        # Deduplicate identical captions within this request too.
        unique: dict[str, SocialPost] = {}
        for p in todo:
            unique.setdefault(hashes[p.id], p)
        usage: dict = {"calls": 0}
        if unique:
            items = [{"caption": p.caption[:600], "platform": p.platform.value if hasattr(p.platform, "value") else p.platform,  # type: ignore[index]
                      "format": p.content_format} for p in unique.values()]  # fmt: skip
            try:
                results, usage = ContentClassificationAgent().classify(self.provider, business_context(project), items)
            except AIProviderError as exc:
                self._log(project.id, "classification", None, exc)
                self.db.commit()
                raise
            for h, r in zip(unique.keys(), results, strict=True):
                if not r:
                    continue
                c = ContentClassification(
                    caption_hash=h, taxonomy_version=TAXONOMY_VERSION, model=model, topic=r["topic"],
                    pillar=TOPIC_TO_PILLAR.get(r["topic"], ContentPillar.OTHER).value,
                    cta_type=r["cta_type"], hook_type=r["hook_type"], confidence=r["confidence"],
                )  # fmt: skip
                self.db.add(c)
                cached[h] = c
            self.db.add(AIRequestLog(project_id=project.id, agent="classification", provider=self.provider.name, model=model,
                                     prompt_hash="batch", prompt_chars=sum(len(i["caption"]) for i in items),
                                     input_tokens=usage.get("input_tokens"), output_tokens=usage.get("output_tokens"),
                                     attempts=usage.get("calls", 1), success=True))  # fmt: skip

        updated = 0
        for p in posts:
            c = cached.get(hashes[p.id])
            if c is None:
                continue
            self.db.execute(
                update(SocialPost).where(SocialPost.id == p.id).values(
                    content_topic=c.topic, content_pillar=c.pillar, topic_source=ClassificationSource.AI,
                    topic_confidence=c.confidence, cta_type=c.cta_type, hook_type=c.hook_type,
                )
            )  # fmt: skip
            updated += 1
        self.db.commit()
        return {
            "candidates": len(posts),
            "cache_hits": len(posts) - len(todo),
            "newly_classified_captions": len(unique),
            "posts_updated": updated,
            "llm_calls": usage.get("calls", 0),
            "note": "Re-run the analysis to use the new classifications.",
        }


def generated_label(g: GeneratedBy | str) -> str:
    return "AI" if str(getattr(g, "value", g)) == GeneratedBy.LLM.value else "Rule-based engine"
