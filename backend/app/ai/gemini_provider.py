"""Google Gemini provider (google-genai SDK, JSON-schema structured outputs).

Google AI Studio keys include a free tier (rate-limited; Google may use free-tier
prompts to improve its products), which makes this the zero-cost AI option.
"""

from google import genai
from google.genai import errors, types
from pydantic import ValidationError

from app.ai.base_provider import LLMProvider, LLMResult, SchemaViolation, T, Usage
from app.core.config import Settings
from app.core.exceptions import AIProviderError


def _usage(resp: types.GenerateContentResponse) -> Usage:
    meta = resp.usage_metadata
    return Usage(getattr(meta, "prompt_token_count", None), getattr(meta, "candidates_token_count", None))


class GeminiProvider(LLMProvider):
    name = "gemini"

    def __init__(self, settings: Settings) -> None:
        if settings.gemini_api_key is None:
            raise AIProviderError("GEMINI_API_KEY is not set.")
        self.model = settings.gemini_model
        self.client = genai.Client(
            api_key=settings.gemini_api_key.get_secret_value(),
            http_options=types.HttpOptions(timeout=int(settings.ai_timeout_seconds * 1000)),
        )

    def _call(self, fn):  # type: ignore[no-untyped-def]
        try:
            return fn()
        except errors.ClientError as exc:
            if exc.code in (401, 403):
                raise AIProviderError("Gemini rejected the API key.", {"status": exc.code}) from exc
            if exc.code == 429:
                raise AIProviderError("Gemini rate limit reached (free tier); try again shortly.", {"status": 429}) from exc
            raise AIProviderError("Gemini rejected the request.", {"status": exc.code}) from exc
        except errors.ServerError as exc:
            if exc.code == 503:
                raise AIProviderError("Gemini is overloaded right now (common on the free tier); try again in a minute.", {"status": 503}) from exc
            raise AIProviderError("Gemini API error.", {"status": exc.code}) from exc
        except errors.APIError as exc:
            raise AIProviderError("Gemini API error.", {"status": exc.code}) from exc
        except OSError as exc:
            raise AIProviderError("Could not reach the Gemini API.") from exc

    def _generate(self, system: str, prompt: str, max_tokens: int) -> LLMResult:
        resp = self._call(
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=types.GenerateContentConfig(system_instruction=system, max_output_tokens=max_tokens),
            )
        )
        return LLMResult(resp.text or "", _usage(resp))

    def _structured(self, system: str, messages: list[dict], schema: type[T], max_tokens: int) -> tuple[T, Usage]:
        contents = [
            types.Content(role="model" if m["role"] == "assistant" else "user", parts=[types.Part(text=m["content"])])
            for m in messages
        ]
        resp = self._call(
            lambda: self.client.models.generate_content(
                model=self.model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    max_output_tokens=max_tokens,
                    response_mime_type="application/json",
                    response_json_schema=schema.model_json_schema(),
                ),
            )
        )
        if not resp.text:
            raise SchemaViolation("The model returned no parsable output (possibly blocked or truncated).")
        try:
            return schema.model_validate_json(resp.text), _usage(resp)
        except ValidationError as exc:
            raise SchemaViolation(str(exc)) from exc
