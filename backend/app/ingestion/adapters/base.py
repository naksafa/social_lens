"""Platform adapters: platform-specific rules for turning canonical-mapped data into posts.

The generic normalizer handles typing/validation; adapters encode what differs per
platform - how raw post-type labels map to content formats and the default format when
an export has no post-type column.
"""

from abc import ABC

from app.core.enums import ContentFormat, Platform


class PlatformAdapter(ABC):
    platform: Platform
    #: Ordered (keywords, format) rules matched against the lowercased raw post type.
    format_rules: tuple[tuple[tuple[str, ...], ContentFormat], ...] = ()
    default_format: ContentFormat = ContentFormat.OTHER

    def normalize_format(self, post_type: object, duration_seconds: float | None) -> str:
        if isinstance(post_type, str) and post_type.strip():
            label = post_type.strip().lower()
            for keywords, fmt in self.format_rules:
                if any(k in label for k in keywords):
                    return fmt.value
            return ContentFormat.OTHER.value
        return self.infer_format(duration_seconds).value

    def infer_format(self, duration_seconds: float | None) -> ContentFormat:
        """Format when the export has no post-type column."""
        return self.default_format
