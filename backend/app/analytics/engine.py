"""AnalysisEngine: runs every analytics module over a canonical posts DataFrame.

Pure computation - no database access - so it is unit-testable and reusable from
background workers. The service layer (services/analysis_pipeline.py) loads posts,
calls ``AnalysisEngine.run`` and persists the result as a versioned AnalyticsRun.
"""

import warnings
from dataclasses import dataclass, field
from typing import Any

import pandas as pd

from app.analytics.anomaly_detection import analyze_anomalies
from app.analytics.audience_analysis import analyze_audience
from app.analytics.classification import TAXONOMY_VERSION, classify_posts
from app.analytics.common import ALPHA, MIN_GROUP_SIZE, MIN_TEST_GROUP_SIZE, fnum
from app.analytics.content_performance import platform_top_content
from app.analytics.cross_platform import analyze_cross_platform
from app.analytics.features import engineer_features
from app.analytics.findings import FindingCollector
from app.analytics.format_analysis import analyze_formats
from app.analytics.insights import InsightContext, InsightData, generate_insights
from app.analytics.kpi_engine import overall_kpis, platform_kpis
from app.analytics.posting_frequency import analyze_posting
from app.analytics.scoring import ObjectiveWeightingService, compute_performance_index
from app.analytics.statistical_models import analyze_statistics
from app.analytics.timing_analysis import analyze_timing
from app.analytics.topic_analysis import analyze_hooks_and_ctas, analyze_pillars
from app.analytics.trends import analyze_trends
from app.analytics.video_analysis import analyze_video
from app.core.exceptions import AnalysisError
from app.utils.serialization import to_jsonable


@dataclass
class AnalysisContext:
    objectives: list[str] = field(default_factory=list)
    timezone: str = "UTC"
    weight_overrides: dict[str, float] | None = None


@dataclass
class AnalysisOutput:
    sections: dict[str, Any]
    findings: list[dict]
    insights: list[InsightData]
    headline: dict[str, Any]
    classifications: pd.DataFrame  # per-post keyword classification (to persist)
    period: tuple[pd.Timestamp, pd.Timestamp]
    parameters: dict[str, Any]


