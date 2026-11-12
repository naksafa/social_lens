"""Claude provider (Anthropic SDK).

* Structured outputs via ``output_format=<PydanticModel>`` (JSON-schema constrained
  decoding + SDK-side validation into ``parsed_output``).
* Streaming (``beta.messages.stream`` + ``get_final_message``) so long strategy/plan
  outputs never hit HTTP timeouts.
* Adaptive thinking with a configurable effort level.
* Server-side refusal fallbacks (``fallbacks="default"``) for Claude Opus 5-class
  models, so a classifier decline is transparently re-run on the recommended model.
"""

import anthropic
from pydantic import BaseModel, ValidationError

from app.ai.base_provider import LLMProvider, LLMResult, SchemaViolation, T, Usage
from app.core.config import Settings
from app.core.exceptions import AIProviderError

FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AnthropicProvider(LLMProvider):
    name = "anthropic"

    def __init__(self, settings: Settings) -> None:
        if settings.anthropic_api_key is None:
            raise AIProviderError("ANTHROPIC_API_KEY is not set.")
        self.model = settings.anthropic_model
        self.effort = settings.ai_effort
        self.use_fallbacks = settings.anthropic_fallbacks
        self.client = anthropic.Anthropic(
            api_key=settings.anthropic_api_key.get_secret_value(),
            timeout=settings.ai_timeout_seconds,
            max_retries=2,
        )

    def _common(self) -> dict:
        kwargs: dict = {
            "model": self.model,
            "thinking": {"type": "adaptive"},
            "output_config": {"effort": self.effort},
        }
        if self.use_fallbacks:
            kwargs["betas"] = [FALLBACK_BETA]
            kwargs["fallbacks"] = "default"
        return kwargs

    def _call(self, fn):  # type: ignore[no-untyped-def]
        try:
            return fn()
        except anthropic.AuthenticationError as exc:
            raise AIProviderError("Anthropic rejected the API key.", {"status": 401}) from exc
        except anthropic.RateLimitError as exc:
            raise AIProviderError("Anthropic rate limit reached; try again shortly.", {"status": 429}) from exc
        except anthropic.BadRequestError as exc:
            raise AIProviderError("Anthropic rejected the request.", {"status": 400, "detail": exc.message}) from exc
        except anthropic.APIStatusError as exc:
            raise AIProviderError("Anthropic API error.", {"status": exc.status_code}) from exc
        except anthropic.APIConnectionError as exc:
            raise AIProviderError("Could not reach the Anthropic API.") from exc

    @staticmethod
    def _check_stop(message) -> None:  # type: ignore[no-untyped-def]
        if message.stop_reason == "refusal":
            category = getattr(getattr(message, "stop_details", None), "category", None)
            raise AIProviderError("The model declined this request.", {"category": category})
        if message.stop_reason == "max_tokens":
            raise SchemaViolation("Output was truncated at max_tokens before the JSON object was complete.")

    def _generate(self, system: str, prompt: str, max_tokens: int) -> LLMResult:
        def run():  # type: ignore[no-untyped-def]
            with self.client.beta.messages.stream(
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
                **self._common(),
            ) as stream:
                return stream.get_final_message()

        message = self._call(run)
        self._check_stop(message)
        text = "".join(b.text for b in message.content if b.type == "text")
        return LLMResult(text, Usage(message.usage.input_tokens, message.usage.output_tokens))

    def _structured(self, system: str, messages: list[dict], schema: type[T], max_tokens: int) -> tuple[T, Usage]:
        def run():  # type: ignore[no-untyped-def]
            with self.client.beta.messages.stream(
                max_tokens=max_tokens,
                system=system,
                messages=messages,
                output_format=schema,
                **self._common(),
            ) as stream:
                return stream.get_final_message()

        try:
            message = self._call(run)
        except ValidationError as exc:  # SDK validates parsed output against the schema
            raise SchemaViolation(str(exc)) from exc
        self._check_stop(message)
        parsed = getattr(message, "parsed_output", None)
        if parsed is None:
            text = "".join(b.text for b in message.content if b.type == "text")
            if not text:
                raise SchemaViolation("Empty response.")
            parsed = schema.model_validate_json(text)
        elif not isinstance(parsed, BaseModel):
            parsed = schema.model_validate(parsed)
        return parsed, Usage(message.usage.input_tokens, message.usage.output_tokens)  # type: ignore[return-value]
