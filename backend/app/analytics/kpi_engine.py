"""KPI engine: headline metrics per platform.

A KPI is only calculated when its underlying fields exist; otherwise it is listed in
``unavailable`` with the reason, never silently reported as 0.

Aggregate rates are ratio-of-sums (e.g. total engagement / total reach), which weights
posts by their size. Median per-post rates are reported alongside, since a few viral
posts can dominate the aggregate.
"""

import pandas as pd

from app.analytics.common import fnum, safe_div
from app.analytics.features import PlatformMetricInfo


def _sum(g: pd.DataFrame, col: str) -> float | None:
    return fnum(g[col].sum(), 2) if col in g and g[col].notna().any() else None


def _mean(g: pd.DataFrame, col: str) -> float | None:
    return fnum(g[col].mean(), 2) if col in g and g[col].notna().any() else None


def _median(g: pd.DataFrame, col: str) -> float | None:
    return fnum(g[col].median(), 2) if col in g and g[col].notna().any() else None


def period_days(g: pd.DataFrame, period: tuple[pd.Timestamp, pd.Timestamp] | None = None) -> int:
    if period:
        return max(1, (period[1] - period[0]).days + 1)
    return max(1, (g["local_time"].max() - g["local_time"].min()).days + 1)


def platform_kpis(
    g: pd.DataFrame, info: PlatformMetricInfo, period: tuple[pd.Timestamp, pd.Timestamp] | None = None
) -> dict:
    days = period_days(g, period)
    has = set(info.available_metrics)
    exp = info.exposure_metric
    m: dict[str, float | int | None] = {
        "total_posts": int(len(g)),
        "period_days": days,
        "posts_per_week": fnum(len(g) / days * 7, 2),
        "posts_per_month": fnum(len(g) / days * 30.44, 1),
        "total_reach": _sum(g, "reach"),
        "avg_reach": _mean(g, "reach"),
        "median_reach": _median(g, "reach"),
        "total_impressions": _sum(g, "impressions"),
        "avg_impressions": _mean(g, "impressions"),
        "total_views": _sum(g, "views"),
        "avg_views": _mean(g, "views"),
        "median_views": _median(g, "views"),
        "total_engagement": _sum(g, "engagement_total"),
        "avg_engagement": _mean(g, "engagement_total"),
        "median_engagement": _median(g, "engagement_total"),
        "engagement_rate": fnum(safe_div(g["engagement_total"].sum(), g["exposure"].sum(), 100), 3) if exp else None,
        "median_engagement_rate": _median(g, "er"),
        "engagement_rate_by_followers": _median(g, "er_followers"),
        "follower_growth": _sum(g, "followers_gained"),
        "total_likes": _sum(g, "likes"),
        "total_comments": _sum(g, "comments"),
        "total_shares": _sum(g, "shares"),
        "share_rate": fnum(safe_div(g["shares"].sum(), g["exposure"].sum(), 100), 3)
        if "shares" in has and exp
        else None,
        "total_saves": _sum(g, "saves"),
        "save_rate": fnum(safe_div(g["saves"].sum(), g["exposure"].sum(), 100), 3) if "saves" in has and exp else None,
        "total_clicks": _sum(g, "all_clicks"),
        "ctr": fnum(
            safe_div(
                g["all_clicks"].sum(),
                (g["impressions"] if "impressions" in has else g["exposure"]).sum(),
                100,
            ),
            3,
        )
        if ("clicks" in has or "website_clicks" in has)
        else None,
        "profile_visits": _sum(g, "profile_visits"),
        "video_posts": int(g["is_video"].sum()),
        "median_completion_rate": _median(g[g["is_video"]], "completion"),
        "avg_watch_time_seconds": _mean(g[g["is_video"]], "average_watch_time_seconds"),
        "median_performance_index": _median(g, "performance_index"),
    }

    reasons = {
        "total_reach": "reach not in export",
        "avg_reach": "reach not in export",
        "median_reach": "reach not in export",
        "total_impressions": "impressions not in export",
        "avg_impressions": "impressions not in export",
        "total_views": "views not in export",
        "avg_views": "views not in export",
        "median_views": "views not in export",
        "engagement_rate": "no exposure metric (reach/impressions/views)",
        "engagement_rate_by_followers": "follower counts per post not in export",
        "follower_growth": "followers gained not in export",
        "total_saves": "platform/export does not report saves",
        "save_rate": "platform/export does not report saves",
        "total_clicks": "clicks not in export",
        "ctr": "clicks not in export",
        "profile_visits": "profile visits not in export",
        "median_completion_rate": "no video completion data",
        "avg_watch_time_seconds": "no watch-time data",
        "share_rate": "shares not in export",
    }
    unavailable = {k: reasons.get(k, "not available") for k, v in m.items() if v is None}
    return {
        "exposure_metric": exp,
        "engagement_components": info.engagement_components,
        "metrics": {k: v for k, v in m.items() if v is not None},
        "unavailable": unavailable,
        "completeness": info.completeness,
    }


def overall_kpis(df: pd.DataFrame) -> dict:
    """Only additive totals are combined across platforms (rates use different denominators)."""
    return {
        "total_posts": int(len(df)),
        "platforms": sorted(df["platform"].unique().tolist()),
        "total_engagement": _sum(df, "engagement_total"),
        "total_clicks": _sum(df, "all_clicks"),
        "follower_growth": _sum(df, "followers_gained"),
        "total_video_posts": int(df["is_video"].sum()),
        "note": (
            "Cross-platform totals add counts only. Rates are not averaged across platforms "
            "because each platform measures exposure differently (reach vs. views vs. impressions)."
        ),
    }
