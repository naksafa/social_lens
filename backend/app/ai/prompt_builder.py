"""Builds the compact, structured analytics summary the LLM receives.

The LLM never sees raw exports. It receives verified numbers computed by the
analytics engine, grouped in the sections below, with every statistical finding
carrying its sample size, adjusted p-value and confidence. IDs (finding / insight)
are included so the model can cite its evidence and the app can trace it back.
"""

import json
from typing import Any

from app.analytics.common import platform_label

MAX_FINDINGS = 45
MAX_LOW_CONFIDENCE_FINDINGS = 10
KPI_KEYS = (
    "total_posts", "posts_per_week", "total_reach", "median_reach", "total_impressions", "total_views",
    "median_views", "total_engagement", "engagement_rate", "median_engagement_rate", "follower_growth",
    "total_clicks", "ctr", "share_rate", "save_rate", "total_shares", "total_saves", "video_posts",
    "median_completion_rate", "avg_watch_time_seconds", "median_performance_index",
)  # fmt: skip


def _slim_table(rows: list[dict], keys: tuple[str, ...], limit: int = 8) -> list[dict]:
    return [{k: r.get(k) for k in ("group", "count", "share_pct", *keys) if r.get(k) is not None} for r in rows[:limit]]


def _post_brief(p: dict) -> dict:
    return {
        k: p.get(k)
        for k in (
            "external_post_id",
            "format",
            "pillar",
            "hook_type",
            "cta_type",
            "exposure",
            "er",
            "shares",
            "saves",
            "clicks",
            "completion",
            "performance_index",
            "caption",
        )  # fmt: skip
        if p.get(k) is not None
    }


def business_context(project: Any) -> dict:
    bp = project.business_profile
    ctx = {"project": project.name, "timezone": project.timezone, "platforms": project.platforms}
    if bp:
        ctx.update(
            business_name=bp.business_name,
            industry=bp.industry,
            country=bp.country,
            city_market=bp.city_market,
            products_services=bp.products_services,
            target_audience=bp.target_audience,
            business_objective=bp.business_objective,
            marketing_objectives=bp.marketing_objectives,
            competitors=bp.competitors,
            monthly_budget=f"{bp.monthly_budget} {bp.budget_currency or ''}".strip()
            if bp.monthly_budget
            else "not provided",
            current_posting_frequency=bp.current_posting_frequency,
        )
    return ctx


def build_analytics_summary(sections: dict, insights: list[dict], run_meta: dict) -> dict:
    overview = sections["overview"]
    platforms_out = {}
    for p, s in sections["platforms"].items():
        k = s["kpis"]
        top = s["top_content"]
        platforms_out[p] = {
            "platform": platform_label(p),
            "exposure_metric": s["exposure_metric"],
            "engagement_formula": f"({' + '.join(k['engagement_components'])}) / {s['exposure_metric']} x 100",
            "kpis": {key: k["metrics"][key] for key in KPI_KEYS if key in k["metrics"]},
            "unavailable_metrics": k["unavailable"],
            "posting": {
                key: s["posting"][key]
                for key in (
                    "posts_per_week",
                    "consistency",
                    "consistency_score",
                    "longest_gap_days",
                    "active_weeks_pct",
                    "inactivity_periods",
                )
            },  # fmt: skip
            "formats": _slim_table(
                s["formats"]["formats"],
                ("median_exposure", "median_er", "median_save_rate", "median_share_rate", "median_performance_index"),
            ),
            "pillar_mix_pct": s["pillars"]["pillar_distribution"],
            "pillars": _slim_table(
                s["pillars"]["pillars"],
                ("median_exposure", "median_er", "median_save_rate", "median_share_rate", "median_click_rate"),
            ),
            "cta_usage_pct": s["hooks_ctas"]["cta_usage_pct"],
            "hook_mix_pct": s["hooks_ctas"]["hook_distribution"],
            "timing": {
                "has_time_of_day": s["timing"]["has_time"],
                "by_day": _slim_table(s["timing"]["by_day"], ("median_er", "median_exposure"), 7),
                "by_hour_block": _slim_table(s["timing"]["by_hour_block"], ("median_er", "median_exposure"), 6),
            },
            "trends": {
                m: {kk: t.get(kk) for kk in ("label", "total_change_pct", "weeks", "p_value")}
                for m, t in s["trends"]["trends"].items()
            },  # fmt: skip
            "video": {kk: v for kk, v in s["video"].items() if kk not in ("scatter",)},
            "top_posts": [_post_brief(x) for x in top["top_by_performance_index"][:3]],
            "bottom_posts": [_post_brief(x) for x in top["bottom_by_performance_index"][:3]],
            "audience_signals": [sig["description"] for sig in s["audience"]["signals"]],
            "regression": (s["statistics"].get("regression") or {}).get("r_squared"),
        }

    findings = sections.get("findings", [])
    strong = [f for f in findings if f["confidence"] in ("high", "medium")][:MAX_FINDINGS]
    weak = [f for f in findings if f["confidence"] == "low"][:MAX_LOW_CONFIDENCE_FINDINGS]
    slim_findings = [
        {
            "id": f["id"],
            "platform": f["platform"],
            "statement": f["statement"],
            "confidence": f["confidence"],
            "sample_size": f["sample_size"],
            "p_adjusted": f["p_adjusted"],
            "effect_size": f["effect_size"],
            "difference_pct": f["difference_pct"],
        }
        for f in (*strong, *weak)
    ]
    return {
        "analysis": {
            "analysis_version": run_meta.get("analysis_version"),
            "period": f"{overview['period_start']} to {overview['period_end']} ({overview['period_days']} days)",
            "total_posts": overview["total_posts"],
            "posts_by_platform": overview["posts_by_platform"],
            "objective_weights": sections.get("scoring", {}).get("weights"),
        },
        "platforms": platforms_out,
        "cross_platform": {
            "methodology": sections["cross_platform"]["methodology"],
            "comparison": sections["cross_platform"]["platforms"],
            "answers": {
                k: (v or {}).get("label")
                and {"platform": v["label"], "value": v.get("value"), "reason": v.get("reason")}
                for k, v in sections["cross_platform"]["answers"].items()
            },  # fmt: skip
        },
        "statistical_findings": slim_findings,
        "rule_based_insights": [
            {
                kk: i[kk]
                for kk in (
                    "id",
                    "rule_id",
                    "platform",
                    "title",
                    "description",
                    "confidence",
                    "severity",
                    "sentiment",
                    "recommendation_hint",
                )
            }  # fmt: skip
            for i in insights
        ],
    }


def render_payload(business: dict, summary: dict, instructions: str | None, extra: dict | None = None) -> str:
    blocks = [
        "<business_context>\n" + json.dumps(business, ensure_ascii=False, default=str) + "\n</business_context>",
        "<verified_analytics>\n" + json.dumps(summary, ensure_ascii=False, default=str) + "\n</verified_analytics>",
    ]
    for tag, value in (extra or {}).items():
        blocks.append(f"<{tag}>\n" + json.dumps(value, ensure_ascii=False, default=str) + f"\n</{tag}>")
    blocks.append(
        "<user_instructions>\n"
        + (instructions.strip() if instructions and instructions.strip() else "None provided.")
        + "\n</user_instructions>"
    )
    return "\n\n".join(blocks)
