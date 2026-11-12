import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Confidence, RunStatus, Severity
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, str_enum


class AnalyticsRun(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One immutable, versioned execution of the analytics pipeline for a project."""

    __tablename__ = "analytics_runs"
    __table_args__ = (UniqueConstraint("project_id", "analysis_version"),)

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    analysis_version: Mapped[int] = mapped_column(Integer)
    status: Mapped[RunStatus] = mapped_column(str_enum(RunStatus), default=RunStatus.RUNNING)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    # Hash of the input posts; identical inputs + params give identical results.
    input_hash: Mapped[str | None] = mapped_column(String(64))
    post_count: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Parameters used (objective, weights, thresholds) for reproducibility.
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    # Compact overview used by dashboards (headline KPIs per platform).
    summary: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    error: Mapped[str | None] = mapped_column(Text)

    results: Mapped[list["AnalyticsResult"]] = relationship(back_populates="run", cascade="all, delete-orphan")
    insights: Mapped[list["Insight"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class AnalyticsResult(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """One section of a run's output (kpis, formats, pillars, timing, trends, stats, ...)."""

    __tablename__ = "analytics_results"
    __table_args__ = (UniqueConstraint("run_id", "section"),)

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("analytics_runs.id", ondelete="CASCADE"), index=True)
    section: Mapped[str] = mapped_column(String(64))
    payload: Mapped[Any] = mapped_column(JSONType)

    run: Mapped[AnalyticsRun] = relationship(back_populates="results")


class Insight(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Deterministic, rule-based finding produced before any LLM call."""

    __tablename__ = "insights"

    run_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("analytics_runs.id", ondelete="CASCADE"), index=True)
    rule_id: Mapped[str] = mapped_column(String(64))
    category: Mapped[str] = mapped_column(String(48))
    platform: Mapped[str | None] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(255))
    description: Mapped[str] = mapped_column(Text)
    metric: Mapped[str | None] = mapped_column(String(64))
    evidence: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)
    confidence: Mapped[Confidence] = mapped_column(str_enum(Confidence))
    severity: Mapped[Severity] = mapped_column(str_enum(Severity))
    sentiment: Mapped[str] = mapped_column(String(16), default="neutral")  # positive/negative/neutral
    recommendation_hint: Mapped[str | None] = mapped_column(Text)

    run: Mapped[AnalyticsRun] = relationship(back_populates="insights")
