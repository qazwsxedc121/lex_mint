"""Tool catalog API endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.application.tools.tool_catalog_service import ToolCatalogService
from src.domain.models.tool_catalog import ToolCatalogResponse
from src.infrastructure.config.tool_description_config_service import ToolDescriptionConfigService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolDescriptionItemResponse(BaseModel):
    name: str
    group: str
    source: str
    default_description: str
    override_description: str | None = None
    effective_description: str
    title_i18n_key: str
    description_i18n_key: str


class ToolDescriptionsResponse(BaseModel):
    tools: list[ToolDescriptionItemResponse]


class ToolDescriptionsUpdate(BaseModel):
    overrides: dict[str, str | None] = Field(default_factory=dict)


@router.get("/catalog", response_model=ToolCatalogResponse)
async def get_tool_catalog() -> ToolCatalogResponse:
    """Return a unified catalog of builtin and request-scoped tools."""
    try:
        description_service = ToolDescriptionConfigService()
        return ToolCatalogService.build_catalog(
            description_overrides=description_service.get_effective_description_map()
        )
    except Exception as exc:
        logger.error("Failed to build tool catalog: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/descriptions", response_model=ToolDescriptionsResponse)
async def get_tool_descriptions() -> ToolDescriptionsResponse:
    """Return default, override, and effective tool descriptions."""
    try:
        description_service = ToolDescriptionConfigService()
        catalog = ToolCatalogService.build_catalog(
            description_overrides=description_service.get_effective_description_map()
        )
        default_map = description_service.default_descriptions
        override_map = description_service.config.overrides
        return ToolDescriptionsResponse(
            tools=[
                ToolDescriptionItemResponse(
                    name=item.name,
                    group=item.group,
                    source=item.source,
                    default_description=default_map.get(item.name, item.description),
                    override_description=override_map.get(item.name),
                    effective_description=item.description,
                    title_i18n_key=item.title_i18n_key,
                    description_i18n_key=item.description_i18n_key,
                )
                for item in catalog.tools
            ]
        )
    except Exception as exc:
        logger.error("Failed to load tool descriptions: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/descriptions")
async def update_tool_descriptions(payload: ToolDescriptionsUpdate) -> dict[str, str]:
    """Update user overrides for tool descriptions."""
    try:
        description_service = ToolDescriptionConfigService()
        description_service.save_overrides(payload.overrides)
        return {"message": "Configuration updated successfully"}
    except Exception as exc:
        logger.error("Failed to update tool descriptions: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
