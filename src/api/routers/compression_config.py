"""
Compression Config API Router

Provides endpoints for configuring context compression.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional
import logging

from ..services.compression_config_service import CompressionConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/compression", tags=["compression"])
ALLOWED_OUTPUT_LANGUAGES = {"auto", "none", "zh", "en", "ja", "ko", "fr", "de", "es", "ru", "pt"}


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
    compression_output_language: str
    compression_strategy: str
    hierarchical_chunk_target_tokens: int
    hierarchical_chunk_overlap_messages: int
    hierarchical_reduce_target_tokens: int
    hierarchical_reduce_overlap_items: int
    hierarchical_max_levels: int
    quality_guard_enabled: bool
    quality_guard_min_coverage: float
    quality_guard_max_facts: int
    compression_metrics_enabled: bool
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
    compression_output_language: Optional[str] = None
    compression_strategy: Optional[Literal["single_pass", "hierarchical"]] = None
    hierarchical_chunk_target_tokens: Optional[int] = Field(None, ge=0, le=8192)
    hierarchical_chunk_overlap_messages: Optional[int] = Field(None, ge=0, le=20)
    hierarchical_reduce_target_tokens: Optional[int] = Field(None, ge=0, le=16384)
    hierarchical_reduce_overlap_items: Optional[int] = Field(None, ge=0, le=10)
    hierarchical_max_levels: Optional[int] = Field(None, ge=1, le=8)
    quality_guard_enabled: Optional[bool] = None
    quality_guard_min_coverage: Optional[float] = Field(None, ge=0.5, le=1.0)
    quality_guard_max_facts: Optional[int] = Field(None, ge=5, le=100)
    compression_metrics_enabled: Optional[bool] = None
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
            compression_output_language=config.compression_output_language,
            compression_strategy=config.compression_strategy,
            hierarchical_chunk_target_tokens=config.hierarchical_chunk_target_tokens,
            hierarchical_chunk_overlap_messages=config.hierarchical_chunk_overlap_messages,
            hierarchical_reduce_target_tokens=config.hierarchical_reduce_target_tokens,
            hierarchical_reduce_overlap_items=config.hierarchical_reduce_overlap_items,
            hierarchical_max_levels=config.hierarchical_max_levels,
            quality_guard_enabled=config.quality_guard_enabled,
            quality_guard_min_coverage=config.quality_guard_min_coverage,
            quality_guard_max_facts=config.quality_guard_max_facts,
            compression_metrics_enabled=config.compression_metrics_enabled,
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
        if 'compression_output_language' in update_dict:
            value = str(update_dict['compression_output_language']).strip().lower()
            if value not in ALLOWED_OUTPUT_LANGUAGES:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported compression output language: {update_dict['compression_output_language']}"
                )
            update_dict['compression_output_language'] = value
        if 'compression_strategy' in update_dict:
            allowed_strategies = {"single_pass", "hierarchical"}
            if update_dict['compression_strategy'] not in allowed_strategies:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported compression strategy: {update_dict['compression_strategy']}"
                )

        service.save_config(update_dict)

        return {"message": "Configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update compression config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
