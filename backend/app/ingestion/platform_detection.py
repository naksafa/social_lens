"""Detect which platform an export came from, using column names, cell values and filename."""

from dataclasses import dataclass

import pandas as pd
from rapidfuzz import fuzz

from app.core.enums import Platform
from app.ingestion.canonical import normalize_header, platform_signatures


@dataclass
class PlatformDetection:
    platform: Platform | None
    confidence: float
    scores: dict[str, float]


def detect_platform(df: pd.DataFrame, filename: str = "") -> PlatformDetection:
    headers = [normalize_header(c) for c in df.columns]
    lower_name = filename.lower()
    # Values of low-cardinality text columns (e.g. "IG reel", "Sponsored").
    values: set[str] = set()
    for col in df.columns:
        uniques = df[col].dropna().astype(str).str.strip().str.lower().unique()
        if 0 < len(uniques) <= 25:
            values.update(uniques)

    raw_scores: dict[Platform, float] = {}
    for platform, sig in platform_signatures().items():
        col_hits = sum(
            1.0 if sc in headers else (0.6 if any(fuzz.ratio(sc, h) >= 90 for h in headers) else 0.0)
            for sc in sig.columns
        )
        value_hits = sum(1 for v in sig.values if v in values)
        filename_hit = any(token in lower_name for token in sig.filename)
        raw_scores[platform] = col_hits * 1.0 + value_hits * 0.75 + (3.0 if filename_hit else 0.0)

    total = sum(raw_scores.values())
    if total == 0:
        return PlatformDetection(None, 0.0, {p.value: 0.0 for p in raw_scores})
    ranked = sorted(raw_scores.items(), key=lambda kv: kv[1], reverse=True)
    (best, best_score), (_, second_score) = ranked[0], ranked[1]
    # Confidence mixes share-of-evidence and margin over the runner-up; weak evidence caps it.
    share = best_score / total
    margin = (best_score - second_score) / best_score if best_score else 0.0
    strength = min(1.0, best_score / 4.0)
    confidence = round(min(0.99, (0.5 * share + 0.5 * margin) * (0.5 + 0.5 * strength)), 2)
    return PlatformDetection(
        platform=best if confidence >= 0.3 else None,
        confidence=confidence,
        scores={p.value: round(s, 2) for p, s in raw_scores.items()},
    )
