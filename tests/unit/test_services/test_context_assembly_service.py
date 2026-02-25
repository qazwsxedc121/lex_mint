"""Unit tests for context assembly service."""

from types import SimpleNamespace
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pytest

from src.api.services.context_assembly_service import ContextAssemblyService


class _Source:
    def __init__(self, payload: Dict[str, Any]):
        self.payload = payload

    def model_dump(self) -> Dict[str, Any]:
        return self.payload


class _FakeStorage:
    def __init__(self, *, param_overrides: Optional[Dict[str, Any]] = None):
        self.param_overrides = param_overrides or {}

    async def get_session(
        self,
        session_id: str,
        *,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        _ = session_id, context_type, project_id
        return {
            "state": {"messages": [{"role": "user", "content": "hi"}]},
            "assistant_id": None,
            "model_id": "provider:model-a",
            "param_overrides": self.param_overrides,
        }


class _FakeMemoryService:
    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: Optional[str],
        include_global: bool,
        include_assistant: bool,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        _ = query, assistant_id, include_global, include_assistant
        return "MEM", [{"type": "memory"}]


class _FakeWebpageService:
    async def build_context(self, query: str) -> Tuple[Optional[str], List[_Source]]:
        _ = query
        return "WEB", [_Source({"type": "webpage"})]


class _FakeSearchService:
    async def search(self, query: str) -> List[_Source]:
        _ = query
        return [_Source({"type": "search"})]

    @staticmethod
    def build_search_context(query: str, sources: Sequence[Any]) -> Optional[str]:
        _ = query, sources
        return "SEARCH"


class _FakeSourceContextService:
    @staticmethod
    def build_source_tags(query, sources):
        return {"q": query, "count": len(sources)}

    @staticmethod
    def apply_template(query, source_context):
        return f"STRUCT:{query}:{source_context['count']}"


class _FakeRagConfigService:
    def __init__(self, enabled: bool):
        self.config = SimpleNamespace(
            retrieval=SimpleNamespace(structured_source_context_enabled=enabled)
        )

    def reload_config(self):
        return None


@pytest.mark.asyncio
async def test_prepare_context_builds_prompt_and_sources():
    async def fake_rag_context_builder(**_kwargs):
        return "RAG", [{"type": "rag"}]

    service = ContextAssemblyService(
        storage=_FakeStorage(),
        memory_service=_FakeMemoryService(),
        webpage_service=_FakeWebpageService(),
        search_service=_FakeSearchService(),
        source_context_service=_FakeSourceContextService(),
        rag_config_service=_FakeRagConfigService(enabled=True),
        rag_context_builder=fake_rag_context_builder,
    )

    ctx = await service.prepare_context(
        session_id="s1",
        raw_user_message="hello",
        use_web_search=True,
    )

    assert ctx.assistant_id is None
    assert ctx.is_legacy_assistant is False
    assert ctx.assistant_memory_enabled is True
    assert ctx.system_prompt == "MEM\n\nWEB\n\nSEARCH\n\nRAG\n\nSTRUCT:hello:4"
    assert [s["type"] for s in ctx.all_sources] == ["memory", "webpage", "search", "rag"]


@pytest.mark.asyncio
async def test_prepare_context_honors_param_overrides_and_disabled_structured_context():
    async def fake_rag_context_builder(**_kwargs):
        return "RAG", [{"type": "rag"}]

    service = ContextAssemblyService(
        storage=_FakeStorage(param_overrides={"model_id": "provider:model-b", "max_rounds": 5}),
        memory_service=_FakeMemoryService(),
        webpage_service=_FakeWebpageService(),
        search_service=_FakeSearchService(),
        source_context_service=_FakeSourceContextService(),
        rag_config_service=_FakeRagConfigService(enabled=False),
        rag_context_builder=fake_rag_context_builder,
    )

    ctx = await service.prepare_context(
        session_id="s2",
        raw_user_message="hello",
        use_web_search=False,
    )

    assert ctx.model_id == "provider:model-b"
    assert ctx.max_rounds == 5
    assert ctx.system_prompt == "MEM\n\nWEB\n\nRAG"
