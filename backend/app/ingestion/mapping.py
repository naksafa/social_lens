"""Automatic column mapping with confidence scores.

For each (source column, canonical field) pair a score in [0, 1] is computed:

* exact match against a platform-specific alias -> 1.00
* exact match against a generic alias            -> 0.95
* otherwise fuzzy similarity (rapidfuzz): x0.9 when similarity >= 0.8, else x0.6
* multiplied by a type-compatibility factor from the column profile
  (e.g. a mostly non-numeric column cannot be ``reach``).

Pairs are then assigned greedily by score so each column maps to at most one
field and each field receives at most one column. Scores below ``MIN_SCORE`` are
left unmapped; scores below ``REVIEW_THRESHOLD`` are flagged for manual review.
"""

from dataclasses import dataclass, field

from rapidfuzz import fuzz

from app.core.enums import MappingMethod, Platform
from app.ingestion.canonical import CanonicalField, canonical_fields, normalize_header
from app.ingestion.profiling import ColumnProfile

MIN_SCORE = 0.60
REVIEW_THRESHOLD = 0.85


@dataclass
class MappingSuggestion:
    source_column: str
    target_field: str | None
    confidence: float
    method: MappingMethod
    needs_review: bool
    alternatives: list[dict] = field(default_factory=list)


def _type_factor(f: CanonicalField, p: ColumnProfile) -> float:
    if p.inferred_type == "empty":
        return 0.3
    if f.type in ("number", "percent"):
        return 1.0 if p.numeric_ratio >= 0.8 else (0.6 if p.numeric_ratio >= 0.5 else 0.2)
    if f.type == "duration":
        ok = max(p.numeric_ratio, p.duration_ratio)
        return 1.0 if ok >= 0.8 else (0.6 if ok >= 0.5 else 0.2)
    if f.type == "datetime":
        return 1.0 if p.datetime_ratio >= 0.7 else (0.5 if p.datetime_ratio >= 0.4 else 0.15)
    if f.type == "longtext":
        return 1.0 if p.avg_length >= 20 else 0.7
    if f.type == "category":
        return 1.0 if p.numeric_ratio < 0.5 else 0.5
    if f.type == "id":
        # IDs must be (almost) unique; a constant column like "Posted by" is not an ID.
        if p.unique_ratio < 0.8:
            return 0.2
        return 1.0 if p.null_pct < 50 else 0.6
    return 1.0


def _name_score(header: str, f: CanonicalField, platform: Platform | None) -> tuple[float, MappingMethod]:
    specific, generic = f.aliases_for(platform)
    if header in specific:
        return 1.0, MappingMethod.EXACT
    if header in generic or header == f.name.replace("_", " "):
        return 0.95, MappingMethod.EXACT
    best = 0.0
    for alias in (*specific, *generic):
        # token_set_ratio handles extra words ("Post reach (organic)"), ratio penalises
        # very different strings; average both to avoid over-matching short aliases.
        s = (fuzz.token_set_ratio(header, alias) + fuzz.ratio(header, alias)) / 200
        best = max(best, s)
    # Weak fuzzy similarity is heavily discounted: short headers produce spurious
    # matches ("posted by" ~ "boosted") that should never be auto-mapped.
    return round(best * (0.9 if best >= 0.8 else 0.6), 3), MappingMethod.FUZZY


def suggest_mappings(profiles: list[ColumnProfile], platform: Platform | None = None) -> list[MappingSuggestion]:
    fields = canonical_fields()
    candidates: list[tuple[float, int, str, MappingMethod]] = []
    per_column: dict[int, list[tuple[float, str]]] = {i: [] for i in range(len(profiles))}

    for i, prof in enumerate(profiles):
        header = normalize_header(prof.name)
        for f in fields.values():
            name_score, method = _name_score(header, f, platform)
            if name_score < 0.4:
                continue
            score = round(name_score * _type_factor(f, prof), 3)
            candidates.append((score, i, f.name, method))
            per_column[i].append((score, f.name))

    candidates.sort(key=lambda c: (-c[0], c[1]))
    assigned_cols: dict[int, tuple[str, float, MappingMethod]] = {}
    used_fields: set[str] = set()
    for score, i, fname, method in candidates:
        if score < MIN_SCORE or i in assigned_cols or fname in used_fields:
            continue
        assigned_cols[i] = (fname, score, method)
        used_fields.add(fname)

    suggestions = []
    for i, prof in enumerate(profiles):
        alts = sorted(per_column[i], reverse=True)[:3]
        alternatives = [{"field": n, "score": s} for s, n in alts]
        if i in assigned_cols:
            fname, score, method = assigned_cols[i]
            suggestions.append(
                MappingSuggestion(prof.name, fname, score, method, score < REVIEW_THRESHOLD, alternatives)
            )
        else:
            best = alts[0][0] if alts else 0.0
            suggestions.append(
                MappingSuggestion(
                    prof.name,
                    None,
                    best,
                    MappingMethod.UNMAPPED,
                    # A plausible but unassigned column deserves a look.
                    needs_review=best >= 0.5,
                    alternatives=alternatives,
                )
            )
    return suggestions


def missing_required(mapped_fields: set[str]) -> list[str]:
    return [f.name for f in canonical_fields().values() if f.required and f.name not in mapped_fields]
