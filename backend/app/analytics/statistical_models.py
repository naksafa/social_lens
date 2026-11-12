"""Correlations and multivariate regression per platform."""

import pandas as pd

from app.analytics.common import ALPHA, fnum, platform_label
from app.analytics.findings import Finding
from app.analytics.statistics import ols_log_target, spearman

CORRELATIONS = [
    ("caption_length", "er", "caption length", "engagement rate"),
    ("hashtag_count", "exposure", "hashtag count", "reach"),
    ("hashtag_count", "er", "hashtag count", "engagement rate"),
    ("hour", "er", "posting hour", "engagement rate"),
]


def analyze_statistics(g: pd.DataFrame, platform: str, exposure_metric: str | None) -> tuple[dict, list[Finding]]:
    out: dict = {"correlations": [], "regression": None}
    findings: list[Finding] = []
    for x, y, xl, yl in CORRELATIONS:
        if x == "hour" and not g["has_time"].all():
            continue
        yl = exposure_metric if y == "exposure" and exposure_metric else yl
        corr = spearman(g[x].astype(float), g[y])
        if corr is None:
            continue
        out["correlations"].append(
            {"x": x, "y": y, "rho": fnum(corr.rho, 3), "p_value": fnum(corr.p_value, 4), "n": corr.n}
        )
        findings.append(
            Finding(
                id=f"correlation:{platform}:{x}_vs_{y}",
                category="correlation",
                platform=platform,
                statement=(
                    f"On {platform_label(platform)}, {xl} and {yl} have a Spearman correlation of "
                    f"{corr.rho:+.2f} (n={corr.n})."
                ),
                metric=y,
                values={"x": x, "y": y, "rho": fnum(corr.rho, 3)},
                sample_size=corr.n,
                p_value=corr.p_value,
                effect_size=fnum(corr.rho, 3),
                method="Spearman rank correlation",
                limitations=["Correlation does not imply causation."],
            )
        )

    reg = ols_log_target(
        g.assign(weekend=g["is_weekend"].map({True: "weekend", False: "weekday"})),
        "exposure",
        ["content_format", "content_pillar", "hook_type", "weekend"],
        min_n=40,
    )
    if reg:
        out["regression"] = {
            "model": f"log(1 + {exposure_metric or 'exposure'}) ~ format + pillar + hook + weekend",
            "n": reg.n,
            "r_squared": fnum(reg.r_squared, 3),
            "adj_r_squared": fnum(reg.adj_r_squared, 3),
            "baselines": reg.baselines,
            "terms": [
                {
                    "term": t.term,
                    "coef": fnum(t.coef, 4),
                    "pct_effect": fnum(t.pct_effect, 1),
                    "std_err": fnum(t.std_err, 4),
                    "p_value": fnum(t.p_value, 4),
                }
                for t in reg.terms
            ],  # fmt: skip
            "interpretation": (
                "pct_effect = expected % change in exposure vs. the baseline level, holding the other "
                "variables constant. Classical OLS standard errors."
            ),
        }
        for t in reg.terms:
            if t.p_value < ALPHA * 2 and abs(t.pct_effect) >= 15:
                var, _, level = t.term.partition("=")
                base = reg.baselines.get(var, "baseline")
                findings.append(
                    Finding(
                        id=f"regression:{platform}:{t.term}",
                        category="regression",
                        platform=platform,
                        statement=(
                            f"Controlling for format, pillar, hook and weekend, {platform_label(platform)} posts with "
                            f"{var.replace('content_', '').replace('_', ' ')} '{level.replace('_', ' ')}' have {t.pct_effect:+.0f}% expected "
                            f"{exposure_metric or 'exposure'} vs. '{base.replace('_', ' ')}'."
                        ),
                        metric="exposure",
                        values={
                            "term": t.term,
                            "pct_effect": fnum(t.pct_effect, 1),
                            "baseline": base,
                            "r_squared": fnum(reg.r_squared, 3),
                        },
                        sample_size=reg.n,
                        p_value=t.p_value,
                        difference_pct=fnum(t.pct_effect, 1),
                        method="OLS on log exposure with categorical dummies",
                        limitations=[f"Model explains {reg.r_squared:.0%} of variance (R²)."],
                    )
                )
    return out, findings
