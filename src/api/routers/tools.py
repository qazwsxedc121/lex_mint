"""Tool catalog API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from ..models.tool_catalog import ToolCatalogResponse
from ..services.tool_catalog_service import ToolCatalogService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


@router.get("/catalog", response_model=ToolCatalogResponse)
async def get_tool_catalog() -> ToolCatalogResponse:
    """Return a unified catalog of builtin and request-scoped tools."""
    try:
        return ToolCatalogService.build_catalog()
    except Exception as exc:
        logger.error("Failed to build tool catalog: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
