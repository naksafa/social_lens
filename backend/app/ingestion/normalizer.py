"""Apply a confirmed column mapping to a raw table and produce canonical posts.

Output is a DataFrame whose columns are canonical ``SocialPost`` fields, plus a
DataFrame of account-level daily snapshots (followers) and a ValidationReport.
"""

import hashlib
import re
from dataclasses import dataclass

import numpy as np
import pandas as pd

from app.core.enums import ContentPillar, ContentTopic, CTAType, Platform
from app.ingestion.adapters.platforms import get_adapter
from app.ingestion.canonical import canonical_fields
from app.ingestion.parsers import (
    duration_unit_factor,
    extract_hashtags,
    is_null,
    normalize_percent,
    parse_datetime_series,
    parse_numeric_series,
    split_hashtags,
)
from app.ingestion.validation import (
    ValidationReport,
    check_negative,
    check_outliers,
    check_percentages,
    check_reach_vs_impressions,
)

_SNAKE = re.compile(r"[^a-z0-9]+")
_CATEGORY_ENUMS = {
    "content_topic": {e.value for e in ContentTopic},
    "content_pillar": {e.value for e in ContentPillar},
    "cta_type": {e.value for e in CTAType},
}


@dataclass
class NormalizationResult:
    posts: pd.DataFrame
    snapshots: pd.DataFrame
    report: ValidationReport
    has_time: bool


def _snake(value: object) -> str | None:
    if is_null(value):
        return None
    return _SNAKE.sub("_", str(value).strip().lower()).strip("_") or None


def _paid_or_organic(value: object) -> str | None:
    if is_null(value):
        return None
    v = str(value).lower()
    if any(k in v for k in ("paid", "sponsor", "boost", "promoted", "ad")):
        return "paid"
    return "organic"


def _fallback_id(platform: Platform, published: pd.Timestamp, caption: object) -> str:
    basis = f"{platform.value}|{published.isoformat() if pd.notna(published) else ''}|{str(caption)[:80]}"
    return "gen_" + hashlib.sha1(basis.encode()).hexdigest()[:16]


