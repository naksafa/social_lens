"""Caption generation from topic templates, hooks and CTAs.

Captions contain the kind of vocabulary the keyword classifier looks for, but a
share of captions is deliberately vague so classification is not trivially perfect.
"""

import numpy as np

HOOKS: dict[str, list[str]] = {
    "question": ["Are you still {x}?", "Why does nobody talk about {s}?", "What if {s} was easier?"],
    "number": ["3 mistakes with {s}", "5 things we learned about {s}", "7 quick wins for {s}"],
    "pov": ["POV: {s} finally clicks", "POV: you just discovered {s}"],
    "bold_claim": ["{S} is not what you think.", "Stop ignoring {s}.", "Nobody is doing {s} right."],
    "how_to": ["How to master {s}", "How we approach {s}", "Here's how {s} works"],
    "none": ["{S}."],
}

BODIES: dict[str, list[str]] = {
    "educational": [
        "A quick guide to {s} - learn the framework we use.",
        "Everything you need to know about {s}, explained step by step.",
        "Lesson of the week: {s}. Here is why it matters.",
    ],
    "tips": [
        "Tip: improve {s} with this simple checklist.",
        "Our top tips for {s} - try these today.",
        "Quick tip on {s} that most people miss.",
    ],
    "promotional": [
        "Introducing {s} - limited offer this month, 20% off.",
        "Book now: {s}. Spots are limited.",
        "Get {s} today - special price for new clients.",
    ],
    "product": ["Meet {s} - now available in store.", "New on the menu: {s}.", "{S} is back, and better."],
    "case_study": [
        "Case study: how we helped {s} grow results in 90 days.",
        "Results: {s} doubled their leads - here is the strategy.",
        "Client story: what worked for {s}.",
    ],
    "behind_the_scenes": [
        "Behind the scenes of {s}.",
        "A look behind the scenes at {s}.",
        "Come with us: {s}, unfiltered.",
    ],
    "testimonial": [
        '"Working with the team changed everything" - {s}. Thank you for the review!',
        "Review from {s}: five stars and a lot of trust.",
        "What our client {s} says about us.",
    ],
    "entertainment": [
        "When {s} hits different 😂",
        "Tell me you work in marketing without telling me: {s} 😅",
        "Us vs {s}. Who wins? 🤣",
    ],
    "trend": ["Jumping on {s} #trend", "We had to try {s} - trending now.", "Our take on {s} (trend)"],
    "announcement": ["Big news: {s}!", "Announcement - {s}. Launching soon.", "We're excited to announce {s}."],
    "faq": ["FAQ: {s}? Here's the honest answer.", "You asked: {s}. We answer.", "Frequently asked question - {s}."],
    "company_culture": [
        "Life at our company: {s}.",
        "Our team and culture: {s}.",
        "Why we believe in {s} - our values in action.",
    ],
    "community": [
        "Shout-out to {s} - this community is everything.",
        "Thank you to {s} ❤️",
        "Community spotlight: {s}.",
    ],
}

# Captions that don't reveal their topic well (classifier should be uncertain).
VAGUE = ["Some thoughts on {s}.", "{S} ✨", "Today: {s}.", "More on {s} soon."]

CTAS: dict[str, list[str]] = {
    "save": ["Save this for later.", "Bookmark this post."],
    "share": ["Share this with a friend who needs it.", "Send this to your team."],
    "comment": ["Comment below with your thoughts.", "Tell us in the comments 👇"],
    "follow": ["Follow for more tips.", "Follow us for daily insights."],
    "link_click": ["Link in bio.", "Read more at the link.", "Visit our website - link in bio."],
    "book_call": ["Book a free call today.", "DM us to book your strategy call."],
    "dm": ["DM us 'GROW' to get started.", "Send us a DM for details."],
    "buy": ["Shop now.", "Order today."],
    "visit": ["Come visit us this week.", "See you at the shop!"],
}

#: Probability that a post of this topic carries a CTA, and which CTAs are typical.
TOPIC_CTA: dict[str, tuple[float, list[str]]] = {
    "educational": (0.45, ["save", "share", "follow"]),
    "tips": (0.5, ["save", "share"]),
    "promotional": (0.85, ["book_call", "link_click", "dm", "buy"]),
    "product": (0.6, ["visit", "buy"]),
    "case_study": (0.55, ["book_call", "link_click"]),
    "behind_the_scenes": (0.15, ["follow", "comment"]),
    "testimonial": (0.4, ["book_call", "link_click"]),
    "entertainment": (0.2, ["share", "comment", "follow"]),
    "trend": (0.15, ["share", "follow"]),
    "announcement": (0.4, ["link_click", "visit"]),
    "faq": (0.4, ["comment", "dm"]),
    "company_culture": (0.2, ["link_click", "comment"]),
    "community": (0.3, ["comment", "share"]),
}


def _cap(text: str) -> str:
    return text[:1].upper() + text[1:]


def build_caption(
    rng: np.random.Generator,
    topic: str,
    subject: str,
    hook: str,
    hashtags: list[str],
    vague_share: float = 0.12,
) -> tuple[str, str]:
    """Return (caption, cta_type)."""
    fill = {"s": subject, "S": _cap(subject), "x": f"struggling with {subject}"}
    hook_text = str(rng.choice(HOOKS[hook])).format(**fill) if hook != "none" else ""
    pool = VAGUE if rng.random() < vague_share else BODIES.get(topic, VAGUE)
    body = str(rng.choice(pool)).format(**fill)

    prob, ctas = TOPIC_CTA.get(topic, (0.3, ["follow"]))
    cta_type = "none"
    cta_text = ""
    if rng.random() < prob:
        cta_type = str(rng.choice(ctas))
        cta_text = str(rng.choice(CTAS[cta_type]))

    k = int(rng.integers(0, 5))
    tags = (
        " ".join(f"#{t}" for t in rng.choice(hashtags, size=min(k, len(hashtags)), replace=False)) if hashtags else ""
    )
    parts = [p for p in (hook_text, body, cta_text, tags) if p]
    return " ".join(parts), cta_type
