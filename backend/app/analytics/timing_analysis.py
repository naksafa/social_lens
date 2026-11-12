"""Day-of-week / hour-of-day / weekday-vs-weekend performance.

Results describe *this dataset only* ("within this dataset, posts published on
Tuesday evenings achieved higher median engagement") - never universal best times.
Groups with fewer than MIN_GROUP_SIZE posts are flagged low-sample and excluded from
best/worst claims. Hour analysis is skipped when the export only had dates.
"""

import pandas as pd

from app.analytics.common import MIN_GROUP_SIZE, disp, fnum, pct_diff, platform_label
from app.analytics.findings import Finding
from app.analytics.grouping import group_table, metric_label
from app.analytics.statistics import mann_whitney

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
HOUR_BLOCKS = [("night", 0, 5), ("morning", 5, 11), ("midday", 11, 14), ("afternoon", 14, 17),
               ("evening", 17, 21), ("late_evening", 21, 24)]  # fmt: skip


def hour_block(hour: int) -> str:
    return next(name for name, lo, hi in HOUR_BLOCKS if lo <= hour < hi)


def _best_vs_rest(g: pd.DataFrame, col: str, metric: str, platform: str, exposure_metric: str | None,
                  describe: str) -> Finding | None:  # fmt: skip
    data = g[[col, metric]].dropna()
    sizes = data[col].value_counts()
    eligible = sizes[sizes >= MIN_GROUP_SIZE].index
    if len(eligible) < 2:
        return None
    medians = data[data[col].isin(eligible)].groupby(col)[metric].median()
    best = medians.idxmax()
    best_vals = data.loc[data[col] == best, metric]
    rest_vals = data.loc[data[col] != best, metric]
    test = mann_whitney(best_vals, rest_vals)
    diff = pct_diff(float(best_vals.median()), float(rest_vals.median()))
    mlabel = metric_label(metric, exposure_metric)
    name = describe.format(best=DAY_NAMES[int(best)] + "s" if col == "dow" else str(best).replace("_", " "))
    return Finding(
        id=f"timing:{platform}:{col}:{metric}",
        category="timing",
        platform=platform,
        statement=(
            f"Within this dataset, {platform_label(platform)} posts published {name} achieved a higher median "
            f"{mlabel} ({disp(best_vals.median())}) than other posts ({disp(rest_vals.median())}"
            + (f", {diff:+.1f}%" if diff is not None else "")
            + ")."
        ),
        metric=metric,
        values={
            "best": str(best) if col != "dow" else DAY_NAMES[int(best)],
            "best_median": fnum(best_vals.median(), 3),
            "rest_median": fnum(rest_vals.median(), 3),
            "n_best": int(len(best_vals)),
            "n_rest": int(len(rest_vals)),
        },
        sample_size=int(len(best_vals)),
        p_value=test.p_value if test else None,
        effect_size=fnum(test.rank_biserial, 3) if test else None,
        difference_pct=diff,
        method="Mann-Whitney U (best group vs. all other posts)" if test else "median comparison",
        limitations=["Timing effects are correlational; content type and audience seasonality also vary by day."],
    )


def analyze_timing(g: pd.DataFrame, platform: str, exposure_metric: str | None) -> tuple[dict, list[Finding]]:
    has_time = bool(g["has_time"].all())
    days = group_table(g.assign(day=g["dow"].map(lambda d: DAY_NAMES[int(d)])), "day")
    order = {d: i for i, d in enumerate(DAY_NAMES)}
    days.sort(key=lambda r: order[r["group"]])
    out: dict = {
        "has_time": has_time,
        "by_day": days,
        "weekday_vs_weekend": group_table(
            g.assign(part=g["is_weekend"].map({True: "weekend", False: "weekday"})), "part"
        ),
        "by_hour_block": [],
        "posting_hours": {},
    }
    findings: list[Finding] = []
    for metric in ("er", "exposure"):
        f = _best_vs_rest(g, "dow", metric, platform, exposure_metric, "on {best}")
        if f:
            findings.append(f)
    if has_time:
        blocks = g.assign(block=g["hour"].map(hour_block))
        block_order = {b[0]: i for i, b in enumerate(HOUR_BLOCKS)}
        out["by_hour_block"] = sorted(group_table(blocks, "block"), key=lambda r: block_order[r["group"]])
        out["posting_hours"] = {int(h): int(c) for h, c in g["hour"].value_counts().sort_index().items()}
        for metric in ("er", "exposure"):
            f = _best_vs_rest(blocks, "block", metric, platform, exposure_metric, "in the {best}")
            if f:
                findings.append(f)
    else:
        out["note"] = "Export contains dates without times; hour-of-day analysis skipped."
    return out, findings
