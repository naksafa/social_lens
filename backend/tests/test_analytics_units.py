import numpy as np
import pandas as pd
import pytest

from app.analytics.classification import classify_caption, detect_cta, detect_hook
from app.analytics.common import pct_diff, safe_div
from app.analytics.confidence import assess_confidence
from app.analytics.features import engineer_features
from app.analytics.findings import benjamini_hochberg
from app.analytics.posting_frequency import analyze_posting
from app.analytics.scoring import ObjectiveWeightingService, compute_performance_index
from app.analytics.statistics import kruskal, mann_whitney, ols_log_target
from app.analytics.trends import classify_trend
from app.utils.csv_export import escape_cell, to_csv


def _posts(n: int = 40, platform: str = "instagram", **cols: object) -> pd.DataFrame:
    rng = np.random.default_rng(0)
    base: dict[str, object] = {
        "id": range(n),
        "platform": platform,
        "published_at": pd.date_range("2025-01-01", periods=n, freq="36h", tz="UTC"),
        "caption": ["Tips for growth #a"] * n,
        "content_format": ["reel", "image"] * (n // 2),
        "reach": rng.integers(100, 5000, n).astype(float),
        "likes": rng.integers(1, 200, n).astype(float),
        "comments": rng.integers(0, 20, n).astype(float),
        "shares": rng.integers(0, 20, n).astype(float),
        "saves": rng.integers(0, 30, n).astype(float),
        "hashtags": [["a"]] * n,
        "has_time": True,
    }
    base.update(cols)
    return pd.DataFrame(base)


class TestSafeMath:
    def test_safe_div_series_zero_and_nan(self) -> None:
        out = safe_div(pd.Series([10.0, 5.0, 1.0]), pd.Series([0.0, np.nan, 2.0]), 100)
        assert out.isna().tolist() == [True, True, False] and out.iloc[2] == 50

    def test_safe_div_scalar(self) -> None:
        assert np.isnan(safe_div(1, 0)) and safe_div(1, 4, 100) == 25

    def test_pct_diff(self) -> None:
        assert pct_diff(150, 100) == 50.0 and pct_diff(1, 0) is None


class TestFeatures:
    def test_er_and_missing_components(self) -> None:
        df = _posts(4, platform="linkedin", reach=np.nan, impressions=[1000.0, 0.0, 500.0, 200.0])
        df = df.drop(columns=["saves"])
        out, infos = engineer_features(df)
        assert infos["linkedin"].exposure_metric == "impressions"
        assert "saves" not in infos["linkedin"].engagement_components
        # zero impressions -> NaN ER, never inf
        assert np.isnan(out[out["impressions"] == 0].iloc[0]["er"])
        assert np.isfinite(out["er"].dropna()).all()

    def test_completion_derived_from_watch_time(self) -> None:
        df = _posts(2, platform="tiktok", views=[100.0, 200.0], average_watch_time_seconds=[5.0, 10.0],
                    video_duration_seconds=[10.0, 20.0])  # fmt: skip
        out, _ = engineer_features(df)
        assert out["completion"].tolist() == [50.0, 50.0]

    def test_missing_optional_columns_do_not_crash(self) -> None:
        df = pd.DataFrame(
            {"id": [1, 2], "platform": "facebook", "likes": [1.0, 2.0],
             "published_at": pd.to_datetime(["2025-01-01", "2025-01-02"], utc=True)}
        )  # fmt: skip
        out, infos = engineer_features(df)
        assert infos["facebook"].exposure_metric is None
        assert out["er"].isna().all()


class TestClassification:
    @pytest.mark.parametrize(
        ("caption", "topic"),
        [
            ("Case study: how we helped a clinic double leads", "case_study"),
            ("Spring offer - 20% off all packages. Book now!", "promotional"),
            ("Behind the scenes of our shoot day", "behind_the_scenes"),
            ("FAQ: how long does SEO take?", "faq"),
            ("Our top tips for better captions - try these today", "tips"),
            ("", "other"),
        ],
    )
    def test_topics(self, caption: str, topic: str) -> None:
        assert classify_caption(caption).topic == topic

    def test_cta_and_hook(self) -> None:
        assert detect_cta("Great stuff. Link in bio.") == "link_click"
        assert detect_cta("Save this for later") == "save"
        assert detect_cta("Just a nice day") == "none"
        assert detect_hook("3 mistakes with ads") == "number"
        assert detect_hook("POV: you post daily") == "pov"
        assert detect_hook("Why does nobody talk about this? Here's why.") == "question"


class TestStatistics:
    def test_mann_whitney_detects_shift_and_sign(self) -> None:
        rng = np.random.default_rng(1)
        res = mann_whitney(pd.Series(rng.normal(10, 1, 40)), pd.Series(rng.normal(8, 1, 40)))
        assert res and res.p_value < 0.001 and res.rank_biserial > 0.5

    def test_small_groups_are_not_tested(self) -> None:
        assert mann_whitney(pd.Series([1, 2, 3]), pd.Series([4, 5, 6])) is None
        assert kruskal({"a": pd.Series([1.0] * 3), "b": pd.Series([2.0] * 3), "c": pd.Series([3.0] * 3)}) is None

    def test_benjamini_hochberg(self) -> None:
        adj = benjamini_hochberg([0.01, 0.04, 0.03, 0.2])
        assert adj == pytest.approx([0.04, 0.0533333, 0.0533333, 0.2], rel=1e-4)
        assert benjamini_hochberg([]) == []

    def test_ols_recovers_effect(self) -> None:
        rng = np.random.default_rng(3)
        n = 200
        fmt = rng.choice(["image", "reel"], n)
        y = np.exp(7 + np.where(fmt == "reel", np.log(2), 0) + rng.normal(0, 0.3, n))
        res = ols_log_target(pd.DataFrame({"y": y, "fmt": fmt}), "y", ["fmt"])
        assert res is not None
        term = res.terms[0]
        assert term.p_value < 0.001
        # reel ~ +100% vs image (or -50% if reel is the baseline level)
        assert term.pct_effect == pytest.approx(100, abs=20) or term.pct_effect == pytest.approx(-50, abs=8)


class TestConfidence:
    def test_levels(self) -> None:
        assert assess_confidence(50, p_value=0.001, effect_size=0.5).level == "high"
        assert assess_confidence(15, p_value=0.001, effect_size=0.5).level == "medium"
        assert assess_confidence(50, p_value=0.5).level == "low"
        assert assess_confidence(50, p_value=0.1).level == "medium"
        assert assess_confidence(50, difference_pct=3).level == "medium"
        assert assess_confidence(6).level == "low"


class TestScoring:
    def test_weights_follow_objective(self) -> None:
        w = ObjectiveWeightingService().resolve(["brand_awareness"]).weights
        assert max(w, key=w.get) == "exposure"  # type: ignore[arg-type]
        w = ObjectiveWeightingService().resolve(["website_traffic"]).weights
        assert max(w, key=w.get) == "click_rate"  # type: ignore[arg-type]
        w = ObjectiveWeightingService().resolve(["engagement", "brand_awareness"]).weights
        assert w["engagement_rate"] > w["exposure"]  # primary objective counts double
        assert sum(w.values()) == pytest.approx(1.0, abs=1e-3)

    def test_index_bounds_and_missing_metrics(self) -> None:
        df, _ = engineer_features(_posts())
        resolved = ObjectiveWeightingService().resolve(["lead_generation"])
        idx = compute_performance_index(df, resolved)
        assert idx.between(0, 100).all()
        assert "leads" in resolved.dropped["instagram"]  # not in data -> weight re-normalized


class TestPostingAndTrends:
    def test_gap_detection(self) -> None:
        dates = list(pd.date_range("2025-01-01", periods=10, freq="D", tz="UTC")) + list(
            pd.date_range("2025-01-26", periods=5, freq="D", tz="UTC")
        )
        out = analyze_posting(pd.DataFrame({"local_time": dates}), (dates[0], dates[-1]))
        assert out["longest_gap_days"] == 15
        assert out["inactivity_periods"][0]["days"] == 15
        assert out["consistency"] in ("low", "moderate")

    def test_trend_labels(self) -> None:
        assert classify_trend(pd.Series([10, 12, 14, 16, 18, 20, 22, 24.0]))["label"] == "growth"
        assert classify_trend(pd.Series([24, 22, 20, 18, 16, 14, 12, 10.0]))["label"] == "decline"
        assert classify_trend(pd.Series([10, 10.5, 9.8, 10.2, 10.1, 9.9, 10.0, 10.3]))["label"] == "plateau"
        assert classify_trend(pd.Series([1.0, 2.0]))["label"] == "insufficient_data"


class TestCsvInjection:
    def test_escape(self) -> None:
        assert escape_cell('=HYPERLINK("x")') == '\'=HYPERLINK("x")'
        assert escape_cell("@SUM(A1)") == "'@SUM(A1)"
        assert escape_cell(-5) == -5
        assert escape_cell("normal") == "normal"
        assert "'=1+1" in to_csv(["a"], [["=1+1"]])
