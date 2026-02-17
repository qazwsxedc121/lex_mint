"""Unit tests for RAG retrieval reorder and diversity behavior."""

import asyncio
from types import SimpleNamespace

import pytest

from src.api.services.rag_service import RagResult, RagService


class _FakeKnowledgeBaseService:
    async def get_knowledge_base(self, kb_id: str):
        return SimpleNamespace(
            id=kb_id,
            enabled=True,
            embedding_model=None,
            document_count=1,
        )


def _build_service(
    *,
    top_k: int,
    score_threshold: float,
    recall_k: int,
    max_per_doc: int,
    reorder_strategy: str,
    retrieval_mode: str = "vector",
    vector_recall_k: int | None = None,
    bm25_recall_k: int | None = None,
    fusion_top_k: int = 30,
    fusion_strategy: str = "rrf",
    rrf_k: int = 60,
    vector_weight: float = 1.0,
    bm25_weight: float = 1.0,
    bm25_min_term_coverage: float = 0.35,
) -> RagService:
    service = RagService.__new__(RagService)
    service.rag_config_service = SimpleNamespace(
        config=SimpleNamespace(
            retrieval=SimpleNamespace(
                retrieval_mode=retrieval_mode,
                top_k=top_k,
                score_threshold=score_threshold,
                recall_k=recall_k,
                vector_recall_k=vector_recall_k if vector_recall_k is not None else recall_k,
                bm25_recall_k=bm25_recall_k if bm25_recall_k is not None else recall_k,
                bm25_min_term_coverage=bm25_min_term_coverage,
                fusion_top_k=fusion_top_k,
                fusion_strategy=fusion_strategy,
                rrf_k=rrf_k,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
                max_per_doc=max_per_doc,
                reorder_strategy=reorder_strategy,
                rerank_enabled=False,
                rerank_api_model="jina-reranker-v2-base-multilingual",
                rerank_api_base_url="https://api.jina.ai/v1/rerank",
                rerank_api_key="",
                rerank_timeout_seconds=20,
                rerank_weight=0.7,
            ),
            embedding=SimpleNamespace(
                provider="api",
                api_model="test-embedding",
                api_base_url="",
            ),
            storage=SimpleNamespace(persist_directory="data/chromadb"),
        )
    )
    service.embedding_service = None
    service.rerank_service = None
    service.bm25_service = None
    return service


def test_retrieve_uses_recall_k_and_doc_diversity(monkeypatch):
    service = _build_service(
        top_k=3,
        score_threshold=0.3,
        recall_k=7,
        max_per_doc=1,
        reorder_strategy="none",
    )
    monkeypatch.setattr(
        "src.api.services.knowledge_base_service.KnowledgeBaseService",
        _FakeKnowledgeBaseService,
    )

    seen_top_k = []

    def fake_search_collection(kb_id, query, top_k, score_threshold, override_model=None):
        seen_top_k.append(top_k)
        if kb_id == "kb_a":
            return [
                RagResult("A chunk 0", 0.95, "kb_a", "doc_a", "a.md", 0),
                RagResult("A chunk 0 duplicate", 0.95, "kb_a", "doc_a", "a.md", 0),
                RagResult("A chunk 1", 0.90, "kb_a", "doc_a", "a.md", 1),
                RagResult("B chunk 0", 0.80, "kb_a", "doc_b", "b.md", 0),
            ]
        return [
            RagResult("C chunk 0", 0.85, "kb_b", "doc_c", "c.md", 0),
        ]

    monkeypatch.setattr(service, "_search_collection", fake_search_collection)

    results, diagnostics = asyncio.run(service.retrieve_with_diagnostics("query", ["kb_a", "kb_b"]))

    assert seen_top_k == [7, 7]
    assert [item.doc_id for item in results] == ["doc_a", "doc_c", "doc_b"]
    assert diagnostics["raw_count"] == 5
    assert diagnostics["deduped_count"] == 4
    assert diagnostics["diversified_count"] == 3
    assert diagnostics["selected_count"] == 3


def test_retrieve_long_context_reorders_selected_results(monkeypatch):
    service = _build_service(
        top_k=6,
        score_threshold=0.3,
        recall_k=6,
        max_per_doc=6,
        reorder_strategy="long_context",
    )
    monkeypatch.setattr(
        "src.api.services.knowledge_base_service.KnowledgeBaseService",
        _FakeKnowledgeBaseService,
    )

    def fake_search_collection(kb_id, query, top_k, score_threshold, override_model=None):
        return [
            RagResult("chunk 1", 0.96, kb_id, "doc_1", "d1.md", 1),
            RagResult("chunk 2", 0.92, kb_id, "doc_2", "d2.md", 2),
            RagResult("chunk 3", 0.88, kb_id, "doc_3", "d3.md", 3),
            RagResult("chunk 4", 0.84, kb_id, "doc_4", "d4.md", 4),
            RagResult("chunk 5", 0.80, kb_id, "doc_5", "d5.md", 5),
            RagResult("chunk 6", 0.76, kb_id, "doc_6", "d6.md", 6),
        ]

    monkeypatch.setattr(service, "_search_collection", fake_search_collection)

    results = asyncio.run(service.retrieve("query", ["kb_a"]))

    assert [item.doc_id for item in results] == [
        "doc_1",
        "doc_3",
        "doc_5",
        "doc_6",
        "doc_4",
        "doc_2",
    ]


def test_reorder_strategy_none_keeps_order():
    items = [
        RagResult("chunk 1", 0.9, "kb", "doc_1", "1.md", 1),
        RagResult("chunk 2", 0.8, "kb", "doc_2", "2.md", 2),
    ]
    output = RagService._reorder_results(items, "none")
    assert output == items


