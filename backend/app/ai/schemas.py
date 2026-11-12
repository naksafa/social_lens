"""Structured output contracts for every AI agent.

LLM responses are validated against these models (structured outputs + Pydantic).
The deterministic (no-LLM) composer produces the same shapes, so the frontend and
reports never need to know which one generated the content.
"""

from typing import Literal

from pydantic import BaseModel, Field

PlatformName = Literal["instagram", "facebook", "tiktok", "linkedin", "all"]
Level = Literal["high", "medium", "low"]
Priority = Literal["critical", "high", "medium", "low"]
Basis = Literal["data_backed", "general_best_practice"]


class Recommendation(BaseModel):
    title: str
    explanation: str
    evidence: str = Field(description="Analytics evidence quoted from the supplied data, or 'No direct data' ")
    evidence_refs: list[str] = Field(default_factory=list, description="IDs of supporting findings/insights")
    platform: PlatformName
    priority: Priority
    impact: Level
    effort: Level
    confidence: Level
    basis: Basis


class AuditPoint(BaseModel):
    title: str
    explanation: str
    evidence: str
    evidence_refs: list[str] = Field(default_factory=list)
    platform: PlatformName
    impact: Level
    confidence: Level
    basis: Basis


class PlatformAudit(BaseModel):
    platform: PlatformName
    summary: str
    performance_assessment: str
    strengths: list[str]
    weaknesses: list[str]
    data_limitations: list[str]


class AuditOutput(BaseModel):
    executive_summary: str
    overall_findings: list[AuditPoint]
    platform_audits: list[PlatformAudit]
    strengths: list[AuditPoint]
    weaknesses: list[AuditPoint]
    opportunities: list[AuditPoint]
    risks: list[AuditPoint]
    content_gaps: list[AuditPoint]
    best_content_patterns: list[AuditPoint]
    worst_content_patterns: list[AuditPoint]
    audience_insights: list[AuditPoint]
    priority_actions: list[Recommendation]
    data_limitations: list[str]


class StrategicObjective(BaseModel):
    objective: str
    kpi: str
    target: str = Field(description="Directional or relative target; never an invented absolute baseline")
    timeframe: str


class PillarShare(BaseModel):
    pillar: str
    share_pct: int = Field(ge=0, le=100)


class PlatformStrategy(BaseModel):
    platform: PlatformName
    role: str
    goal: str
    formats: list[str]
    posting_frequency: str
    content_mix: list[PillarShare]
    hook_guidance: str
    cta_approach: str
    video_guidance: str
    community_approach: str
    rationale: str
    evidence_refs: list[str] = Field(default_factory=list)


class ContentPillarDef(BaseModel):
    name: str
    description: str
    target_share_pct: int = Field(ge=0, le=100)
    rationale: str
    example_topics: list[str]


class MeasurementItem(BaseModel):
    kpi: str
    platform: PlatformName
    definition: str
    baseline: str = Field(description="Value from the supplied analytics, or 'not available'")
    target_direction: str
    review_cadence: str


class WeeklyActions(BaseModel):
    week: int = Field(ge=1, le=5)
    focus: str
    actions: list[str]


class StrategyOutput(BaseModel):
    strategy_summary: str
    strategic_objectives: list[StrategicObjective]
    platform_strategies: list[PlatformStrategy]
    content_pillars: list[ContentPillarDef]
    format_strategy: str
    video_strategy: str
    caption_strategy: str
    cta_strategy: str
    community_strategy: str
    growth_strategy: str
    audience_strategy: str
    measurement_plan: list[MeasurementItem]
    action_plan_30_days: list[WeeklyActions]
    recommendations: list[Recommendation]
    assumptions: list[str]


class ContentPlanEntry(BaseModel):
    day: int = Field(ge=1, le=31)
    date: str | None = None
    platform: PlatformName
    pillar: str
    format: str
    topic: str
    hook: str
    concept: str
    cta: str
    objective: str
    kpi: str


class ContentIdea(BaseModel):
    title: str
    platform: PlatformName
    format: str
    pillar: str
    hook: str
    concept: str
    caption_direction: str
    cta: str
    goal: str
    based_on: str = Field(description="Which historical pattern or gap this idea builds on")


class ContentPlanOutput(BaseModel):
    plan_summary: str
    entries: list[ContentPlanEntry]
    ideas: list[ContentIdea]
    notes: list[str]


class PostClassification(BaseModel):
    index: int
    topic: Literal[
        "educational", "promotional", "product", "service", "behind_the_scenes", "testimonial",
        "entertainment", "trend", "company_culture", "case_study", "tips", "faq", "community",
        "announcement", "other",
    ]  # fmt: skip
    cta_type: Literal[
        "none", "save", "share", "comment", "follow", "link_click", "dm", "book_call", "buy", "visit", "other"
    ]
    hook_type: Literal["question", "number", "pov", "how_to", "bold_claim", "none"]
    confidence: float = Field(ge=0, le=1)


class ClassificationOutput(BaseModel):
    items: list[PostClassification]