def normalize_table(
    raw: pd.DataFrame,
    mapping: dict[str, str],
    platform: Platform,
    timezone: str = "UTC",
) -> NormalizationResult:
    """``mapping`` is {source_column: canonical_field} for mapped columns only."""
    fields = canonical_fields()
    report = ValidationReport(rows_in=len(raw))
    out = pd.DataFrame(index=raw.index)
    has_time = True

    for source, target in mapping.items():
        spec = fields[target]
        series = raw[source]
        if spec.type == "datetime":
            out[target], has_time = parse_datetime_series(series, timezone)
        elif spec.type in ("number", "percent", "duration"):
            parsed, failures = parse_numeric_series(series, spec.type)
            if spec.type == "duration":
                parsed = parsed * duration_unit_factor(source)
            if spec.type == "percent":
                parsed = normalize_percent(parsed)
            if failures:
                examples = series[(~series.map(is_null)) & parsed.isna()].head().tolist()
                report.add(
                    "non_numeric_values",
                    "warning",
                    f"{failures} value(s) in '{source}' are not numbers and were treated as missing.",
                    source,
                    failures,
                    examples,
                )
            out[target] = parsed
        else:
            out[target] = series.where(~series.map(is_null), None)

    # --- Required: publish date ---
    if "published_at" not in out:
        report.add("missing_required_field", "error", "No publish date column is mapped.", None)
        return NormalizationResult(pd.DataFrame(), pd.DataFrame(), report, False)
    bad_dates = out["published_at"].isna()
    if bad_dates.any():
        report.add(
            "invalid_dates",
            "warning",
            f"{int(bad_dates.sum())} row(s) have a missing or unreadable date and were skipped.",
            next(s for s, t in mapping.items() if t == "published_at"),
            int(bad_dates.sum()),
            raw.loc[bad_dates, next(s for s, t in mapping.items() if t == "published_at")].head().tolist(),
        )
        out = out[~bad_dates]
    if out.empty:
        report.add("empty_dataset", "error", "No rows with a valid date remain.")
        return NormalizationResult(pd.DataFrame(), pd.DataFrame(), report, has_time)

    # --- Required: at least one performance metric ---
    metric_cols = [f.name for f in fields.values() if f.is_numeric and f.name in out]
    if not metric_cols:
        report.add(
            "no_metrics",
            "error",
            "No performance metric (likes, reach, views...) is mapped, so nothing can be analyzed.",
        )
        return NormalizationResult(pd.DataFrame(), pd.DataFrame(), report, has_time)

    check_negative(out, [c for c in metric_cols if c != "followers_gained"], report)
    check_percentages(out, [c for c in metric_cols if fields[c].type == "percent"], report)
    check_reach_vs_impressions(out, report)
    check_outliers(out, [c for c in ("reach", "views", "impressions") if c in out], report)

    empty_metrics = out[metric_cols].isna().all(axis=1)
    if empty_metrics.any():
        report.add(
            "rows_without_metrics",
            "warning",
            f"{int(empty_metrics.sum())} row(s) have no metric values and were skipped.",
            count=int(empty_metrics.sum()),
        )
        out = out[~empty_metrics]

    # --- Identity & text fields ---
    if "external_post_id" not in out:
        out["external_post_id"] = None
        report.add(
            "missing_post_id",
            "info",
            "No post ID column; stable IDs were generated from date and caption.",
        )
    ids = out["external_post_id"].map(lambda v: None if is_null(v) else str(v).strip())
    captions = out["caption"] if "caption" in out else pd.Series(None, index=out.index)
    out["external_post_id"] = [
        i if i else _fallback_id(platform, ts, cap)
        for i, ts, cap in zip(ids, out["published_at"], captions, strict=True)
    ]

    if "hashtags" in out:
        out["hashtags"] = out["hashtags"].map(split_hashtags)
        from_captions = captions.map(extract_hashtags)
        out["hashtags"] = [h or c for h, c in zip(out["hashtags"], from_captions, strict=True)]
    else:
        out["hashtags"] = captions.map(extract_hashtags)

    # --- Formats & categories ---
    adapter = get_adapter(platform)
    durations = out["video_duration_seconds"] if "video_duration_seconds" in out else pd.Series(np.nan, index=out.index)
    post_types = out["post_type"] if "post_type" in out else pd.Series(None, index=out.index)
    out["content_format"] = [
        adapter.normalize_format(pt, None if pd.isna(d) else float(d))
        for pt, d in zip(post_types, durations, strict=True)
    ]
    if "paid_or_organic" in out:
        out["paid_or_organic"] = out["paid_or_organic"].map(_paid_or_organic)
    for col in ("content_topic", "content_pillar", "cta_type", "hook_type"):
        if col in out:
            out[col] = out[col].map(_snake)
            allowed = _CATEGORY_ENUMS.get(col)
            if allowed:
                out[col] = out[col].map(lambda v, a=allowed: v if v in a or v is None else "other")

    # --- Duplicates ---
    dup = out.duplicated(subset=["external_post_id"], keep="last")
    if dup.any():
        report.add(
            "duplicate_posts",
            "warning",
            f"{int(dup.sum())} duplicate post(s) were removed (kept the last occurrence).",
            "external_post_id",
            int(dup.sum()),
            out.loc[dup, "external_post_id"].head().tolist(),
        )
        out = out[~dup]

    # Posts keep their follower count (needed for ER by followers); the account-level
    # series is additionally lifted into snapshots.
    snapshots = _build_snapshots(out, timezone)
    out["platform"] = platform.value
    out["has_time"] = has_time
    report.rows_valid = len(out)

    if not has_time:
        report.add(
            "dates_without_time",
            "info",
            "The export contains dates but no times; hour-of-day analysis will be skipped.",
        )
    return NormalizationResult(out.reset_index(drop=True), snapshots, report, has_time)


def _build_snapshots(posts: pd.DataFrame, timezone: str) -> pd.DataFrame:
    """Lift follower counts (an account metric) into daily account snapshots."""
    if "followers" not in posts or posts["followers"].isna().all():
        return pd.DataFrame(columns=["snapshot_date", "followers"])
    local_date = posts["published_at"].dt.tz_convert(timezone).dt.date
    snaps = (
        pd.DataFrame({"snapshot_date": local_date, "followers": posts["followers"]})
        .dropna()
        .groupby("snapshot_date", as_index=False)["followers"]
        .max()
    )
    return snaps
