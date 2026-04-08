"""Unit tests for context assembly service."""

from collections.abc import Sequence
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from src.application.chat.context_assembly_service import ContextAssemblyService


class _Source:
    def __init__(self, payload: dict[str, Any]):
        self.payload = payload

    def model_dump(self) -> dict[str, Any]:
        return self.payload


class _FakeStorage:
    def __init__(
        self,
        *,
        param_overrides: dict[str, Any] | None = None,
        assistant_id: str | None = None,
    ):
        self.param_overrides = param_overrides or {}
        self.assistant_id = assistant_id

    async def get_session(
        self,
        session_id: str,
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> dict[str, Any]:
        _ = session_id, context_type, project_id
        return {
            "state": {"messages": [{"role": "user", "content": "hi"}]},
            "assistant_id": self.assistant_id,
            "model_id": "provider:model-a",
            "param_overrides": self.param_overrides,
        }


class _FakeMemoryService:
    def __init__(self):
        self.calls: list[dict[str, Any]] = []

    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: str | None,
        include_global: bool,
        include_assistant: bool,
    ) -> tuple[str | None, list[dict[str, Any]]]:
        self.calls.append(
            {
                "query": query,
                "assistant_id": assistant_id,
                "include_global": include_global,
                "include_assistant": include_assistant,
            }
        )
        return "MEM", [{"type": "memory"}]


class _FakeWebpageService:
    async def build_context(self, query: str) -> tuple[str | None, list[_Source]]:
        _ = query
        return "WEB", [_Source({"type": "webpage"})]


class _FakeSearchService:
    async def search(self, query: str) -> list[_Source]:
        _ = query
        return [_Source({"type": "search"})]

    @staticmethod
    def build_search_context(query: str, sources: Sequence[Any]) -> str | None:
        _ = query, sources
        return "SEARCH"


class _FakeSourceContextService:
    @staticmethod
    def build_source_tags(query, sources, max_sources: int = 20, max_chars_per_source: int = 1200):
        _ = max_sources, max_chars_per_source
        return {"q": query, "count": len(sources)}

    @staticmethod
    def apply_template(query, source_context, template=None):
        _ = template
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
    assert ctx.assistant_memory_enabled is True
    assert ctx.base_system_prompt is None
    assert ctx.memory_context == "MEM"
    assert ctx.webpage_context == "WEB"
    assert ctx.search_context == "SEARCH"
    assert ctx.rag_context == "RAG"
    assert ctx.structured_source_context == "STRUCT:hello:4"
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
    assert ctx.search_context is None
    assert ctx.structured_source_context is None
    assert ctx.system_prompt == "MEM\n\nWEB\n\nRAG"


@pytest.mark.asyncio
async def test_prepare_context_disables_assistant_memory_when_assistant_setting_is_off():
    async def fake_rag_context_builder(**_kwargs):
        return None, []

    memory_service = _FakeMemoryService()
    assistant = SimpleNamespace(
        system_prompt="ASSISTANT",
        max_rounds=4,
        temperature=0.2,
        max_tokens=512,
        top_p=0.9,
        top_k=20,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        memory_enabled=False,
    )
    mocked_assistant_service = SimpleNamespace(
        require_enabled_assistant=AsyncMock(return_value=assistant)
    )
    service = ContextAssemblyService(
        storage=_FakeStorage(assistant_id="assistant-a"),
        memory_service=memory_service,
        webpage_service=_FakeWebpageService(),
        search_service=_FakeSearchService(),
        source_context_service=_FakeSourceContextService(),
        rag_config_service=_FakeRagConfigService(enabled=False),
        rag_context_builder=fake_rag_context_builder,
    )

    with patch(
        "src.infrastructure.config.assistant_config_service.AssistantConfigService",
        return_value=mocked_assistant_service,
    ):
        ctx = await service.prepare_context(
            session_id="s3",
            raw_user_message="hello",
            use_web_search=False,
        )

    assert ctx.assistant_id == "assistant-a"
    assert ctx.assistant_memory_enabled is False
    assert ctx.base_system_prompt == "ASSISTANT"
    assert ctx.max_rounds == 4
    assert memory_service.calls == [
        {
            "query": "hello",
            "assistant_id": None,
            "include_global": True,
            "include_assistant": False,
        }
    ]


@pytest.mark.asyncio
async def test_prepare_context_skips_web_context_when_web_tools_plugin_unavailable(monkeypatch):
    async def fake_rag_context_builder(**_kwargs):
        return None, []

    monkeypatch.setattr(
        "src.application.chat.context_assembly_service.get_tool_registry",
        lambda: SimpleNamespace(get_tool_names_by_group=lambda _group: set()),
    )
    service = ContextAssemblyService(
        storage=_FakeStorage(),
        memory_service=_FakeMemoryService(),
        webpage_service=_FakeWebpageService(),
        search_service=_FakeSearchService(),
        source_context_service=_FakeSourceContextService(),
        rag_config_service=_FakeRagConfigService(enabled=False),
        rag_context_builder=fake_rag_context_builder,
    )

    ctx = await service.prepare_context(
        session_id="s4",
        raw_user_message="hello",
        use_web_search=True,
    )

    assert ctx.webpage_context is None
    assert ctx.search_context is None
    assert [s["type"] for s in ctx.all_sources] == ["memory"]
