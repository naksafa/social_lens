"""Platform integration stubs.

Each source declares what it will need (scopes, endpoints) and reports itself as
unavailable in the MVP. They are deliberately not partially implemented: live API
access requires app review / OAuth app registration per platform, which is out of the
MVP's scope. Calling ``fetch_*`` raises a clear FeatureUnavailableError.
"""

from datetime import datetime

import pandas as pd

from app.core.enums import Platform
from app.core.exceptions import FeatureUnavailableError
from app.integrations.base import IntegrationCredentials, IntegrationStatus, SocialDataSource


class _PlannedSource(SocialDataSource):
    def status(self) -> IntegrationStatus:
        return IntegrationStatus(
            platform=self.platform,
            available=False,
            reason="Planned integration - use CSV/XLSX exports in the MVP.",
            required_scopes=list(self.required_scopes),
            docs_url=self.docs_url,
        )

    def _unavailable(self) -> FeatureUnavailableError:
        return FeatureUnavailableError(
            f"Direct {self.platform.value} API import is not available yet. Upload an export file instead.",
            {"required_scopes": list(self.required_scopes)},
        )

    def fetch_posts(self, creds: IntegrationCredentials, since: datetime, until: datetime) -> pd.DataFrame:
        raise self._unavailable()

    def fetch_account_metrics(self, creds: IntegrationCredentials, since: datetime, until: datetime) -> pd.DataFrame:
        raise self._unavailable()


class InstagramGraphSource(_PlannedSource):
    platform = Platform.INSTAGRAM
    required_scopes = ("instagram_basic", "instagram_manage_insights", "pages_read_engagement")
    docs_url = "https://developers.facebook.com/docs/instagram-platform/insights"


class FacebookGraphSource(_PlannedSource):
    platform = Platform.FACEBOOK
    required_scopes = ("pages_read_engagement", "read_insights")
    docs_url = "https://developers.facebook.com/docs/graph-api/reference/insights"


class TikTokSource(_PlannedSource):
    platform = Platform.TIKTOK
    required_scopes = ("video.list", "user.info.stats")
    docs_url = "https://developers.tiktok.com/doc/display-api-overview"


class LinkedInSource(_PlannedSource):
    platform = Platform.LINKEDIN
    required_scopes = ("r_organization_social", "rw_organization_admin")
    docs_url = "https://learn.microsoft.com/linkedin/marketing/community-management/organizations/share-statistics"


SOURCES: dict[Platform, SocialDataSource] = {
    s.platform: s for s in (InstagramGraphSource(), FacebookGraphSource(), TikTokSource(), LinkedInSource())
}
