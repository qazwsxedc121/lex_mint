"""
Search Config API Router

Provides endpoints for configuring web search provider settings.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.search_service import SearchService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/search", tags=["search"])


class SearchConfigResponse(BaseModel):
    """Response model for search configuration"""
    provider: str
    max_results: int
    timeout_seconds: int


class SearchConfigUpdate(BaseModel):
    """Request model for updating search configuration"""
    provider: Optional[str] = None
    max_results: Optional[int] = Field(None, ge=1, le=20)
    timeout_seconds: Optional[int] = Field(None, ge=5, le=60)


def get_search_service() -> SearchService:
    """Dependency injection for SearchService."""
    return SearchService()

def _validate_provider(provider: Optional[str]) -> None:
    if provider is None:
        return
    allowed = {"duckduckgo", "tavily"}
    if provider not in allowed:
        raise HTTPException(status_code=400, detail=f"Unsupported provider: {provider}")

@router.get("/config", response_model=SearchConfigResponse)
async def get_config(
    service: SearchService = Depends(get_search_service)
):
    """Get current search configuration"""
    try:
        config = service.config
        return SearchConfigResponse(
            provider=config.provider,
            max_results=config.max_results,
            timeout_seconds=config.timeout_seconds
        )
    except Exception as e:
        logger.error(f"Failed to get search config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: SearchConfigUpdate,
    service: SearchService = Depends(get_search_service)
):
    """Update search configuration"""
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        _validate_provider(update_dict.get("provider"))
        service.save_config(update_dict)
        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update search config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
