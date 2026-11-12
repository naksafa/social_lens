import uuid
from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.core.enums import GeneratedBy


class GenerateRequest(BaseModel):
    instructions: str | None = Field(
        default=None,
        max_length=4000,
        description='Custom focus, e.g. "Focus on generating leads" or "Do not recommend paid advertising".',
    )
    use_ai: bool = Field(default=True, description="False forces the deterministic rule-based composer.")


class AuditRequest(GenerateRequest):
    analysis_version: int | None = Field(default=None, description="Analytics version to audit (default: latest)")


class ContentPlanRequest(GenerateRequest):
    start_date: date | None = Field(default=None, description="First day of the 30-day plan (default: tomorrow)")


class AIOutputRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    project_id: uuid.UUID
    analytics_run_id: uuid.UUID
    version: int
    generated_by: GeneratedBy
    provider: str | None
    model: str | None
    user_instructions: str | None
    content: dict[str, Any]
    created_at: datetime


class ClassifyResponse(BaseModel):
    candidates: int
    cache_hits: int
    newly_classified_captions: int
    posts_updated: int
    llm_calls: int
    note: str
