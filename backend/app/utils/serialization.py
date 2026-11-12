"""Convert pandas/numpy structures into plain JSON-safe Python values."""

import math
from datetime import date, datetime
from typing import Any

import numpy as np
import pandas as pd


def to_jsonable(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, dict):
        return {str(k): to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(v) for v in value]
    if isinstance(value, np.ndarray):
        return [to_jsonable(v) for v in value.tolist()]
    if isinstance(value, pd.Timestamp):
        return None if pd.isna(value) else value.isoformat()
    if isinstance(value, datetime | date):
        return value.isoformat()
    if isinstance(value, np.bool_ | bool):
        return bool(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        f = float(value)
        return None if math.isnan(f) or math.isinf(f) else f
    if value is pd.NaT or value is pd.NA:
        return None
    return value


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> list of dicts with NaN/NaT -> None and numpy scalars unwrapped.

    Timestamps are kept as Python datetimes (for ORM inserts), not strings.
    """
    out = []
    for row in df.to_dict(orient="records"):
        clean = {}
        for k, v in row.items():
            if isinstance(v, pd.Timestamp):
                clean[k] = None if pd.isna(v) else v.to_pydatetime()
            elif isinstance(v, list | dict):
                clean[k] = v
            elif v is None or (not isinstance(v, str) and pd.isna(v)):
                clean[k] = None
            elif isinstance(v, np.generic):
                clean[k] = v.item()
            else:
                clean[k] = v
        out.append(clean)
    return out


def round_floats(value: Any, ndigits: int = 4) -> Any:
    if isinstance(value, dict):
        return {k: round_floats(v, ndigits) for k, v in value.items()}
    if isinstance(value, list):
        return [round_floats(v, ndigits) for v in value]
    if isinstance(value, float):
        return round(value, ndigits)
    return value