def test_build_rag_diagnostics_source_contains_expected_fields():
    source = RagService.build_rag_diagnostics_source(
        {
            "raw_count": 8,
            "deduped_count": 7,
            "diversified_count": 5,
            "selected_count": 3,
            "top_k": 3,
            "recall_k": 12,
            "score_threshold": 0.35,
            "max_per_doc": 2,
            "reorder_strategy": "long_context",
            "searched_kb_count": 2,
            "requested_kb_count": 3,
            "best_score": 0.91,
        }
    )

    assert source["type"] == "rag_diagnostics"
    assert source["raw_count"] == 8
    assert source["selected_count"] == 3
    assert source["reorder_strategy"] == "long_context"
    assert source["requested_kb_count"] == 3
    assert source["best_score"] == pytest.approx(0.91)


def test_retrieve_with_rerank_reorders_by_blended_score(monkeypatch):
    service = _build_service(
        top_k=3,
        score_threshold=0.0,
        recall_k=10,
        max_per_doc=3,
        reorder_strategy="none",
    )
    service.rag_config_service.config.retrieval.rerank_enabled = True
    service.rag_config_service.config.retrieval.rerank_weight = 1.0

    monkeypatch.setattr(
        "src.api.services.knowledge_base_service.KnowledgeBaseService",
        _FakeKnowledgeBaseService,
    )

    def fake_search_collection(kb_id, query, top_k, score_threshold, override_model=None):
        return [
            RagResult("chunk 1", 0.95, kb_id, "doc_1", "d1.md", 1),
            RagResult("chunk 2", 0.90, kb_id, "doc_2", "d2.md", 2),
            RagResult("chunk 3", 0.85, kb_id, "doc_3", "d3.md", 3),
        ]

    async def fake_rerank(**kwargs):
        _ = kwargs
        return {0: 0.1, 1: 0.9, 2: 0.7}

    monkeypatch.setattr(service, "_search_collection", fake_search_collection)
    service.rerank_service = SimpleNamespace(rerank=fake_rerank)

    results, diagnostics = asyncio.run(service.retrieve_with_diagnostics("query", ["kb_a"]))

    assert [item.doc_id for item in results] == ["doc_2", "doc_3", "doc_1"]
    assert diagnostics["rerank_enabled"] is True
    assert diagnostics["rerank_applied"] is True


def test_retrieve_hybrid_rrf_merges_vector_and_bm25(monkeypatch):
    service = _build_service(
        top_k=3,
        score_threshold=0.0,
        recall_k=10,
        max_per_doc=3,
        reorder_strategy="none",
        retrieval_mode="hybrid",
        vector_recall_k=10,
        bm25_recall_k=10,
        fusion_top_k=10,
        vector_weight=1.0,
        bm25_weight=1.0,
        rrf_k=60,
    )
    monkeypatch.setattr(
        "src.api.services.knowledge_base_service.KnowledgeBaseService",
        _FakeKnowledgeBaseService,
    )

    def fake_search_collection(kb_id, query, top_k, score_threshold, override_model=None):
        _ = kb_id, query, top_k, score_threshold, override_model
        return [
            RagResult("vec-a", 0.95, "kb_a", "doc_a", "a.md", 0),
            RagResult("vec-b", 0.90, "kb_a", "doc_b", "b.md", 0),
        ]

    def fake_search_bm25_collection(*, kb_id, query, top_k, min_term_coverage):
        _ = kb_id, query, top_k
        assert min_term_coverage == pytest.approx(0.35)
        return [
            RagResult("bm25-b", 0.96, "kb_a", "doc_b", "b.md", 0),
            RagResult("bm25-c", 0.92, "kb_a", "doc_c", "c.md", 0),
        ]

    monkeypatch.setattr(service, "_search_collection", fake_search_collection)
    monkeypatch.setattr(service, "_search_bm25_collection", fake_search_bm25_collection)

    results, diagnostics = asyncio.run(service.retrieve_with_diagnostics("query", ["kb_a"]))

    assert [item.doc_id for item in results] == ["doc_b", "doc_a", "doc_c"]
    assert diagnostics["retrieval_mode"] == "hybrid"
    assert diagnostics["vector_raw_count"] == 2
    assert diagnostics["bm25_raw_count"] == 2
    assert diagnostics["bm25_min_term_coverage"] == pytest.approx(0.35)


def test_search_collection_dispatches_to_sqlite_vec(monkeypatch):
    service = _build_service(
        top_k=3,
        score_threshold=0.0,
        recall_k=10,
        max_per_doc=3,
        reorder_strategy="none",
    )
    service.rag_config_service.config.storage.vector_store_backend = "sqlite_vec"

    def fake_sqlite_search(kb_id, query, top_k, score_threshold, override_model=None):
        _ = query, top_k, score_threshold, override_model
        return [RagResult("sqlite", 0.9, kb_id, "doc_sqlite", "sqlite.md", 0)]

    def fail_chroma_search(*args, **kwargs):
        _ = args, kwargs
        raise AssertionError("chroma backend should not be used when sqlite_vec is selected")

    monkeypatch.setattr(service, "_search_collection_sqlite_vec", fake_sqlite_search)
    monkeypatch.setattr(service, "_search_collection_chroma", fail_chroma_search)

    result = service._search_collection("kb1", "hello", 5, 0.1, None)
    assert len(result) == 1
    assert result[0].doc_id == "doc_sqlite"
