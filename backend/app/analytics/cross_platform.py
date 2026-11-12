"""Cross-platform comparison with explicit normalization.

Raw metrics are NOT comparable across platforms: TikTok "views" count plays (including
repeats and non-followers), LinkedIn "impressions" count feed renders, Instagram
"reach" counts unique accounts. So this module compares only:

* unitless ratios within each platform's own exposure definition (ER, clicks per 1k
  exposure, follows per 1k exposure) - reported with the exposure metric used;
* process metrics that share a unit (posts/week, consistency score);
* each platform's *trend* (% change), which is relative to itself;
* rank positions across platforms, rather than differences in raw values.

The answers to "which platform is strongest at X" are therefore relative statements
about this account, not claims that one platform's audience is bigger.
"""

import numpy as np
import pandas as pd

from app.analytics.common import fnum, platform_label, safe_div

EFFICIENCY_LABELS = {
    "median_er": "engagement rate",
    "clicks_per_1k_exposure": "clicks per 1k exposure",
    "follows_per_1k_exposure": "follows per 1k exposure",
}

METHODOLOGY = (
    "Platforms define exposure differently (Instagram/Facebook: reach = unique accounts; TikTok: video views; "
    "LinkedIn: impressions). Comparisons use ratios within each platform's own exposure metric, process "
    "metrics (frequency, consistency), relative trends and rank positions - never raw counts across platforms."
)


def analyze_cross_platform(df: pd.DataFrame, per_platform: dict[str, dict]) -> dict:
    rows = []
    total_posts = len(df)
    for platform, g in df.groupby("platform"):
        p = per_platform[str(platform)]
        videos = g[g["is_video"]]
        rows.append(
            {
                "platform": str(platform),
                "label": platform_label(str(platform)),
                "exposure_metric": p["kpis"]["exposure_metric"],
                "posts": int(len(g)),
                "share_of_posts_pct": fnum(len(g) / total_posts * 100, 1),
                "posts_per_week": p["posting"]["posts_per_week"],
                "consistency_score": p["posting"]["consistency_score"],
                "median_er": fnum(g["er"].median(), 3),
                "aggregate_er": p["kpis"]["metrics"].get("engagement_rate"),
                "clicks_total": fnum(g["all_clicks"].sum(), 0) if g["all_clicks"].notna().any() else None,
                "clicks_per_1k_exposure": fnum(safe_div(g["all_clicks"].sum(), g["exposure"].sum(), 1000), 2)
                if g["all_clicks"].notna().any() else None,
                "follows_per_1k_exposure": fnum(safe_div(g["followers_gained"].sum(), g["exposure"].sum(), 1000), 2)
                if g["followers_gained"].notna().any() else None,
                "follower_growth": fnum(g["followers_gained"].sum(), 0) if g["followers_gained"].notna().any() else None,
                "share_rate_median": fnum(g["share_rate"].median(), 3),
                "video_posts": int(len(videos)),
                "median_video_completion": fnum(videos["completion"].median(), 1) if len(videos) >= 5 else None,
                "exposure_trend": p["trends"]["trends"].get("median_exposure", {}).get("label"),
                "exposure_trend_pct": p["trends"]["trends"].get("median_exposure", {}).get("total_change_pct"),
                "er_trend": p["trends"]["trends"].get("median_er", {}).get("label"),
            }
        )  # fmt: skip
    table = pd.DataFrame(rows).set_index("platform") if rows else pd.DataFrame()

    def leader(col: str, min_rows: int = 1) -> dict | None:
        if table.empty or col not in table or table[col].notna().sum() < min_rows:
            return None
        s = table[col].dropna()
        best = s.idxmax()
        return {"platform": best, "label": platform_label(best), "value": fnum(s[best], 3), "metric": col,
                "ranking": [{"platform": k, "value": fnum(v, 3)} for k, v in s.sort_values(ascending=False).items()]}  # fmt: skip

    # Relative efficiency: mean percentile rank across platforms of ER, click rate, follow rate.
    underutilized = None
    if len(table) >= 2:
        eff_cols = [
            c for c in ("median_er", "clicks_per_1k_exposure", "follows_per_1k_exposure") if table[c].notna().sum() >= 2
        ]
        if eff_cols:
            eff = table[eff_cols].rank(pct=True).mean(axis=1)
            effort = table["share_of_posts_pct"].rank(pct=True)
            gap = (eff - effort).sort_values(ascending=False)
            top = gap.index[0]
            if gap.iloc[0] > 0:
                underutilized = {
                    "platform": top,
                    "label": platform_label(top),
                    "efficiency_rank_pct": fnum(eff[top] * 100, 0),
                    "share_of_posts_pct": fnum(table.loc[top, "share_of_posts_pct"], 1),
                    "reason": (
                        f"{platform_label(top)} ranks high on efficiency ({', '.join(EFFICIENCY_LABELS[c] for c in eff_cols)}) "
                        f"but receives only {table.loc[top, 'share_of_posts_pct']}% of posting effort."
                    ),
                }

    return {
        "methodology": METHODOLOGY,
        "platforms": rows,
        "answers": {
            "strongest_relative_engagement": leader("median_er", 2),
            "most_traffic": leader("clicks_total", 1),
            "most_traffic_efficient": leader("clicks_per_1k_exposure", 2),
            "strongest_video_retention": leader("median_video_completion", 1),
            "most_consistent_publishing": leader("consistency_score", 2),
            "strongest_follower_conversion": leader("follows_per_1k_exposure", 2),
            "underutilized": underutilized,
        },
        "normalized_scores": _normalized_scores(table),
    }


def _normalized_scores(table: pd.DataFrame) -> list[dict]:
    """0-100 rank-based scores per dimension (100 = best of the platforms compared)."""
    if table.empty or len(table) < 2:
        return []
    dims = {
        "engagement": "median_er",
        "traffic": "clicks_per_1k_exposure",
        "growth": "follows_per_1k_exposure",
        "consistency": "consistency_score",
        "video": "median_video_completion",
    }
    out = []
    for platform in table.index:
        scores = {}
        for dim, col in dims.items():
            s = table[col].astype(float)
            if s.notna().sum() >= 2 and pd.notna(s[platform]):
                scores[dim] = fnum((s.rank(pct=True, method="max")[platform]) * 100, 0)
        out.append({"platform": platform, "label": platform_label(platform), "scores": scores,
                    "overall": fnum(np.mean(list(scores.values())), 0) if scores else None})  # fmt: skip
    return out
