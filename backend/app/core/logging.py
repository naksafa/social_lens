"""Structured (JSON) logging with request correlation and secret redaction.

Usage::

    logger = get_logger(__name__)
    logger.info("analysis.started", extra={"project_id": str(pid), "rows": 412})

Anything passed through ``extra`` is emitted as structured fields. Fields whose
name looks sensitive (api_key, token, secret, password, authorization) are
redacted, and inline values shaped like provider keys are masked in messages.
"""

import json
import logging
import re
import sys
from contextvars import ContextVar
from datetime import UTC, datetime

request_id_ctx: ContextVar[str | None] = ContextVar("request_id", default=None)

_SENSITIVE_FIELD = re.compile(r"(api[_-]?key|token|secret|password|authorization)", re.I)
_KEY_PATTERN = re.compile(r"\b(sk-[A-Za-z0-9_\-]{8,}|sk-ant-[A-Za-z0-9_\-]{8,})")

# Attributes present on every LogRecord; everything else came from ``extra``.
_STANDARD_ATTRS = set(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()) | {
    "message",
    "asctime",
    "taskName",
}

REDACTED = "***"


def redact(value: object, key: str | None = None) -> object:
    if key and _SENSITIVE_FIELD.search(key):
        return REDACTED
    if isinstance(value, str):
        return _KEY_PATTERN.sub(REDACTED, value)
    if isinstance(value, dict):
        return {k: redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [redact(v) for v in value]
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, object] = {
            "ts": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "event": redact(record.getMessage()),
        }
        if (rid := request_id_ctx.get()) is not None:
            payload["request_id"] = rid
        for key, value in record.__dict__.items():
            if key not in _STANDARD_ATTRS and not key.startswith("_"):
                payload[key] = redact(value, key)
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


class ConsoleFormatter(logging.Formatter):
    """Human-friendly single-line format for local development."""

    def format(self, record: logging.LogRecord) -> str:
        extras = {
            k: redact(v, k) for k, v in record.__dict__.items() if k not in _STANDARD_ATTRS and not k.startswith("_")
        }
        rid = request_id_ctx.get()
        base = f"{record.levelname:<7} {record.name}: {redact(record.getMessage())}"
        if rid:
            base += f" [req={rid}]"
        if extras:
            base += " " + " ".join(f"{k}={v}" for k, v in extras.items())
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base


def configure_logging(level: str = "INFO", json_output: bool = True) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter() if json_output else ConsoleFormatter())
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level.upper())
    # Keep noisy libraries quiet unless explicitly debugging.
    for noisy in ("uvicorn.access", "httpx", "httpcore", "anthropic", "openai"):
        logging.getLogger(noisy).setLevel(max(logging.WARNING, root.level))


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
