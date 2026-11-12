"""Generic "compare groups of posts" logic reused by format, pillar, hook, CTA and timing analyses."""

from collections.abc import Callable

import pandas as pd

from app.analytics.common import MIN_GROUP_SIZE, disp, fnum, pct_diff, platform_label
from app.analytics.findings import Finding
from app.analytics.statistics import effect_label_eps, effect_label_r, kruskal, mann_whitney

METRIC_LABELS = {
    "exposure": "reach",  # overwritten per platform with the actual exposure metric
    "er": "engagement rate",
    "engagement_total": "engagement",
    "share_rate": "share rate",
    "save_rate": "save rate",
    "comment_rate": "comment rate",
    "click_rate": "click rate",
    "completion": "completion rate",
    "performance_index": "performance index",
    "views": "views",
}

TABLE_METRICS = ("exposure", "er", "engagement_total", "share_rate", "save_rate", "comment_rate",
                 "click_rate", "completion", "performance_index")  # fmt: skip


def metric_label(metric: str, exposure_metric: str | None = None) -> str:
    if metric == "exposure" and exposure_metric:
        return exposure_metric
    return METRIC_LABELS.get(metric, metric.replace("_", " "))


def group_table(df: pd.DataFrame, group_col: str, metrics: tuple[str, ...] = TABLE_METRICS) -> list[dict]:
    """Per-group count, share of posts, median and mean for each metric."""
    total = len(df)
    rows = []
    for level, g in df.groupby(group_col, dropna=True):
        row: dict = {"group": str(level), "count": int(len(g)), "share_pct": fnum(len(g) / total * 100, 1)}
        for m in metrics:
            if m in g and g[m].notna().any():
                row[f"median_{m}"] = fnum(g[m].median(), 3)
                row[f"mean_{m}"] = fnum(g[m].mean(), 3)
        row["low_sample"] = len(g) < MIN_GROUP_SIZE
        rows.append(row)
    rows.sort(key=lambda r: r["count"], reverse=True)
    return rows


def compare_groups(
    df: pd.DataFrame,
    group_col: str,
    metric: str,
    *,
    platform: str | None,
    category: str,
    exposure_metric: str | None = None,
    group_label: Callable[[str], str] = str,
    subject: str = "posts",
) -> list[Finding]:
    """Best-vs-worst Mann-Whitney finding + Kruskal-Wallis omnibus finding for one metric."""
    data = df[[group_col, metric]].dropna()
    groups = {str(k): g[metric] for k, g in data.groupby(group_col) if len(g) >= MIN_GROUP_SIZE}
    if len(groups) < 2:
        return []
    mlabel = metric_label(metric, exposure_metric)
    where = f" on {platform_label(platform)}" if platform else ""
    medians = {k: float(v.median()) for k, v in groups.items()}
    best = max(medians, key=medians.get)  # type: ignore[arg-type]
    worst = min(medians, key=medians.get)  # type: ignore[arg-type]
    findings: list[Finding] = []
    completeness = float(df[metric].notna().mean()) if len(df) else 0.0

    if best != worst:
        diff = pct_diff(medians[best], medians[worst])
        test = mann_whitney(groups[best], groups[worst])
        n_min = min(len(groups[best]), len(groups[worst]))
        statement = (
            f"{group_label(best)} outperform {group_label(worst)} in median {mlabel}{where} "
            f"({disp(medians[best])} vs {disp(medians[worst])}" + (f", {diff:+.1f}%" if diff is not None else "") + ")."
        )
        findings.append(
            Finding(
                id=f"{category}:{platform or 'all'}:{metric}:{best}_vs_{worst}",
                category=category,
                platform=platform,
                statement=statement,
                metric=metric,
                values={
                    "group_a": best,
                    "group_b": worst,
                    f"{best}_median": fnum(medians[best], 3),
                    f"{worst}_median": fnum(medians[worst], 3),
                    "n_a": len(groups[best]),
                    "n_b": len(groups[worst]),
                    "metric_label": mlabel,
                },
                sample_size=n_min,
                p_value=test.p_value if test else None,
                effect_size=fnum(test.rank_biserial, 3) if test else None,
                effect_size_label=effect_label_r(test.rank_biserial) if test else None,
                difference_pct=diff,
                method="Mann-Whitney U (two-sided), rank-biserial r"
                if test
                else "median comparison (groups too small for a test)",
                completeness=completeness,
                limitations=[] if test else [f"fewer than 8 {subject} in a group; no significance test"],
            )
        )

    omnibus = kruskal(groups)
    if omnibus is not None:
        findings.append(
            Finding(
                id=f"{category}:{platform or 'all'}:{metric}:omnibus",
                category=category,
                platform=platform,
                statement=(
                    f"Median {mlabel} differs across {omnibus.k} {category} groups{where} "
                    f"(Kruskal-Wallis H={omnibus.h_stat:.1f})."
                ),
                metric=metric,
                values={"groups": {k: fnum(v, 3) for k, v in medians.items()}, "h_stat": fnum(omnibus.h_stat, 2)},
                sample_size=min(len(v) for v in groups.values()),
                p_value=omnibus.p_value,
                effect_size=fnum(omnibus.epsilon_squared, 3),
                effect_size_label=effect_label_eps(omnibus.epsilon_squared),
                method="Kruskal-Wallis H, epsilon-squared",
                completeness=completeness,
            )
        )
    return findings
