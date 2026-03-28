from dataclasses import dataclass

import pytest

from src.application.chat.chat_runtime.turn_executor import CommitteeTurnExecutor


@dataclass
class _AssistantStub:
    id: str
    name: str
    model_id: str
    icon: str
    system_prompt: str | None
    temperature: float | None
    max_tokens: int | None
    top_p: float | None
    top_k: int | None
    frequency_penalty: float | None
    presence_penalty: float | None
    max_rounds: int | None
    memory_enabled: bool = True
    knowledge_base_ids: list[str] | None = None
    enabled: bool = True


class _StorageStub:
    def __init__(self):
        self.append_calls = []

    async def get_session(self, *_args, **_kwargs):
        return {"state": {"messages": [{"role": "user", "content": "hello"}]}}

    async def append_message(self, *args, **kwargs):
        self.append_calls.append((args, kwargs))
        return "assistant-msg-1"


class _MemoryServiceStub:
    def build_memory_context(self, **_kwargs):
        return "memory ctx", [{"type": "memory", "title": "Memory"}]


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_group_turn_executor_merges_tool_diagnostics_into_sources(monkeypatch):
    async def fake_call_llm_stream(*_args, **_kwargs):
        yield {
            "type": "tool_diagnostics",
            "tool_search_count": 2,
            "tool_search_unique_count": 2,
            "tool_search_duplicate_count": 0,
            "tool_read_count": 1,
            "tool_finalize_reason": "normal_with_tools",
        }
        yield "hello from group"

    async def fake_build_rag_context_and_sources(**_kwargs):
        return (
            "rag ctx",
            [
                {
                    "type": "rag_diagnostics",
                    "title": "RAG Diagnostics",
                    "snippet": "retrieved context",
                },
                {"type": "rag", "title": "Doc 1"},
            ],
        )

    monkeypatch.setattr(
        "src.application.chat.chat_runtime.turn_stream_runner.call_llm_stream",
        fake_call_llm_stream,
    )

    storage = _StorageStub()
    executor = CommitteeTurnExecutor(
        storage=storage,
        pricing_service=object(),
        memory_service=_MemoryServiceStub(),
        file_service=None,
        assistant_params_from_config=lambda _assistant: {},
        build_group_history_hint=lambda *_args, **_kwargs: "",
        build_group_identity_prompt=lambda *_args, **_kwargs: "identity",
        build_group_instruction_prompt=lambda *_args, **_kwargs: None,
        build_rag_context_and_sources=fake_build_rag_context_and_sources,
        truncate_log_text=lambda text, _limit: text or "",
        build_messages_preview_for_log=lambda messages: messages,
        log_group_trace=lambda *_args, **_kwargs: None,
    )

    assistant = _AssistantStub(
        id="a1",
        name="Architect",
        model_id="provider:model-a",
        icon="architect.png",
        system_prompt="You are helpful.",
        temperature=0.2,
        max_tokens=512,
        top_p=1.0,
        top_k=40,
        frequency_penalty=0.0,
        presence_penalty=0.0,
        max_rounds=3,
    )

    events = await _collect_events(
        executor.stream_group_assistant_turn(
            session_id="s1",
            assistant_id="a1",
            assistant_obj=assistant,
            group_assistants=["a1"],
            assistant_name_map={"a1": "Architect"},
            raw_user_message="hello",
            reasoning_effort=None,
            context_type="chat",
            project_id=None,
            search_context="search ctx",
            search_sources=[{"type": "search", "title": "Web"}],
        )
    )

    assert "tool_diagnostics" not in [
        event.get("type") for event in events if isinstance(event, dict)
    ]
    sources_event = next(event for event in events if event.get("type") == "sources")
    assert [source["type"] for source in sources_event["sources"]] == [
        "memory",
        "search",
        "rag_diagnostics",
        "rag",
    ]
    assert sources_event["sources"][2]["tool_search_count"] == 2
    assert sources_event["sources"][2]["snippet"] == (
        "retrieved context | tool s:2 u:2 d:0 r:1 f:normal_with_tools"
    )

    append_kwargs = storage.append_calls[0][1]
    assert append_kwargs["sources"] == sources_event["sources"]
