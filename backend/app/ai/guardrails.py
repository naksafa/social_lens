"""Post-generation verification of AI output against the supplied analytics.

Prompts forbid invented statistics; this module *checks* it. Every number appearing
in data-backed text fields (evidence, explanations, summaries) must match a number
present in the analytics payload the model received, **at the precision it was
written**: "12.5%" must equal some payload value rounded to 1 decimal, "6,476" some
value rounded to an integer. (A loose relative tolerance would let almost any number
through, because the payload contains thousands of values.) Unmatched numbers are
reported as "unverified" so a reviewer can check them.

Small integers (<= 31: day counts, list counts, "3 posts per week") and years are
ignored because they are usually structural or prescriptive, not statistics.
"""

import json
import re
from typing import Any

from pydantic import BaseModel

_NUMBER = re.compile(r"(?<![\w.])[-+]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|(?<![\w.])[-+]?\d+(?:\.\d+)?")
CHECKED_FIELDS = {"evidence", "explanation", "executive_summary", "summary", "performance_assessment",
                  "strategy_summary", "baseline", "rationale"}  # fmt: skip
MAX_DECIMALS = 4


def _tokens(text: str) -> list[tuple[float, int]]:
    """(value, decimals written) for every number in the text."""
    out = []
    for m in _NUMBER.findall(text or ""):
        raw = m.replace(",", "")
        try:
            value = float(raw)
        except ValueError:
            continue
        decimals = len(raw.split(".")[1]) if "." in raw else 0
        out.append((value, min(decimals, MAX_DECIMALS)))
    return out


def extract_numbers(text: str) -> list[float]:
    return [v for v, _ in _tokens(text)]


def allowed_numbers(payload: Any) -> set[float]:
    """All numeric values in the analytics payload (plus fraction->percent forms)."""
    nums: set[float] = set()

    def walk(v: Any) -> None:
        if isinstance(v, bool):
            return
        if isinstance(v, int | float):
            f = float(v)
            nums.update({f, abs(f)})
            if 0 < abs(f) <= 1:
                nums.add(abs(f) * 100)  # fraction written as a percentage
        elif isinstance(v, str):
            nums.update(extract_numbers(v))
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list | tuple):
            for x in v:
                walk(x)

    walk(payload)
    return nums


def _rounded_index(allowed: set[float]) -> dict[int, set[float]]:
    return {d: {round(a, d) for a in allowed} for d in range(MAX_DECIMALS + 1)}


def _is_supported(value: float, decimals: int, index: dict[int, set[float]]) -> bool:
    n = abs(value)
    if n <= 31 and float(n).is_integer():
        return True
    if 1900 <= n <= 2100 and float(n).is_integer():
        return True
    return round(n, decimals) in index[decimals]


def verify_output(output: BaseModel, payload: Any) -> dict:
    """Return a verification report and annotate nothing in-place (pure)."""
    index = _rounded_index(allowed_numbers(payload))
    issues: list[dict] = []
    checked = 0

    def walk(node: Any, path: str) -> None:
        nonlocal checked
        if isinstance(node, dict):
            for k, v in node.items():
                if k in CHECKED_FIELDS and isinstance(v, str):
                    toks = _tokens(v)
                    checked += len(toks)
                    bad = [n for n, d in toks if not _is_supported(n, d, index)]
                    if bad:
                        issues.append({"path": f"{path}.{k}", "unverified_numbers": bad, "text": v[:200]})
                else:
                    walk(v, f"{path}.{k}")
        elif isinstance(node, list):
            for i, v in enumerate(node):
                walk(v, f"{path}[{i}]")

    walk(json.loads(output.model_dump_json()), "$")
    return {
        "numbers_checked": checked,
        "unverified_count": sum(len(i["unverified_numbers"]) for i in issues),
        "issues": issues[:50],
        "status": "verified" if not issues else "needs_review",
        "method": "Numbers in evidence/explanation/summary fields matched against the analytics payload at the precision written.",
    }
