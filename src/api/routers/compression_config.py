"""
Compression Config API Router

Provides endpoints for configuring context compression.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.compression_config_service import CompressionConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/compression", tags=["compression"])


# Pydantic models
class CompressionConfigResponse(BaseModel):
    """Response model for compression configuration"""
    model_id: str
    temperature: float
    min_messages: int
    timeout_seconds: int
    prompt_template: str


class CompressionConfigUpdate(BaseModel):
    """Request model for updating compression configuration"""
    model_id: Optional[str] = None
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    min_messages: Optional[int] = Field(None, ge=1, le=50)
    timeout_seconds: Optional[int] = Field(None, ge=10, le=300)
    prompt_template: Optional[str] = None


# Dependency
def get_compression_config_service() -> CompressionConfigService:
    """Get CompressionConfigService instance"""
    return CompressionConfigService()


# Endpoints
@router.get("/config", response_model=CompressionConfigResponse)
async def get_config(
    service: CompressionConfigService = Depends(get_compression_config_service)
):
    """Get current compression configuration"""
    try:
        config = service.config
        return CompressionConfigResponse(
            model_id=config.model_id,
            temperature=config.temperature,
            min_messages=config.min_messages,
            timeout_seconds=config.timeout_seconds,
            prompt_template=config.prompt_template,
        )
    except Exception as e:
        logger.error(f"Failed to get compression config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: CompressionConfigUpdate,
    service: CompressionConfigService = Depends(get_compression_config_service)
):
    """Update compression configuration"""
    try:
        update_dict = updates.model_dump(exclude_none=True)

        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        service.save_config(update_dict)

        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update compression config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
