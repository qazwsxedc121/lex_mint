"""
RAG Config API Router

Provides endpoints for configuring RAG (Retrieval-Augmented Generation) settings.
"""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Literal, Optional
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
    embedding_batch_size: int
    embedding_batch_delay_seconds: float
    embedding_batch_max_retries: int
    chunk_size: int
    chunk_overlap: int
    retrieval_mode: str
    top_k: int
    score_threshold: float
    recall_k: int
    vector_recall_k: int
    bm25_recall_k: int
    bm25_min_term_coverage: float
    fusion_top_k: int
    fusion_strategy: str
    rrf_k: int
    vector_weight: float
    bm25_weight: float
    max_per_doc: int
    reorder_strategy: str
    rerank_enabled: bool
    rerank_api_model: str
    rerank_api_base_url: str
    rerank_api_key: str = ""
    rerank_timeout_seconds: int
    rerank_weight: float
    vector_store_backend: str
    vector_sqlite_path: str
    persist_directory: str
    bm25_sqlite_path: str


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
    embedding_batch_size: Optional[int] = Field(None, ge=1, le=1000)
    embedding_batch_delay_seconds: Optional[float] = Field(None, ge=0.0, le=60.0)
    embedding_batch_max_retries: Optional[int] = Field(None, ge=0, le=20)
    chunk_size: Optional[int] = Field(None, ge=100, le=10000)
    chunk_overlap: Optional[int] = Field(None, ge=0, le=5000)
    retrieval_mode: Optional[Literal["vector", "bm25", "hybrid"]] = None
    top_k: Optional[int] = Field(None, ge=1, le=50)
    score_threshold: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall_k: Optional[int] = Field(None, ge=1, le=200)
    vector_recall_k: Optional[int] = Field(None, ge=1, le=500)
    bm25_recall_k: Optional[int] = Field(None, ge=1, le=500)
    bm25_min_term_coverage: Optional[float] = Field(None, ge=0.0, le=1.0)
    fusion_top_k: Optional[int] = Field(None, ge=1, le=500)
    fusion_strategy: Optional[Literal["rrf"]] = None
    rrf_k: Optional[int] = Field(None, ge=1, le=500)
    vector_weight: Optional[float] = Field(None, ge=0.0, le=10.0)
    bm25_weight: Optional[float] = Field(None, ge=0.0, le=10.0)
    max_per_doc: Optional[int] = Field(None, ge=0, le=20)
    reorder_strategy: Optional[Literal["none", "long_context"]] = None
    rerank_enabled: Optional[bool] = None
    rerank_api_model: Optional[str] = None
    rerank_api_base_url: Optional[str] = None
    rerank_api_key: Optional[str] = None
    rerank_timeout_seconds: Optional[int] = Field(None, ge=1, le=120)
    rerank_weight: Optional[float] = Field(None, ge=0.0, le=1.0)
    vector_store_backend: Optional[Literal["sqlite_vec", "chroma"]] = None
    vector_sqlite_path: Optional[str] = None
    persist_directory: Optional[str] = None
    bm25_sqlite_path: Optional[str] = None


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
        if 'reorder_strategy' in update_dict:
            allowed_strategies = {"none", "long_context"}
            if update_dict['reorder_strategy'] not in allowed_strategies:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported reorder strategy: {update_dict['reorder_strategy']}"
                )
        if 'fusion_strategy' in update_dict:
            allowed_fusion = {"rrf"}
            if update_dict['fusion_strategy'] not in allowed_fusion:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported fusion strategy: {update_dict['fusion_strategy']}"
                )
        if 'vector_store_backend' in update_dict:
            allowed_backends = {"sqlite_vec", "chroma"}
            if update_dict['vector_store_backend'] not in allowed_backends:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported vector backend: {update_dict['vector_store_backend']}"
                )

        service.save_flat_config(update_dict)
        return {"message": "RAG configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update RAG config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
