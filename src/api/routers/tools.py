"""Tool catalog API endpoints."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_jsonschema
from pydantic import BaseModel, Field

from src.application.tools.tool_catalog_service import ToolCatalogService
from src.domain.models.tool_catalog import ToolCatalogResponse
from src.infrastructure.config.tool_description_config_service import ToolDescriptionConfigService
from src.infrastructure.config.tool_plugin_settings_service import ToolPluginSettingsService
from src.tools.registry import get_tool_registry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tools", tags=["tools"])


class ToolDescriptionItemResponse(BaseModel):
    name: str
    group: str
    source: str
    plugin_id: str | None = None
    plugin_name: str | None = None
    plugin_version: str | None = None
    default_description: str
    override_description: str | None = None
    effective_description: str
    title_i18n_key: str
    description_i18n_key: str


class ToolDescriptionsResponse(BaseModel):
    tools: list[ToolDescriptionItemResponse]


class ToolDescriptionsUpdate(BaseModel):
    overrides: dict[str, str | None] = Field(default_factory=dict)


class ToolPluginStatusResponse(BaseModel):
    id: str
    name: str
    version: str
    entrypoint: str
    plugin_dir: str
    enabled: bool
    loaded: bool
    definitions_count: int = 0
    tools_count: int = 0
    has_settings_schema: bool = False
    settings_configured: bool = False
    error: str | None = None


class ToolPluginsResponse(BaseModel):
    plugins: list[ToolPluginStatusResponse]


class ToolPluginSettingsResponse(BaseModel):
    plugin_id: str
    schema: dict[str, Any]
    defaults: dict[str, Any]
    settings: dict[str, Any]
    effective_settings: dict[str, Any]


class ToolPluginSettingsUpdate(BaseModel):
    settings: dict[str, Any] = Field(default_factory=dict)


class ToolPluginSettingsValidateResult(BaseModel):
    valid: bool


def _find_plugin_status(plugin_id: str):
    for item in get_tool_registry().get_plugin_statuses():
        if item.id == plugin_id:
            return item
    return None


def _load_plugin_settings_bundle(plugin_id: str) -> tuple[Path, str, str | None]:
    plugin_status = _find_plugin_status(plugin_id)
    if plugin_status is None:
        raise HTTPException(status_code=404, detail=f"Plugin not found: {plugin_id}")
    if not plugin_status.has_settings_schema or not plugin_status.settings_schema_path:
        raise HTTPException(status_code=404, detail=f"Plugin has no settings schema: {plugin_id}")
    return (
        Path(plugin_status.plugin_dir),
        plugin_status.settings_schema_path,
        plugin_status.settings_defaults_path,
    )


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
                    plugin_id=item.plugin_id,
                    plugin_name=item.plugin_name,
                    plugin_version=item.plugin_version,
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


@router.get("/plugins", response_model=ToolPluginsResponse)
async def get_tool_plugins() -> ToolPluginsResponse:
    """Return startup plugin load statuses."""
    try:
        settings_service = ToolPluginSettingsService()
        statuses = get_tool_registry().get_plugin_statuses()
        return ToolPluginsResponse(
            plugins=[
                ToolPluginStatusResponse(
                    id=item.id,
                    name=item.name,
                    version=item.version,
                    entrypoint=item.entrypoint,
                    plugin_dir=item.plugin_dir,
                    enabled=item.enabled,
                    loaded=item.loaded,
                    definitions_count=item.definitions_count,
                    tools_count=item.tools_count,
                    has_settings_schema=item.has_settings_schema,
                    settings_configured=settings_service.has_plugin_settings(item.id),
                    error=item.error,
                )
                for item in statuses
            ]
        )
    except Exception as exc:
        logger.error("Failed to load tool plugin statuses: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/plugins/{plugin_id}/settings", response_model=ToolPluginSettingsResponse)
async def get_tool_plugin_settings(plugin_id: str) -> ToolPluginSettingsResponse:
    """Return schema/defaults/current settings for one plugin."""
    try:
        plugin_dir, schema_path, defaults_path = _load_plugin_settings_bundle(plugin_id)
        settings_service = ToolPluginSettingsService()
        schema = settings_service.load_schema(plugin_dir, schema_path)
        defaults = settings_service.load_defaults(plugin_dir, defaults_path)
        settings = settings_service.get_plugin_settings(plugin_id)
        effective_settings = settings_service.merge_effective_settings(defaults, settings)
        return ToolPluginSettingsResponse(
            plugin_id=plugin_id,
            schema=schema,
            defaults=defaults,
            settings=settings,
            effective_settings=effective_settings,
        )
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to load plugin settings for %s: %s", plugin_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.put("/plugins/{plugin_id}/settings")
async def update_tool_plugin_settings(
    plugin_id: str, payload: ToolPluginSettingsUpdate
) -> dict[str, str]:
    """Validate and persist plugin settings."""
    try:
        plugin_dir, schema_path, _ = _load_plugin_settings_bundle(plugin_id)
        settings_service = ToolPluginSettingsService()
        schema = settings_service.load_schema(plugin_dir, schema_path)
        validate_jsonschema(instance=payload.settings, schema=schema)
        settings_service.save_plugin_settings(plugin_id, payload.settings)
        return {"message": "Configuration updated successfully"}
    except JsonSchemaValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid plugin settings: {exc.message}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to update plugin settings for %s: %s", plugin_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))


@router.post(
    "/plugins/{plugin_id}/settings/validate", response_model=ToolPluginSettingsValidateResult
)
async def validate_tool_plugin_settings(
    plugin_id: str, payload: ToolPluginSettingsUpdate
) -> ToolPluginSettingsValidateResult:
    """Validate plugin settings payload without persisting."""
    try:
        plugin_dir, schema_path, _ = _load_plugin_settings_bundle(plugin_id)
        settings_service = ToolPluginSettingsService()
        schema = settings_service.load_schema(plugin_dir, schema_path)
        validate_jsonschema(instance=payload.settings, schema=schema)
        return ToolPluginSettingsValidateResult(valid=True)
    except JsonSchemaValidationError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid plugin settings: {exc.message}")
    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Failed to validate plugin settings for %s: %s", plugin_id, exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
