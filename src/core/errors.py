"""Core application error hierarchy shared across layers."""

from __future__ import annotations

from typing import Any


class AppError(Exception):
    """Base application error with an HTTP status and stable error code."""

    status_code = 500
    code = "internal_error"

    def __init__(self, message: str, *, code: str | None = None, extra: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.extra = extra or {}
        if code is not None:
            self.code = code


class ValidationError(AppError):
    status_code = 400
    code = "validation_error"


class NotFoundError(AppError):
    status_code = 404
    code = "not_found"


class ConflictError(AppError):
    status_code = 409
    code = "conflict"


class ExternalServiceError(AppError):
    status_code = 502
    code = "external_service_error"
