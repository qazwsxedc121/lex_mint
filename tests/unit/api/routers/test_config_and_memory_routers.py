"""Tests for config and memory API routers."""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import HTTPException

from src.api.routers import compression_config as compression_router
from src.api.routers import memory as memory_router
from src.api.routers import rag_config as rag_router


class _CompressionConfig:
    provider = "model_config"
    model_id = "openai:gpt-4.1-mini"
    local_gguf_model_path = ""
    local_gguf_n_ctx = 4096
    local_gguf_n_threads = 4
    local_gguf_n_gpu_layers = 0
    local_gguf_max_tokens = 1024
    temperature = 0.2
    min_messages = 2
    timeout_seconds = 30
    prompt_template = "compress"
    compression_output_language = "auto"
    compression_strategy = "single_pass"
    hierarchical_chunk_target_tokens = 400
    hierarchical_chunk_overlap_messages = 1
    hierarchical_reduce_target_tokens = 800
    hierarchical_reduce_overlap_items = 1
    hierarchical_max_levels = 2
    quality_guard_enabled = True
    quality_guard_min_coverage = 0.8
    quality_guard_max_facts = 20
    compression_metrics_enabled = True
    auto_compress_enabled = False
    auto_compress_threshold = 0.5


class _CompressionService:
    def __init__(self):
        self.config = _CompressionConfig()
        self.saved: dict[str, Any] | None = None

    def save_config(self, updates: dict[str, Any]) -> None:
        self.saved = updates


class _RagService:
    def __init__(self):
        self.saved: dict[str, Any] | None = None
        self.flat = {
            "embedding_provider": "api",
            "embedding_api_model": "text-embedding-3-small",
            "embedding_api_base_url": "",
            "embedding_api_key": "",
            "embedding_local_model": "",
            "embedding_local_device": "cpu",
            "embedding_local_gguf_model_path": "",
            "embedding_local_gguf_n_ctx": 2048,
            "embedding_local_gguf_n_threads": 4,
            "embedding_local_gguf_n_gpu_layers": 0,
            "embedding_local_gguf_normalize": True,
            "embedding_batch_size": 8,
            "embedding_batch_delay_seconds": 0.0,
            "embedding_batch_max_retries": 1,
            "chunk_size": 500,
            "chunk_overlap": 50,
            "retrieval_mode": "hybrid",
            "top_k": 6,
            "score_threshold": 0.2,
            "recall_k": 20,
            "vector_recall_k": 20,
            "bm25_recall_k": 20,
            "bm25_min_term_coverage": 0.35,
            "fusion_top_k": 20,
            "fusion_strategy": "rrf",
            "rrf_k": 60,
            "vector_weight": 1.0,
            "bm25_weight": 1.0,
            "max_per_doc": 2,
            "reorder_strategy": "none",
            "context_neighbor_window": 1,
            "context_neighbor_max_total": 10,
            "context_neighbor_dedup_coverage": 0.9,
            "retrieval_query_planner_enabled": False,
            "retrieval_query_planner_model_id": "",
            "retrieval_query_planner_max_queries": 3,
            "retrieval_query_planner_timeout_seconds": 5,
            "structured_source_context_enabled": True,
            "query_transform_enabled": False,
            "query_transform_mode": "none",
            "query_transform_model_id": "",
            "query_transform_timeout_seconds": 5,
            "query_transform_guard_enabled": False,
            "query_transform_guard_max_new_terms": 4,
            "query_transform_crag_enabled": False,
            "query_transform_crag_lower_threshold": 0.3,
            "query_transform_crag_upper_threshold": 0.7,
            "rerank_enabled": False,
            "rerank_api_model": "",
            "rerank_api_base_url": "",
            "rerank_api_key": "",
            "rerank_timeout_seconds": 30,
            "rerank_weight": 0.3,
            "vector_store_backend": "sqlite_vec",
            "vector_sqlite_path": "vec.db",
            "persist_directory": "persist",
            "bm25_sqlite_path": "bm25.db",
        }

    def get_flat_config(self) -> dict[str, Any]:
        return dict(self.flat)

    def save_flat_config(self, updates: dict[str, Any]) -> None:
        self.saved = updates


class _MemoryConfigService:
    def __init__(self):
        self.saved: dict[str, Any] | None = None

    def get_flat_config(self) -> dict[str, Any]:
        return {
            "enabled": True,
            "profile_id": "default",
            "collection_name": "memories",
            "enabled_layers": ["fact"],
            "top_k": 6,
            "score_threshold": 0.2,
            "max_injected_items": 4,
            "max_item_length": 200,
            "auto_extract_enabled": True,
            "min_text_length": 20,
            "max_items_per_turn": 3,
            "global_enabled": True,
            "assistant_enabled": True,
        }

    def save_flat_config(self, updates: dict[str, Any]) -> None:
        self.saved = updates


