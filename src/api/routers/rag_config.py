"""
RAG Config API Router

Provides endpoints for configuring RAG (Retrieval-Augmented Generation) settings.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional
import logging

from ..services.rag_config_service import RagConfigService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/rag", tags=["rag"])


class RagConfigResponse(BaseModel):
    """Response model for RAG configuration"""
    embedding_provider: str
    embedding_api_model: str
    embedding_api_base_url: str = ""
    embedding_api_key: str = ""
    embedding_local_model: str
    embedding_local_device: str
    embedding_local_gguf_model_path: str
    embedding_local_gguf_n_ctx: int
    embedding_local_gguf_n_threads: int
    embedding_local_gguf_n_gpu_layers: int
    embedding_local_gguf_normalize: bool
    chunk_size: int
    chunk_overlap: int
    top_k: int
    score_threshold: float
    persist_directory: str


class RagConfigUpdate(BaseModel):
    """Request model for updating RAG configuration"""
    embedding_provider: Optional[str] = None
    embedding_api_model: Optional[str] = None
    embedding_api_base_url: Optional[str] = None
    embedding_api_key: Optional[str] = None
    embedding_local_model: Optional[str] = None
    embedding_local_device: Optional[str] = None
    embedding_local_gguf_model_path: Optional[str] = None
    embedding_local_gguf_n_ctx: Optional[int] = Field(None, ge=256, le=65536)
    embedding_local_gguf_n_threads: Optional[int] = Field(None, ge=0, le=256)
    embedding_local_gguf_n_gpu_layers: Optional[int] = Field(None, ge=0, le=1024)
    embedding_local_gguf_normalize: Optional[bool] = None
    chunk_size: Optional[int] = Field(None, ge=100, le=10000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=5000)
    top_k: Optional[int] = Field(None, ge=1, le=50)
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    persist_directory: Optional[str] = None


def get_rag_config_service() -> RagConfigService:
    """Dependency injection for RagConfigService."""
    return RagConfigService()


@router.get("/config", response_model=RagConfigResponse)
async def get_config(
    service: RagConfigService = Depends(get_rag_config_service)
):
    """Get current RAG configuration"""
    try:
        flat = service.get_flat_config()
        return RagConfigResponse(**flat)
    except Exception as e:
        logger.error(f"Failed to get RAG config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: RagConfigUpdate,
    service: RagConfigService = Depends(get_rag_config_service)
):
    """Update RAG configuration"""
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Validate embedding provider
        if 'embedding_provider' in update_dict:
            allowed = {"api", "local", "local_gguf"}
            if update_dict['embedding_provider'] not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported embedding provider: {update_dict['embedding_provider']}"
                )

        service.save_flat_config(update_dict)
        return {"message": "RAG configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update RAG config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
