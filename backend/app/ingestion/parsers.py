"""Robust value parsers for messy export data (localized numbers, 1.2K, 0:45, 12%...)."""

import re
from collections.abc import Iterable

import numpy as np
import pandas as pd

NULL_TOKENS = frozenset({"", "-", "--", "n/a", "na", "nan", "none", "null", "—", "–", "#n/a"})
_SUFFIX = {"k": 1e3, "m": 1e6, "b": 1e9}
_NUM_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")
_HASHTAG_RE = re.compile(r"#(\w+)", re.UNICODE)


def is_null(value: object) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and np.isnan(value):
        return True
    return isinstance(value, str) and value.strip().lower() in NULL_TOKENS


def parse_number(value: object) -> float | None:
    """Parse '1,234', '1 234', '1.234,5', '1.2K', '(12)', '12%' -> float. Returns None if unparsable."""
    if is_null(value):
        return None
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int | float | np.integer | np.floating):
        return float(value)
    text = str(value).strip().lower().replace(" ", "").replace(" ", "")
    negative = text.startswith("(") and text.endswith(")")
    text = text.strip("()").rstrip("%").lstrip("$€£")
    multiplier = 1.0
    if text and text[-1] in _SUFFIX:
        multiplier = _SUFFIX[text[-1]]
        text = text[:-1]
    if "," in text and "." in text:
        # Whichever separator comes last is the decimal separator.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        head, _, tail = text.rpartition(",")
        # "1,234" / "12,345,678" -> thousands; "12,5" -> decimal.
        text = text.replace(",", "") if len(tail) == 3 and head else text.replace(",", ".")
    if not _NUM_RE.match(text):
        return None
    number = float(text) * multiplier
    return -number if negative else number


def parse_duration(value: object) -> float | None:
    """Parse '0:45', '1:02:03', '45s', '1m 5s', '2.5' (seconds) -> seconds."""
    if is_null(value):
        return None
    if isinstance(value, int | float | np.integer | np.floating):
        return float(value)
    if isinstance(value, pd.Timedelta):
        return value.total_seconds()
    text = str(value).strip().lower()
    if ":" in text:
        parts = text.split(":")
        try:
            nums = [float(p) for p in parts]
        except ValueError:
            return None
        seconds = 0.0
        for n in nums:
            seconds = seconds * 60 + n
        return seconds
    match = re.fullmatch(
        r"(?:(\d+(?:\.\d+)?)\s*h)?\s*(?:(\d+(?:\.\d+)?)\s*m(?:in)?)?\s*(?:(\d+(?:\.\d+)?)\s*s(?:ec)?)?", text
    )
    if match and any(match.groups()):
        h, m, s = (float(g) if g else 0.0 for g in match.groups())
        return h * 3600 + m * 60 + s
    return parse_number(text)


def duration_unit_factor(header: str) -> float:
    """Infer the unit of a duration column from its header ('Total play time (h)')."""
    h = header.lower()
    if re.search(r"\((h|hr|hrs|hours?)\)|\bhours\b", h):
        return 3600.0
    if re.search(r"\((m|min|mins|minutes?)\)|\bminutes\b", h):
        return 60.0
    if re.search(r"\(ms\)|millisecond", h):
        return 0.001
    return 1.0


_DOT_THOUSANDS = re.compile(r"^-?\d{1,3}(?:\.\d{3})+$")


def uses_dot_thousands(series: pd.Series) -> bool:
    """Column-level locale check: True when every dotted value looks like '4.210' / '1.234.567'.

    A single '4.210' is ambiguous, but a count column where *all* dotted values have
    exactly three-digit groups is almost certainly an EU-formatted integer column.
    """
    text = series[~series.map(is_null)].astype(str).str.strip()
    dotted = text[text.str.contains(".", regex=False)]
    if len(dotted) < 2 or text.str.contains(",", regex=False).any():
        return False
    return bool(dotted.str.match(_DOT_THOUSANDS).all())


def parse_numeric_series(series: pd.Series, kind: str = "number") -> tuple[pd.Series, int]:
    """Parse a raw series. Returns (float series, number of non-null raw values that failed).

    ``kind`` is "number" (counts), "percent" or "duration".
    """
    parser = parse_duration if kind == "duration" else parse_number
    raw_nonnull = ~series.map(is_null)
    if kind == "number" and series.dtype == object and uses_dot_thousands(series):
        series = series.map(lambda v: v.replace(".", "") if isinstance(v, str) else v)
    parsed = series.map(parser).astype("float64")
    failures = int((raw_nonnull & parsed.isna()).sum())
    return parsed, failures


def normalize_percent(series: pd.Series) -> pd.Series:
    """Express percentages on a 0-100 scale; a column entirely within [0, 1] is treated as fractions."""
    valid = series.dropna()
    if len(valid) and valid.between(0, 1).all() and valid.max() > 0:
        return series * 100
    return series


def guess_dayfirst(values: Iterable[str]) -> bool:
    """True when some value's first numeric component > 12 (e.g. 25/03/2024)."""
    first_gt_12 = second_gt_12 = 0
    for v in values:
        m = re.match(r"^\s*(\d{1,2})[/.-](\d{1,2})[/.-]\d{2,4}", str(v))
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            first_gt_12 += a > 12
            second_gt_12 += b > 12
    return first_gt_12 > second_gt_12


def parse_datetime_series(series: pd.Series, timezone: str = "UTC") -> tuple[pd.Series, bool]:
    """Parse to tz-aware UTC timestamps. Naive values are interpreted in ``timezone``.

    Returns (series, has_time) where has_time is False when every value is at midnight
    (i.e. the export only provided dates, so hour-of-day analysis must be skipped).
    """
    s = series.copy()
    numeric = pd.to_numeric(s, errors="coerce")
    # Excel serial dates (e.g. 45123.5) when the column is mostly numeric in a plausible range.
    if numeric.notna().mean() > 0.8 and numeric.dropna().between(20000, 80000).all():
        parsed = pd.to_datetime(numeric, unit="D", origin="1899-12-30", errors="coerce")
    elif pd.api.types.is_datetime64_any_dtype(s):
        parsed = pd.to_datetime(s, errors="coerce")
    else:
        text = s.astype("string").str.strip()
        dayfirst = guess_dayfirst(text.dropna().head(200))
        # Explicit offsets ("...+04:00", "...Z") are honoured by parsing to UTC directly.
        has_offset = bool(text.str.contains(r"(?:Z|[+-]\d{2}:?\d{2})$", regex=True).any())
        parsed = pd.to_datetime(text, errors="coerce", format="mixed", dayfirst=dayfirst, utc=has_offset)

    if getattr(parsed.dt, "tz", None) is None:
        parsed = parsed.dt.tz_localize(timezone, ambiguous="NaT", nonexistent="shift_forward")
    parsed = parsed.dt.tz_convert("UTC")

    local = parsed.dt.tz_convert(timezone).dropna()
    has_time = bool(len(local)) and not ((local.dt.hour == 0) & (local.dt.minute == 0) & (local.dt.second == 0)).all()
    return parsed, has_time


def extract_hashtags(text: object) -> list[str]:
    if is_null(text):
        return []
    return list(dict.fromkeys(tag.lower() for tag in _HASHTAG_RE.findall(str(text))))


def split_hashtags(value: object) -> list[str]:
    if is_null(value):
        return []
    parts = re.split(r"[\s,;]+", str(value))
    return list(dict.fromkeys(p.lstrip("#").lower() for p in parts if p.strip("#")))
