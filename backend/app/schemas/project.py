import uuid
from datetime import datetime
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.core.enums import MarketingObjective, Platform, ProjectStatus


def _check_timezone(value: str | None) -> str | None:
    if value is None:
        return value
    try:
        ZoneInfo(value)
    except (ZoneInfoNotFoundError, ValueError) as exc:
        raise ValueError(f"Unknown timezone: {value}") from exc
    return value


class BusinessProfileBase(BaseModel):
    business_name: str = Field(min_length=1, max_length=200)
    industry: str = Field(min_length=1, max_length=120)
    country: str = Field(min_length=1, max_length=80)
    city_market: str | None = Field(default=None, max_length=120)
    products_services: str = Field(min_length=1, max_length=4000)
    target_audience: str = Field(min_length=1, max_length=4000)
    business_objective: str = Field(min_length=1, max_length=4000)
    marketing_objectives: list[MarketingObjective] = Field(min_length=1)
    competitors: list[str] = Field(default_factory=list, max_length=20)
    monthly_budget: Decimal | None = Field(default=None, ge=0)
    budget_currency: str | None = Field(default=None, min_length=3, max_length=3)
    current_posting_frequency: str | None = Field(default=None, max_length=120)
    additional_instructions: str | None = Field(default=None, max_length=4000)


class BusinessProfileRead(BusinessProfileBase):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    platforms: list[Platform] = Field(min_length=1)
    timezone: str = "UTC"
    business_profile: BusinessProfileBase

    _valid_timezone = field_validator("timezone")(_check_timezone)

    @field_validator("platforms")
    @classmethod
    def _dedupe(cls, value: list[Platform]) -> list[Platform]:
        return list(dict.fromkeys(value))


class ProjectUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    platforms: list[Platform] | None = Field(default=None, min_length=1)
    timezone: str | None = None
    business_profile: BusinessProfileBase | None = None

    _valid_timezone = field_validator("timezone")(_check_timezone)


class ProjectFileSummary(BaseModel):
    count: int
    platforms: list[Platform]


class LatestRunSummary(BaseModel):
    id: uuid.UUID
    analysis_version: int
    status: str
    finished_at: datetime | None
    post_count: int
    headline: dict = Field(default_factory=dict)


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    status: ProjectStatus
    platforms: list[Platform]
    timezone: str
    is_demo: bool
    created_at: datetime
    updated_at: datetime
    business_profile: BusinessProfileRead | None


class ProjectListItem(ProjectRead):
    files: ProjectFileSummary
    post_count: int
    latest_run: LatestRunSummary | None
    has_audit: bool
    has_strategy: bool