class _MemoryService:
    def __init__(self):
        self.calls: list[tuple[str, Any]] = []
        self.fail_with: Exception | None = None

    def list_memories(self, **kwargs):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("list", kwargs))
        return [{"id": "m1", "content": "fact"}]

    def upsert_memory(self, **kwargs):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("create", kwargs))
        return {"id": "m1", **kwargs}

    def update_memory(self, memory_id: str, **kwargs):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("update", {"memory_id": memory_id, **kwargs}))
        return {"id": memory_id, **kwargs}

    def delete_memory(self, memory_id: str):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("delete", memory_id))

    def search_memories(self, **kwargs):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("search_scope", kwargs))
        return [{"id": "m1"}]

    def search_memories_for_scopes(self, **kwargs):
        if self.fail_with:
            raise self.fail_with
        self.calls.append(("search_scopes", kwargs))
        return [{"id": "m2"}]

    def build_memory_context(self, **kwargs):
        self.calls.append(("context", kwargs))
        return "memory context", [{"id": "m2"}]


@pytest.mark.asyncio
async def test_compression_config_router_get_and_update():
    service = _CompressionService()

    response = await compression_router.get_config(service=service)
    assert response.provider == "model_config"

    update_response = await compression_router.update_config(
        updates=compression_router.CompressionConfigUpdate(
            provider="local_gguf",
            compression_output_language="EN",
            compression_strategy="hierarchical",
        ),
        service=service,
    )
    assert update_response["message"] == "Configuration updated successfully"
    assert service.saved == {
        "provider": "local_gguf",
        "compression_output_language": "en",
        "compression_strategy": "hierarchical",
    }

    with pytest.raises(HTTPException) as exc_info:
        await compression_router.update_config(
            updates=compression_router.CompressionConfigUpdate(provider="invalid"),
            service=service,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_rag_config_router_get_and_update():
    service = _RagService()

    response = await rag_router.get_config(service=service)
    assert response.embedding_provider == "api"

    update_response = await rag_router.update_config(
        updates=rag_router.RagConfigUpdate(
            embedding_provider="local",
            reorder_strategy="long_context",
            query_transform_mode="rewrite",
            query_transform_crag_lower_threshold=0.2,
            query_transform_crag_upper_threshold=0.9,
            vector_store_backend="chroma",
        ),
        service=service,
    )
    assert update_response["message"] == "RAG configuration updated successfully"
    assert service.saved["embedding_provider"] == "local"
    assert service.saved["vector_store_backend"] == "chroma"

    with pytest.raises(HTTPException) as exc_info:
        await rag_router.update_config(
            updates=rag_router.RagConfigUpdate(
                query_transform_crag_lower_threshold=0.8,
                query_transform_crag_upper_threshold=0.4,
            ),
            service=service,
        )
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_memory_router_crud_and_search():
    config_service = _MemoryConfigService()
    memory_service = _MemoryService()

    settings = await memory_router.get_memory_settings(service=config_service)
    assert settings.enabled is True

    update_response = await memory_router.update_memory_settings(
        updates=memory_router.MemorySettingsUpdate(top_k=5),
        service=config_service,
    )
    assert update_response["message"] == "Memory settings updated successfully"
    assert config_service.saved == {"top_k": 5}

    list_response = await memory_router.list_memories(limit=10, service=memory_service)
    assert list_response.count == 1

    create_response = await memory_router.create_memory(
        request=memory_router.MemoryCreateRequest(content="remember this"),
        service=memory_service,
    )
    assert create_response["item"]["content"] == "remember this"

    update_item_response = await memory_router.update_memory(
        memory_id="m1",
        request=memory_router.MemoryUpdateRequest(content="updated"),
        service=memory_service,
    )
    assert update_item_response["item"]["content"] == "updated"

    delete_response = await memory_router.delete_memory(memory_id="m1", service=memory_service)
    assert delete_response["id"] == "m1"

    scoped_search = await memory_router.search_memory(
        request=memory_router.MemorySearchRequest(query="fact", scope="global"),
        service=memory_service,
    )
    assert scoped_search["count"] == 1

    blended_search = await memory_router.search_memory(
        request=memory_router.MemorySearchRequest(query="fact", scope=None),
        service=memory_service,
    )
    assert blended_search["context"] == "memory context"


@pytest.mark.asyncio
async def test_memory_router_maps_errors():
    service = _MemoryService()
    service.fail_with = ValueError("bad filter")

    with pytest.raises(HTTPException) as exc_info:
        await memory_router.list_memories(limit=10, service=service)
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await memory_router.create_memory(
            request=memory_router.MemoryCreateRequest(content="x"),
            service=service,
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await memory_router.update_memory(
            memory_id="m1",
            request=memory_router.MemoryUpdateRequest(content="x"),
            service=service,
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await memory_router.search_memory(
            request=memory_router.MemorySearchRequest(query="x"),
            service=service,
        )
    assert exc_info.value.status_code == 400
