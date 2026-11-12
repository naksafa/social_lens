"""Synthetic social media dataset generator.

Performance model (per post)::

    base         = starting followers * platform_reach_ratio
    reach        = base * format_mult * topic_mult * hook_mult * weekday_mult * hour_mult
                        * trend(t) * LogNormal(0, sigma_platform) [* viral boost, 2% of posts]
    ER           = base_ER * format_ER * topic_ER * hook_ER * LogNormal(0, 0.35)
    engagement   = exposure * ER, split into likes/comments/shares/saves using
                   topic-specific component weights, each drawn from a Poisson.

Effects are *tendencies*, not rules: noise (sigma 0.45-0.95 on log scale) is large
enough that patterns only emerge statistically over many posts - exactly what the
analytics engine must detect. Everything is driven by a seeded ``numpy.random.Generator``
so datasets are reproducible.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

from app.core.enums import Platform
from app.synthetic.captions import build_caption
from app.synthetic.profiles import DemoBusiness, PlatformPlan


@dataclass(frozen=True)
class PlatformModel:
    exposure: str  # metric that engagement is relative to: reach | views | impressions
    reach_ratio: float
    sigma: float
    base_er: float
    format_reach: dict[str, float]
    format_er: dict[str, float]
    click_rate: float
    follow_rate: float
    reports_saves: bool
    hook_weights: dict[str, float]


MODELS: dict[Platform, PlatformModel] = {
    Platform.INSTAGRAM: PlatformModel(
        exposure="reach",
        reach_ratio=0.30,
        sigma=0.45,
        base_er=0.045,
        format_reach={"reel": 1.85, "carousel": 1.05, "image": 0.72},
        format_er={"reel": 0.95, "carousel": 1.25, "image": 0.85},
        click_rate=0.0025,
        follow_rate=0.0022,
        reports_saves=True,
        hook_weights={"question": 0.18, "number": 0.2, "pov": 0.08, "bold_claim": 0.12, "how_to": 0.14, "none": 0.28},
    ),
    Platform.FACEBOOK: PlatformModel(
        exposure="reach",
        reach_ratio=0.11,
        sigma=0.5,
        base_er=0.028,
        format_reach={"video": 1.35, "image": 1.0, "link": 0.75, "text": 0.6},
        format_er={"video": 1.1, "image": 1.0, "link": 0.7, "text": 0.9},
        click_rate=0.012,
        follow_rate=0.0006,
        reports_saves=False,
        hook_weights={"question": 0.2, "number": 0.1, "pov": 0.0, "bold_claim": 0.1, "how_to": 0.1, "none": 0.5},
    ),
    Platform.TIKTOK: PlatformModel(
        exposure="views",
        reach_ratio=2.6,
        sigma=0.95,
        base_er=0.065,
        format_reach={"short_video": 1.1, "video": 0.75},
        format_er={"short_video": 1.0, "video": 0.9},
        click_rate=0.009,
        follow_rate=0.004,
        reports_saves=True,
        hook_weights={"question": 0.15, "number": 0.12, "pov": 0.3, "bold_claim": 0.15, "how_to": 0.1, "none": 0.18},
    ),
    Platform.LINKEDIN: PlatformModel(
        exposure="impressions",
        reach_ratio=0.85,
        sigma=0.5,
        base_er=0.032,
        format_reach={"document": 1.45, "video": 1.05, "image": 1.0, "text": 0.85},
        format_er={"document": 1.3, "video": 1.0, "image": 1.0, "text": 1.05},
        click_rate=0.011,
        follow_rate=0.0015,
        reports_saves=False,
        hook_weights={"question": 0.15, "number": 0.15, "pov": 0.0, "bold_claim": 0.15, "how_to": 0.2, "none": 0.35},
    ),
}

#: topic -> multipliers. Keys: reach, er, likes, comments, shares, saves, clicks, follows, completion (+pp)
TOPIC_EFFECTS: dict[str, dict[str, float]] = {
    "educational": {"reach": 1.0, "er": 1.15, "saves": 3.0, "shares": 1.5, "follows": 1.4},
    "tips": {"reach": 1.05, "er": 1.15, "saves": 2.6, "shares": 1.6, "follows": 1.2},
    "promotional": {"reach": 0.78, "er": 0.55, "clicks": 2.3, "saves": 0.4, "shares": 0.4},
    "product": {"reach": 0.9, "er": 0.9, "clicks": 1.5},
    "case_study": {"reach": 1.0, "er": 1.2, "clicks": 1.8, "saves": 1.3, "follows": 1.3},
    "behind_the_scenes": {"reach": 1.1, "er": 1.2, "comments": 1.4, "completion": 6, "follows": 1.1},
    "testimonial": {"reach": 0.9, "er": 1.05, "clicks": 1.4},
    "entertainment": {"reach": 1.35, "er": 1.25, "shares": 2.6, "saves": 0.5, "comments": 1.3},
    "trend": {"reach": 1.25, "er": 1.1, "shares": 2.0},
    "announcement": {"reach": 0.9, "er": 0.8},
    "faq": {"reach": 0.95, "er": 1.05, "comments": 1.6, "saves": 1.5},
    "company_culture": {"reach": 1.0, "er": 1.0, "comments": 1.2},
    "community": {"reach": 0.95, "er": 1.1, "comments": 1.8},
}
PLATFORM_TOPIC_OVERRIDES: dict[tuple[Platform, str], dict[str, float]] = {
    (Platform.LINKEDIN, "case_study"): {"er": 1.9, "clicks": 2.2},
    (Platform.LINKEDIN, "company_culture"): {"er": 1.35},
    (Platform.TIKTOK, "behind_the_scenes"): {"completion": 18, "er": 1.3},
    (Platform.TIKTOK, "promotional"): {"reach": 0.6, "completion": -8},
}
HOOK_EFFECTS: dict[str, dict[str, float]] = {
    "question": {"reach": 1.05, "comments": 1.35},
    "number": {"reach": 1.1, "saves": 1.2},
    "pov": {"reach": 1.15, "completion": 5},
    "bold_claim": {"reach": 1.06},
    "how_to": {"reach": 1.04, "saves": 1.2},
    "none": {"reach": 0.92},
}
COMPONENT_BASE = {"likes": 0.78, "comments": 0.05, "shares": 0.07, "saves": 0.10}
HOUR_WEIGHTS = {8: 5, 9: 7, 10: 5, 12: 8, 13: 10, 14: 5, 17: 8, 18: 12, 19: 14, 20: 12, 21: 8, 22: 4, 11: 2}
VIDEO_FORMATS = {"reel", "video", "short_video"}


def _hour_effect(hour: int) -> float:
    if 18 <= hour <= 21:
        return 1.12
    if 12 <= hour <= 14:
        return 1.03
    if 7 <= hour <= 10:
        return 0.95
    if hour >= 22:
        return 0.9
    return 0.85


def _effect(topic: str, platform: Platform, key: str, default: float = 1.0) -> float:
    override = PLATFORM_TOPIC_OVERRIDES.get((platform, topic), {})
    if key in override:
        return override[key]
    return TOPIC_EFFECTS.get(topic, {}).get(key, default)


def _weighted_choice(rng: np.random.Generator, weights: dict[str, float], size: int) -> list[str]:
    keys = list(weights)
    p = np.array([weights[k] for k in keys], dtype=float)
    return list(rng.choice(keys, size=size, p=p / p.sum()))


class SyntheticGenerator:
    def __init__(self, seed: int = 42) -> None:
        self.seed = seed

    def _rng(self, platform: Platform) -> np.random.Generator:
        # Independent, reproducible stream per platform.
        return np.random.default_rng([self.seed, list(Platform).index(platform)])

    def _schedule(
        self,
        rng: np.random.Generator,
        plan: PlatformPlan,
        n_posts: int,
        days: int,
        end_date: date,
        tz: ZoneInfo,
        weekday_effect: dict[int, float],
    ) -> list[datetime]:
        start = end_date - timedelta(days=days - 1)
        day_list = [start + timedelta(days=i) for i in range(days)]
        if plan.gap:
            gap_start, gap_len = plan.gap
            scale = days / 90  # gaps are specified for a 90-day window
            gs, gl = int(gap_start * scale), max(3, int(gap_len * min(1.0, scale)))
            day_list = [d for i, d in enumerate(day_list) if not (gs <= i < gs + gl)]
        w = np.array([weekday_effect.get(d.weekday(), 1.0) ** 2 for d in day_list])
        chosen = rng.choice(len(day_list), size=n_posts, replace=n_posts > len(day_list), p=w / w.sum())
        hours = _weighted_choice(rng, {str(h): v for h, v in HOUR_WEIGHTS.items()}, n_posts)
        stamps = []
        for idx, h in zip(sorted(chosen), hours, strict=True):
            minute = int(rng.integers(0, 60))
            stamps.append(datetime.combine(day_list[idx], time(int(h), minute), tzinfo=tz))
        return sorted(stamps)

    def generate(
        self,
        business: DemoBusiness,
        platform: Platform,
        days: int = 90,
        n_posts: int | None = None,
        end_date: date | None = None,
    ) -> pd.DataFrame:
        """Return the canonical ('ground truth') dataset for one platform."""
        plan = business.plans[platform]
        model = MODELS[platform]
        rng = self._rng(platform)
        tz = ZoneInfo(business.timezone)
        end_date = end_date or date.today()
        n = n_posts or max(5, round(plan.posts * days / 90))

        stamps = self._schedule(rng, plan, n, days, end_date, tz, business.weekday_effect)
        topics = _weighted_choice(rng, plan.topic_mix, n)
        formats = _weighted_choice(rng, plan.format_mix, n)
        hooks = _weighted_choice(rng, model.hook_weights, n)
        period_start = datetime.combine(end_date - timedelta(days=days - 1), time(0), tzinfo=tz)

        followers = float(plan.followers_start)
        rows = []
        # Random-walk volatility term (strong on TikTok).
        walk = 0.0
        for i, (ts, topic, fmt, hook) in enumerate(zip(stamps, topics, formats, hooks, strict=True)):
            progress = (ts - period_start).total_seconds() / (days * 86400)
            walk = 0.85 * walk + rng.normal(0, 0.12 if platform == Platform.TIKTOK else 0.03)
            trend = (1 + plan.trend * progress) * float(np.exp(walk))

            subject = str(rng.choice(business.subjects.get(topic) or ["our work"]))
            caption, cta = build_caption(rng, topic, subject, hook, business.hashtags)

            # --- video properties ---
            duration = completion = avg_watch = None
            if fmt in VIDEO_FORMATS:
                if platform == Platform.TIKTOK:
                    duration = (
                        float(rng.integers(61, 181))
                        if fmt == "video"
                        else float(np.clip(rng.lognormal(3.0, 0.45), 7, 60))
                    )
                elif platform == Platform.LINKEDIN:
                    duration = float(np.clip(rng.lognormal(4.3, 0.4), 20, 240))
                else:
                    duration = float(np.clip(rng.lognormal(3.3, 0.5), 7, 180))
                completion = 72 * np.exp(-duration / 42) + 9
                completion += _effect(topic, platform, "completion", 0) + HOOK_EFFECTS[hook].get("completion", 0)
                completion = float(np.clip(completion + rng.normal(0, 6), 2, 95))
                avg_watch = duration * (completion / 100 + (1 - completion / 100) * 0.3)

            # --- exposure ---
            reach_mult = (
                model.format_reach.get(fmt, 1.0)
                * _effect(topic, platform, "reach")
                * HOOK_EFFECTS[hook]["reach"]
                * business.weekday_effect.get(ts.weekday(), 1.0)
                * _hour_effect(ts.hour)
                * trend
            )
            if completion is not None and platform == Platform.TIKTOK:
                reach_mult *= 1 + (completion - 35) / 120  # retention feeds distribution
            # Exposure scales with the starting audience x trend; follower growth is tracked but
            # not fed back, which would compound unrealistically over the period.
            exposure = plan.followers_start * model.reach_ratio * reach_mult * rng.lognormal(0, model.sigma)
            viral = rng.random() < 0.02
            if viral:
                exposure *= rng.uniform(3, 7)
            exposure = max(exposure, 20.0)

            # --- engagement ---
            er = model.base_er * model.format_er.get(fmt, 1.0) * _effect(topic, platform, "er") * rng.lognormal(0, 0.35)
            weights = {
                k: v * _effect(topic, platform, k) * HOOK_EFFECTS[hook].get(k, 1.0) for k, v in COMPONENT_BASE.items()
            }
            if not model.reports_saves:
                weights["saves"] = 0.0
            if viral:
                weights["shares"] *= 1.5
            total_w = sum(weights.values())
            engagement = exposure * er
            comp = {k: int(rng.poisson(engagement * w / total_w)) for k, w in weights.items()}

            # --- clicks & follows ---
            cta_boost = 2.0 if cta in ("link_click", "book_call", "dm", "buy") else 1.0
            fmt_click = 3.5 if fmt == "link" else (1.4 if fmt == "document" else 1.0)
            clicks = int(
                rng.poisson(exposure * model.click_rate * _effect(topic, platform, "clicks") * cta_boost * fmt_click)
            )
            gained = int(
                rng.poisson(exposure * model.follow_rate * _effect(topic, platform, "follows") * rng.lognormal(0, 0.4))
            )
            followers += gained + rng.poisson(followers * 0.0004)

            row: dict[str, object] = {
                "external_post_id": f"{platform.value[:2]}{self.seed:03d}{i:04d}",
                "published_at": ts,
                "platform": platform.value,
                "content_format": fmt,
                "content_topic": topic,
                "hook_type": hook,
                "cta_type": cta,
                "caption": caption,
                **comp,
                "clicks": clicks,
                "followers_gained": gained,
                "followers": round(followers),
                "video_duration_seconds": duration,
                "completion_rate": None if completion is None else round(completion, 1),
                "average_watch_time_seconds": None if avg_watch is None else round(avg_watch, 1),
                "paid_or_organic": "organic",
            }
            if platform == Platform.TIKTOK:
                row["views"] = round(exposure)
                row["reach"] = round(exposure * rng.uniform(0.72, 0.9))
                row["watch_time_seconds"] = round((avg_watch or 0) * exposure, 1)
                row["profile_visits"] = int(rng.poisson(exposure * 0.012))
            elif platform == Platform.LINKEDIN:
                row["impressions"] = round(exposure)
                row["views"] = round(exposure * rng.uniform(0.3, 0.5)) if fmt == "video" else None
                row["paid_or_organic"] = "paid" if topic == "promotional" and rng.random() < 0.3 else "organic"
            else:
                row["reach"] = round(exposure)
                row["impressions"] = round(exposure * rng.uniform(1.12, 1.5))
                row["views"] = round(exposure * rng.uniform(1.1, 1.45)) if fmt in VIDEO_FORMATS else None
                row["profile_visits"] = int(rng.poisson(exposure * 0.015)) if platform == Platform.INSTAGRAM else None
            rows.append(row)

        return pd.DataFrame(rows)
