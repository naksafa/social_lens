"""Rule-based insight engine.

Deterministic rules run over the computed analytics *before* any LLM call and emit
structured Insight objects (category, platform, title, description, metric, evidence,
confidence, severity, sentiment, recommendation_hint). Each rule is a small function
registered in ``RULES``; thresholds are module constants so they are easy to audit.
"""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from app.analytics.common import fnum, format_label, label, platform_label
from app.analytics.confidence import sample_confidence
from app.core.enums import MarketingObjective as MO

PROMO_SHARE_WARN = 50.0
PROMO_SHARE_CRITICAL = 70.0
CTA_USAGE_MIN = 20.0
GAP_WARN_DAYS = 8
GAP_CRITICAL_DAYS = 14
MIN_POSTS_PER_WEEK = 2.0
UNDERUSED_SHARE = 30.0
LOW_COMPLETION = 25.0
LOW_DIVERSITY = 45.0
CLICK_OBJECTIVES = {MO.LEAD_GENERATION.value, MO.WEBSITE_TRAFFIC.value, MO.SALES.value}


@dataclass
class InsightData:
    rule_id: str
    category: str
    platform: str | None
    title: str
    description: str
    metric: str | None
    evidence: dict[str, Any]
    confidence: str
    severity: str  # critical | high | medium | low | info
    sentiment: str  # positive | negative | neutral
    recommendation_hint: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class InsightContext:
    platforms: dict[str, dict]  # per-platform analytics sections
    findings: list[dict]  # finalized findings (dicts)
    cross_platform: dict
    objectives: list[str]
    overall: dict = field(default_factory=dict)

    def findings_for(self, category: str, platform: str | None = None) -> list[dict]:
        return [
            f for f in self.findings if f["category"] == category and (platform is None or f["platform"] == platform)
        ]


Rule = Callable[[InsightContext], list[InsightData]]
RULES: list[Rule] = []


def rule(fn: Rule) -> Rule:
    RULES.append(fn)
    return fn


def _pillar_row(section: dict, pillar: str) -> dict | None:
    return next((r for r in section["pillars"]["pillars"] if r["group"] == pillar), None)


@rule
def content_mix_imbalance(ctx: InsightContext) -> list[InsightData]:
    out = []
    for p, s in ctx.platforms.items():
        share = s["pillars"]["pillar_distribution"].get("promotional", 0) or 0
        if share <= PROMO_SHARE_WARN:
            continue
        promo = _pillar_row(s, "promotional") or {}
        others = [r for r in s["pillars"]["pillars"] if r["group"] != "promotional" and not r["low_sample"]]
        other_er = max((r.get("median_er") or 0 for r in others), default=None)
        out.append(InsightData(
            rule_id="content_mix_imbalance", category="content_mix", platform=p,
            title=f"Promotional content dominates on {platform_label(p)}",
            description=(
                f"{share}% of {platform_label(p)} posts are promotional. Promotional posts have a median ER of "
                f"{promo.get('median_er')}% vs up to {fnum(other_er)}% for other pillars."
            ),
            metric="pillar_share",
            evidence={"promotional_share_pct": share, "promotional_median_er": promo.get("median_er"),
                      "best_other_pillar_median_er": fnum(other_er), "posts": s["kpis"]["metrics"]["total_posts"]},
            confidence=sample_confidence(s["kpis"]["metrics"]["total_posts"]).value,
            severity="high" if share > PROMO_SHARE_CRITICAL else "medium",
            sentiment="negative",
            recommendation_hint="Rebalance toward value-first pillars (education, social proof); keep promotion to roughly 20-30% of posts.",
        ))  # fmt: skip
    return out


@rule
def weak_cta_usage(ctx: InsightContext) -> list[InsightData]:
    out = []
    needs_clicks = bool(set(ctx.objectives) & CLICK_OBJECTIVES)
    for p, s in ctx.platforms.items():
        usage = s["hooks_ctas"]["cta_usage_pct"]
        if usage is None or usage >= CTA_USAGE_MIN:
            continue
        out.append(InsightData(
            rule_id="weak_cta_usage", category="cta", platform=p,
            title=f"Few posts include a call-to-action on {platform_label(p)}",
            description=f"Only {usage}% of {platform_label(p)} posts contain a detectable call-to-action.",
            metric="cta_usage_pct", evidence={"cta_usage_pct": usage, "cta_distribution": s["hooks_ctas"]["cta_distribution"]},
            confidence=sample_confidence(s["kpis"]["metrics"]["total_posts"]).value,
            severity="high" if needs_clicks else "medium", sentiment="negative",
            recommendation_hint="Add a clear, single CTA matched to the post's goal (save/share for reach, link/DM for leads).",
        ))  # fmt: skip
    return out


