"""Shared API error types and FastAPI exception handlers."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from src.core.errors import (
    AppError,
)

logger = logging.getLogger(__name__)


def _build_error_response(
    status_code: int, code: str, message: str, extra: dict[str, Any] | None = None
) -> JSONResponse:
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
