"""Demo businesses: business context + content vocabulary + posting plan.

Each profile drives the synthetic generator: which platforms, how many posts,
what the content mix looks like (deliberately imperfect, so the analytics engine
has real problems to find), and topic-specific caption vocabulary.
"""

from dataclasses import dataclass, field

from app.core.enums import MarketingObjective as MO
from app.core.enums import Platform


@dataclass(frozen=True)
class PlatformPlan:
    posts: int
    followers_start: int
    #: Topic mix as weights (normalized by the generator).
    topic_mix: dict[str, float]
    #: Content format mix as weights.
    format_mix: dict[str, float]
    #: Relative growth of reach over the period (0.2 = +20% by the end).
    trend: float = 0.0
    #: Optional inactivity gap: (start day offset, length in days).
    gap: tuple[int, int] | None = None


@dataclass(frozen=True)
class DemoBusiness:
    key: str
    business_name: str
    industry: str
    country: str
    city_market: str
    timezone: str
    products_services: str
    target_audience: str
    business_objective: str
    marketing_objectives: list[MO]
    competitors: list[str]
    monthly_budget: float | None
    budget_currency: str | None
    current_posting_frequency: str
    handle: str
    #: Weekday (0=Mon) reach multipliers for this audience.
    weekday_effect: dict[int, float]
    plans: dict[Platform, PlatformPlan]
    #: topic -> list of subjects used to fill caption templates.
    subjects: dict[str, list[str]] = field(default_factory=dict)
    hashtags: list[str] = field(default_factory=list)
    additional_instructions: str | None = None