@rule
def posting_gaps(ctx: InsightContext) -> list[InsightData]:
    out = []
    for p, s in ctx.platforms.items():
        post = s["posting"]
        gap = post["longest_gap_days"]
        if gap >= GAP_WARN_DAYS:
            out.append(InsightData(
                rule_id="posting_gap", category="consistency", platform=p,
                title=f"{gap}-day posting gap on {platform_label(p)}",
                description=(
                    f"The longest period without posting on {platform_label(p)} was {gap} days "
                    f"(consistency score {post['consistency_score']}/100, {post['consistency']})."
                ),
                metric="longest_gap_days",
                evidence={"longest_gap_days": gap, "inactivity_periods": post["inactivity_periods"],
                          "consistency_score": post["consistency_score"]},
                confidence="high", severity="high" if gap > GAP_CRITICAL_DAYS else "medium", sentiment="negative",
                recommendation_hint="Build a content buffer and a fixed weekly publishing cadence to avoid gaps.",
            ))  # fmt: skip
        if post["posts_per_week"] is not None and post["posts_per_week"] < MIN_POSTS_PER_WEEK:
            out.append(InsightData(
                rule_id="low_frequency", category="consistency", platform=p,
                title=f"Low posting frequency on {platform_label(p)}",
                description=f"{platform_label(p)} averaged {post['posts_per_week']} posts per week over the period.",
                metric="posts_per_week", evidence={"posts_per_week": post["posts_per_week"]},
                confidence="high", severity="medium", sentiment="negative",
                recommendation_hint="Increase to a sustainable minimum cadence before optimising content details.",
            ))  # fmt: skip
        elif post["consistency"] == "low" and gap < GAP_WARN_DAYS:
            out.append(InsightData(
                rule_id="irregular_posting", category="consistency", platform=p,
                title=f"Irregular weekly posting on {platform_label(p)}",
                description=f"Weekly post counts vary strongly (CV {post['weekly_cv']}).",
                metric="weekly_cv", evidence={"weekly_cv": post["weekly_cv"], "consistency_score": post["consistency_score"]},
                confidence="medium", severity="low", sentiment="negative",
                recommendation_hint="Batch-produce content to keep a steady weekly rhythm.",
            ))  # fmt: skip
    return out


def _best_group_findings(ctx: InsightContext, category: str, metrics: tuple[str, ...]) -> list[dict]:
    return [
        f for f in ctx.findings
        if f["category"] == category and f["metric"] in metrics and "group_a" in f["values"]
        and f["confidence"] in ("high", "medium") and (f["difference_pct"] or 0) >= 20
    ]  # fmt: skip


@rule
def format_performance(ctx: InsightContext) -> list[InsightData]:
    out = []
    seen = set()
    for f in _best_group_findings(ctx, "format", ("exposure", "er", "save_rate", "share_rate")):
        p = f["platform"]
        best = f["values"]["group_a"]
        if (p, best, f["metric"]) in seen:
            continue
        seen.add((p, best, f["metric"]))
        table = ctx.platforms[p]["formats"]["formats"]
        share = next((r["share_pct"] for r in table if r["group"] == best), None)
        underused = share is not None and share < UNDERUSED_SHARE
        out.append(InsightData(
            rule_id="format_outperforms", category="format", platform=p,
            title=f"{format_label(best)} lead on {f['values']['metric_label']} ({platform_label(p)})",
            description=f["statement"] + (f" Yet they are only {share}% of posts." if underused else ""),
            metric=f["metric"],
            evidence={"finding_id": f["id"], **f["values"], "difference_pct": f["difference_pct"],
                      "p_adjusted": f["p_adjusted"], "share_of_posts_pct": share},
            confidence=f["confidence"], severity="medium" if underused else "low", sentiment="positive",
            recommendation_hint=(f"Increase the share of {format_label(best).lower()}" if underused
                                 else f"Keep {format_label(best).lower()} as a core format") + f" on {platform_label(p)}.",
        ))  # fmt: skip
    return out


