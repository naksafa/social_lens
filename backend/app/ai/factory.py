"""Provider selection. Adding a provider = implement LLMProvider + register it here."""

from collections.abc import Callable

from app.ai.anthropic_provider import AnthropicProvider
from app.ai.base_provider import LLMProvider
from app.ai.gemini_provider import GeminiProvider
from app.ai.openai_provider import OpenAIProvider
from app.core.config import Settings, get_settings

_REGISTRY: dict[str, Callable[[Settings], LLMProvider]] = {
    "anthropic": AnthropicProvider,
    "openai": OpenAIProvider,
    "gemini": GeminiProvider,
}


def get_provider(settings: Settings | None = None) -> LLMProvider | None:
    """Return the configured provider, or None when AI is disabled / not configured."""
    settings = settings or get_settings()
    if not settings.ai_configured:
        return None
    return _REGISTRY[settings.ai_provider](settings)
