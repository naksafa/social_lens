"""AI agents: AuditAgent, StrategyAgent, ContentPlanAgent, ContentClassificationAgent.

Each agent takes the business context + a stored analytics run (never raw data),
calls the configured LLM with a structured-output schema, verifies numbers in the
result against the supplied analytics, and returns the output plus metadata.
Without a provider, the analytical agents fall back to the deterministic composer.
"""

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from pydantic import BaseModel

from app.ai import deterministic as rules
from app.ai.base_provider import LLMProvider, StructuredResult
from app.ai.guardrails import verify_output
from app.ai.prompt_builder import render_payload
from app.ai.prompts import AUDIT_SYSTEM, CLASSIFICATION_SYSTEM, CONTENT_SYSTEM, STRATEGY_SYSTEM
from app.ai.schemas import AuditOutput, ClassificationOutput, ContentPlanOutput, StrategyOutput
from app.core.config import get_settings
from app.core.enums import GeneratedBy
from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class AgentContext:
    business: dict
    summary: dict  # compact analytics summary (prompt_builder.build_analytics_summary)
    sections: dict  # full analytics sections (used by the deterministic composer)
    insights: list[dict]
    instructions: str | None = None


@dataclass
class AgentResult:
    output: BaseModel
    generated_by: GeneratedBy
    provider: str | None = None
    model: str | None = None
    verification: dict = field(default_factory=dict)
    llm: StructuredResult | None = None

    def content(self) -> dict[str, Any]:
        return {**self.output.model_dump(mode="json"), "_verification": self.verification}


def _run_llm(provider: LLMProvider, agent: str, system: str, payload: str, schema: type[BaseModel],
             verify_against: Any) -> AgentResult:  # fmt: skip
    settings = get_settings()
    logger.info(
        "ai.request",
        extra={"agent": agent, "provider": provider.name, "model": provider.model, "prompt_chars": len(payload)},
    )
    result = provider.generate_structured(
        system, payload, schema, max_tokens=settings.ai_max_output_tokens, agent=agent
    )
    verification = verify_output(result.data, verify_against)
    logger.info(
        "ai.response",
        extra={
            "agent": agent,
            "attempts": result.attempts,
            "latency_ms": result.latency_ms,
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "unverified_numbers": verification["unverified_count"],
        },  # fmt: skip
    )
    return AgentResult(result.data, GeneratedBy.LLM, provider.name, provider.model, verification, result)


class AuditAgent:
    name = "audit"

    def run(self, ctx: AgentContext, provider: LLMProvider | None) -> AgentResult:
        if provider is None:
            out = rules.compose_audit(ctx.business, ctx.sections, ctx.insights)
            return AgentResult(out, GeneratedBy.RULES, verification={"status": "deterministic"})
        payload = render_payload(ctx.business, ctx.summary, ctx.instructions)
        return _run_llm(provider, self.name, AUDIT_SYSTEM, payload, AuditOutput, ctx.summary)


class StrategyAgent:
    name = "strategy"

    def run(self, ctx: AgentContext, provider: LLMProvider | None, audit: dict) -> AgentResult:
        if provider is None:
            audit_model = AuditOutput.model_validate({k: v for k, v in audit.items() if not k.startswith("_")})
            out = rules.compose_strategy(ctx.business, ctx.sections, ctx.insights, audit_model)
            return AgentResult(out, GeneratedBy.RULES, verification={"status": "deterministic"})
        audit_brief = {k: audit.get(k) for k in ("executive_summary", "strengths", "weaknesses", "opportunities",
                                                  "content_gaps", "priority_actions")}  # fmt: skip
        payload = render_payload(ctx.business, ctx.summary, ctx.instructions, {"audit": audit_brief})
        return _run_llm(provider, self.name, STRATEGY_SYSTEM, payload, StrategyOutput, [ctx.summary, audit_brief])


class ContentPlanAgent:
    name = "content_plan"

    def run(self, ctx: AgentContext, provider: LLMProvider | None, strategy: dict, start: date) -> AgentResult:
        if provider is None:
            strat = StrategyOutput.model_validate({k: v for k, v in strategy.items() if not k.startswith("_")})
            out = rules.compose_content_plan(ctx.business, ctx.sections, strat, start)
            return AgentResult(out, GeneratedBy.RULES, verification={"status": "deterministic"})
        strategy_brief = {k: strategy.get(k) for k in ("platform_strategies", "content_pillars", "video_strategy",
                                                        "caption_strategy", "cta_strategy")}  # fmt: skip
        extra = {
            "strategy": strategy_brief,
            "calendar": {"start_date": start.isoformat(), "days": 30,
                         "instruction": "Set `day` 1-30 and `date` = start_date + (day - 1). Also produce 10-15 ideas."},
        }  # fmt: skip
        summary = {"platforms": {p: {k: v for k, v in s.items() if k in ("formats", "pillars", "top_posts", "hook_mix_pct", "timing")}
                                 for p, s in ctx.summary["platforms"].items()}}  # fmt: skip
        payload = render_payload(ctx.business, summary, ctx.instructions, extra)
        return _run_llm(provider, self.name, CONTENT_SYSTEM, payload, ContentPlanOutput, ctx.summary)


class ContentClassificationAgent:
    name = "classification"
    batch_size = 40

    def classify(self, provider: LLMProvider, business: dict, posts: list[dict]) -> tuple[list[dict], dict]:
        """posts: [{"caption", "platform", "format"}]. Returns (classifications aligned by index, usage)."""
        out: list[dict] = [{} for _ in posts]
        usage = {"input_tokens": 0, "output_tokens": 0, "calls": 0}
        for start in range(0, len(posts), self.batch_size):
            batch = posts[start : start + self.batch_size]
            items = [{"index": i, **p} for i, p in enumerate(batch)]
            prompt = (
                "<business_context>\n" + json.dumps(business, default=str) + "\n</business_context>\n\n"
                "<posts>\n" + json.dumps(items, ensure_ascii=False) + "\n</posts>"
            )
            result = provider.classify(CLASSIFICATION_SYSTEM, prompt, ClassificationOutput)
            usage["calls"] += 1
            usage["input_tokens"] += result.usage.input_tokens or 0
            usage["output_tokens"] += result.usage.output_tokens or 0
            for item in result.data.items:
                if 0 <= item.index < len(batch):
                    out[start + item.index] = item.model_dump()
        return out, usage
