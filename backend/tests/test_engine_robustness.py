"""The engine must degrade gracefully on sparse or tiny datasets, never crash."""

import json

import numpy as np
import pandas as pd
import pytest

from app.analytics.engine import AnalysisContext, AnalysisEngine
from app.core.exceptions import AnalysisError


def _run(df: pd.DataFrame) -> dict:
    out = AnalysisEngine(AnalysisContext(objectives=["lead_generation"])).run(df)
    json.dumps(out.sections)  # must be JSON-serializable (no NaN/inf/numpy types)
    json.dumps(out.findings)
    return {**out.sections, "findings": out.findings}


def test_minimal_columns_only_date_and_likes() -> None:
    df = pd.DataFrame(
        {
            "id": range(12),
            "platform": "facebook",
            "published_at": pd.date_range("2025-03-01", periods=12, freq="2D", tz="UTC"),
            "likes": np.arange(12, dtype=float),
        }
    )
    s = _run(df)
    kpis = s["platforms"]["facebook"]["kpis"]
    assert kpis["exposure_metric"] is None
    assert "engagement_rate" in kpis["unavailable"]
    assert kpis["metrics"]["total_posts"] == 12


def test_tiny_dataset_three_posts() -> None:
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "platform": ["instagram", "instagram", "tiktok"],
            "published_at": pd.to_datetime(["2025-01-01", "2025-01-02", "2025-01-03"], utc=True),
            "reach": [100.0, 0.0, None],
            "views": [None, None, 500.0],
            "likes": [10.0, 0.0, 30.0],
            "caption": ["Case study", None, "POV: it works"],
            "content_format": ["reel", None, "short_video"],
        }
    )
    s = _run(df)
    assert s["overview"]["total_posts"] == 3
    # Too little data -> no statistical findings claimed.
    assert all(f["confidence"] == "low" for f in s["findings"])


def test_empty_raises_clean_error() -> None:
    with pytest.raises(AnalysisError):
        AnalysisEngine(AnalysisContext()).run(pd.DataFrame())
