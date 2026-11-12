"""Objective-weighted performance index.

For each post::

    performance_index = sum_i( w_i * pct_rank_i ) / sum_i( w_i  for metrics present )

* ``pct_rank_i`` is the post's percentile rank (0-100) for metric *i* **within its own
  platform**, so the index is scale-free and comparable across platforms in the sense
  of "how good is this post relative to its platform peers".
* Weights ``w_i`` come from the business objectives (ObjectiveWeightingService).
  Metrics a platform doesn't report are dropped and the remaining weights re-normalized,
  so a LinkedIn post isn't penalised for LinkedIn not reporting saves.
* With several objectives, the primary (first) objective counts double.
"""

from dataclasses import dataclass, field

import pandas as pd

from app.core.enums import MarketingObjective as MO

#: metric key -> per-post column used for scoring
SCORING_METRICS: dict[str, str] = {
    "exposure": "exposure",
    "engagement_rate": "er",
    "share_rate": "share_rate",
    "save_rate": "save_rate",
    "comment_rate": "comment_rate",
    "click_rate": "click_rate",
    "follower_conversion": "follower_conversion",
    "completion": "completion",
    "leads": "leads",
    "conversions": "conversions",
}

OBJECTIVE_WEIGHTS: dict[MO, dict[str, float]] = {
    MO.BRAND_AWARENESS: {"exposure": 0.45, "share_rate": 0.2, "engagement_rate": 0.15, "follower_conversion": 0.1, "completion": 0.1},
    MO.ENGAGEMENT: {"engagement_rate": 0.35, "comment_rate": 0.2, "share_rate": 0.2, "save_rate": 0.2, "exposure": 0.05},
    MO.LEAD_GENERATION: {"leads": 0.3, "click_rate": 0.3, "comment_rate": 0.1, "save_rate": 0.1, "engagement_rate": 0.1, "exposure": 0.1},
    MO.SALES: {"conversions": 0.3, "click_rate": 0.3, "engagement_rate": 0.15, "exposure": 0.15, "save_rate": 0.1},
    MO.WEBSITE_TRAFFIC: {"click_rate": 0.45, "exposure": 0.25, "engagement_rate": 0.15, "share_rate": 0.15},
    MO.STORE_VISITS: {"exposure": 0.3, "engagement_rate": 0.2, "share_rate": 0.2, "comment_rate": 0.15, "save_rate": 0.15},
    MO.COMMUNITY_GROWTH: {"comment_rate": 0.3, "engagement_rate": 0.25, "follower_conversion": 0.25, "share_rate": 0.2},
    MO.FOLLOWER_GROWTH: {"follower_conversion": 0.45, "exposure": 0.3, "share_rate": 0.15, "engagement_rate": 0.1},
    MO.VIDEO_VIEWS: {"exposure": 0.4, "completion": 0.35, "share_rate": 0.15, "engagement_rate": 0.1},
}  # fmt: skip

DEFAULT_WEIGHTS = {"exposure": 0.3, "engagement_rate": 0.3, "share_rate": 0.15, "save_rate": 0.1, "comment_rate": 0.15}


@dataclass
class ResolvedWeights:
    weights: dict[str, float]
    objectives: list[str]
    explanation: str
    dropped: dict[str, list[str]] = field(default_factory=dict)  # platform -> metrics without data


class ObjectiveWeightingService:
    def __init__(self, overrides: dict[str, float] | None = None) -> None:
        self.overrides = overrides

    def resolve(self, objectives: list[str] | None) -> ResolvedWeights:
        if self.overrides:
            total = sum(self.overrides.values()) or 1
            return ResolvedWeights(
                {k: v / total for k, v in self.overrides.items()}, objectives or [], "Custom weights."
            )
        valid = [MO(o) for o in (objectives or []) if o in MO._value2member_map_]
        if not valid:
            return ResolvedWeights(DEFAULT_WEIGHTS.copy(), [], "No objective selected; balanced default weights.")
        combined: dict[str, float] = {}
        for i, obj in enumerate(valid):
            factor = 2.0 if i == 0 and len(valid) > 1 else 1.0
            for k, w in OBJECTIVE_WEIGHTS[obj].items():
                combined[k] = combined.get(k, 0.0) + w * factor
        total = sum(combined.values())
        weights = {k: round(v / total, 4) for k, v in sorted(combined.items(), key=lambda kv: -kv[1])}
        names = ", ".join(o.value.replace("_", " ") for o in valid)
        return ResolvedWeights(
            weights,
            [o.value for o in valid],
            f"Weights derived from objectives ({names}); the primary objective counts double.",
        )


def compute_performance_index(df: pd.DataFrame, resolved: ResolvedWeights) -> pd.Series:
    """Return a 0-100 performance index per post (NaN if no weighted metric is present)."""
    index = pd.Series(float("nan"), index=df.index)
    for platform, g in df.groupby("platform"):
        num = pd.Series(0.0, index=g.index)
        den = pd.Series(0.0, index=g.index)
        dropped = []
        for key, weight in resolved.weights.items():
            col = SCORING_METRICS.get(key)
            if col is None or col not in g or g[col].notna().sum() < 3:
                dropped.append(key)
                continue
            pct = g[col].rank(pct=True, method="average") * 100
            present = pct.notna()
            num[present] += weight * pct[present]
            den[present] += weight
        resolved.dropped[str(platform)] = dropped
        index.loc[g.index] = (num / den.where(den > 0)).round(1)
    return index
