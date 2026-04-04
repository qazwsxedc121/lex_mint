"""
RAG Config API Router

Provides endpoints for configuring RAG (Retrieval-Augmented Generation) settings.
"""

import logging
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from src.api.routers.service_protocols import FlatConfigServiceLike
from src.infrastructure.config.rag_config_service import RagConfigService

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
    context_neighbor_window: int
    context_neighbor_max_total: int
    context_neighbor_dedup_coverage: float
    retrieval_query_planner_enabled: bool
    retrieval_query_planner_model_id: str
    retrieval_query_planner_max_queries: int
    retrieval_query_planner_timeout_seconds: int
    structured_source_context_enabled: bool
    query_transform_enabled: bool
    query_transform_mode: str
    query_transform_model_id: str
    query_transform_timeout_seconds: int
    query_transform_guard_enabled: bool
    query_transform_guard_max_new_terms: int
    query_transform_crag_enabled: bool
    query_transform_crag_lower_threshold: float
    query_transform_crag_upper_threshold: float
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

    embedding_provider: str | None = None
    embedding_api_model: str | None = None
    embedding_api_base_url: str | None = None
    embedding_api_key: str | None = None
    embedding_local_model: str | None = None
    embedding_local_device: str | None = None
    embedding_local_gguf_model_path: str | None = None
    embedding_local_gguf_n_ctx: int | None = Field(default=None, ge=256, le=65536)
    embedding_local_gguf_n_threads: int | None = Field(default=None, ge=0, le=256)
    embedding_local_gguf_n_gpu_layers: int | None = Field(default=None, ge=0, le=1024)
    embedding_local_gguf_normalize: bool | None = None
    embedding_batch_size: int | None = Field(default=None, ge=1, le=1000)
    embedding_batch_delay_seconds: float | None = Field(default=None, ge=0.0, le=60.0)
    embedding_batch_max_retries: int | None = Field(default=None, ge=0, le=20)
    chunk_size: int | None = Field(default=None, ge=100, le=10000)
    chunk_overlap: int | None = Field(default=None, ge=0, le=5000)
    retrieval_mode: Literal["vector", "bm25", "hybrid"] | None = None
    top_k: int | None = Field(default=None, ge=1, le=50)
    score_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    recall_k: int | None = Field(default=None, ge=1, le=200)
    vector_recall_k: int | None = Field(default=None, ge=1, le=500)
    bm25_recall_k: int | None = Field(default=None, ge=1, le=500)
    bm25_min_term_coverage: float | None = Field(default=None, ge=0.0, le=1.0)
    fusion_top_k: int | None = Field(default=None, ge=1, le=500)
    fusion_strategy: Literal["rrf"] | None = None
    rrf_k: int | None = Field(default=None, ge=1, le=500)
    vector_weight: float | None = Field(default=None, ge=0.0, le=10.0)
    bm25_weight: float | None = Field(default=None, ge=0.0, le=10.0)
    max_per_doc: int | None = Field(default=None, ge=0, le=20)
    reorder_strategy: Literal["none", "long_context"] | None = None
    context_neighbor_window: int | None = Field(default=None, ge=0, le=10)
    context_neighbor_max_total: int | None = Field(default=None, ge=0, le=200)
    context_neighbor_dedup_coverage: float | None = Field(default=None, ge=0.5, le=1.0)
    retrieval_query_planner_enabled: bool | None = None
    retrieval_query_planner_model_id: str | None = None
    retrieval_query_planner_max_queries: int | None = Field(default=None, ge=1, le=8)
    retrieval_query_planner_timeout_seconds: int | None = Field(default=None, ge=1, le=30)
    structured_source_context_enabled: bool | None = None
    query_transform_enabled: bool | None = None
    query_transform_mode: Literal["none", "rewrite"] | None = None
    query_transform_model_id: str | None = None
    query_transform_timeout_seconds: int | None = Field(default=None, ge=1, le=30)
    query_transform_guard_enabled: bool | None = None
    query_transform_guard_max_new_terms: int | None = Field(default=None, ge=0, le=20)
    query_transform_crag_enabled: bool | None = None
    query_transform_crag_lower_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    query_transform_crag_upper_threshold: float | None = Field(default=None, ge=0.0, le=1.0)
    rerank_enabled: bool | None = None
    rerank_api_model: str | None = None
    rerank_api_base_url: str | None = None
    rerank_api_key: str | None = None
    rerank_timeout_seconds: int | None = Field(default=None, ge=1, le=120)
    rerank_weight: float | None = Field(default=None, ge=0.0, le=1.0)
    vector_store_backend: Literal["sqlite_vec", "chroma"] | None = None
    vector_sqlite_path: str | None = None
    persist_directory: str | None = None
    bm25_sqlite_path: str | None = None


def get_rag_config_service() -> RagConfigService:
    """Dependency injection for RagConfigService."""
    return RagConfigService()


@router.get("/config", response_model=RagConfigResponse)
async def get_config(service: FlatConfigServiceLike = Depends(get_rag_config_service)):
    """Get current RAG configuration"""
    try:
        flat = service.get_flat_config()
        return RagConfigResponse(**flat)
    except Exception as e:
        logger.error(f"Failed to get RAG config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config")
async def update_config(
    updates: RagConfigUpdate, service: FlatConfigServiceLike = Depends(get_rag_config_service)
):
    """Update RAG configuration"""
    try:
        update_dict = updates.model_dump(exclude_none=True)
        if not update_dict:
            raise HTTPException(status_code=400, detail="No updates provided")

        # Validate embedding provider
        if "embedding_provider" in update_dict:
            allowed = {"api", "local", "local_gguf"}
            if update_dict["embedding_provider"] not in allowed:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported embedding provider: {update_dict['embedding_provider']}",
                )
        if "reorder_strategy" in update_dict:
            allowed_strategies = {"none", "long_context"}
            if update_dict["reorder_strategy"] not in allowed_strategies:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported reorder strategy: {update_dict['reorder_strategy']}",
                )
        if "query_transform_mode" in update_dict:
            allowed_modes = {"none", "rewrite"}
            if update_dict["query_transform_mode"] not in allowed_modes:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported query transform mode: {update_dict['query_transform_mode']}",
                )
        if (
            "query_transform_crag_lower_threshold" in update_dict
            or "query_transform_crag_upper_threshold" in update_dict
        ):
            current = service.get_flat_config()
            lower_value = float(
                update_dict.get(
                    "query_transform_crag_lower_threshold",
                    current["query_transform_crag_lower_threshold"],
                )
            )
            upper_value = float(
                update_dict.get(
                    "query_transform_crag_upper_threshold",
                    current["query_transform_crag_upper_threshold"],
                )
            )
            if lower_value >= upper_value:
                raise HTTPException(
                    status_code=400,
                    detail="query_transform_crag_lower_threshold must be smaller than query_transform_crag_upper_threshold",
                )
        if "fusion_strategy" in update_dict:
            allowed_fusion = {"rrf"}
            if update_dict["fusion_strategy"] not in allowed_fusion:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported fusion strategy: {update_dict['fusion_strategy']}",
                )
        if "vector_store_backend" in update_dict:
            allowed_backends = {"sqlite_vec", "chroma"}
            if update_dict["vector_store_backend"] not in allowed_backends:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported vector backend: {update_dict['vector_store_backend']}",
                )

        service.save_flat_config(update_dict)
        return {"message": "RAG configuration updated successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update RAG config: {e}")
        raise HTTPException(status_code=500, detail=str(e))
