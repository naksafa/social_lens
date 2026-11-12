"""Keyword-based content classification (topic, pillar, CTA, hook).

This deterministic classifier runs on every analysis; it is transparent and free.
Posts it cannot classify confidently can optionally be re-classified by the AI
ContentClassificationAgent (results cached so a caption is never classified twice).

Scoring: each topic has weighted keyword patterns; a caption's topic is the highest
scoring one. Confidence = top score / (top + runner-up), damped for low absolute scores.
"""

import re
from dataclasses import dataclass

import pandas as pd

from app.core.enums import ContentPillar as P
from app.core.enums import ContentTopic as T

TAXONOMY_VERSION = "v1"

# (regex, weight). Patterns are matched case-insensitively on the caption.
TOPIC_KEYWORDS: dict[T, list[tuple[str, float]]] = {
    T.EDUCATIONAL: [
        (r"\bguide\b", 2),
        (r"\blearn", 2),
        (r"\bexplain", 2),
        (r"\blesson", 2),
        (r"\bframework", 1.5),
        (r"\bhow (to|it works|\w+ works)", 1.5),
        (r"\bstep[- ]by[- ]step", 2),
        (r"everything you need to know", 2),
        (r"\bwhy it matters", 1.5),
        (r"\bmistakes?\b", 1),
    ],
    T.TIPS: [(r"\btips?\b", 3), (r"\bchecklist", 2), (r"\bquick win", 2), (r"\bhack", 1.5), (r"\btry these", 1.5)],
    T.PROMOTIONAL: [
        (r"\boffer\b", 2.5),
        (r"\b\d+% off\b", 3),
        (r"\bdiscount", 2.5),
        (r"\bbook (now|a|your)", 2),
        (r"\blimited\b", 2),
        (r"\bspecial price", 2.5),
        (r"\bintroducing\b", 1.5),
        (r"\bpackage\b", 1),
        (r"\bsale\b", 2.5),
        (r"\bget .+ today", 1.5),
        (r"\bspots? (are )?limited", 2),
        (r"\bfree trial", 2),
    ],
    T.PRODUCT: [
        (r"\bnew on the menu", 3),
        (r"\bnow available", 2.5),
        (r"\bin store\b", 2),
        (r"\bmeet\b", 1),
        (r"\bis back\b", 2),
        (r"\bnew product", 2.5),
        (r"\bflavou?r", 1.5),
    ],
    T.CASE_STUDY: [
        (r"\bcase study", 4),
        (r"\bclient story", 3),
        (r"\bresults?\b", 1.5),
        (r"\bhelped\b", 1.5),
        (r"\bgrew|doubled|tripled|\dx\b", 1.5),
    ],
    T.BEHIND_THE_SCENES: [
        (r"behind the scenes", 4),
        (r"\bbts\b", 3),
        (r"\bunfiltered", 2),
        (r"\bcome with us", 2),
        (r"\bday (in|at) the", 1.5),
        (r"\bprocess\b", 1),
    ],
    T.TESTIMONIAL: [
        (r"\btestimonial", 4),
        (r"\breview", 2.5),
        (r"\bfive stars|5 stars|★", 3),
        (r"\bsays about us", 3),
        (r"\bthank you for the review", 3),
        (r"\bchanged everything", 1.5),
    ],
    T.ENTERTAINMENT: [
        (r"😂|🤣|😅", 2),
        (r"\bwhen .+ hits", 2),
        (r"\bmeme", 2.5),
        (r"\btell me you", 2.5),
        (r"\bwho wins", 1.5),
        (r"\bpov\b", 1),
        (r"\bfunny", 2),
    ],
    T.TREND: [(r"#trend\b|\btrending\b", 3), (r"\btrend\b", 2.5), (r"\bviral sound", 2), (r"\bchallenge\b", 1.5)],
    T.COMPANY_CULTURE: [
        (r"\bour team\b", 2),
        (r"\bculture\b", 3),
        (r"\blife at\b", 3),
        (r"\bour values", 3),
        (r"\bwe'?re hiring|\bhiring\b", 2),
        (r"\bwork week|remote-first", 2),
    ],
    T.FAQ: [(r"\bfaq\b", 4), (r"frequently asked", 4), (r"\byou asked", 3), (r"\bhonest answer", 2)],
    T.COMMUNITY: [
        (r"\bcommunity\b", 3),
        (r"\bshout-?out", 3),
        (r"\bspotlight", 2),
        (r"\bthank you to\b", 2),
        (r"\bmeetup\b", 2),
        (r"❤️", 1),
    ],
    T.ANNOUNCEMENT: [
        (r"\bannounc", 4),
        (r"\bbig news", 3),
        (r"\blaunch", 2),
        (r"\bexcited to", 2),
        (r"\bnew office|new team member|welcome\b", 2),
        (r"\bcoming soon|soon\b", 1),
    ],
}

TOPIC_TO_PILLAR: dict[str, P] = {
    T.EDUCATIONAL: P.EDUCATIONAL, T.TIPS: P.EDUCATIONAL, T.FAQ: P.EDUCATIONAL,
    T.PROMOTIONAL: P.PROMOTIONAL, T.PRODUCT: P.PROMOTIONAL, T.SERVICE: P.PROMOTIONAL,
    T.ANNOUNCEMENT: P.BRAND,
    T.CASE_STUDY: P.SOCIAL_PROOF, T.TESTIMONIAL: P.SOCIAL_PROOF,
    T.ENTERTAINMENT: P.ENTERTAINMENT, T.TREND: P.ENTERTAINMENT,
    T.BEHIND_THE_SCENES: P.BRAND, T.COMPANY_CULTURE: P.BRAND,
    T.COMMUNITY: P.COMMUNITY,
    T.OTHER: P.OTHER,
}  # fmt: skip

