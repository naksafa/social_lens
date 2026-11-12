"""Deterministic (no-LLM) composer for audit, strategy and content plan.

Used when no AI provider is configured (e.g. offline demos). It assembles the same
output schemas purely from rule-based insights, statistical findings and KPIs using
templates - so every statement is traceable, but the writing is plainer and the
creative parts (hooks, concepts) are template-driven. Outputs are labelled
``generated_by = "rules"`` everywhere they are displayed.
"""

import re
from datetime import date, timedelta
from itertools import cycle

from app.ai.schemas import (
    AuditOutput,
    AuditPoint,
    ContentIdea,
    ContentPillarDef,
    ContentPlanEntry,
    ContentPlanOutput,
    MeasurementItem,
    PillarShare,
    PlatformAudit,
    PlatformStrategy,
    Recommendation,
    StrategicObjective,
    StrategyOutput,
    WeeklyActions,
)
from app.analytics.common import format_label, label, platform_label

IMPACT = {"critical": "high", "high": "high", "medium": "medium", "low": "low", "info": "low"}
PRIORITY = {"critical": "critical", "high": "high", "medium": "medium", "low": "low", "info": "low"}
EFFORT_BY_CATEGORY = {"cta": "low", "timing": "low", "data_quality": "low", "consistency": "medium",
                      "content_mix": "medium", "format": "medium", "content_pillar": "medium", "video": "medium",
                      "trend": "medium", "cross_platform": "high", "conversion": "medium", "content": "low"}  # fmt: skip
OPPORTUNITY_RULES = {"format_outperforms", "pillar_outperforms", "underutilized_platform", "viral_outliers",
                     "awareness_without_traffic", "short_video_advantage", "timing_window", "hook_effect", "cta_effect"}  # fmt: skip
RISK_RULES = {"trend_decline", "missing_click_data", "low_video_completion", "posting_gap"}
FREQUENCY_RANGE = {"instagram": (4, 7), "tiktok": (4, 7), "linkedin": (3, 5), "facebook": (3, 5)}
PLATFORM_ROLES = {
    "instagram": ("Brand showcase and community hub", "Grow engaged reach with saveable, shareable content"),
    "tiktok": ("Top-of-funnel reach and discovery", "Reach new audiences with native short video"),
    "linkedin": ("Authority, trust and B2B lead generation", "Build credibility with decision-makers and drive leads"),
    "facebook": ("Community, local awareness and retargeting", "Keep existing customers engaged and informed"),
}
OBJECTIVE_KPIS = {
    "brand_awareness": ("Grow reach among the target audience", "median reach / views per post"),
    "engagement": ("Increase meaningful interactions", "median engagement rate"),
    "lead_generation": ("Generate qualified leads from social", "clicks and leads per week"),
    "sales": ("Drive sales attributable to social", "conversions and click-through rate"),
    "website_traffic": ("Send more visitors to the website", "clicks per 1,000 exposures"),
    "store_visits": ("Increase store visits", "saves, shares and local engagement"),
    "community_growth": ("Build an active community", "comment rate and follower growth"),
    "follower_growth": ("Grow the follower base", "followers gained per 1,000 exposures"),
    "video_views": ("Increase video views and retention", "median views and completion rate"),
}
PILLAR_TOPICS = {
    "educational": ["How-to guide on {x}", "Common mistakes with {x}", "Myth vs. fact: {x}"],
    "social_proof": ["Client result story: {x}", "Before/after with {x}", "Testimonial spotlight: {x}"],
    "entertainment": ["Relatable moment about {x}", "Trend remix featuring {x}", "Day-in-the-life with {x}"],
    "brand": ["Behind the scenes of {x}", "Meet the team behind {x}", "Our process for {x}"],
    "community": ["Ask the audience about {x}", "Community spotlight: {x}", "Poll: your take on {x}"],
    "promotional": ["Offer: {x}", "Why choose our {x}", "Limited spots for {x}"],
    "other": ["Update on {x}"],
}
PILLAR_HOOKS = {
    "educational": [
        "3 mistakes people make with {x}",
        "Stop doing this with {x}",
        "How to get more from {x} in 60 seconds",
    ],
    "social_proof": [
        "How we helped a client with {x}",
        "This result surprised even us",
        "What changed after 30 days of {x}",
    ],
    "entertainment": [
        "POV: you just discovered {x}",
        "Tell me you need {x} without telling me",
        "Nobody talks about this part of {x}",
    ],
    "brand": ["What really happens behind the scenes", "Here's how we do {x}", "Meet the people behind {x}"],
    "community": ["Which one are you?", "We need your opinion on {x}", "Shout-out to our community"],
    "promotional": [
        "Only a few spots left for {x}",
        "The easiest way to start with {x}",
        "Here's what you get with {x}",
    ],
    "other": ["Quick update"],
}
PILLAR_CTA = {"educational": "Save this for later", "social_proof": "Book a free call", "entertainment": "Share with a friend",
              "brand": "Follow for more", "community": "Comment below", "promotional": "DM us to get started", "other": "Follow for more"}  # fmt: skip
