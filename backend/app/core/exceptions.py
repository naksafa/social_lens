"""Domain exceptions. Every error surfaced by the API derives from ``AppError``
and is rendered as ``{"code": ..., "message": ..., "details": {...}}``.
"""

from typing import Any


class AppError(Exception):
    status_code: int = 500
    code: str = "internal_error"

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class InvalidDatasetError(AppError):
    """The uploaded dataset cannot be used (empty, malformed, wrong structure...)."""

    status_code = 422
    code = "invalid_dataset"


class UnsupportedFileTypeError(AppError):
    status_code = 415
    code = "unsupported_file_type"


class FileTooLargeError(AppError):
    status_code = 413
    code = "file_too_large"


class MappingError(AppError):
    """Column mapping could not be detected or the confirmed mapping is invalid."""

    status_code = 422
    code = "mapping_error"


class AnalysisError(AppError):
    status_code = 500
    code = "analysis_error"


class AIProviderError(AppError):
    """Upstream LLM provider failed, timed out, or returned unusable output."""

    status_code = 502
    code = "ai_provider_error"


class AINotConfiguredError(AppError):
    status_code = 503
    code = "ai_not_configured"


class ReportGenerationError(AppError):
    status_code = 500
    code = "report_generation_error"


class StorageError(AppError):
    status_code = 500
    code = "storage_error"


class FeatureUnavailableError(AppError):
    """An optional feature is not installed/enabled on this server."""

    status_code = 501
    code = "feature_unavailable"
