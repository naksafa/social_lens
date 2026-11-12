"""Confidence system.

Every finding is graded high / medium / low from explicit, documented criteria so
that the AI layer (and the user) can tell strong evidence from weak signals:

1. Sample size sets a ceiling: n >= 30 -> high, 10-29 -> medium, 5-9 -> low.
   (n is the size of the *smallest* group being compared.)
2. Statistical significance (BH-adjusted p): p >= 0.20 caps at low; 0.05 <= p < 0.20
   downgrades one level.
3. Effect size: a negligible effect (|r| < 0.1, or |difference| < 10%) downgrades one level.
4. Data completeness: < 70% non-missing values for the metric downgrades one level.
"""

from dataclasses import dataclass, field

from app.core.enums import Confidence

_ORDER = [Confidence.LOW, Confidence.MEDIUM, Confidence.HIGH]


@dataclass
class ConfidenceAssessment:
    level: Confidence
    reasons: list[str] = field(default_factory=list)


def _downgrade(level: Confidence) -> Confidence:
    return _ORDER[max(0, _ORDER.index(level) - 1)]


def assess_confidence(
    n: int,
    *,
    p_value: float | None = None,
    effect_size: float | None = None,
    difference_pct: float | None = None,
    completeness: float = 1.0,
) -> ConfidenceAssessment:
    reasons: list[str] = []
    if n >= 30:
        level = Confidence.HIGH
    elif n >= 10:
        level = Confidence.MEDIUM
        reasons.append(f"moderate sample size (n={n})")
    else:
        level = Confidence.LOW
        reasons.append(f"small sample size (n={n})")

    if p_value is not None:
        if p_value >= 0.20:
            level = Confidence.LOW
            reasons.append(f"not statistically significant (adjusted p={p_value:.2f})")
        elif p_value >= 0.05:
            level = _downgrade(level)
            reasons.append(f"weak statistical evidence (adjusted p={p_value:.2f})")

    negligible = (effect_size is not None and abs(effect_size) < 0.1) or (
        difference_pct is not None and abs(difference_pct) < 10
    )
    if negligible:
        level = _downgrade(level)
        reasons.append("small effect size")

    if completeness < 0.7:
        level = _downgrade(level)
        reasons.append(f"incomplete data ({completeness:.0%} of values present)")

    return ConfidenceAssessment(level, reasons)


def sample_confidence(n: int) -> Confidence:
    """Confidence for purely descriptive statistics (no comparison)."""
    return assess_confidence(n).level
