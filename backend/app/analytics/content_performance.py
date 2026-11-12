"""Best / worst content with robust ranking.

Rate-based rankings (engagement rate, completion) only consider posts whose exposure
is at least max(RATE_RANKING_MIN_EXPOSURE, 25th percentile of the platform), so a post
seen by 40 people with 10 likes cannot top the "best engagement rate" list.
"""

import pandas as pd

from app.analytics.common import RATE_RANKING_MIN_EXPOSURE, RATE_RANKING_MIN_PERCENTILE, fnum

TOP_N = 5


def post_card(row: pd.Series) -> dict:
    caption = row.get("caption") or ""
    return {
        "post_id": str(row.get("id")) if row.get("id") is not None else None,
        "external_post_id": row.get("external_post_id"),
        "platform": row.get("platform"),
        "published_at": row["local_time"].isoformat() if pd.notna(row.get("local_time")) else None,
        "format": row.get("content_format"),
        "pillar": row.get("content_pillar"),
        "topic": row.get("content_topic"),
        "hook_type": row.get("hook_type"),
        "cta_type": row.get("cta_type"),
        "caption": caption[:160] + ("…" if len(caption) > 160 else ""),
        "permalink": row.get("permalink"),
        "exposure": fnum(row.get("exposure"), 0),
        "engagement": fnum(row.get("engagement_total"), 0),
        "er": fnum(row.get("er"), 2),
        "likes": fnum(row.get("likes"), 0),
        "comments": fnum(row.get("comments"), 0),
        "shares": fnum(row.get("shares"), 0),
        "saves": fnum(row.get("saves"), 0),
        "clicks": fnum(row.get("all_clicks"), 0),
        "views": fnum(row.get("views"), 0),
        "completion": fnum(row.get("completion"), 1),
        "video_duration_seconds": fnum(row.get("video_duration_seconds"), 0),
        "performance_index": fnum(row.get("performance_index"), 1),
    }


def _top(g: pd.DataFrame, col: str, n: int = TOP_N, ascending: bool = False) -> list[dict]:
    if col not in g or g[col].notna().sum() == 0:
        return []
    ranked = g.dropna(subset=[col]).sort_values(col, ascending=ascending).head(n)
    return [post_card(r) for _, r in ranked.iterrows()]


def exposure_threshold(g: pd.DataFrame) -> float:
    if g["exposure"].notna().sum() == 0:
        return 0.0
    return max(RATE_RANKING_MIN_EXPOSURE, float(g["exposure"].quantile(RATE_RANKING_MIN_PERCENTILE)))


def platform_top_content(g: pd.DataFrame, exposure_metric: str | None) -> dict:
    threshold = exposure_threshold(g)
    eligible = g[g["exposure"] >= threshold] if threshold else g
    videos = g[g["is_video"]]
    eligible_videos = videos[videos["exposure"] >= threshold] if threshold else videos
    return {
        "exposure_metric": exposure_metric,
        "rate_ranking_min_exposure": fnum(threshold, 0),
        "eligible_for_rate_rankings": int(len(eligible)),
        "top_by_exposure": _top(g, "exposure"),
        "top_by_engagement": _top(g, "engagement_total"),
        "top_by_engagement_rate": _top(eligible, "er"),
        "top_by_saves": _top(g, "saves"),
        "top_by_shares": _top(g, "shares"),
        "top_by_clicks": _top(g, "all_clicks"),
        "top_videos_by_views": _top(videos, "views" if videos["views"].notna().any() else "exposure"),
        "top_videos_by_completion": _top(eligible_videos, "completion"),
        "top_by_performance_index": _top(g, "performance_index"),
        "bottom_by_performance_index": _top(g, "performance_index", ascending=True),
        "bottom_by_engagement_rate": _top(eligible, "er", ascending=True),
    }
