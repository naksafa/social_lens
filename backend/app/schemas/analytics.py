import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import Platform, RunStatus


class AnalyzeRequest(BaseModel):
    weight_overrides: dict[str, float] | None = Field(
        default=None,
        description="Optional custom performance-index weights, e.g. {'exposure': 0.5, 'engagement_rate': 0.5}.",
    )


class AnalyticsRunRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    analysis_version: int
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    duration_ms: int | None
    post_count: int
    period_start: datetime | None
    period_end: datetime | None
    parameters: dict[str, Any]
    summary: dict[str, Any]
    error: str | None
    created_at: datetime


class AnalyticsRead(BaseModel):
    run: AnalyticsRunRead
    sections: dict[str, Any]


class InsightRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    rule_id: str
    category: str
    platform: str | None
    title: str
    description: str
    metric: str | None
    evidence: dict[str, Any]
    confidence: str
    severity: str
    sentiment: str
    recommendation_hint: str | None


class InsightList(BaseModel):
    analysis_version: int
    insights: list[InsightRead]


class PostRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    platform: Platform
    external_post_id: str
    published_at: datetime
    permalink: str | None
    post_type: str | None
    content_format: str | None
    caption: str | None
    hashtags: list[str]
    content_topic: str | None
    content_pillar: str | None
    topic_source: str | None
    topic_confidence: float | None
    cta_type: str | None
    hook_type: str | None
    likes: float | None
    comments: float | None
    shares: float | None
    saves: float | None
    views: float | None
    reach: float | None
    impressions: float | None
    clicks: float | None
    website_clicks: float | None
    followers_gained: float | None
    video_duration_seconds: float | None
    completion_rate: float | None
    average_watch_time_seconds: float | None


class PostPage(BaseModel):
    total: int
    items: list[PostRead]
