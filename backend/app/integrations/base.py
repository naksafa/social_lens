"""Interfaces for future direct API integrations (Meta Graph, TikTok, LinkedIn).

The MVP works entirely from uploaded exports. Integrations plug into the *same*
ingestion path: a source returns a raw DataFrame with the platform's native column
names, which then goes through platform detection, column mapping, normalization and
validation exactly like an upload. No analytics code needs to change.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime

import pandas as pd

from app.core.enums import Platform


@dataclass(frozen=True)
class IntegrationCredentials:
    """OAuth tokens are stored encrypted server-side; never logged."""

    access_token: str
    account_id: str
    expires_at: datetime | None = None
    scopes: tuple[str, ...] = ()


@dataclass(frozen=True)
class IntegrationStatus:
    platform: Platform
    available: bool
    reason: str
    required_scopes: list[str] = field(default_factory=list)
    docs_url: str | None = None


class SocialDataSource(ABC):
    platform: Platform
    required_scopes: tuple[str, ...] = ()
    docs_url: str | None = None

    @abstractmethod
    def status(self) -> IntegrationStatus:
        """Whether this integration is usable on this deployment."""

    @abstractmethod
    def fetch_posts(self, creds: IntegrationCredentials, since: datetime, until: datetime) -> pd.DataFrame:
        """Return one row per post with native column names (fed to the normal ingestion pipeline)."""

    @abstractmethod
    def fetch_account_metrics(self, creds: IntegrationCredentials, since: datetime, until: datetime) -> pd.DataFrame:
        """Daily account-level metrics (followers, reach) -> MetricSnapshot."""
