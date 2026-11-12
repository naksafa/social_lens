"""Provider-agnostic LLM interface.

``generate_structured`` owns the validate-and-retry loop: the provider returns an
object parsed against the Pydantic schema; if parsing or validation fails, the call is
retried once with the validation error appended ("schema correction"). Concrete
providers only implement the raw ``_generate`` / ``_structured`` calls.
"""

import hashlib
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Generic, TypeVar

from pydantic import BaseModel, ValidationError

from app.core.exceptions import AIProviderError
from app.core.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T", bound=BaseModel)


@dataclass
class Usage:
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass
class LLMResult:
    text: str
    usage: Usage = field(default_factory=Usage)


@dataclass
class StructuredResult(Generic[T]):
    data: T
    usage: Usage
    attempts: int
    latency_ms: float
    prompt_hash: str
    prompt_chars: int


class SchemaViolation(Exception):
    """Raised by providers when the model output doesn't match the schema."""


class LLMProvider(ABC):
    name: str
    model: str

    @abstractmethod
    def _generate(self, system: str, prompt: str, max_tokens: int) -> LLMResult: ...

    @abstractmethod
    def _structured(self, system: str, messages: list[dict], schema: type[T], max_tokens: int) -> tuple[T, Usage]:
        """Return a validated instance of ``schema``; raise SchemaViolation on bad output."""

    def generate(self, system: str, prompt: str, max_tokens: int = 4000) -> LLMResult:
        return self._generate(system, prompt, max_tokens)

    def generate_structured(
        self, system: str, prompt: str, schema: type[T], max_tokens: int = 16000, agent: str = "agent"
    ) -> StructuredResult[T]:
        messages: list[dict] = [{"role": "user", "content": prompt}]
        started = time.perf_counter()
        total = Usage(0, 0)
        last_error: str | None = None
        for attempt in (1, 2):
            try:
                data, usage = self._structured(system, messages, schema, max_tokens)
                total.input_tokens = (total.input_tokens or 0) + (usage.input_tokens or 0)
                total.output_tokens = (total.output_tokens or 0) + (usage.output_tokens or 0)
                return StructuredResult(
                    data=data,
                    usage=total,
                    attempts=attempt,
                    latency_ms=round((time.perf_counter() - started) * 1000, 1),
                    prompt_hash=hashlib.sha256((system + prompt).encode()).hexdigest(),
                    prompt_chars=len(system) + len(prompt),
                )
            except (SchemaViolation, ValidationError) as exc:
                last_error = str(exc)[:1500]
                logger.warning("ai.schema_violation", extra={"agent": agent, "provider": self.name, "attempt": attempt})
                # Schema correction: show the model its own error and ask for a corrected object.
                messages = [
                    *messages[:1],
                    {
                        "role": "user",
                        "content": (
                            "Your previous response did not match the required JSON schema. "
                            f"Validation error:\n{last_error}\n\nReturn a corrected response that satisfies the schema."
                        ),
                    },
                ]
        raise AIProviderError(
            "The AI response did not match the expected structure after a retry.",
            {"agent": agent, "provider": self.name, "error": last_error},
        )

    def classify(self, system: str, prompt: str, schema: type[T]) -> StructuredResult[T]:
        return self.generate_structured(system, prompt, schema, max_tokens=8000, agent="classification")
