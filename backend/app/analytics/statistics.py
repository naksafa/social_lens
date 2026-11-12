"""Statistical methods used across the analytics engine.

Choice of methods: social metrics are heavily right-skewed with outliers (viral
posts), so the engine relies on *non-parametric* rank-based tests and medians:

* Mann-Whitney U for two groups, with rank-biserial correlation as effect size
  (r = 1 - 2U/(n1*n2); |r| ~ 0.1 small, 0.3 medium, 0.5 large).
* Kruskal-Wallis H for 3+ groups, with epsilon-squared effect size
  (e2 = H / (n - 1); ~0.01 small, 0.08 medium, 0.26 large).
* Spearman rank correlation for monotone relationships.
* OLS on log(exposure) with categorical dummies for a multivariate view
  (coefficients read as % effects: exp(b) - 1), reported with p-values and R^2.

Tests are skipped when groups are smaller than MIN_TEST_GROUP_SIZE.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from app.analytics.common import MIN_TEST_GROUP_SIZE


@dataclass
class TwoGroupResult:
    n_a: int
    n_b: int
    median_a: float
    median_b: float
    u_stat: float
    p_value: float
    rank_biserial: float


@dataclass
class MultiGroupResult:
    h_stat: float
    p_value: float
    epsilon_squared: float
    n: int
    k: int


def effect_label_r(r: float) -> str:
    a = abs(r)
    return "large" if a >= 0.5 else "medium" if a >= 0.3 else "small" if a >= 0.1 else "negligible"


def effect_label_eps(e: float) -> str:
    return "large" if e >= 0.26 else "medium" if e >= 0.08 else "small" if e >= 0.01 else "negligible"


def mann_whitney(a: pd.Series, b: pd.Series) -> TwoGroupResult | None:
    a, b = a.dropna(), b.dropna()
    if len(a) < MIN_TEST_GROUP_SIZE or len(b) < MIN_TEST_GROUP_SIZE:
        return None
    if a.nunique() == 1 and b.nunique() == 1 and a.iloc[0] == b.iloc[0]:
        return None
    u, p = stats.mannwhitneyu(a, b, alternative="two-sided")
    r = 1 - 2 * u / (len(a) * len(b))
    # r > 0 means group a tends to be larger (sign convention aligned with medians).
    return TwoGroupResult(len(a), len(b), float(a.median()), float(b.median()), float(u), float(p), float(-r))


def kruskal(groups: dict[str, pd.Series]) -> MultiGroupResult | None:
    valid = {k: v.dropna() for k, v in groups.items() if v.dropna().size >= MIN_TEST_GROUP_SIZE}
    if len(valid) < 3:
        return None
    values = list(valid.values())
    if len({float(x) for s in values for x in s}) < 2:
        return None
    h, p = stats.kruskal(*values)
    n = sum(len(v) for v in values)
    eps = float(h) / (n - 1) if n > 1 else 0.0
    return MultiGroupResult(float(h), float(p), eps, n, len(valid))


@dataclass
class CorrelationResult:
    rho: float
    p_value: float
    n: int


def spearman(x: pd.Series, y: pd.Series, min_n: int = 15) -> CorrelationResult | None:
    mask = x.notna() & y.notna()
    if mask.sum() < min_n or x[mask].nunique() < 3 or y[mask].nunique() < 3:
        return None
    rho, p = stats.spearmanr(x[mask], y[mask])
    if not np.isfinite(rho):
        return None
    return CorrelationResult(float(rho), float(p), int(mask.sum()))


@dataclass
class OLSTerm:
    term: str
    coef: float
    pct_effect: float
    std_err: float
    p_value: float


@dataclass
class OLSResult:
    target: str
    n: int
    r_squared: float
    adj_r_squared: float
    terms: list[OLSTerm]
    baselines: dict[str, str]


def ols_log_target(
    df: pd.DataFrame,
    target: str,
    categoricals: list[str],
    numerics: list[str] | None = None,
    min_n: int = 30,
    min_level_size: int = 5,
) -> OLSResult | None:
    """OLS of log1p(target) on one-hot categoricals (+ optional numerics).

    Rare levels (< min_level_size posts) are merged into their variable's baseline to
    avoid unstable coefficients. Standard errors are classical (homoskedastic).
    """
    numerics = numerics or []
    cols = [target, *categoricals, *numerics]
    data = df[cols].dropna(subset=[target]).copy()
    data = data[data[target] >= 0]
    if len(data) < min_n:
        return None

    X_parts = [pd.Series(1.0, index=data.index, name="intercept")]
    baselines: dict[str, str] = {}
    for cat in categoricals:
        s = data[cat].fillna("unknown").astype(str)
        counts = s.value_counts()
        frequent = counts[counts >= min_level_size]
        if len(frequent) < 2:
            continue
        baseline = str(frequent.index[0])  # most common level is the reference
        baselines[cat] = baseline
        for level in frequent.index[1:]:
            X_parts.append((s == level).astype(float).rename(f"{cat}={level}"))
    for num in numerics:
        v = data[num].astype(float)
        if v.notna().all() and v.nunique() > 2:
            X_parts.append(((v - v.mean()) / (v.std() or 1)).rename(f"{num} (per SD)"))
    X = pd.concat(X_parts, axis=1)
    y = np.log1p(data[target].astype(float).to_numpy())
    n, k = X.shape
    if n <= k + 5:
        return None

    Xv = X.to_numpy()
    beta, *_ = np.linalg.lstsq(Xv, y, rcond=None)
    resid = y - Xv @ beta
    ss_res = float(resid @ resid)
    ss_tot = float(((y - y.mean()) ** 2).sum())
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0.0
    adj_r2 = 1 - (1 - r2) * (n - 1) / (n - k)
    sigma2 = ss_res / (n - k)
    try:
        cov = sigma2 * np.linalg.inv(Xv.T @ Xv)
    except np.linalg.LinAlgError:
        return None
    se = np.sqrt(np.clip(np.diag(cov), 0, None))
    t = np.divide(beta, se, out=np.zeros_like(beta), where=se > 0)
    p = 2 * stats.t.sf(np.abs(t), df=n - k)

    terms = [
        OLSTerm(name, float(b), float(np.expm1(b) * 100), float(s), float(pv))
        for name, b, s, pv in zip(X.columns, beta, se, p, strict=True)
        if name != "intercept"
    ]
    return OLSResult(target, n, float(r2), float(adj_r2), terms, baselines)


def iqr_bounds(s: pd.Series, k: float = 1.5) -> tuple[float, float] | None:
    s = s.dropna()
    if len(s) < 8:
        return None
    q1, q3 = s.quantile([0.25, 0.75])
    iqr = q3 - q1
    return float(q1 - k * iqr), float(q3 + k * iqr)


def robust_z(s: pd.Series) -> pd.Series:
    """Robust z-score using median and MAD (scaled to be comparable to a standard z)."""
    med = s.median()
    mad = (s - med).abs().median()
    if not mad or not np.isfinite(mad):
        return pd.Series(0.0, index=s.index)
    return 0.6745 * (s - med) / mad
