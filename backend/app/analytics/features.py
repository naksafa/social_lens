"""Feature engineering: derived per-post metrics.

All rates are percentages. Denominators of 0 / missing yield NaN, never errors.

* engagement_total = sum of the engagement components the platform reports
  (likes + comments + shares + saves). A component the platform does not report
  at all (e.g. saves on LinkedIn) is excluded rather than counted as zero.
* exposure = the platform's primary reach-type metric (see EXPOSURE_PRIORITY).
* er = engagement_total / exposure x 100, plus explicit er_reach / er_impressions /
  er_views / er_followers variants when the denominators exist.
* share_rate, save_rate, comment_rate = component / exposure x 100
* ctr = clicks / impressions x 100 (falls back to exposure when impressions are absent)
* completion = native completion rate, else average_watch_time / duration x 100
* follower_conversion = followers_gained / exposure x 100
"""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from app.analytics.common import ENGAGEMENT_COMPONENTS, EXPOSURE_PRIORITY, safe_div


@dataclass
class PlatformMetricInfo:
    platform: str
    exposure_metric: str | None
    engagement_components: list[str]
    available_metrics: list[str]
    completeness: dict[str, float] = field(default_factory=dict)


METRIC_COLUMNS = (
    "likes", "comments", "shares", "saves", "views", "reach", "impressions", "clicks",
    "profile_visits", "website_clicks", "followers", "followers_gained", "watch_time_seconds",
    "average_watch_time_seconds", "video_duration_seconds", "completion_rate", "engaged_users",
    "ad_spend", "conversions", "leads",
)  # fmt: skip


def _available(df: pd.DataFrame, col: str, min_share: float = 0.3) -> bool:
    return col in df and df[col].notna().mean() >= min_share


def platform_metric_info(df: pd.DataFrame, platform: str) -> PlatformMetricInfo:
    exposure = next((m for m in EXPOSURE_PRIORITY.get(platform, ("reach",)) if _available(df, m, 0.5)), None)
    components = [c for c in ENGAGEMENT_COMPONENTS if _available(df, c)]
    available = [c for c in METRIC_COLUMNS if _available(df, c, 0.05)]
    completeness = {c: round(float(df[c].notna().mean()), 3) for c in METRIC_COLUMNS if c in df}
    return PlatformMetricInfo(platform, exposure, components, available, completeness)


def engineer_features(posts: pd.DataFrame, timezone: str = "UTC") -> tuple[pd.DataFrame, dict[str, PlatformMetricInfo]]:
    """Add derived columns to a canonical posts frame (one or many platforms)."""
    df = posts.copy()
    for col in METRIC_COLUMNS:
        if col not in df:
            df[col] = np.nan
        df[col] = pd.to_numeric(df[col], errors="coerce")

    infos: dict[str, PlatformMetricInfo] = {}
    parts = []
    for platform, g in df.groupby("platform", sort=False):
        info = platform_metric_info(g, str(platform))
        infos[str(platform)] = info
        g = g.copy()
        g["exposure"] = g[info.exposure_metric] if info.exposure_metric else np.nan
        comps = g[info.engagement_components] if info.engagement_components else pd.DataFrame(index=g.index)
        g["engagement_total"] = comps.sum(axis=1, min_count=1) if len(comps.columns) else np.nan
        parts.append(g)
    df = pd.concat(parts) if parts else df.assign(exposure=np.nan, engagement_total=np.nan)

    df["er"] = safe_div(df["engagement_total"], df["exposure"], 100)
    df["er_reach"] = safe_div(df["engagement_total"], df["reach"], 100)
    df["er_impressions"] = safe_div(df["engagement_total"], df["impressions"], 100)
    df["er_views"] = safe_div(df["engagement_total"], df["views"], 100)
    df["er_followers"] = safe_div(df["engagement_total"], df["followers"], 100)
    df["share_rate"] = safe_div(df["shares"], df["exposure"], 100)
    df["save_rate"] = safe_div(df["saves"], df["exposure"], 100)
    df["comment_rate"] = safe_div(df["comments"], df["exposure"], 100)
    all_clicks = df["clicks"].fillna(df["website_clicks"])
    df["all_clicks"] = all_clicks
    ctr_den = df["impressions"].where(df["impressions"].notna(), df["exposure"])
    df["ctr"] = safe_div(all_clicks, ctr_den, 100)
    df["click_rate"] = safe_div(all_clicks, df["exposure"], 100)
    df["follower_conversion"] = safe_div(df["followers_gained"], df["exposure"], 100)
    derived_completion = safe_div(df["average_watch_time_seconds"], df["video_duration_seconds"], 100)
    df["completion"] = df["completion_rate"].fillna(derived_completion.clip(upper=100))

    # --- content features (defaults when an export lacks the column) ---
    if "content_format" not in df:
        df["content_format"] = "other"
    df["content_format"] = df["content_format"].fillna("other")
    captions = df["caption"].fillna("") if "caption" in df else pd.Series("", index=df.index)
    df["caption_length"] = captions.str.len()
    df["hashtag_count"] = df["hashtags"].map(lambda h: len(h) if isinstance(h, list) else 0) if "hashtags" in df else 0
    df["has_cta"] = df["cta_type"].fillna("none").ne("none") if "cta_type" in df else False
    df["is_video"] = df["content_format"].isin(["reel", "video", "short_video"])

    # --- time features (in the business's local timezone) ---
    local = pd.to_datetime(df["published_at"], utc=True).dt.tz_convert(timezone)
    df["local_time"] = local
    df["date"] = local.dt.date
    df["dow"] = local.dt.dayofweek
    df["hour"] = local.dt.hour
    df["is_weekend"] = df["dow"] >= 5
    df["week"] = local.dt.tz_localize(None).dt.to_period("W-SUN").dt.start_time
    if "has_time" not in df:
        df["has_time"] = True

    df = df.sort_values("local_time")
    df["days_since_prev_post"] = df.groupby("platform")["local_time"].diff().dt.total_seconds() / 86400
    return df, infos
