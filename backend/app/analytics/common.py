"""Shared analytics constants and small numeric helpers."""

import numpy as np
import pandas as pd

from app.core.enums import Platform

#: Minimum posts in a group before its statistics are reported at all.
MIN_GROUP_SIZE = 5
#: Minimum posts per group before a hypothesis test is run.
MIN_TEST_GROUP_SIZE = 8
#: Significance level applied to Benjamini-Hochberg adjusted p-values.
ALPHA = 0.05
#: Posts with exposure below this platform percentile are excluded from *rate* rankings,
#: so a post with 40 views and 10 likes is not crowned "best engagement rate".
RATE_RANKING_MIN_PERCENTILE = 0.25
RATE_RANKING_MIN_EXPOSURE = 100

ENGAGEMENT_COMPONENTS = ("likes", "comments", "shares", "saves")

#: Which metric represents "exposure" per platform, in order of preference. Platforms
#: count exposure differently (unique reach vs. plays vs. impressions); the chosen
#: metric is recorded with every result that uses it.
EXPOSURE_PRIORITY: dict[str, tuple[str, ...]] = {
    Platform.INSTAGRAM.value: ("reach", "impressions", "views"),
    Platform.FACEBOOK.value: ("reach", "impressions", "views"),
    Platform.TIKTOK.value: ("views", "reach", "impressions"),
    Platform.LINKEDIN.value: ("impressions", "reach", "views"),
}

PLATFORM_LABELS = {
    "instagram": "Instagram",
    "facebook": "Facebook",
    "tiktok": "TikTok",
    "linkedin": "LinkedIn",
}

FORMAT_LABELS = {
    "reel": "Reels",
    "carousel": "Carousels",
    "image": "Images",
    "video": "Videos",
    "short_video": "Short videos",
    "text": "Text posts",
    "link": "Link posts",
    "document": "Documents",
    "story": "Stories",
    "other": "Other",
}


def safe_div(num: pd.Series | float, den: pd.Series | float, scale: float = 1.0) -> pd.Series | float:
    """Division that yields NaN (never inf / ZeroDivisionError) when the denominator is 0 or missing."""
    if isinstance(num, pd.Series) or isinstance(den, pd.Series):
        den_s = den if isinstance(den, pd.Series) else pd.Series(den, index=num.index)  # type: ignore[union-attr]
        den_s = den_s.where(den_s > 0)
        return num / den_s * scale
    if den is None or not np.isfinite(den) or den <= 0 or num is None or not np.isfinite(num):
        return float("nan")
    return num / den * scale


def pct_diff(a: float, b: float) -> float | None:
    """Percentage difference of a relative to b; None when b is 0/NaN."""
    if b is None or a is None or not np.isfinite(a) or not np.isfinite(b) or b == 0:
        return None
    return round((a - b) / abs(b) * 100, 1)


def fnum(value: float | None, ndigits: int = 2) -> float | None:
    """Round and convert NaN -> None for JSON output."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(f) else round(f, ndigits)


def disp(value: float | None) -> str:
    """Human-readable number for finding statements: 1,745 / 12.5 / 0.83."""
    if value is None:
        return "n/a"
    v = float(value)
    if not np.isfinite(v):
        return "n/a"
    if abs(v) >= 100:
        return f"{v:,.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}".rstrip("0").rstrip(".")
    return f"{v:.2f}".rstrip("0").rstrip(".")


def platform_label(platform: str | None) -> str:
    return PLATFORM_LABELS.get(platform or "", platform or "All platforms")


def format_label(fmt: str) -> str:
    return FORMAT_LABELS.get(fmt, fmt.replace("_", " ").title())


def label(text: str) -> str:
    return text.replace("_", " ").title()
