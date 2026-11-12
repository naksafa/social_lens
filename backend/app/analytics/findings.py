"""Statistical finding objects and the collector that finalizes them.

Findings are produced by the analysis modules with raw p-values. ``FindingCollector``
then applies Benjamini-Hochberg correction across *all* tests of the run (many
comparisons are made: formats x pillars x days x platforms) and assigns confidence
from the adjusted p-value, sample size, effect size and completeness.
"""

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np

from app.analytics.confidence import assess_confidence


@dataclass
class Finding:
    id: str
    category: str  # format | pillar | timing | trend | correlation | regression | video | ...
    platform: str | None
    statement: str
    metric: str
    values: dict[str, Any] = field(default_factory=dict)
    sample_size: int = 0
    p_value: float | None = None
    p_adjusted: float | None = None
    effect_size: float | None = None
    effect_size_label: str | None = None
    difference_pct: float | None = None
    method: str = "descriptive"
    completeness: float = 1.0
    confidence: str = "low"
    confidence_reasons: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=list)
    significant: bool | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def benjamini_hochberg(p_values: list[float]) -> list[float]:
    """Benjamini-Hochberg FDR-adjusted p-values (monotone, capped at 1)."""
    p = np.asarray(p_values, dtype=float)
    n = len(p)
    if n == 0:
        return []
    order = np.argsort(p)
    ranked = p[order] * n / (np.arange(n) + 1)
    adjusted = np.minimum.accumulate(ranked[::-1])[::-1]
    out = np.empty(n)
    out[order] = np.minimum(adjusted, 1.0)
    return out.tolist()


class FindingCollector:
    def __init__(self) -> None:
        self.findings: list[Finding] = []

    def add(self, finding: Finding | None) -> None:
        if finding is not None:
            self.findings.append(finding)

    def extend(self, findings: list[Finding]) -> None:
        self.findings.extend(findings)

    def finalize(self, alpha: float = 0.05) -> list[Finding]:
        tested = [f for f in self.findings if f.p_value is not None]
        for f, adj in zip(tested, benjamini_hochberg([f.p_value for f in tested]), strict=True):  # type: ignore[misc]
            f.p_adjusted = round(adj, 4)
            f.significant = adj < alpha
        for f in self.findings:
            if f.p_value is not None:
                f.p_value = round(f.p_value, 4)
            assessment = assess_confidence(
                f.sample_size,
                p_value=f.p_adjusted,
                effect_size=f.effect_size,
                difference_pct=f.difference_pct,
                completeness=f.completeness,
            )
            f.confidence = assessment.level.value
            f.confidence_reasons = assessment.reasons
        # Most reliable and largest effects first.
        rank = {"high": 0, "medium": 1, "low": 2}
        self.findings.sort(key=lambda f: (rank[f.confidence], -(abs(f.difference_pct or 0))))
        return self.findings
