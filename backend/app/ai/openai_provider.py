"""OpenAI provider (Responses API with Pydantic structured outputs)."""

import openai
from pydantic import ValidationError

from app.ai.base_provider import LLMProvider, LLMResult, SchemaViolation, T, Usage
from app.core.config import Settings
from app.core.exceptions import AIProviderError


class OpenAIProvider(LLMProvider):
    name = "openai"

    def __init__(self, settings: Settings) -> None:
        if settings.openai_api_key is None:
            raise AIProviderError("OPENAI_API_KEY is not set.")
        self.model = settings.openai_model
        self.client = openai.OpenAI(
            api_key=settings.openai_api_key.get_secret_value(),
            timeout=settings.ai_timeout_seconds,
            max_retries=2,
        )

    def _call(self, fn):  # type: ignore[no-untyped-def]
        try:
            return fn()
        except openai.AuthenticationError as exc:
            raise AIProviderError("OpenAI rejected the API key.", {"status": 401}) from exc
        except openai.RateLimitError as exc:
            raise AIProviderError("OpenAI rate limit reached; try again shortly.", {"status": 429}) from exc
        except openai.BadRequestError as exc:
            raise AIProviderError("OpenAI rejected the request.", {"status": 400}) from exc
        except openai.APIStatusError as exc:
            raise AIProviderError("OpenAI API error.", {"status": exc.status_code}) from exc
        except openai.APIConnectionError as exc:
            raise AIProviderError("Could not reach the OpenAI API.") from exc

    def _generate(self, system: str, prompt: str, max_tokens: int) -> LLMResult:
        resp = self._call(
            lambda: self.client.responses.create(
                model=self.model, instructions=system, input=prompt, max_output_tokens=max_tokens
            )
        )
        usage = Usage(getattr(resp.usage, "input_tokens", None), getattr(resp.usage, "output_tokens", None))
        return LLMResult(resp.output_text, usage)

    def _structured(self, system: str, messages: list[dict], schema: type[T], max_tokens: int) -> tuple[T, Usage]:
        try:
            resp = self._call(
                lambda: self.client.responses.parse(
                    model=self.model,
                    instructions=system,
                    input=messages,
                    text_format=schema,
                    max_output_tokens=max_tokens,
                )
            )
        except ValidationError as exc:
            raise SchemaViolation(str(exc)) from exc
        parsed = resp.output_parsed
        if parsed is None:
            raise SchemaViolation("The model returned no parsable output (possibly a refusal or truncation).")
        usage = Usage(getattr(resp.usage, "input_tokens", None), getattr(resp.usage, "output_tokens", None))
        return parsed, usage
