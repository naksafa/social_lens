from typing import Any, Literal

from pydantic import BaseModel, Field


class ErrorResponse(BaseModel):
    code: str = Field(examples=["invalid_dataset"])
    message: str
    details: dict[str, Any] = Field(default_factory=dict)


class ComponentStatus(BaseModel):
    status: Literal["ok", "error", "not_configured"]
    detail: str | None = None


class HealthResponse(BaseModel):
    status: Literal["ok", "degraded"]
    app: str
    version: str
    environment: str
    database: ComponentStatus
    ai: ComponentStatus
