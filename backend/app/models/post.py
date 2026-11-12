import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.enums import ClassificationSource, Platform
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, str_enum

# Canonical numeric metrics on a post. All nullable: platforms report different subsets.
POST_METRIC_FIELDS: tuple[str, ...] = (
    "likes",
    "comments",
    "shares",
    "saves",
    "views",
    "reach",
    "impressions",
    "clicks",
    "profile_visits",
    "website_clicks",
    "followers",
    "followers_gained",
    "watch_time_seconds",
    "average_watch_time_seconds",
    "video_duration_seconds",
    "completion_rate",
    "engaged_users",
    "ad_spend",
    "conversions",
    "leads",
)


class SocialPost(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "social_posts"
    __table_args__ = (
        UniqueConstraint("project_id", "platform", "external_post_id"),
        Index("ix_social_posts_project_platform_published", "project_id", "platform", "published_at"),
    )

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("uploaded_files.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[Platform] = mapped_column(str_enum(Platform))
    external_post_id: Mapped[str] = mapped_column(String(255))
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    has_time: Mapped[bool] = mapped_column(default=True)  # False when export only had a date
    permalink: Mapped[str | None] = mapped_column(String(1024))

    post_type: Mapped[str | None] = mapped_column(String(64))  # raw platform label
    media_type: Mapped[str | None] = mapped_column(String(64))
    content_format: Mapped[str | None] = mapped_column(String(32))  # normalized ContentFormat
    caption: Mapped[str | None] = mapped_column(Text)
    hashtags: Mapped[list[str]] = mapped_column(JSONType, default=list)

    content_topic: Mapped[str | None] = mapped_column(String(32))
    content_pillar: Mapped[str | None] = mapped_column(String(32))
    topic_source: Mapped[ClassificationSource | None] = mapped_column(str_enum(ClassificationSource))
    topic_confidence: Mapped[float | None] = mapped_column(Float)
    cta_type: Mapped[str | None] = mapped_column(String(32))
    hook_type: Mapped[str | None] = mapped_column(String(32))
    paid_or_organic: Mapped[str | None] = mapped_column(String(16))

    likes: Mapped[float | None] = mapped_column(Float)
    comments: Mapped[float | None] = mapped_column(Float)
    shares: Mapped[float | None] = mapped_column(Float)
    saves: Mapped[float | None] = mapped_column(Float)
    views: Mapped[float | None] = mapped_column(Float)
    reach: Mapped[float | None] = mapped_column(Float)
    impressions: Mapped[float | None] = mapped_column(Float)
    clicks: Mapped[float | None] = mapped_column(Float)
    profile_visits: Mapped[float | None] = mapped_column(Float)
    website_clicks: Mapped[float | None] = mapped_column(Float)
    followers: Mapped[float | None] = mapped_column(Float)
    followers_gained: Mapped[float | None] = mapped_column(Float)
    watch_time_seconds: Mapped[float | None] = mapped_column(Float)
    average_watch_time_seconds: Mapped[float | None] = mapped_column(Float)
    video_duration_seconds: Mapped[float | None] = mapped_column(Float)
    completion_rate: Mapped[float | None] = mapped_column(Float)  # percent 0-100
    engaged_users: Mapped[float | None] = mapped_column(Float)
    ad_spend: Mapped[float | None] = mapped_column(Float)
    conversions: Mapped[float | None] = mapped_column(Float)
    leads: Mapped[float | None] = mapped_column(Float)

    # --- Future multimodal analysis (not required for MVP) ---
    thumbnail_url: Mapped[str | None] = mapped_column(String(1024))
    media_url: Mapped[str | None] = mapped_column(String(1024))
    # e.g. {"human_presence": true, "text_heavy": false, "logo_presence": true, ...}
    visual_features: Mapped[dict[str, Any] | None] = mapped_column(JSONType)

    # Unmapped source columns kept for traceability.
    extra: Mapped[dict[str, Any]] = mapped_column(JSONType, default=dict)


class MetricSnapshot(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Account-level daily metrics (followers etc.), separate from post-level metrics."""

    __tablename__ = "metric_snapshots"
    __table_args__ = (UniqueConstraint("project_id", "platform", "snapshot_date"),)

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(str_enum(Platform))
    snapshot_date: Mapped[date] = mapped_column(Date)
    followers: Mapped[float | None] = mapped_column(Float)
    followers_gained: Mapped[float | None] = mapped_column(Float)
    reach: Mapped[float | None] = mapped_column(Float)
    impressions: Mapped[float | None] = mapped_column(Float)
    profile_visits: Mapped[float | None] = mapped_column(Float)
    source_file_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("uploaded_files.id", ondelete="CASCADE"))


class ContentClassification(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Cache of AI topic classifications so the same caption is never classified twice."""

    __tablename__ = "content_classifications"
    __table_args__ = (UniqueConstraint("caption_hash", "taxonomy_version", "model"),)

    caption_hash: Mapped[str] = mapped_column(String(64))
    taxonomy_version: Mapped[str] = mapped_column(String(16))
    model: Mapped[str] = mapped_column(String(80))
    topic: Mapped[str] = mapped_column(String(32))
    pillar: Mapped[str] = mapped_column(String(32))
    cta_type: Mapped[str | None] = mapped_column(String(32))
    hook_type: Mapped[str | None] = mapped_column(String(32))
    confidence: Mapped[float] = mapped_column(Float)
    rationale: Mapped[str | None] = mapped_column(Text)
    platform: Mapped[str | None] = mapped_column(String(16))
    post_count: Mapped[int] = mapped_column(Integer, default=1)
