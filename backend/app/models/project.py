import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.enums import Platform, ProjectStatus
from app.db.base import Base, TimestampMixin, UUIDPrimaryKeyMixin
from app.db.types import JSONType, str_enum

if TYPE_CHECKING:
    from app.models.file import UploadedFile


class User(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """Optional for the MVP (no auth yet); projects carry a nullable owner for future multi-tenancy."""

    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str | None] = mapped_column(String(255))


class Project(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "projects"

    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[ProjectStatus] = mapped_column(str_enum(ProjectStatus), default=ProjectStatus.DRAFT)
    platforms: Mapped[list[str]] = mapped_column(JSONType, default=list)
    # IANA timezone used to interpret naive timestamps for day/hour analysis.
    timezone: Mapped[str] = mapped_column(String(64), default="UTC")
    is_demo: Mapped[bool] = mapped_column(default=False)
    owner_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, ForeignKey("users.id", ondelete="SET NULL"))

    business_profile: Mapped["BusinessProfile | None"] = relationship(
        back_populates="project", cascade="all, delete-orphan", uselist=False
    )
    platform_accounts: Mapped[list["PlatformAccount"]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    files: Mapped[list["UploadedFile"]] = relationship(back_populates="project", cascade="all, delete-orphan")


class BusinessProfile(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "business_profiles"

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), unique=True)
    business_name: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(80))
    city_market: Mapped[str | None] = mapped_column(String(120))
    products_services: Mapped[str] = mapped_column(Text)
    target_audience: Mapped[str] = mapped_column(Text)
    business_objective: Mapped[str] = mapped_column(Text)
    marketing_objectives: Mapped[list[str]] = mapped_column(JSONType, default=list)
    competitors: Mapped[list[str]] = mapped_column(JSONType, default=list)
    monthly_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    budget_currency: Mapped[str | None] = mapped_column(String(3))
    current_posting_frequency: Mapped[str | None] = mapped_column(String(120))
    additional_instructions: Mapped[str | None] = mapped_column(Text)

    project: Mapped[Project] = relationship(back_populates="business_profile")


class PlatformAccount(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    """A social account for a platform. ``source`` is 'upload' now; 'api' once integrations exist."""

    __tablename__ = "platform_accounts"
    __table_args__ = (UniqueConstraint("project_id", "platform"),)

    project_id: Mapped[uuid.UUID] = mapped_column(Uuid, ForeignKey("projects.id", ondelete="CASCADE"), index=True)
    platform: Mapped[Platform] = mapped_column(str_enum(Platform))
    handle: Mapped[str | None] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(20), default="upload")
    external_account_id: Mapped[str | None] = mapped_column(String(120))

    project: Mapped[Project] = relationship(back_populates="platform_accounts")
