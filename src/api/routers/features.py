"""Feature plugin management endpoints."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from src.application.chat.session_export_plugins import list_session_export_plugin_statuses

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/features", tags=["features"])


class SessionExportPluginStatusResponse(BaseModel):
    id: str
    name: str
    version: str
    entrypoint: str
    plugin_dir: str
    enabled: bool
    loaded: bool
    error: str | None = None


class FeaturePluginsResponse(BaseModel):
    session_export_plugins: list[SessionExportPluginStatusResponse]


@router.get("/plugins", response_model=FeaturePluginsResponse)
async def get_feature_plugins() -> FeaturePluginsResponse:
    """Return feature plugin load statuses."""
    try:
        statuses = list_session_export_plugin_statuses()
        return FeaturePluginsResponse(
            session_export_plugins=[
                SessionExportPluginStatusResponse(
                    id=item.id,
                    name=item.name,
                    version=item.version,
                    entrypoint=item.entrypoint,
                    plugin_dir=item.plugin_dir,
                    enabled=item.enabled,
                    loaded=item.loaded,
                    error=item.error,
                )
                for item in statuses
            ]
        )
    except Exception as exc:
        logger.error("Failed to load feature plugin statuses: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc))