@rule
def pillar_performance(ctx: InsightContext) -> list[InsightData]:
    out = []
    seen = set()
    for f in _best_group_findings(ctx, "pillar", ("er", "save_rate", "share_rate", "click_rate", "exposure")):
        p = f["platform"]
        best = f["values"]["group_a"]
        if (p, best) in seen or p is None or best == "other":
            continue
        seen.add((p, best))
        share = ctx.platforms[p]["pillars"]["pillar_distribution"].get(best)
        if best == "promotional":
            # Promotion winning on clicks is expected; it's not a reason to post more of it
            # (the content_mix_imbalance rule handles over-promotion).
            if f["metric"] != "click_rate":
                continue
            out.append(InsightData(
                rule_id="promotional_drives_clicks", category="conversion", platform=p,
                title=f"Promotional posts drive the most clicks on {platform_label(p)}",
                description=f["statement"], metric=f["metric"],
                evidence={"finding_id": f["id"], **f["values"], "difference_pct": f["difference_pct"],
                          "p_adjusted": f["p_adjusted"], "share_of_posts_pct": share},
                confidence=f["confidence"], severity="low", sentiment="neutral",
                recommendation_hint="Keep promotional posts focused on one clear conversion action rather than increasing their volume.",
            ))  # fmt: skip
            continue
        underused = share is not None and share < UNDERUSED_SHARE
        out.append(InsightData(
            rule_id="pillar_outperforms", category="content_pillar", platform=p,
            title=f"{label(best)} content performs best on {f['values']['metric_label']} ({platform_label(p)})",
            description=f["statement"] + (f" It represents only {share}% of posts." if underused else ""),
            metric=f["metric"],
            evidence={"finding_id": f["id"], **f["values"], "difference_pct": f["difference_pct"],
                      "p_adjusted": f["p_adjusted"], "share_of_posts_pct": share},
            confidence=f["confidence"], severity="medium" if underused else "low", sentiment="positive",
            recommendation_hint=f"Give the {label(best).lower()} pillar more room in the {platform_label(p)} content mix.",
        ))  # fmt: skip
    return out


@rule
def trend_direction(ctx: InsightContext) -> list[InsightData]:
    out = []
    for f in ctx.findings:
        if f["category"] != "trend" or f["metric"] not in ("median_exposure", "median_er", "followers_gained"):
            continue
        t = f["values"]
        if t["label"] not in ("growth", "decline"):
            continue
        decline = t["label"] == "decline"
        out.append(InsightData(
            rule_id=f"trend_{t['label']}", category="trend", platform=f["platform"],
            title=f"{platform_label(f['platform'])} {f['metric'].replace('median_', '').replace('_', ' ')} is in {t['label']}",
            description=f["statement"], metric=f["metric"],
            evidence={"finding_id": f["id"], "total_change_pct": t["total_change_pct"], "weeks": t["weeks"],
                      "spearman_rho": t["spearman_rho"], "p_value": t["p_value"]},
            confidence=f["confidence"], severity="high" if decline else "low",
            sentiment="negative" if decline else "positive",
            recommendation_hint=("Investigate what changed (format mix, frequency, topics) in the declining weeks."
                                 if decline else "Identify what drove recent growth and double down on it."),
        ))  # fmt: skip
    return out


