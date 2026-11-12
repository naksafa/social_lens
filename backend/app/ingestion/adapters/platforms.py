from app.core.enums import ContentFormat as F
from app.core.enums import Platform
from app.ingestion.adapters.base import PlatformAdapter

SHORT_VIDEO_MAX_SECONDS = 60


class InstagramAdapter(PlatformAdapter):
    platform = Platform.INSTAGRAM
    format_rules = (
        (("reel", "clips"), F.REEL),
        (("carousel", "album"), F.CAROUSEL),
        (("story", "stories"), F.STORY),
        (("video", "igtv"), F.VIDEO),
        (("image", "photo", "picture", "post"), F.IMAGE),
    )
    default_format = F.IMAGE


class FacebookAdapter(PlatformAdapter):
    platform = Platform.FACEBOOK
    format_rules = (
        (("reel",), F.REEL),
        (("album", "carousel", "multi"), F.CAROUSEL),
        (("video", "live"), F.VIDEO),
        (("photo", "image"), F.IMAGE),
        (("link", "share"), F.LINK),
        (("status", "text"), F.TEXT),
    )
    default_format = F.IMAGE


class TikTokAdapter(PlatformAdapter):
    platform = Platform.TIKTOK
    format_rules = (
        (("photo", "carousel", "slideshow"), F.CAROUSEL),
        (("live",), F.VIDEO),
    )
    default_format = F.SHORT_VIDEO

    def normalize_format(self, post_type: object, duration_seconds: float | None) -> str:
        # Every TikTok post is a video unless it is explicitly a photo mode post;
        # the meaningful distinction is length.
        if isinstance(post_type, str) and any(k in post_type.lower() for k in ("photo", "carousel", "slideshow")):
            return F.CAROUSEL.value
        return self.infer_format(duration_seconds).value

    def infer_format(self, duration_seconds: float | None) -> F:
        if duration_seconds is not None and duration_seconds > SHORT_VIDEO_MAX_SECONDS:
            return F.VIDEO
        return F.SHORT_VIDEO


class LinkedInAdapter(PlatformAdapter):
    platform = Platform.LINKEDIN
    format_rules = (
        (("document", "pdf", "carousel", "slides"), F.DOCUMENT),
        (("video",), F.VIDEO),
        (("image", "photo", "picture"), F.IMAGE),
        (("article", "link", "url"), F.LINK),
        (("text", "post", "status", "poll"), F.TEXT),
    )
    default_format = F.TEXT


_ADAPTERS: dict[Platform, PlatformAdapter] = {
    a.platform: a for a in (InstagramAdapter(), FacebookAdapter(), TikTokAdapter(), LinkedInAdapter())
}


def get_adapter(platform: Platform) -> PlatformAdapter:
    return _ADAPTERS[platform]
