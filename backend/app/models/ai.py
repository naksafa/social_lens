import uuid
from typing import Any

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import GeneratedBy
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, str_enum


class _AIOutputMixin(UUIDPrimaryKeyMixin, TimestampMixin):
    """Common columns for versioned AI outputs tied to a specific analytics run."""

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analytics_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("analytics_runs.id", ondelete="CASCADE"), index=True
    )
    version: Mapped[int] = mapped_column(Integer)
    generated_by: Mapped[GeneratedBy] = mapped_column(str_enum(GeneratedBy))
    provider: Mapped[str | None] = mapped_column(String(32))
    model: Mapped[str | None] = mapped_column(String(80))
    user_instructions: Mapped[str | None] = mapped_column(Text)
    content: Mapped[dict[str, Any]] = mapped_column(JSONType)


class AIAudit(_AIOutputMixin, Base):
    __tablename__ = "ai_audits"


class MarketingStrategy(_AIOutputMixin, Base):
    __tablename__ = "marketing_strategies"

    audit_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("ai_audits.id", ondelete="SET NULL"))


class ContentPlan(_AIOutputMixin, Base):
    __tablename__ = "content_plans"

    strategy_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("marketing_strategies.id", ondelete="SET NULL")
    )


class AIRequestLog(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Audit trail of LLM calls. Stores a prompt hash and sizes, never raw prompts or keys."""

    __tablename__ = "ai_request_logs"

    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True
    )
    agent: Mapped[str] = mapped_column(String(48))
    provider: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(80))
    prompt_hash: Mapped[str] = mapped_column(String(64))
    prompt_chars: Mapped[int] = mapped_column(Integer)
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    latency_ms: Mapped[float | None] = mapped_column(Float)
    attempts: Mapped[int] = mapped_column(Integer, default=1)
    success: Mapped[bool] = mapped_column(default=True)
    error_code: Mapped[str | None] = mapped_column(String(64))
