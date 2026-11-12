"""Interface for future multimodal (image / thumbnail / video) content analysis.

Not required for the MVP. ``SocialPost`` already stores ``thumbnail_url``,
``media_url`` and a JSON ``visual_features`` column; an extractor implementing
``VisualFeatureExtractor`` (e.g. a vision-capable LLM or a CV model) fills it, and
the analytics engine can then group posts by these features exactly like it groups
by format or pillar.
"""

from typing import Protocol

from pydantic import BaseModel, Field


class VisualFeatures(BaseModel):
    human_presence: bool | None = None
    product_only: bool | None = None
    text_heavy: bool | None = None
    logo_presence: bool | None = None
    dominant_colors: list[str] = Field(default_factory=list)
    visual_category: str | None = None  # e.g. "talking_head", "product_shot", "infographic"
    confidence: float | None = None


class VisualFeatureExtractor(Protocol):
    name: str

    def extract(self, media_url: str, media_type: str) -> VisualFeatures: ...
