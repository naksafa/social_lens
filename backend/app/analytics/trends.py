"""Metric trends over time.

Weekly series (posts, median exposure, median ER, total engagement, followers gained)
with a 3-week rolling mean. Direction is estimated with the Theil-Sen slope (robust to
viral outliers) and tested with Spearman's rho between week index and value.

Classification of a series (>= 4 complete weeks):
  * growth / decline : Spearman p < 0.10 and |total change over period| >= 10%
  * volatile         : otherwise, if the coefficient of variation > 0.5
  * plateau          : otherwise
"""

import numpy as np
import pandas as pd
from scipy import stats

from app.analytics.common import fnum, platform_label
from app.analytics.findings import Finding
from app.analytics.grouping import metric_label

MIN_WEEKS = 4

SERIES = {
    "posts": ("id", "count"),
    "median_exposure": ("exposure", "median"),
    "median_er": ("er", "median"),
    "total_engagement": ("engagement_total", "sum"),
    "followers_gained": ("followers_gained", "sum"),
    "median_completion": ("completion", "median"),
}


def weekly_series(g: pd.DataFrame, period: tuple[pd.Timestamp, pd.Timestamp]) -> pd.DataFrame:
    start, end = (p.tz_localize(None).normalize() for p in period)
    all_weeks = pd.period_range(start, end, freq="W-SUN").start_time
    data = g.assign(_id=1)
    agg = {}
    for name, (col, how) in SERIES.items():
        src = "_id" if col == "id" else col
        if src in data and data[src].notna().any():
            agg[name] = data.groupby("week")[src].agg("sum" if how == "count" else how)
    weekly = pd.DataFrame(agg).reindex(all_weeks)
    if "posts" in weekly:
        weekly["posts"] = weekly["posts"].fillna(0)
    for col in ("total_engagement", "followers_gained"):
        if col in weekly:
            weekly[col] = weekly[col].fillna(0)
    # Only full weeks inside the period are used to fit trends (partial edges are shown, not fitted).
    weekly["complete"] = [(w >= start) and (w + pd.Timedelta(days=6) <= end) for w in weekly.index]
    return weekly


def classify_trend(values: pd.Series) -> dict:
    # x = the week's real position, so weeks without posts don't compress the time axis.
    positions = np.arange(len(values))[values.notna().to_numpy()]
    v = values.dropna()
    if len(v) < MIN_WEEKS or v.mean() == 0 or v.nunique() < 2:
        return {"label": "insufficient_data", "weeks": int(len(v))}
    x = positions
    slope, intercept, _, _ = stats.theilslopes(v.to_numpy(), x)
    rho, p = stats.spearmanr(x, v.to_numpy())
    mean = float(v.mean())
    total_change = slope * (len(values) - 1) / mean * 100
    cv = float(v.std(ddof=0) / mean) if mean else 0.0
    if np.isfinite(p) and p < 0.10 and abs(total_change) >= 10:
        label = "growth" if slope > 0 else "decline"
    elif cv > 0.5:
        label = "volatile"
    else:
        label = "plateau"
    half = len(v) // 2
    first, second = v.iloc[:half].mean(), v.iloc[half:].mean()
    return {
        "label": label,
        "weeks": int(len(v)),
        "slope_per_week": fnum(slope, 4),
        "pct_change_per_week": fnum(slope / mean * 100, 2),
        "total_change_pct": fnum(total_change, 1),
        "spearman_rho": fnum(rho, 3),
        "p_value": fnum(p, 4),
        "cv": fnum(cv, 3),
        "first_half_mean": fnum(first, 3),
        "second_half_mean": fnum(second, 3),
        "half_over_half_pct": fnum((second - first) / first * 100, 1) if first else None,
    }


def analyze_trends(
    g: pd.DataFrame, platform: str, period: tuple[pd.Timestamp, pd.Timestamp], exposure_metric: str | None
) -> tuple[dict, list[Finding]]:
    weekly = weekly_series(g, period)
    for col in [c for c in SERIES if c in weekly]:
        weekly[f"{col}_rolling3"] = weekly[col].rolling(3, min_periods=2).mean()
    complete = weekly[weekly["complete"]]

    trends = {col: classify_trend(complete[col]) for col in SERIES if col in complete}
    findings = []
    for col, t in trends.items():
        if t["label"] in ("growth", "decline", "volatile") and col != "posts":
            name = {"median_exposure": metric_label("exposure", exposure_metric), "median_er": "engagement rate",
                    "total_engagement": "total engagement", "followers_gained": "follower gains",
                    "median_completion": "video completion"}.get(col, col)  # fmt: skip
            if t["label"] == "volatile":
                statement = (
                    f"{platform_label(platform)} weekly {name} is volatile (CV {t['cv']}), with no clear direction."
                )
            else:
                statement = (
                    f"{platform_label(platform)} weekly {name} shows a {t['label']} trend: "
                    f"{t['total_change_pct']:+.1f}% over {t['weeks']} weeks (Theil-Sen slope)."
                )
            findings.append(
                Finding(
                    id=f"trend:{platform}:{col}",
                    category="trend",
                    platform=platform,
                    statement=statement,
                    metric=col,
                    values=t,
                    sample_size=t["weeks"],  # data points in the trend test = weeks
                    p_value=t["p_value"] if t["label"] != "volatile" else None,
                    difference_pct=t["total_change_pct"],
                    method="Theil-Sen slope; Spearman rank test on weekly values",
                    limitations=[f"Based on {t['weeks']} complete weeks."],
                )
            )
    series = [
        {
            "week": w.date().isoformat(),
            **{k: fnum(v, 3) for k, v in row.items() if k != "complete"},
            "complete": bool(row["complete"]),
        }
        for w, row in weekly.iterrows()
    ]
    return {"weekly": series, "trends": trends}, findings