PILLAR_OBJECTIVE = {"educational": ("Saves & authority", "save rate"), "social_proof": ("Trust & leads", "click rate"),
                    "entertainment": ("Reach & shares", "share rate"), "brand": ("Connection", "engagement rate"),
                    "community": ("Conversation", "comment rate"), "promotional": ("Conversions", "clicks / leads"),
                    "other": ("Awareness", "reach")}  # fmt: skip


def _point(i: dict) -> AuditPoint:
    ev = i.get("evidence") or {}
    refs = [i["id"]] + ([ev["finding_id"]] if ev.get("finding_id") else [])
    return AuditPoint(
        title=i["title"],
        explanation=i["description"],
        evidence=i["description"],
        evidence_refs=refs,
        platform=i["platform"] or "all",
        impact=IMPACT.get(i["severity"], "medium"),  # type: ignore[arg-type]
        confidence=i["confidence"],
        basis="data_backed",
    )


def _recommendation(i: dict) -> Recommendation:
    return Recommendation(
        title=i.get("recommendation_hint") or i["title"],
        explanation=i["description"],
        evidence=i["description"],
        evidence_refs=[i["id"]],
        platform=i["platform"] or "all",
        priority=PRIORITY.get(i["severity"], "medium"),  # type: ignore[arg-type]
        impact=IMPACT.get(i["severity"], "medium"),  # type: ignore[arg-type]
        effort=EFFORT_BY_CATEGORY.get(i["category"], "medium"),  # type: ignore[arg-type]
        confidence=i["confidence"],
        basis="data_backed",
    )


def _pattern_points(findings: list[dict], best: bool) -> list[AuditPoint]:
    out = []
    for f in findings:
        if f["category"] not in ("format", "pillar", "hook", "video", "timing") or f["confidence"] == "low":
            continue
        if "group_a" not in f["values"] and f["category"] in ("format", "pillar"):
            continue
        if f["category"] in ("format", "pillar"):
            grp = f["values"]["group_a"] if best else f["values"]["group_b"]
            name = format_label(grp) if f["category"] == "format" else f"{label(grp)} content"
            title = f"{name} {'lead' if best else 'trail'} on {f['values']['metric_label']} ({platform_label(f['platform'])})"
        elif not best:
            continue
        else:
            title = f"{label(f['category'])} pattern on {platform_label(f['platform'])}"
        out.append(AuditPoint(
            title=title, explanation=f["statement"], evidence=f["statement"], evidence_refs=[f["id"]],
            platform=f["platform"] or "all", impact="medium", confidence=f["confidence"], basis="data_backed",
        ))  # fmt: skip
        if len(out) >= 6:
            break
    return out


