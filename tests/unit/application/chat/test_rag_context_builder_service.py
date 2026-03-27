"""Tests for the RAG context builder service."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from src.application.chat.rag_context_builder_service import RagContextBuilderService
from src.infrastructure.config import assistant_config_service
from src.infrastructure.projects import project_knowledge_base_resolver
from src.infrastructure.retrieval import rag_service as rag_service_module


class _AssistantService:
    def __init__(self, assistant):
        self.assistant = assistant

    async def get_assistant(self, assistant_id: str):
        assert assistant_id == "assistant-1"
        return self.assistant


class _Resolver:
    def __init__(self, kb_ids):
        self.kb_ids = kb_ids

    async def resolve_effective_kb_ids(self, **kwargs):
        assert kwargs["context_type"] in {"chat", "project"}
        return list(self.kb_ids)


class _RagResult:
    def __init__(self, content: str):
        self.content = content

    def to_dict(self):
        return {"content": self.content}


class _RagService:
    def __init__(self, results=None, diagnostics=None):
        self.results = results or []
        self.diagnostics = diagnostics or {"raw_count": 1}

    async def retrieve_with_diagnostics(self, raw_user_message: str, kb_ids, runtime_model_id=None):
        assert raw_user_message
        assert kb_ids
        return list(self.results), dict(self.diagnostics)

    def build_rag_diagnostics_source(self, diagnostics):
        return {"type": "rag_diagnostics", **diagnostics}

    def build_rag_context(self, raw_user_message: str, results):
        return f"context:{raw_user_message}:{len(results)}"


@pytest.mark.asyncio
async def test_rag_context_builder_returns_none_when_no_effective_kbs(monkeypatch):
    monkeypatch.setattr(project_knowledge_base_resolver, "ProjectKnowledgeBaseResolver", lambda: _Resolver([]))

    service = RagContextBuilderService()
    context, sources = await service.build_context_and_sources(raw_user_message="hello", assistant_id=None)

    assert context is None
    assert sources == []


@pytest.mark.asyncio
async def test_rag_context_builder_builds_context_and_sources(monkeypatch):
    monkeypatch.setattr(
        assistant_config_service,
        "AssistantConfigService",
        lambda: _AssistantService(SimpleNamespace(id="assistant-1")),
    )
    monkeypatch.setattr(project_knowledge_base_resolver, "ProjectKnowledgeBaseResolver", lambda: _Resolver(["kb-1"]))
    monkeypatch.setattr(
        rag_service_module,
        "RagService",
        lambda: _RagService(results=[_RagResult("chunk-1"), _RagResult("chunk-2")]),
    )

    service = RagContextBuilderService()
    context, sources = await service.build_context_and_sources(
        raw_user_message="hello",
        assistant_id="assistant-1",
        runtime_model_id="provider:model",
        context_type="project",
        project_id="proj-1",
    )

    assert context == "context:hello:2"
    assert sources[0]["type"] == "rag_diagnostics"
    assert sources[1:] == [{"content": "chunk-1"}, {"content": "chunk-2"}]


@pytest.mark.asyncio
async def test_rag_context_builder_handles_retrieval_errors(monkeypatch):
    monkeypatch.setattr(project_knowledge_base_resolver, "ProjectKnowledgeBaseResolver", lambda: _Resolver(["kb-1"]))

    class _BrokenRagService:
        async def retrieve_with_diagnostics(self, *args, **kwargs):
            raise RuntimeError("rag failed")

    monkeypatch.setattr(rag_service_module, "RagService", lambda: _BrokenRagService())

    service = RagContextBuilderService()
    context, sources = await service.build_context_and_sources(raw_user_message="hello", assistant_id=None)

    assert context is None
    assert sources == []