CTA_PATTERNS: list[tuple[str, str]] = [
    ("book_call", r"\bbook (a|your|now)|\bstrategy call|\bschedule a call|\bfree call"),
    ("dm", r"\bdm us|\bsend us a (dm|message)|\bmessage us"),
    (
        "link_click",
        r"\blink in bio|\bclick the link|\bvisit our (website|site)|\bread more at|\bsign up|\blearn more at",
    ),
    ("buy", r"\bshop now|\border (now|today)|\bbuy now|\bget yours"),
    ("visit", r"\bcome visit|\bvisit us|\bsee you (at|there)"),
    ("save", r"\bsave this|\bbookmark"),
    ("share", r"\bshare this|\bsend this to|\btag a friend"),
    ("comment", r"\bcomment below|\bin the comments|\blet us know|\btell us"),
    ("follow", r"\bfollow (us|for)"),
]

HOOK_PATTERNS: list[tuple[str, str]] = [
    ("pov", r"^\s*pov\b"),
    ("number", r"^\s*\d+\s+\w+"),
    ("how_to", r"^\s*(how to|here'?s how|how we)\b"),
    ("question", r"^[^.!\n]{3,90}\?"),
    ("bold_claim", r"^\s*(stop|nobody|never|everyone|the truth|\w+ is not what)"),
]


@dataclass
class Classification:
    topic: str
    pillar: str
    confidence: float
    cta_type: str
    hook_type: str


_COMPILED = {t: [(re.compile(p, re.I), w) for p, w in pats] for t, pats in TOPIC_KEYWORDS.items()}
_CTA_COMPILED = [(c, re.compile(p, re.I)) for c, p in CTA_PATTERNS]
_HOOK_COMPILED = [(h, re.compile(p, re.I)) for h, p in HOOK_PATTERNS]


def detect_cta(caption: str) -> str:
    for cta, pattern in _CTA_COMPILED:
        if pattern.search(caption):
            return cta
    return "none"


def detect_hook(caption: str) -> str:
    first = caption.strip().split("\n")[0]
    for hook, pattern in _HOOK_COMPILED:
        if pattern.search(first):
            return hook
    return "none"


def classify_caption(caption: object) -> Classification:
    text = caption if isinstance(caption, str) else ""
    scores = {t: sum(w for p, w in pats if p.search(text)) for t, pats in _COMPILED.items()}
    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    (top, top_score), (_, second) = ranked[0], ranked[1]
    if top_score <= 0:
        topic, confidence = T.OTHER, 0.0
    else:
        margin = top_score / (top_score + second)
        strength = min(1.0, top_score / 3)
        topic, confidence = top, round(margin * (0.5 + 0.5 * strength), 2)
    return Classification(
        topic=topic.value,
        pillar=TOPIC_TO_PILLAR.get(topic, P.OTHER).value,
        confidence=confidence,
        cta_type=detect_cta(text),
        hook_type=detect_hook(text),
    )


def classify_posts(df: pd.DataFrame) -> pd.DataFrame:
    """Fill topic/pillar/CTA/hook for posts not classified by a stronger source.

    Returns a frame with columns: content_topic, content_pillar, topic_confidence,
    topic_source, cta_type, hook_type (aligned to ``df.index``).
    """
    out = pd.DataFrame(index=df.index)
    captions = df["caption"] if "caption" in df else pd.Series(None, index=df.index)
    results = captions.map(classify_caption)
    keep = (
        df["topic_source"].isin(["source", "ai", "manual"])
        if "topic_source" in df
        else pd.Series(False, index=df.index)
    )

    existing_topic = df["content_topic"] if "content_topic" in df else pd.Series(None, index=df.index)
    out["content_topic"] = existing_topic.where(keep, results.map(lambda r: r.topic))
    out["topic_confidence"] = (
        df["topic_confidence"].where(keep, results.map(lambda r: r.confidence))
        if "topic_confidence" in df
        else results.map(lambda r: r.confidence)
    )
    out["topic_source"] = pd.Series("keyword", index=df.index).where(~keep, df.get("topic_source"))
    pillar_from_topic = out["content_topic"].map(
        lambda t: TOPIC_TO_PILLAR.get(t, P.OTHER).value if t else P.OTHER.value
    )
    existing_pillar = df["content_pillar"] if "content_pillar" in df else pd.Series(None, index=df.index)
    out["content_pillar"] = existing_pillar.where(keep & existing_pillar.notna(), pillar_from_topic)

    existing_cta = df["cta_type"] if "cta_type" in df else pd.Series(None, index=df.index)
    out["cta_type"] = existing_cta.where(existing_cta.notna(), results.map(lambda r: r.cta_type))
    existing_hook = df["hook_type"] if "hook_type" in df else pd.Series(None, index=df.index)
    out["hook_type"] = existing_hook.where(existing_hook.notna(), results.map(lambda r: r.hook_type))
    return out