class AnalysisEngine:
    def __init__(self, context: AnalysisContext) -> None:
        self.ctx = context

    def run(self, posts: pd.DataFrame) -> AnalysisOutput:
        # All-NaN slices (e.g. a metric a platform doesn't report) are expected and
        # handled explicitly; silence numpy's "mean of empty slice" noise.
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            return self._run(posts)

    def _run(self, posts: pd.DataFrame) -> AnalysisOutput:
        if posts.empty:
            raise AnalysisError("No posts to analyze. Import and normalize data first.")

        # 1. Content classification (keyword) for posts not classified by a stronger source.
        classes = classify_posts(posts)
        posts = posts.assign(**{c: classes[c] for c in classes.columns})

        # 2. Feature engineering.
        df, infos = engineer_features(posts, self.ctx.timezone)
        period = (df["local_time"].min().normalize(), df["local_time"].max().normalize())

        # 3. Objective-weighted performance index.
        weighting = ObjectiveWeightingService(self.ctx.weight_overrides)
        weights = weighting.resolve(self.ctx.objectives)
        df["performance_index"] = compute_performance_index(df, weights)

        collector = FindingCollector()
        per_platform: dict[str, dict] = {}
        for platform, g in df.groupby("platform", sort=True):
            p = str(platform)
            info = infos[p]
            exp = info.exposure_metric
            section: dict[str, Any] = {"exposure_metric": exp}
            section["kpis"] = platform_kpis(g, info, period)
            section["posting"] = analyze_posting(g, period)
            section["formats"], f = analyze_formats(g, p, exp)
            collector.extend(f)
            section["pillars"], f = analyze_pillars(g, p, exp)
            collector.extend(f)
            section["hooks_ctas"], f = analyze_hooks_and_ctas(g, p, exp)
            collector.extend(f)
            section["timing"], f = analyze_timing(g, p, exp)
            collector.extend(f)
            section["trends"], f = analyze_trends(g, p, period, exp)
            collector.extend(f)
            section["video"], f = analyze_video(g, p, exp)
            collector.extend(f)
            section["statistics"], f = analyze_statistics(g, p, exp)
            collector.extend(f)
            section["top_content"] = platform_top_content(g, exp)
            section["anomalies"] = analyze_anomalies(g)
            section["audience"] = analyze_audience(g, p, info.engagement_components)
            per_platform[p] = section

        # Overall pillar mix is descriptive only: pooled rates would mix exposure definitions.
        overall_pillars, _ = analyze_pillars(df, None, None)
        cross = analyze_cross_platform(df, per_platform)

        findings = [x.to_dict() for x in collector.finalize(ALPHA)]
        insights = generate_insights(
            InsightContext(
                platforms=per_platform, findings=findings, cross_platform=cross, objectives=self.ctx.objectives
            )
        )

        parameters = {
            "objectives": weights.objectives,
            "weights": weights.weights,
            "weights_explanation": weights.explanation,
            "weights_dropped_by_platform": weights.dropped,
            "timezone": self.ctx.timezone,
            "alpha": ALPHA,
            "multiple_testing_correction": "Benjamini-Hochberg",
            "min_group_size": MIN_GROUP_SIZE,
            "min_test_group_size": MIN_TEST_GROUP_SIZE,
            "taxonomy_version": TAXONOMY_VERSION,
        }
        sections = {
            "overview": self._overview(df, infos, period),
            "platforms": per_platform,
            "overall": {"kpis": overall_kpis(df), "pillars": overall_pillars},
            "cross_platform": cross,
            "scoring": {
                "method": (
                    "performance_index = weighted mean of within-platform percentile ranks (0-100); "
                    "weights from business objectives, re-normalized over metrics present."
                ),
                **parameters,
            },
            "post_metrics": self._post_metrics(df),
        }
        headline = self._headline(df, per_platform, insights, findings)
        return AnalysisOutput(
            sections=to_jsonable(sections),
            findings=to_jsonable(findings),
            insights=insights,
            headline=to_jsonable(headline),
            classifications=df[
                ["content_topic", "content_pillar", "topic_confidence", "topic_source", "cta_type", "hook_type"]
            ].assign(id=df.get("id")),
            period=period,
            parameters=to_jsonable(parameters),
        )

    @staticmethod
    def _overview(df: pd.DataFrame, infos: dict, period: tuple[pd.Timestamp, pd.Timestamp]) -> dict:
        return {
            "period_start": period[0].date().isoformat(),
            "period_end": period[1].date().isoformat(),
            "period_days": (period[1] - period[0]).days + 1,
            "total_posts": int(len(df)),
            "posts_by_platform": df["platform"].value_counts().to_dict(),
            "exposure_metric_by_platform": {p: i.exposure_metric for p, i in infos.items()},
            "engagement_components_by_platform": {p: i.engagement_components for p, i in infos.items()},
            "data_completeness_by_platform": {p: i.completeness for p, i in infos.items()},
        }

    @staticmethod
    def _post_metrics(df: pd.DataFrame) -> list[dict]:
        cols = ["id", "platform", "external_post_id", "local_time", "content_format", "content_pillar", "content_topic",
                "hook_type", "cta_type", "exposure", "engagement_total", "er", "share_rate", "save_rate", "click_rate",
                "completion", "video_duration_seconds", "performance_index", "caption"]  # fmt: skip
        out = []
        for r in df.reindex(columns=cols).itertuples(index=False):
            d = r._asdict()
            d["published_at"] = d.pop("local_time").isoformat()
            d["caption"] = d["caption"][:100] if isinstance(d["caption"], str) else ""
            d["id"] = str(d["id"]) if d["id"] is not None and not pd.isna(d["id"]) else None
            for k in ("content_format", "content_pillar", "content_topic", "hook_type", "cta_type", "external_post_id"):
                if not isinstance(d[k], str):
                    d[k] = None
            for k in ("exposure", "engagement_total", "video_duration_seconds"):
                d[k] = fnum(d[k], 0)
            for k in ("er", "share_rate", "save_rate", "click_rate", "completion", "performance_index"):
                d[k] = fnum(d[k], 3)
            out.append(d)
        return out

    @staticmethod
    def _headline(df: pd.DataFrame, per_platform: dict, insights: list[InsightData], findings: list[dict]) -> dict:
        return {
            "total_posts": int(len(df)),
            "platforms": {
                p: {
                    "posts": s["kpis"]["metrics"]["total_posts"],
                    "exposure_metric": s["exposure_metric"],
                    "median_exposure": fnum(df.loc[df.platform == p, "exposure"].median(), 0),
                    "engagement_rate": s["kpis"]["metrics"].get("engagement_rate"),
                    "median_engagement_rate": s["kpis"]["metrics"].get("median_engagement_rate"),
                    "follower_growth": s["kpis"]["metrics"].get("follower_growth"),
                    "total_clicks": s["kpis"]["metrics"].get("total_clicks"),
                    "total_views": s["kpis"]["metrics"].get("total_views"),
                    "total_reach": s["kpis"]["metrics"].get("total_reach"),
                    "posts_per_week": s["posting"]["posts_per_week"],
                    "consistency": s["posting"]["consistency"],
                    "exposure_trend": s["trends"]["trends"].get("median_exposure", {}).get("label"),
                }
                for p, s in per_platform.items()
            },
            "insight_counts": {
                "negative": sum(i.sentiment == "negative" for i in insights),
                "positive": sum(i.sentiment == "positive" for i in insights),
                "high_severity": sum(i.severity in ("critical", "high") for i in insights),
            },
            "findings": {
                "total": len(findings),
                "significant": sum(1 for f in findings if f.get("significant")),
                "high_confidence": sum(1 for f in findings if f["confidence"] == "high"),
            },
        }
