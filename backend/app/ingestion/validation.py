"""Dataset validation with user-friendly, structured issues.

Validation never crashes on optional data problems: bad values are nulled and
reported as warnings; only problems that make the dataset unusable are errors.
"""

from dataclasses import asdict, dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

Severity = Literal["error", "warning", "info"]


@dataclass
class ValidationIssue:
    code: str
    severity: Severity
    message: str
    column: str | None = None
    count: int = 0
    examples: list[str] = field(default_factory=list)


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)
    rows_in: int = 0
    rows_valid: int = 0

    def add(
        self,
        code: str,
        severity: Severity,
        message: str,
        column: str | None = None,
        count: int = 0,
        examples: list[object] | None = None,
    ) -> None:
        self.issues.append(
            ValidationIssue(code, severity, message, column, count, [str(e)[:80] for e in (examples or [])[:5]])
        )

    @property
    def is_valid(self) -> bool:
        return not any(i.severity == "error" for i in self.issues)

    def to_dict(self) -> dict:
        return {
            "is_valid": self.is_valid,
            "rows_in": self.rows_in,
            "rows_valid": self.rows_valid,
            "rows_dropped": self.rows_in - self.rows_valid,
            "error_count": sum(i.severity == "error" for i in self.issues),
            "warning_count": sum(i.severity == "warning" for i in self.issues),
            "issues": [asdict(i) for i in self.issues],
        }


def check_negative(df: pd.DataFrame, columns: list[str], report: ValidationReport) -> None:
    for col in columns:
        if col not in df:
            continue
        mask = df[col] < 0
        if mask.any():
            report.add(
                "negative_values",
                "warning",
                f"{int(mask.sum())} negative value(s) in '{col}' were treated as missing.",
                col,
                int(mask.sum()),
                df.loc[mask, col].head().tolist(),
            )
            df.loc[mask, col] = np.nan


def check_percentages(df: pd.DataFrame, columns: list[str], report: ValidationReport) -> None:
    for col in columns:
        if col not in df:
            continue
        mask = (df[col] < 0) | (df[col] > 100)
        if mask.any():
            report.add(
                "impossible_percentage",
                "warning",
                f"{int(mask.sum())} value(s) in '{col}' are outside 0-100% and were treated as missing.",
                col,
                int(mask.sum()),
                df.loc[mask, col].head().tolist(),
            )
            df.loc[mask, col] = np.nan


def check_reach_vs_impressions(df: pd.DataFrame, report: ValidationReport) -> None:
    if {"reach", "impressions"} <= set(df.columns):
        mask = df["reach"] > df["impressions"] * 1.01
        if mask.any():
            report.add(
                "reach_exceeds_impressions",
                "info",
                f"{int(mask.sum())} post(s) report reach above impressions, which is unusual "
                "(reach counts unique accounts). Values were kept; check the export.",
                "reach",
                int(mask.sum()),
            )


def check_outliers(df: pd.DataFrame, columns: list[str], report: ValidationReport) -> None:
    """Flag extreme values (robust z-score > 10 on log scale). Informational only."""
    for col in columns:
        if col not in df:
            continue
        s = df[col].dropna()
        if len(s) < 10:
            continue
        logged = np.log1p(s.clip(lower=0))
        med = logged.median()
        mad = (logged - med).abs().median()
        if mad == 0:
            continue
        z = 0.6745 * (logged - med) / mad
        n = int((z.abs() > 10).sum())
        if n:
            report.add(
                "suspicious_outliers",
                "info",
                f"{n} extreme value(s) in '{col}' (possible viral posts or data errors).",
                col,
                n,
                s[z.abs() > 10].head().tolist(),
            )
