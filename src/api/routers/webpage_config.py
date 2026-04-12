"""
Webpage Config API Router

Provides endpoints for configuring webpage fetch settings.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.routers.service_protocols import ConfigSaveServiceLike
from src.infrastructure.web.web_tools_settings import save_web_tools_settings_updates
from src.infrastructure.web.webpage_service import WebpageService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/webpage", tags=["webpage"])


class WebpageConfigResponse(BaseModel):
    """Response model for webpage configuration."""

    enabled: bool
    max_urls: int
    timeout_seconds: int
    max_bytes: int
    max_content_chars: int
    user_agent: str
    proxy: str | None
    trust_env: bool
    diagnostics_enabled: bool
    diagnostics_timeout_seconds: float


class WebpageConfigUpdate(BaseModel):
    """Request model for updating webpage configuration."""

    enabled: bool | None = None
    max_urls: int | None = Field(default=None, ge=1, le=10)
    timeout_seconds: int | None = Field(default=None, ge=2, le=120)
    max_bytes: int | None = Field(default=None, ge=100_000, le=20_000_000)
    max_content_chars: int | None = Field(default=None, ge=500, le=200_000)
    user_agent: str | None = Field(default=None, min_length=1, max_length=300)
    proxy: str | None = None
    trust_env: bool | None = None
    diagnostics_enabled: bool | None = None
    diagnostics_timeout_seconds: float | None = Field(default=None, ge=0.5, le=5.0)


def get_webpage_service() -> WebpageService:
    """Dependency injection for WebpageService."""
    return WebpageService()


@router.get("/config", response_model=WebpageConfigResponse)
async def get_config(service: ConfigSaveServiceLike = Depends(get_webpage_service)):
    """Get current webpage configuration."""
    try:
        config = service.config
        return WebpageConfigResponse(
            enabled=config.enabled,
            max_urls=config.max_urls,
            timeout_seconds=config.timeout_seconds,
            max_bytes=config.max_bytes,
            max_content_chars=config.max_content_chars,
            user_agent=config.user_agent,
            proxy=config.proxy,
            trust_env=config.trust_env,
            diagnostics_enabled=config.diagnostics_enabled,
            diagnostics_timeout_seconds=config.diagnostics_timeout_seconds,
        )
    except Exception as e:
        logger.error(f"Failed to get webpage config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: WebpageConfigUpdate, service: ConfigSaveServiceLike = Depends(get_webpage_service)
):
    """Update webpage configuration."""
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        save_web_tools_settings_updates({"webpage": update_dict})
        load_config = getattr(service, "_load_config", None)
        if callable(load_config):
            service.config = load_config()
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update webpage config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