@rule
def video_retention(ctx: InsightContext) -> list[InsightData]:
    out = []
    for p, s in ctx.platforms.items():
        v = s["video"]
        if (
            v.get("video_count", 0) >= 5
            and v.get("median_completion") is not None
            and v["median_completion"] < LOW_COMPLETION
        ):
            out.append(InsightData(
                rule_id="low_video_completion", category="video", platform=p,
                title=f"Low video completion on {platform_label(p)}",
                description=f"Median completion rate is {v['median_completion']}% across {v['video_count']} videos.",
                metric="completion", evidence={"median_completion": v["median_completion"], "videos": v["video_count"]},
                confidence=sample_confidence(v["video_count"]).value, severity="medium", sentiment="negative",
                recommendation_hint="Tighten the first 2 seconds and shorten videos; front-load the payoff.",
            ))  # fmt: skip
    for f in ctx.findings:
        if (
            f["category"] == "video"
            and "short_vs_long" in f["id"]
            and f["confidence"] in ("high", "medium")
            and (f["difference_pct"] or 0) >= 15
        ):
            out.append(InsightData(
                rule_id="short_video_advantage", category="video", platform=f["platform"],
                title=f"Short videos outperform longer ones on {platform_label(f['platform'])}",
                description=f["statement"], metric=f["metric"],
                evidence={"finding_id": f["id"], **f["values"], "difference_pct": f["difference_pct"], "p_adjusted": f["p_adjusted"]},
                confidence=f["confidence"], severity="low", sentiment="positive",
                recommendation_hint=f"Default to videos of {f['values']['short_max_seconds']}s or less on {platform_label(f['platform'])}.",
            ))  # fmt: skip
    return out


@rule
def timing_windows(ctx: InsightContext) -> list[InsightData]:
    out = []
    for f in ctx.findings:
        if f["category"] == "timing" and f["confidence"] in ("high", "medium") and (f["difference_pct"] or 0) >= 15:
            out.append(InsightData(
                rule_id="timing_window", category="timing", platform=f["platform"],
                title=f"Stronger results {('on ' + f['values']['best']) if 'dow' in f['id'] else ('in the ' + f['values']['best'].replace('_', ' '))} ({platform_label(f['platform'])})",
                description=f["statement"], metric=f["metric"],
                evidence={"finding_id": f["id"], **f["values"], "difference_pct": f["difference_pct"], "p_adjusted": f["p_adjusted"]},
                confidence=f["confidence"], severity="low", sentiment="positive",
                recommendation_hint="Schedule key posts in this window and keep testing - timing effects can shift.",
            ))  # fmt: skip
    return out


@rule
def hook_and_cta_effects(ctx: InsightContext) -> list[InsightData]:
    out = []
    for f in ctx.findings:
        if (
            f["category"] in ("hook", "cta")
            and f["confidence"] in ("high", "medium")
            and (f["difference_pct"] or 0) >= 15
        ):
            what = "Opening hooks" if f["category"] == "hook" else "Calls-to-action"
            out.append(InsightData(
                rule_id=f"{f['category']}_effect", category=f["category"], platform=f["platform"],
                title=f"{what} lift results on {platform_label(f['platform'])}",
                description=f["statement"], metric=f["metric"],
                evidence={"finding_id": f["id"], **f["values"], "difference_pct": f["difference_pct"], "p_adjusted": f["p_adjusted"]},
                confidence=f["confidence"], severity="low", sentiment="positive",
                recommendation_hint=f"Make {what.lower()} a standard part of every {platform_label(f['platform'])} post.",
            ))  # fmt: skip
    return out


@rule
def low_diversity(ctx: InsightContext) -> list[InsightData]:
    out = []
    for p, s in ctx.platforms.items():
        fd = s["pillars"]["format_diversity"]
        if fd is not None and fd < LOW_DIVERSITY and s["formats"]["format_count"] <= 2 and p != "tiktok":
            out.append(InsightData(
                rule_id="low_format_diversity", category="content_mix", platform=p,
                title=f"Limited format variety on {platform_label(p)}",
                description=f"Format diversity score is {fd}/100 ({s['formats']['format_count']} formats used).",
                metric="format_diversity", evidence={"format_diversity": fd, "formats": [r["group"] for r in s["formats"]["formats"]]},
                confidence="medium", severity="low", sentiment="negative",
                recommendation_hint="Test additional native formats to find untapped reach.",
            ))  # fmt: skip
    return out


