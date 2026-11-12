"""Audience behaviour signals inferred from interaction patterns.

Post exports contain no demographics, so "audience insights" here are *behavioural*:
how the audience chooses to interact (saving = reference value, sharing = social
currency, commenting = conversation), whether exposure converts to follows or clicks,
and video retention. When the audience responds best is covered by timing_analysis.
"""

import pandas as pd

from app.analytics.common import fnum, platform_label, safe_div


def interaction_mix(g: pd.DataFrame, components: list[str]) -> dict[str, float]:
    totals = {c: float(g[c].sum()) for c in components if c in g and g[c].notna().any()}
    total = sum(totals.values())
    return {c: fnum(v / total * 100, 1) for c, v in totals.items()} if total else {}  # type: ignore[misc]


def analyze_audience(g: pd.DataFrame, platform: str, components: list[str]) -> dict:
    mix = interaction_mix(g, components)
    exp_sum = g["exposure"].sum()
    signals: list[dict] = []
    name = platform_label(platform)

    non_like = {k: v for k, v in mix.items() if k != "likes"}
    if non_like:
        dominant = max(non_like, key=non_like.get)  # type: ignore[arg-type]
        meaning = {
            "saves": "the audience treats content as reference material worth returning to",
            "shares": "content is used as social currency and spreads beyond followers",
            "comments": "content sparks conversation",
        }[dominant]
        signals.append({
            "signal": f"dominant_{dominant}",
            "description": f"Beyond likes, {name} interaction is led by {dominant} ({mix[dominant]}% of engagement): {meaning}.",
            "evidence": {"interaction_mix_pct": mix},
        })  # fmt: skip

    conv = (
        fnum(safe_div(g["followers_gained"].sum(), exp_sum, 1000), 2) if g["followers_gained"].notna().any() else None
    )
    if conv is not None:
        signals.append({
            "signal": "follower_conversion",
            "description": f"{name} converts about {conv} followers per 1,000 {('views' if platform == 'tiktok' else 'accounts reached')}.",
            "evidence": {"followers_per_1k_exposure": conv},
        })  # fmt: skip
    clicks = g["all_clicks"]
    click_per_1k = fnum(safe_div(clicks.sum(), exp_sum, 1000), 2) if clicks.notna().any() else None
    if click_per_1k is not None:
        signals.append({
            "signal": "click_intent",
            "description": f"{name} generates {click_per_1k} clicks per 1,000 exposures.",
            "evidence": {"clicks_per_1k_exposure": click_per_1k, "total_clicks": fnum(clicks.sum(), 0)},
        })  # fmt: skip
    videos = g[g["is_video"]]
    if len(videos) >= 5 and videos["completion"].notna().any():
        med = fnum(videos["completion"].median(), 1)
        signals.append({
            "signal": "video_retention",
            "description": f"Median {name} video completion is {med}%.",
            "evidence": {"median_completion_pct": med, "videos": int(len(videos))},
        })  # fmt: skip

    return {
        "interaction_mix_pct": mix,
        "comment_rate_median": fnum(g["comment_rate"].median(), 3),
        "save_to_share_ratio": fnum(safe_div(g["saves"].sum(), g["shares"].sum()), 2)
        if g["saves"].notna().any()
        else None,
        "followers_per_1k_exposure": conv,
        "clicks_per_1k_exposure": click_per_1k,
        "signals": signals,
        "limitations": "Exports contain no demographic data; insights describe interaction behaviour only.",
    }