def compose_audit(business: dict, sections: dict, insights: list[dict]) -> AuditOutput:
    findings = sections.get("findings", [])
    positives = [i for i in insights if i["sentiment"] == "positive"]
    negatives = [i for i in insights if i["sentiment"] == "negative"]
    platforms = sections["platforms"]

    platform_audits = []
    limitations: list[str] = []
    for p, s in platforms.items():
        m = s["kpis"]["metrics"]
        er = m.get("median_engagement_rate")
        trend = s["trends"]["trends"].get("median_exposure", {}).get("label", "n/a")
        mine = [i for i in insights if i["platform"] == p]
        unavailable = [f"{k.replace('_', ' ')}: {v}" for k, v in s["kpis"]["unavailable"].items()]
        limitations += [f"{platform_label(p)} - {u}" for u in unavailable[:3]]
        platform_audits.append(PlatformAudit(
            platform=p,
            summary=(f"{m['total_posts']} posts ({m['posts_per_week']}/week), median engagement rate "
                     f"{er if er is not None else 'n/a'}% on {s['exposure_metric'] or 'no exposure metric'}."),
            performance_assessment=(f"Weekly {s['exposure_metric'] or 'exposure'} trend: {trend}. Posting consistency: "
                                    f"{s['posting']['consistency']} (score {s['posting']['consistency_score']}/100)."),
            strengths=[i["title"] for i in mine if i["sentiment"] == "positive"][:5],
            weaknesses=[i["title"] for i in mine if i["sentiment"] == "negative"][:5],
            data_limitations=unavailable[:6],
        ))  # fmt: skip

    content_gaps = []
    for p, s in platforms.items():
        dist = s["pillars"]["pillar_distribution"]
        for pillar in ("educational", "social_proof", "community"):
            share = dist.get(pillar, 0) or 0
            if share < 10:
                content_gaps.append(AuditPoint(
                    title=f"Little {label(pillar).lower()} content on {platform_label(p)}",
                    explanation=f"{label(pillar)} posts are {share}% of {platform_label(p)} content.",
                    evidence=f"Pillar mix on {platform_label(p)}: {dist}",
                    platform=p, impact="medium", confidence="medium", basis="data_backed",
                ))  # fmt: skip

    audience = []
    for p, s in platforms.items():
        for sig in s["audience"]["signals"][:2]:
            audience.append(AuditPoint(
                title=f"{platform_label(p)}: {sig['signal'].replace('_', ' ')}", explanation=sig["description"],
                evidence=sig["description"], platform=p, impact="medium", confidence="medium", basis="data_backed",
            ))  # fmt: skip

    top_neg = negatives[:3]
    top_pos = positives[:3]
    ov = sections["overview"]
    summary = (
        f"This audit of {business.get('business_name', 'the business')} covers {ov['total_posts']} posts across "
        f"{len(platforms)} platform(s) from {ov['period_start']} to {ov['period_end']}. "
        + (f"The most pressing issues: {'; '.join(i['title'] for i in top_neg)}. " if top_neg else "")
        + (f"Strengths to build on: {'; '.join(i['title'] for i in top_pos)}. " if top_pos else "")
        + "Recommendations below are ranked by impact and tied to the supporting analytics. "
        "This summary was generated by the rule-based engine (no AI provider configured)."
    )
    return AuditOutput(
        executive_summary=summary,
        overall_findings=[_point(i) for i in insights if i["severity"] in ("critical", "high", "medium")][:8],
        platform_audits=platform_audits,
        strengths=[_point(i) for i in positives][:8],
        weaknesses=[_point(i) for i in negatives][:8],
        opportunities=[_point(i) for i in insights if i["rule_id"] in OPPORTUNITY_RULES][:8],
        risks=[_point(i) for i in insights if i["rule_id"] in RISK_RULES][:6],
        content_gaps=content_gaps[:8],
        best_content_patterns=_pattern_points(findings, best=True),
        worst_content_patterns=_pattern_points(findings, best=False),
        audience_insights=audience[:8],
        priority_actions=[_recommendation(i) for i in negatives + [i for i in positives if i["severity"] == "medium"]][
            :8
        ],
        data_limitations=limitations[:10] or ["No major data gaps detected."],
    )