@rule
def awareness_without_traffic(ctx: InsightContext) -> list[InsightData]:
    rows = [r for r in ctx.cross_platform.get("platforms", []) if r.get("clicks_per_1k_exposure") is not None]
    if len(rows) < 2:
        return []
    shares = sorted(r["share_rate_median"] or 0 for r in ctx.cross_platform["platforms"])
    median_share = shares[len(shares) // 2]
    worst_clicks = min(rows, key=lambda r: r["clicks_per_1k_exposure"])
    if (worst_clicks["share_rate_median"] or 0) >= median_share:
        p = worst_clicks["platform"]
        return [InsightData(
            rule_id="awareness_without_traffic", category="conversion", platform=p,
            title=f"{platform_label(p)} spreads well but drives little traffic",
            description=(
                f"{platform_label(p)} has an above-median share rate ({worst_clicks['share_rate_median']}%) but the lowest "
                f"click efficiency ({worst_clicks['clicks_per_1k_exposure']} clicks per 1,000 exposures)."
            ),
            metric="clicks_per_1k_exposure",
            evidence={"share_rate_median": worst_clicks["share_rate_median"], "clicks_per_1k_exposure": worst_clicks["clicks_per_1k_exposure"]},
            confidence="medium", severity="medium" if set(ctx.objectives) & CLICK_OBJECTIVES else "low", sentiment="neutral",
            recommendation_hint="Awareness is working; add conversion paths (link-in-bio offers, DM keywords, lead magnets).",
        )]  # fmt: skip
    return []


@rule
def missing_measurement(ctx: InsightContext) -> list[InsightData]:
    if not set(ctx.objectives) & CLICK_OBJECTIVES:
        return []
    out = []
    for p, s in ctx.platforms.items():
        if "total_clicks" in s["kpis"]["unavailable"]:
            out.append(InsightData(
                rule_id="missing_click_data", category="data_quality", platform=p,
                title=f"Traffic can't be measured on {platform_label(p)}",
                description=f"The {platform_label(p)} export has no click data, so traffic/lead impact is unknown.",
                metric="clicks", evidence={"unavailable": s["kpis"]["unavailable"]["total_clicks"]},
                confidence="high", severity="medium", sentiment="neutral",
                recommendation_hint="Use UTM-tagged links and include link-click columns in exports.",
            ))  # fmt: skip
    return out


@rule
def cross_platform_opportunities(ctx: InsightContext) -> list[InsightData]:
    out = []
    ans = ctx.cross_platform.get("answers", {})
    u = ans.get("underutilized")
    if u:
        out.append(InsightData(
            rule_id="underutilized_platform", category="cross_platform", platform=u["platform"],
            title=f"{u['label']} looks underutilized", description=u["reason"], metric="efficiency_vs_effort",
            evidence=u, confidence="medium", severity="medium", sentiment="positive",
            recommendation_hint=f"Shift some production effort to {u['label']} and measure the marginal return.",
        ))  # fmt: skip
    best = ans.get("strongest_relative_engagement")
    if best:
        out.append(InsightData(
            rule_id="engagement_leader", category="cross_platform", platform=best["platform"],
            title=f"{best['label']} has the strongest relative engagement",
            description=(f"{best['label']} has the highest median engagement rate relative to its own exposure metric "
                         f"({best['value']}%). Exposure definitions differ by platform."),
            metric="median_er", evidence=best, confidence="medium", severity="info", sentiment="positive",
        ))  # fmt: skip
    return out


@rule
def viral_outliers(ctx: InsightContext) -> list[InsightData]:
    out = []
    for p, s in ctx.platforms.items():
        over = s["anomalies"]["metrics"].get("exposure", {}).get("over_performers", [])
        if over:
            out.append(InsightData(
                rule_id="viral_outliers", category="content", platform=p,
                title=f"{len(over)} breakout post(s) on {platform_label(p)}",
                description=(f"{len(over)} {platform_label(p)} post(s) reached far above normal (robust z > 3). "
                             f"Top: \"{over[0]['caption'][:80]}\" ({over[0]['format']}, {over[0]['exposure']:,.0f})."),
                metric="exposure", evidence={"posts": [{k: o[k] for k in ("external_post_id", "format", "pillar", "exposure", "z_score")} for o in over]},
                confidence="medium", severity="info", sentiment="positive",
                recommendation_hint="Deconstruct breakout posts (hook, format, topic) and create deliberate variations.",
            ))  # fmt: skip
    return out


SEVERITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}


def generate_insights(ctx: InsightContext) -> list[InsightData]:
    insights: list[InsightData] = []
    for r in RULES:
        insights.extend(r(ctx))
    insights.sort(key=lambda i: (SEVERITY_ORDER[i.severity], i.sentiment != "negative", i.platform or ""))
    return insights
