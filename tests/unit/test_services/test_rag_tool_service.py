"""Unit tests for session-scoped RAG tool service."""

import asyncio
import json

from src.api.services.rag_service import RagResult
from src.api.services.rag_tool_service import RagToolService


class _FakeRagService:
    async def retrieve_with_diagnostics(self, *, query, kb_ids, top_k, runtime_model_id):
        _ = (query, kb_ids, top_k, runtime_model_id)
        return (
            [
                RagResult(
                    content="Chunk content for testing.",
                    score=0.42,
                    kb_id="kb_test",
                    doc_id="doc_1",
                    filename="doc.md",
                    chunk_index=3,
                )
            ],
            {
                "query_effective": "effective query",
                "retrieval_queries": ["q1", "q2"],
                "retrieval_query_planner_applied": True,
                "retrieval_mode": "hybrid",
                "raw_count": 1,
                "selected_count": 1,
            },
        )


class _FakeBm25Service:
    def list_document_chunks_in_range(self, *, kb_id, doc_id, start_index, end_index, limit):
        _ = (kb_id, doc_id, start_index, end_index, limit)
        return [
            {
                "chunk_id": "c1",
                "kb_id": "kb_test",
                "doc_id": "doc_1",
                "filename": "doc.md",
                "chunk_index": 3,
                "content": "Exact chunk payload",
            }
        ]


class _FakeSqliteVecService:
    def list_document_chunks_in_range(self, *, kb_id, doc_id, start_index, end_index, limit):
        _ = (kb_id, doc_id, start_index, end_index, limit)
        return []


def _build_service(allowed_kb_ids=None):
    return RagToolService(
        assistant_id="assistant_a",
        allowed_kb_ids=allowed_kb_ids if allowed_kb_ids is not None else ["kb_test"],
        runtime_model_id="deepseek:deepseek-chat",
        rag_service=_FakeRagService(),
        bm25_service=_FakeBm25Service(),
        sqlite_vec_service=_FakeSqliteVecService(),
    )


def test_search_knowledge_returns_ref_hits():
    service = _build_service()
    result = asyncio.run(
        service.search_knowledge(
            query="what is active rag",
            top_k=3,
            include_diagnostics=True,
        )
    )
    payload = json.loads(result)

    assert payload["ok"] is True
    assert payload["planner_applied"] is True
    assert payload["retrieval_queries"] == ["q1", "q2"]
    assert len(payload["hits"]) == 1
    assert payload["hits"][0]["ref_id"] == "kb:kb_test|doc:doc_1|chunk:3"
    assert payload["hits"][0]["citation_id"] == "S1"


def test_read_knowledge_accepts_citation_id_from_search():
    service = _build_service()
    asyncio.run(service.search_knowledge(query="q", top_k=3))
    result = asyncio.run(
        service.read_knowledge(
            refs=["S1"],
            max_chars=6000,
            neighbor_window=0,
        )
    )
    payload = json.loads(result)

    assert payload["ok"] is True
    assert payload["sources"][0]["ref_id"] == "kb:kb_test|doc:doc_1|chunk:3"
    assert payload["sources"][0]["content"] == "Exact chunk payload"
    assert "<source id=\"1\"" in payload["context_block"]


def test_read_knowledge_blocks_unbound_kb_ref():
    service = _build_service()
    result = asyncio.run(
        service.read_knowledge(
            refs=["kb:other|doc:doc_1|chunk:1"],
            max_chars=6000,
            neighbor_window=0,
        )
    )
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "NOT_FOUND"
    assert "kb:other|doc:doc_1|chunk:1" in payload["missing_refs"]


def test_search_knowledge_requires_bound_kb():
    service = _build_service(allowed_kb_ids=[])
    result = asyncio.run(service.search_knowledge(query="q", top_k=3))
    payload = json.loads(result)

    assert payload["ok"] is False
    assert payload["error"]["code"] == "NO_KB_ACCESS"


def test_execute_tool_returns_none_for_unknown_name():
    service = _build_service()
    result = asyncio.run(service.execute_tool("unknown_tool", {}))
    assert result is None