def _normalize_mix(weights: dict[str, float]) -> list[PillarShare]:
    total = sum(weights.values()) or 1
    raw = {k: v / total * 100 for k, v in weights.items() if v > 0}
    floored = {k: int(v) for k, v in raw.items()}
    remainder = 100 - sum(floored.values())
    for k in sorted(raw, key=lambda k: raw[k] - floored[k], reverse=True)[:remainder]:
        floored[k] += 1
    return [PillarShare(pillar=k, share_pct=v) for k, v in sorted(floored.items(), key=lambda kv: -kv[1]) if v > 0]


def _recommended_mix(s: dict, objectives: list[str]) -> list[PillarShare]:
    dist = {k: float(v or 0) for k, v in s["pillars"]["pillar_distribution"].items() if k != "other"}
    perf = {
        r["group"]: r.get("median_er") or 0
        for r in s["pillars"]["pillars"]
        if not r["low_sample"] and r["group"] != "other"
    }
    weights = dict(dist)
    for k, _ in sorted(perf.items(), key=lambda kv: -kv[1])[:2]:
        weights[k] = weights.get(k, 0) + 15  # scale up the best-performing pillars
    weights["educational"] = max(weights.get("educational", 0), 20)
    if {"lead_generation", "sales"} & set(objectives):
        weights["social_proof"] = max(weights.get("social_proof", 0), 15)
    promo_cap = 25.0
    total = sum(weights.values())
    if weights.get("promotional", 0) / total * 100 > promo_cap:
        weights["promotional"] = promo_cap / 100 * (total - weights["promotional"]) / (1 - promo_cap / 100)
    return _normalize_mix(weights)


