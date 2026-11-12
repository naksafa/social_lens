"""Column profiling: infers what kind of values each raw column contains.

Profiles feed both the mapping UI (preview) and the mapper's type-compatibility check.
"""

from dataclasses import asdict, dataclass

import pandas as pd

from app.ingestion.parsers import is_null, parse_duration, parse_number


@dataclass
class ColumnProfile:
    name: str
    inferred_type: str  # number | datetime | duration | text | longtext | empty
    null_pct: float
    unique_count: int
    unique_ratio: float  # distinct non-null values / non-null values
    numeric_ratio: float
    datetime_ratio: float
    duration_ratio: float
    avg_length: float
    sample_values: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _ratio(mask: pd.Series) -> float:
    return round(float(mask.mean()), 3) if len(mask) else 0.0


def profile_column(name: str, series: pd.Series, sample_size: int = 300) -> ColumnProfile:
    non_null = series[~series.map(is_null)]
    total = len(series)
    null_pct = round(100 * (1 - len(non_null) / total), 1) if total else 100.0
    sample = non_null.head(sample_size)

    if sample.empty:
        return ColumnProfile(name, "empty", null_pct, 0, 0.0, 0.0, 0.0, 0.0, 0.0, [])

    as_text = sample.astype(str).str.strip()
    numeric_ratio = _ratio(sample.map(parse_number).notna())
    # A value is datetime-like if it parses as a date AND is not a plain small number.
    looks_numeric = sample.map(parse_number).notna()
    dt = pd.to_datetime(as_text, errors="coerce", format="mixed")
    datetime_ratio = _ratio(dt.notna() & (~looks_numeric | as_text.str.len().ge(8)))
    if pd.api.types.is_datetime64_any_dtype(series):
        datetime_ratio = 1.0
    duration_ratio = _ratio(
        as_text.str.contains(r"^\d{1,2}:\d{2}(?::\d{2})?$", regex=True) & sample.map(parse_duration).notna()
    )
    avg_length = round(float(as_text.str.len().mean()), 1)

    if datetime_ratio >= 0.8:
        inferred = "datetime"
    elif duration_ratio >= 0.8:
        inferred = "duration"
    elif numeric_ratio >= 0.8:
        inferred = "number"
    elif avg_length >= 40:
        inferred = "longtext"
    else:
        inferred = "text"

    return ColumnProfile(
        name=name,
        inferred_type=inferred,
        null_pct=null_pct,
        unique_count=(uniques := int(non_null.astype(str).nunique())),
        unique_ratio=round(uniques / len(non_null), 3),
        numeric_ratio=numeric_ratio,
        datetime_ratio=datetime_ratio,
        duration_ratio=duration_ratio,
        avg_length=avg_length,
        sample_values=[s[:120] for s in as_text.drop_duplicates().head(5).tolist()],
    )


def profile_table(df: pd.DataFrame) -> list[ColumnProfile]:
    return [profile_column(str(c), df[c]) for c in df.columns]
