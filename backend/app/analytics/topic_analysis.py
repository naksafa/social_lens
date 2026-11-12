"""Content pillar / topic mix, hooks and CTA usage."""

import numpy as np
import pandas as pd

from app.analytics.common import disp, fnum, label, platform_label
from app.analytics.findings import Finding
from app.analytics.grouping import compare_groups, group_table
from app.analytics.statistics import mann_whitney


def distribution(s: pd.Series) -> dict[str, float]:
    counts = s.fillna("other").value_counts()
    return {str(k): fnum(v / counts.sum() * 100, 1) for k, v in counts.items()}  # type: ignore[misc]


def diversity_score(s: pd.Series) -> float | None:
    """Normalized Shannon entropy in [0, 100]: 0 = one category only, 100 = perfectly even."""
    counts = s.dropna().value_counts()
    if len(counts) <= 1:
        return 0.0 if len(counts) == 1 else None
    p = counts / counts.sum()
    return fnum(float(-(p * np.log(p)).sum() / np.log(len(p)) * 100), 1)


def analyze_pillars(g: pd.DataFrame, platform: str | None, exposure_metric: str | None) -> tuple[dict, list[Finding]]:
    out = {
        "pillar_distribution": distribution(g["content_pillar"]),
        "topic_distribution": distribution(g["content_topic"]),
        "pillars": group_table(g, "content_pillar"),
        "topics": group_table(g, "content_topic"),
        "pillar_diversity": diversity_score(g["content_pillar"]),
        "format_diversity": diversity_score(g["content_format"]),
        "classification": {
            "source_counts": g["topic_source"].fillna("keyword").value_counts().to_dict()
            if "topic_source" in g
            else {},
            "low_confidence_share": fnum(
                (pd.to_numeric(g["topic_confidence"], errors="coerce").fillna(0) < 0.5).mean() * 100, 1
            ),
        },
    }
    findings: list[Finding] = []
    for metric in ("er", "exposure", "save_rate", "share_rate", "click_rate"):
        if metric in g and g[metric].notna().sum() >= 10:
            findings += compare_groups(
                g, "content_pillar", metric,
                platform=platform, category="pillar", exposure_metric=exposure_metric,
                group_label=lambda x: f"{label(x)} posts",
            )  # fmt: skip
    return out, findings


def analyze_hooks_and_ctas(g: pd.DataFrame, platform: str, exposure_metric: str | None) -> tuple[dict, list[Finding]]:
    has_cta = g["has_cta"].astype(bool)
    out = {
        "cta_usage_pct": fnum(has_cta.mean() * 100, 1),
        "cta_distribution": distribution(g["cta_type"]),
        "hook_distribution": distribution(g["hook_type"]),
        "hooks": group_table(g, "hook_type"),
        "ctas": group_table(g.assign(cta_present=np.where(has_cta, "with_cta", "no_cta")), "cta_present"),
    }
    findings: list[Finding] = []
    # Posts opening with a recognizable hook vs. no hook
    hooked = g.assign(has_hook=np.where(g["hook_type"].fillna("none") != "none", "with_hook", "no_hook"))
    for metric in ("exposure", "er"):
        test = mann_whitney(
            hooked.loc[hooked.has_hook == "with_hook", metric], hooked.loc[hooked.has_hook == "no_hook", metric]
        )
        if test:
            diff = (test.median_a - test.median_b) / test.median_b * 100 if test.median_b else None
            findings.append(
                Finding(
                    id=f"hook:{platform}:{metric}",
                    category="hook",
                    platform=platform,
                    statement=(
                        f"{platform_label(platform)} posts opening with a hook (question, number, POV, how-to, "
                        f"bold claim) have a median "
                        f"{(exposure_metric or 'reach') if metric == 'exposure' else 'engagement rate'} of {disp(test.median_a)} vs "
                        f"{disp(test.median_b)} without one."
                    ),
                    metric=metric,
                    values={
                        "with_hook_median": fnum(test.median_a, 3),
                        "no_hook_median": fnum(test.median_b, 3),
                        "n_with": test.n_a,
                        "n_without": test.n_b,
                    },
                    sample_size=min(test.n_a, test.n_b),
                    p_value=test.p_value,
                    effect_size=fnum(test.rank_biserial, 3),
                    difference_pct=fnum(diff, 1),
                    method="Mann-Whitney U, rank-biserial r",
                )
            )
    if g["click_rate"].notna().sum() >= 10:
        test = mann_whitney(g.loc[has_cta, "click_rate"], g.loc[~has_cta, "click_rate"])
        if test:
            diff = (test.median_a - test.median_b) / test.median_b * 100 if test.median_b else None
            findings.append(
                Finding(
                    id=f"cta:{platform}:click_rate",
                    category="cta",
                    platform=platform,
                    statement=(
                        f"{platform_label(platform)} posts with an explicit call-to-action have a median click "
                        f"rate of {fnum(test.median_a, 3)}% "
                        f"vs {fnum(test.median_b, 3)}% without."
                    ),
                    metric="click_rate",
                    values={
                        "with_cta_median": fnum(test.median_a, 4),
                        "no_cta_median": fnum(test.median_b, 4),
                        "n_with": test.n_a,
                        "n_without": test.n_b,
                    },
                    sample_size=min(test.n_a, test.n_b),
                    p_value=test.p_value,
                    effect_size=fnum(test.rank_biserial, 3),
                    difference_pct=fnum(diff, 1),
                    method="Mann-Whitney U, rank-biserial r",
                )
            )
    return out, findings