def compose_strategy(business: dict, sections: dict, insights: list[dict], audit: AuditOutput) -> StrategyOutput:
    objectives = business.get("marketing_objectives") or []
    platforms = sections["platforms"]
    underused = (sections["cross_platform"]["answers"].get("underutilized") or {}).get("platform")
    strategies, measurement = [], []
    for p, s in platforms.items():
        cur = s["posting"]["posts_per_week"] or 0
        lo, hi = FREQUENCY_RANGE.get(p, (3, 5))
        target = min(max(round(cur), lo), hi)
        formats = sorted(
            (r for r in s["formats"]["formats"] if not r["low_sample"]),
            key=lambda r: r.get("median_performance_index") or 0, reverse=True,
        )  # fmt: skip
        role, goal = PLATFORM_ROLES.get(p, ("Supporting channel", "Maintain presence"))
        cta_usage = s["hooks_ctas"]["cta_usage_pct"]
        refs = [i["id"] for i in insights if i["platform"] == p][:5]
        strategies.append(PlatformStrategy(
            platform=p, role=role + (" (underutilized - grow)" if p == underused else ""), goal=goal,
            formats=[format_label(r["group"]) for r in formats[:3]] or ["Test 2-3 native formats"],
            posting_frequency=f"{target} posts/week (currently {cur})",
            content_mix=_recommended_mix(s, objectives),
            hook_guidance="Open with a specific promise, number or question in the first line/2 seconds.",
            cta_approach=(f"CTA usage is {cta_usage}% today; use one clear CTA per post matched to its goal "
                          "(save/share for reach posts, link/DM/booking for conversion posts)."),
            video_guidance=(f"Median completion {s['video'].get('median_completion')}%; keep videos short and front-load the payoff."
                            if s["video"].get("video_count", 0) >= 5 else "Test short native video; too little video history to judge."),
            community_approach="Reply to comments within 24h and turn frequent questions into content.",
            rationale=f"Based on {s['kpis']['metrics']['total_posts']} posts of history on {platform_label(p)}.",
            evidence_refs=refs,
        ))  # fmt: skip
        m = s["kpis"]["metrics"]
        measurement.append(MeasurementItem(
            kpi="Median engagement rate", platform=p, definition=f"engagement / {s['exposure_metric']} x 100 per post",
            baseline=f"{m['median_engagement_rate']}%" if m.get("median_engagement_rate") is not None else "not available",
            target_direction="increase", review_cadence="weekly",
        ))  # fmt: skip
        if m.get("total_clicks") is not None:
            measurement.append(MeasurementItem(
                kpi="Clicks", platform=p, definition="link/website clicks per week",
                baseline=f"{m['total_clicks']} total over the period", target_direction="increase", review_cadence="weekly",
            ))  # fmt: skip

    pillar_totals: dict[str, int] = {}
    for st in strategies:
        for ps in st.content_mix:
            pillar_totals[ps.pillar] = pillar_totals.get(ps.pillar, 0) + ps.share_pct
    pillars = [
        ContentPillarDef(
            name=label(k), description=f"{label(k)} content tailored to {business.get('target_audience', 'the audience')}.",
            target_share_pct=round(v / max(len(strategies), 1)), rationale="Weighted by historical engagement and objectives.",
            example_topics=[t.format(x=_subject(business, i)) for i, t in enumerate(PILLAR_TOPICS.get(k, PILLAR_TOPICS["other"]))],
        )
        for k, v in sorted(pillar_totals.items(), key=lambda kv: -kv[1])
    ]  # fmt: skip

    negatives = [i for i in insights if i["sentiment"] == "negative"]
    wins = [i for i in insights if i["sentiment"] == "positive"]
    weeks = [
        WeeklyActions(week=1, focus="Fix the fundamentals",
                      actions=[i["recommendation_hint"] for i in negatives[:4] if i.get("recommendation_hint")] or ["Set a fixed weekly publishing cadence"]),
        WeeklyActions(week=2, focus="Rebalance content mix and formats",
                      actions=[f"Apply the new pillar mix on {platform_label(s.platform)}" for s in strategies][:4]),
        WeeklyActions(week=3, focus="Scale what works",
                      actions=[i["recommendation_hint"] for i in wins[:4] if i.get("recommendation_hint")] or ["Double down on top formats"]),
        WeeklyActions(week=4, focus="Measure and iterate",
                      actions=["Compare week-4 KPIs to the baselines above", "Re-run the analysis with the new data", "Keep winners, drop underperformers"]),
    ]  # fmt: skip
    return StrategyOutput(
        strategy_summary=(
            f"A 30-day plan for {business.get('business_name', 'the business')} focused on "
            f"{', '.join(o.replace('_', ' ') for o in objectives) or 'balanced growth'}: fix consistency and content-mix "
            "issues first, shift effort toward the formats and pillars that perform best in the data, and measure weekly. "
            "Generated by the rule-based engine (no AI provider configured)."
        ),
        strategic_objectives=[
            StrategicObjective(
                objective=OBJECTIVE_KPIS[o][0],
                kpi=OBJECTIVE_KPIS[o][1],
                target="Improve vs. current baseline over 30 days",
                timeframe="30 days",
            )
            for o in objectives
            if o in OBJECTIVE_KPIS
        ],  # fmt: skip
        platform_strategies=strategies,
        content_pillars=pillars,
        format_strategy="Prioritize each platform's top formats by performance index; keep ~20% of posts for format tests.",
        video_strategy="Favor short, native video with a strong hook; review completion weekly.",
        caption_strategy="Lead with the hook, deliver one idea, end with one CTA; keep hashtags relevant and few.",
        cta_strategy="Match the CTA to the post goal; conversion CTAs on promotional and social-proof posts only.",
        community_strategy="Respond to comments and DMs within 24h; feature customers and community voices.",
        growth_strategy="Grow reach on the discovery platform, convert on the authority platform, retain on community platforms.",
        audience_strategy=f"Speak to {business.get('target_audience', 'the target audience')} with problem-first, specific content.",
        measurement_plan=measurement,
        action_plan_30_days=weeks,
        recommendations=audit.priority_actions,
        assumptions=["Frequency ranges are general best-practice guidance, not derived from this dataset."],
    )


