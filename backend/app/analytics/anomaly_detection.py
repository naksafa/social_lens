"""Outlier detection on exposure and engagement rate.

Uses the robust z-score (median/MAD) on log(1 + exposure) and on ER: |z| > 3 flags a
post as an over- or under-performer. IQR fences (Q1 - 1.5 IQR, Q3 + 1.5 IQR) are also
reported for transparency. Outliers are *kept* in all analyses (medians and rank tests
are robust to them) but surfaced so viral hits can be studied.
"""

import numpy as np
import pandas as pd

from app.analytics.common import fnum
from app.analytics.content_performance import post_card
from app.analytics.statistics import iqr_bounds, robust_z

Z_THRESHOLD = 3.0


def analyze_anomalies(g: pd.DataFrame) -> dict:
    out: dict = {"method": "robust z-score (median/MAD) > 3 on log exposure and on ER; IQR fences reported"}
    results = {}
    for metric, transform in (("exposure", np.log1p), ("er", lambda s: s)):
        s = g[metric].dropna()
        if len(s) < 10:
            continue
        z = robust_z(transform(s))
        over = z[z > Z_THRESHOLD].index
        under = z[z < -Z_THRESHOLD].index
        bounds = iqr_bounds(s)
        results[metric] = {
            "over_performers": [dict(post_card(g.loc[i]), z_score=fnum(z[i], 2)) for i in over][:10],
            "under_performers": [dict(post_card(g.loc[i]), z_score=fnum(z[i], 2)) for i in under][:10],
            "iqr_lower": fnum(bounds[0], 3) if bounds else None,
            "iqr_upper": fnum(bounds[1], 3) if bounds else None,
            "iqr_outlier_count": int(((s < bounds[0]) | (s > bounds[1])).sum()) if bounds else 0,
        }
    out["metrics"] = results
    out["outlier_share_pct"] = fnum(
        len({p["external_post_id"] for m in results.values() for p in m["over_performers"] + m["under_performers"]})
        / max(len(g), 1)
        * 100,
        1,
    )
    return out
