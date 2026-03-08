"""Shared API error types and FastAPI exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)


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


def _build_error_response(status_code: int, code: str, message: str, extra: dict[str, Any] | None = None) -> JSONResponse:
    payload: dict[str, Any] = {
        "error": {
            "code": code,
            "message": message,
        }
    }
    if extra:
        payload["error"]["details"] = extra
    return JSONResponse(status_code=status_code, content=payload)


def register_exception_handlers(app: FastAPI) -> None:
    """Register shared API exception handlers."""

    @app.exception_handler(AppError)
    async def handle_app_error(_request: Request, exc: AppError) -> JSONResponse:
        if exc.status_code >= 500:
            logger.exception("Application error: %s", exc.message)
        return _build_error_response(exc.status_code, exc.code, exc.message, exc.extra)

    @app.exception_handler(FileNotFoundError)
    async def handle_file_not_found(_request: Request, exc: FileNotFoundError) -> JSONResponse:
        return _build_error_response(404, "not_found", str(exc))