AGENCY = DemoBusiness(
    key="agency_uae",
    business_name="Falcon Growth Studio",
    industry="Digital marketing agency",
    country="United Arab Emirates",
    city_market="Dubai",
    timezone="Asia/Dubai",
    products_services=(
        "Social media management, performance marketing (Meta & Google Ads), "
        "content production, marketing strategy workshops for SMEs"
    ),
    target_audience=(
        "Founders and marketing managers of SMEs in the UAE (clinics, real estate, F&B, e-commerce), 28-50 years old"
    ),
    business_objective="Generate qualified leads for monthly retainer services",
    marketing_objectives=[MO.LEAD_GENERATION, MO.BRAND_AWARENESS, MO.ENGAGEMENT],
    competitors=["Hive Digital Dubai", "Pixel Souq Agency"],
    monthly_budget=15000,
    budget_currency="AED",
    current_posting_frequency="Daily on Instagram, 5-6x/week elsewhere",
    handle="falcongrowth",
    # UAE weekend is Sat-Sun; B2B audience most active Tue-Wed.
    weekday_effect={0: 0.97, 1: 1.14, 2: 1.10, 3: 1.0, 4: 0.9, 5: 0.8, 6: 0.88},
    plans={
        Platform.INSTAGRAM: PlatformPlan(
            posts=100,
            followers_start=8400,
            topic_mix={
                "educational": 0.16,
                "tips": 0.08,
                "promotional": 0.30,
                "case_study": 0.08,
                "behind_the_scenes": 0.10,
                "testimonial": 0.06,
                "entertainment": 0.10,
                "announcement": 0.06,
                "faq": 0.06,
            },
            format_mix={"reel": 0.40, "carousel": 0.30, "image": 0.30},
            trend=0.18,
        ),
        Platform.FACEBOOK: PlatformPlan(
            posts=80,
            followers_start=12600,
            topic_mix={
                "promotional": 0.52,
                "announcement": 0.12,
                "educational": 0.10,
                "testimonial": 0.08,
                "community": 0.08,
                "behind_the_scenes": 0.10,
            },
            format_mix={"image": 0.45, "video": 0.20, "link": 0.22, "text": 0.13},
            trend=-0.22,
            gap=(40, 13),
        ),
        Platform.TIKTOK: PlatformPlan(
            posts=75,
            followers_start=3100,
            topic_mix={
                "entertainment": 0.28,
                "behind_the_scenes": 0.22,
                "educational": 0.18,
                "trend": 0.14,
                "tips": 0.10,
                "promotional": 0.08,
            },
            format_mix={"short_video": 0.8, "video": 0.2},
            trend=0.45,
        ),
        Platform.LINKEDIN: PlatformPlan(
            posts=50,
            followers_start=4200,
            topic_mix={
                "case_study": 0.18,
                "educational": 0.20,
                "company_culture": 0.16,
                "promotional": 0.20,
                "announcement": 0.14,
                "testimonial": 0.12,
            },
            format_mix={"text": 0.34, "image": 0.30, "document": 0.20, "video": 0.16},
            trend=0.02,
        ),
    },
    subjects={
        "educational": [
            "Meta Ads targeting",
            "content calendars",
            "UGC for clinics",
            "lead magnets",
            "Instagram SEO",
            "retargeting audiences",
            "landing page conversion",
            "creative testing",
            "the marketing funnel",
            "brand positioning",
        ],
        "tips": [
            "better hooks",
            "writing captions that convert",
            "posting consistency",
            "Reels editing",
            "budgeting ad spend",
            "choosing KPIs",
        ],
        "promotional": [
            "our social media retainer",
            "the free strategy audit",
            "our Ramadan campaign package",
            "our content production day",
            "the performance ads package",
            "our growth workshop",
        ],
        "case_study": [
            "a Dubai dental clinic",
            "a JLT real estate broker",
            "a DIFC café",
            "an Abu Dhabi skincare brand",
            "a Sharjah furniture store",
        ],
        "behind_the_scenes": [
            "our shoot day",
            "a client strategy session",
            "our editing process",
            "the team brainstorm",
            "a day at the studio",
        ],
        "testimonial": [
            "Dr. Sara's clinic",
            "Omar from Marina Homes",
            "the team at Bean Bar",
            "Layla, founder of Glow Lab",
        ],
        "entertainment": ["agency life", "client briefs", "marketing memes", "Monday meetings", "the algorithm"],
        "trend": ["the viral sound of the week", "a trending transition", "the 'tell me without telling me' trend"],
        "announcement": [
            "our new office in Business Bay",
            "a new team member",
            "our Google Partner badge",
            "our upcoming webinar",
        ],
        "faq": ["how long SEO takes", "what a retainer includes", "minimum ad budgets", "reporting frequency"],
        "company_culture": [
            "our 4-day work week pilot",
            "learning Fridays",
            "our team values",
            "hiring our first data analyst",
        ],
        "community": ["local business owners", "our Dubai founders meetup", "your marketing wins"],
    },
    hashtags=[
        "dubaimarketing",
        "uaebusiness",
        "socialmediatips",
        "digitalmarketing",
        "smallbusinessuae",
        "contentstrategy",
        "metaads",
        "dubaientrepreneur",
    ],
)


