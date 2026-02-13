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
    provider: str
    model_id: str
    local_gguf_model_path: str
    local_gguf_n_ctx: int
    local_gguf_n_threads: int
    local_gguf_n_gpu_layers: int
    local_gguf_max_tokens: int
    temperature: float
    min_messages: int
    timeout_seconds: int
    prompt_template: str
    auto_compress_enabled: bool
    auto_compress_threshold: float


class CompressionConfigUpdate(BaseModel):
    """Request model for updating compression configuration"""
    provider: Optional[str] = None
    model_id: Optional[str] = None
    local_gguf_model_path: Optional[str] = None
    local_gguf_n_ctx: Optional[int] = Field(None, ge=512, le=65536)
    local_gguf_n_threads: Optional[int] = Field(None, ge=0, le=256)
    local_gguf_n_gpu_layers: Optional[int] = Field(None, ge=0, le=1024)
    local_gguf_max_tokens: Optional[int] = Field(None, ge=64, le=16384)
    temperature: Optional[float] = Field(None, ge=0.0, le=2.0)
    min_messages: Optional[int] = Field(None, ge=1, le=50)
    timeout_seconds: Optional[int] = Field(None, ge=10, le=300)
    prompt_template: Optional[str] = None
    auto_compress_enabled: Optional[bool] = None
    auto_compress_threshold: Optional[float] = Field(None, ge=0.1, le=0.9)


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
            provider=config.provider,
            model_id=config.model_id,
            local_gguf_model_path=config.local_gguf_model_path,
            local_gguf_n_ctx=config.local_gguf_n_ctx,
            local_gguf_n_threads=config.local_gguf_n_threads,
            local_gguf_n_gpu_layers=config.local_gguf_n_gpu_layers,
            local_gguf_max_tokens=config.local_gguf_max_tokens,
            temperature=config.temperature,
            min_messages=config.min_messages,
            timeout_seconds=config.timeout_seconds,
            prompt_template=config.prompt_template,
            auto_compress_enabled=config.auto_compress_enabled,
            auto_compress_threshold=config.auto_compress_threshold,
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

        if 'provider' in update_dict:
            allowed = {"model_config", "local_gguf"}
            if update_dict['provider'] not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported compression provider: {update_dict['provider']}"
                )

        service.save_config(update_dict)

        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update compression config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
