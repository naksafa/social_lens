"""Shared enumerations. Stored as strings in the database (portable, readable)."""

from enum import StrEnum


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    TIKTOK = "tiktok"
    LINKEDIN = "linkedin"


class MarketingObjective(StrEnum):
    BRAND_AWARENESS = "brand_awareness"
    ENGAGEMENT = "engagement"
    LEAD_GENERATION = "lead_generation"
    SALES = "sales"
    WEBSITE_TRAFFIC = "website_traffic"
    STORE_VISITS = "store_visits"
    COMMUNITY_GROWTH = "community_growth"
    FOLLOWER_GROWTH = "follower_growth"
    VIDEO_VIEWS = "video_views"


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    DATA_UPLOADED = "data_uploaded"
    NORMALIZED = "normalized"
    ANALYZED = "analyzed"
    AUDITED = "audited"
    STRATEGY_READY = "strategy_ready"


class FileStatus(StrEnum):
    UPLOADED = "uploaded"
    MAPPED = "mapped"
    NORMALIZED = "normalized"
    FAILED = "failed"


class MappingMethod(StrEnum):
    EXACT = "exact"
    FUZZY = "fuzzy"
    MANUAL = "manual"
    UNMAPPED = "unmapped"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class Confidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Priority(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Level(StrEnum):
    """Generic high/medium/low scale used for impact and effort."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ContentFormat(StrEnum):
    REEL = "reel"
    CAROUSEL = "carousel"
    IMAGE = "image"
    VIDEO = "video"
    SHORT_VIDEO = "short_video"
    TEXT = "text"
    LINK = "link"
    DOCUMENT = "document"
    STORY = "story"
    OTHER = "other"


class ContentTopic(StrEnum):
    EDUCATIONAL = "educational"
    PROMOTIONAL = "promotional"
    PRODUCT = "product"
    SERVICE = "service"
    BEHIND_THE_SCENES = "behind_the_scenes"
    TESTIMONIAL = "testimonial"
    ENTERTAINMENT = "entertainment"
    TREND = "trend"
    COMPANY_CULTURE = "company_culture"
    CASE_STUDY = "case_study"
    TIPS = "tips"
    FAQ = "faq"
    COMMUNITY = "community"
    ANNOUNCEMENT = "announcement"
    OTHER = "other"


class ContentPillar(StrEnum):
    """Coarser strategic grouping of topics (see analytics.classification.TOPIC_TO_PILLAR)."""

    EDUCATIONAL = "educational"
    PROMOTIONAL = "promotional"
    SOCIAL_PROOF = "social_proof"
    ENTERTAINMENT = "entertainment"
    BRAND = "brand"
    COMMUNITY = "community"
    OTHER = "other"


class CTAType(StrEnum):
    NONE = "none"
    SAVE = "save"
    SHARE = "share"
    COMMENT = "comment"
    FOLLOW = "follow"
    LINK_CLICK = "link_click"
    DM = "dm"
    BOOK_CALL = "book_call"
    BUY = "buy"
    VISIT = "visit"
    OTHER = "other"


class ClassificationSource(StrEnum):
    SOURCE = "source"  # provided in the uploaded file
    KEYWORD = "keyword"
    AI = "ai"
    MANUAL = "manual"


class GeneratedBy(StrEnum):
    LLM = "llm"
    RULES = "rules"  # deterministic composer used when no AI provider is configured