CAFE = DemoBusiness(
    key="cafe_paris",
    business_name="Maison Mouture",
    industry="Specialty coffee shop & roastery",
    country="France",
    city_market="Paris (11e)",
    timezone="Europe/Paris",
    products_services="Specialty coffee, pastries, coffee beans subscription, barista workshops",
    target_audience="Urban professionals and students 20-40 in eastern Paris; coffee enthusiasts",
    business_objective="Increase weekday footfall and grow the beans subscription",
    marketing_objectives=[MO.STORE_VISITS, MO.COMMUNITY_GROWTH, MO.SALES],
    competitors=["Café Lomi", "Ten Belles"],
    monthly_budget=800,
    budget_currency="EUR",
    current_posting_frequency="3-4x/week on Instagram, occasional TikTok",
    handle="maisonmouture",
    weekday_effect={0: 0.92, 1: 0.95, 2: 1.0, 3: 1.05, 4: 1.12, 5: 1.1, 6: 0.98},
    plans={
        Platform.INSTAGRAM: PlatformPlan(
            posts=48,
            followers_start=5200,
            topic_mix={
                "product": 0.35,
                "behind_the_scenes": 0.2,
                "promotional": 0.2,
                "community": 0.1,
                "educational": 0.1,
                "announcement": 0.05,
            },
            format_mix={"reel": 0.3, "carousel": 0.2, "image": 0.5},
            trend=0.05,
            gap=(30, 16),
        ),
        Platform.TIKTOK: PlatformPlan(
            posts=22,
            followers_start=900,
            topic_mix={"behind_the_scenes": 0.4, "educational": 0.3, "entertainment": 0.3},
            format_mix={"short_video": 0.9, "video": 0.1},
            trend=0.3,
        ),
        Platform.FACEBOOK: PlatformPlan(
            posts=20,
            followers_start=1800,
            topic_mix={"promotional": 0.5, "announcement": 0.3, "community": 0.2},
            format_mix={"image": 0.7, "link": 0.2, "text": 0.1},
            trend=-0.1,
        ),
    },
    subjects={
        "product": [
            "our Ethiopian Guji filter",
            "the new cardamom bun",
            "our house espresso blend",
            "the oat flat white",
            "seasonal cold brew",
        ],
        "behind_the_scenes": ["roasting day", "our 7am opening routine", "latte art practice", "cupping session"],
        "promotional": ["the beans subscription", "our loyalty card", "the weekend brunch menu"],
        "community": ["our regulars", "the neighbourhood book club", "local artists on our walls"],
        "educational": ["brewing V60 at home", "grind size", "washed vs natural process", "storing beans"],
        "entertainment": ["barista life", "coffee order personalities", "Monday mornings"],
        "announcement": ["our new opening hours", "a pop-up at Marché d'Aligre", "the barista workshop dates"],
    },
    hashtags=["specialtycoffee", "pariscafe", "coffeelover", "paris11", "baristalife", "latteart"],
)


SAAS = DemoBusiness(
    key="saas_uk",
    business_name="Ledgerly",
    industry="B2B SaaS (accounting automation)",
    country="United Kingdom",
    city_market="London / UK-wide",
    timezone="Europe/London",
    products_services="Cloud bookkeeping automation for UK small businesses and accountants",
    target_audience="UK accountants, bookkeepers and SME finance leads",
    business_objective="Drive free-trial sign-ups from organic social",
    marketing_objectives=[MO.WEBSITE_TRAFFIC, MO.LEAD_GENERATION],
    competitors=["Xero", "FreeAgent"],
    monthly_budget=None,
    budget_currency=None,
    current_posting_frequency="LinkedIn 4x/week, Instagram 2x/week",
    handle="ledgerlyhq",
    weekday_effect={0: 1.0, 1: 1.1, 2: 1.08, 3: 1.05, 4: 0.85, 5: 0.6, 6: 0.65},
    plans={
        Platform.LINKEDIN: PlatformPlan(
            posts=52,
            followers_start=9800,
            topic_mix={
                "educational": 0.3,
                "case_study": 0.15,
                "promotional": 0.3,
                "company_culture": 0.1,
                "announcement": 0.15,
            },
            format_mix={"text": 0.3, "image": 0.3, "document": 0.25, "video": 0.15},
            trend=0.12,
        ),
        Platform.INSTAGRAM: PlatformPlan(
            posts=26,
            followers_start=2100,
            topic_mix={"educational": 0.3, "tips": 0.2, "promotional": 0.3, "company_culture": 0.2},
            format_mix={"reel": 0.3, "carousel": 0.5, "image": 0.2},
            trend=0.0,
        ),
    },
    subjects={
        "educational": [
            "Making Tax Digital",
            "VAT returns",
            "month-end close",
            "bank reconciliation",
            "cash-flow forecasting",
        ],
        "tips": ["invoice chasing", "receipt capture", "chart of accounts hygiene"],
        "promotional": ["our 30-day free trial", "the new bank-feed integration", "Ledgerly for practices"],
        "case_study": ["a Manchester accounting practice", "a Bristol e-commerce brand", "a Leeds agency"],
        "company_culture": ["our remote-first team", "engineering at Ledgerly", "our hack week"],
        "announcement": ["our Series A", "a new integration with Stripe", "the product roadmap webinar"],
    },
    hashtags=["accounting", "bookkeeping", "ukbusiness", "makingtaxdigital", "fintech", "smallbusinessuk"],
)

DEMO_BUSINESSES: dict[str, DemoBusiness] = {b.key: b for b in (AGENCY, CAFE, SAAS)}