def _subject(business: dict, i: int) -> str:
    parts = [p.strip() for p in re.split(r"[,;/]| and ", business.get("products_services") or "") if p.strip()]
    return (parts[i % len(parts)] if parts else "our services").lower()


def _frequency(strategy: PlatformStrategy) -> int:
    m = re.match(r"\s*(\d+)", strategy.posting_frequency)
    return int(m.group(1)) if m else 3


def compose_content_plan(business: dict, sections: dict, strategy: StrategyOutput, start: date) -> ContentPlanOutput:
    entries: list[ContentPlanEntry] = []
    for offset, st in enumerate(strategy.platform_strategies):
        per_week = _frequency(st)
        n = round(per_week * 30 / 7)
        slots = sorted({int(round(i * 30 / n + offset)) % 30 for i in range(n)})
        pillar_seq: list[str] = []
        for ps in st.content_mix:
            pillar_seq += [ps.pillar] * max(1, round(ps.share_pct / 10))
        pillars = cycle(pillar_seq or ["educational"])
        formats = cycle(st.formats or ["Post"])
        for k, day_idx in enumerate(slots):
            pillar = next(pillars)
            subj = _subject(business, k + offset)
            hooks = PILLAR_HOOKS.get(pillar, PILLAR_HOOKS["other"])
            topics = PILLAR_TOPICS.get(pillar, PILLAR_TOPICS["other"])
            obj, kpi = PILLAR_OBJECTIVE.get(pillar, PILLAR_OBJECTIVE["other"])
            fmt = next(formats)
            entries.append(ContentPlanEntry(
                day=day_idx + 1, date=(start + timedelta(days=day_idx)).isoformat(), platform=st.platform,
                pillar=label(pillar), format=fmt, topic=topics[k % len(topics)].format(x=subj),
                hook=hooks[k % len(hooks)].format(x=subj),
                concept=f"{fmt} for {platform_label(st.platform)}: {topics[k % len(topics)].format(x=subj).lower()}, "
                        f"aimed at {business.get('target_audience', 'the audience')}.",
                cta=PILLAR_CTA.get(pillar, "Follow for more"), objective=obj, kpi=kpi,
            ))  # fmt: skip
    entries.sort(key=lambda e: (e.day, e.platform))

    ideas = []
    for i, f in enumerate(
        [f for f in sections.get("findings", []) if f["category"] in ("format", "pillar") and f["confidence"] != "low"][
            :10
        ]
    ):
        grp = f["values"].get("group_a", "content")
        pillar = grp if f["category"] == "pillar" else "educational"
        fmt = format_label(grp) if f["category"] == "format" else "Post"
        subj = _subject(business, i)
        ideas.append(ContentIdea(
            title=PILLAR_TOPICS.get(pillar, PILLAR_TOPICS["other"])[i % 3 if pillar in PILLAR_TOPICS else 0].format(x=subj),
            platform=f["platform"] or "all", format=fmt, pillar=label(pillar),
            hook=PILLAR_HOOKS.get(pillar, PILLAR_HOOKS["other"])[0].format(x=subj),
            concept=f"Build on the pattern: {f['statement']}", caption_direction="Hook, one clear idea, single CTA.",
            cta=PILLAR_CTA.get(pillar, "Follow for more"), goal=PILLAR_OBJECTIVE.get(pillar, PILLAR_OBJECTIVE["other"])[0],
            based_on=f["id"],
        ))  # fmt: skip
    return ContentPlanOutput(
        plan_summary=f"{len(entries)} posts over 30 days starting {start.isoformat()}, following the strategy's frequencies and pillar mix.",
        entries=entries,
        ideas=ideas,
        notes=[
            "Generated by the rule-based engine (no AI provider configured); hooks and concepts are templates to adapt."
        ],
    )
