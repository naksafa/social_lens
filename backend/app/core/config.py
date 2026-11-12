"""Application settings, loaded from environment variables / .env.

Secrets are typed as ``SecretStr`` so they never appear in reprs or logs.
"""

import json
from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- App ---
    app_name: str = "SocialLens AI"
    app_version: str = "0.1.0"
    environment: Literal["development", "test", "production"] = "development"
    secret_key: SecretStr = SecretStr("change-me")
    cors_origins: Annotated[list[str], NoDecode] = Field(default_factory=lambda: ["http://localhost:3000"])

    # --- Logging ---
    log_level: str = "INFO"
    log_json: bool = True

    # --- Database ---
    database_url: str = "postgresql+psycopg://sociallens:sociallens@localhost:5432/sociallens"
    db_echo: bool = False

    # --- Storage ---
    storage_backend: Literal["local"] = "local"
    storage_local_path: Path = REPO_ROOT / "storage"
    max_upload_mb: int = 20
    allowed_upload_extensions: Annotated[list[str], NoDecode] = Field(default_factory=lambda: [".csv", ".xlsx"])

    # --- AI ---
    ai_provider: Literal["anthropic", "openai", "gemini", "none"] = "anthropic"
    anthropic_api_key: SecretStr | None = None
    anthropic_model: str = "claude-opus-5"
    # Server-side refusal fallbacks (re-run a classifier-declined request on the recommended model).
    anthropic_fallbacks: bool = True
    openai_api_key: SecretStr | None = None
    openai_model: str = "gpt-5"
    # Google AI Studio key - has a free tier
    gemini_api_key: SecretStr | None = None
    gemini_model: str = "gemini-3.5-flash-lite"
    ai_timeout_seconds: float = 600.0
    ai_max_output_tokens: int = 32000
    ai_effort: Literal["low", "medium", "high", "xhigh", "max"] = "high"

    @field_validator("cors_origins", "allowed_upload_extensions", mode="before")
    @classmethod
    def _split_csv(cls, value: object) -> object:
        # Accept comma-separated (CORS_ORIGINS=http://a,http://b) or JSON list env values.
        if isinstance(value, str):
            if value.strip().startswith("["):
                return json.loads(value)
            return [item.strip() for item in value.split(",") if item.strip()]
        return value

    @field_validator("anthropic_api_key", "openai_api_key", "gemini_api_key", mode="before")
    @classmethod
    def _empty_secret_is_none(cls, value: object) -> object:
        return None if value in ("", None) else value

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def ai_configured(self) -> bool:
        """True when the selected provider has an API key available."""
        if self.ai_provider == "anthropic":
            return self.anthropic_api_key is not None
        if self.ai_provider == "openai":
            return self.openai_api_key is not None
        if self.ai_provider == "gemini":
            return self.gemini_api_key is not None
        return False


@lru_cache
def get_settings() -> Settings:
    return Settings()
