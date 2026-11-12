"""Canonical field registry, loaded from ``field_aliases.json``."""

import json
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Literal

from app.core.enums import Platform

FieldType = Literal["id", "datetime", "text", "longtext", "category", "number", "duration", "percent"]
NUMERIC_TYPES: frozenset[str] = frozenset({"number", "duration", "percent"})

_REGISTRY_PATH = Path(__file__).with_name("field_aliases.json")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def normalize_header(name: object) -> str:
    """'Accounts Reached (#)' -> 'accounts reached'. Used for all alias comparisons."""
    text = str(name).lower().replace("_", " ")
    text = _NON_ALNUM.sub(" ", text)
    return " ".join(text.split())


@dataclass(frozen=True)
class CanonicalField:
    name: str
    type: FieldType
    label: str
    required: bool = False
    aliases: tuple[str, ...] = ()
    platform_aliases: dict[str, tuple[str, ...]] = field(default_factory=dict)

    @property
    def is_numeric(self) -> bool:
        return self.type in NUMERIC_TYPES

    def aliases_for(self, platform: Platform | None) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """Return (platform-specific aliases, generic aliases), normalized."""
        specific = self.platform_aliases.get(platform.value, ()) if platform else ()
        return (
            tuple(normalize_header(a) for a in specific),
            tuple(normalize_header(a) for a in self.aliases),
        )


@dataclass(frozen=True)
class PlatformSignature:
    columns: tuple[str, ...]
    values: tuple[str, ...]
    filename: tuple[str, ...]


@lru_cache
def _load() -> dict:
    return json.loads(_REGISTRY_PATH.read_text(encoding="utf-8"))


@lru_cache
def canonical_fields() -> dict[str, CanonicalField]:
    raw = _load()["fields"]
    return {
        name: CanonicalField(
            name=name,
            type=spec["type"],
            label=spec["label"],
            required=spec.get("required", False),
            aliases=tuple(spec.get("aliases", ())),
            platform_aliases={k: tuple(v) for k, v in spec.get("platform_aliases", {}).items()},
        )
        for name, spec in raw.items()
    }


@lru_cache
def platform_signatures() -> dict[Platform, PlatformSignature]:
    raw = _load()["platform_signatures"]
    return {
        Platform(p): PlatformSignature(
            columns=tuple(normalize_header(c) for c in spec.get("columns", ())),
            values=tuple(v.lower() for v in spec.get("values", ())),
            filename=tuple(v.lower() for v in spec.get("filename", ())),
        )
        for p, spec in raw.items()
    }


def metric_fields() -> list[str]:
    return [f.name for f in canonical_fields().values() if f.is_numeric]
