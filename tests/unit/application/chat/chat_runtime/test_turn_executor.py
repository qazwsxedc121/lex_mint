import asyncio
from dataclasses import dataclass

import pytest

from src.application.chat.chat_runtime.turn_context_builder import GroupTurnContext
from src.application.chat.chat_runtime.turn_executor import CommitteeTurnExecutor
from src.application.chat.request_contexts import (
    CommitteeExecutionContext,
    CommitteeMemberTurnContext,
    ConversationScope,
)


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
            turn_context=CommitteeMemberTurnContext(
                execution=CommitteeExecutionContext(
                    scope=ConversationScope(session_id="s1"),
                    raw_user_message="hello",
                    group_assistants=["a1"],
                    assistant_name_map={"a1": "Architect"},
                    assistant_config_map={"a1": assistant},
                    group_settings=None,
                    reasoning_effort=None,
                    search_context="search ctx",
                    search_sources=[{"type": "search", "title": "Web"}],
                ),
                assistant_id="a1",
                assistant_obj=assistant,
            )
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


def test_extract_bullet_items_and_keyword_sentences():
    text = """
    - First actionable point
    - First actionable point
    1. Second actionable point
    random line
    """
    bullets = CommitteeTurnExecutor.extract_bullet_items(text, limit=5)
    assert bullets == ["First actionable point", "Second actionable point"]

    sentences = CommitteeTurnExecutor.extract_keyword_sentences(
        "We should validate this. Ignore. Next action is rollout.",
        keywords=["should", "next action"],
    )
    assert len(sentences) == 2


def test_detect_group_role_drift_and_retry_instruction():
    reason = CommitteeTurnExecutor.detect_group_role_drift(
        content="[Reviewer] I am taking over this turn.",
        expected_assistant_id="architect",
        expected_assistant_name="Architect",
        participant_name_map={"architect": "Architect", "reviewer": "Reviewer"},
    )
    assert reason == "role_drift_claimed_reviewer"

    corrected = CommitteeTurnExecutor.build_role_retry_instruction(
        base_instruction="Focus on design",
        expected_assistant_name="Architect",
    )
    assert "Focus on design" in corrected
    assert "You must answer strictly as Architect" in corrected


@pytest.mark.asyncio
async def test_get_message_content_by_id_found_and_missing():
    class _StorageWithMessages:
        async def get_session(self, *_args, **_kwargs):
            return {
                "state": {
                    "messages": [
                        {"message_id": "m1", "content": "hello"},
                        {"message_id": "m2", "content": "world"},
                    ]
                }
            }

    executor = CommitteeTurnExecutor(
        storage=_StorageWithMessages(),
        pricing_service=object(),
        memory_service=_MemoryServiceStub(),
        file_service=None,
        assistant_params_from_config=lambda _assistant: {},
        build_group_history_hint=lambda *_args, **_kwargs: "",
        build_group_identity_prompt=lambda *_args, **_kwargs: "identity",
        build_group_instruction_prompt=lambda *_args, **_kwargs: None,
        build_rag_context_and_sources=lambda **_kwargs: _return_async((None, [])),
        truncate_log_text=lambda text, _limit: text or "",
        build_messages_preview_for_log=lambda messages: messages,
        log_group_trace=lambda *_args, **_kwargs: None,
    )
    assert (
        await executor.get_message_content_by_id(
            session_id="s1", message_id="m2", context_type="chat", project_id=None
        )
        == "world"
    )
    assert (
        await executor.get_message_content_by_id(
            session_id="s1", message_id="not-found", context_type="chat", project_id=None
        )
        == ""
    )


@pytest.mark.asyncio
async def test_group_turn_executor_cancellation_saves_partial(monkeypatch):
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
        build_rag_context_and_sources=lambda **_kwargs: _return_async((None, [])),
        truncate_log_text=lambda text, _limit: text or "",
        build_messages_preview_for_log=lambda messages: messages,
        log_group_trace=lambda *_args, **_kwargs: None,
    )

    async def _fake_build(*_args, **_kwargs):
        return GroupTurnContext(
            assistant_name="Architect",
            model_id="provider:model-a",
            messages=[{"role": "user", "content": "hello"}],
            history_hint="",
            identity_prompt="identity",
            instruction_prompt=None,
            system_prompt="sys",
            sources=[],
        )

    async def _cancelled_stream(*, state, **_kwargs):
        state.full_response = "partial text"
        raise asyncio.CancelledError
        yield  # pragma: no cover

    monkeypatch.setattr(executor._context_builder, "build", _fake_build)
    monkeypatch.setattr(executor._stream_runner, "stream_turn", _cancelled_stream)

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
    turn_context = CommitteeMemberTurnContext(
        execution=CommitteeExecutionContext(
            scope=ConversationScope(session_id="s1"),
            raw_user_message="hello",
            group_assistants=["a1"],
            assistant_name_map={"a1": "Architect"},
            assistant_config_map={"a1": assistant},
            group_settings=None,
            reasoning_effort=None,
            search_context=None,
            search_sources=[],
        ),
        assistant_id="a1",
        assistant_obj=assistant,
    )

    with pytest.raises(asyncio.CancelledError):
        _ = await _collect_events(executor.stream_group_assistant_turn(turn_context=turn_context))

    assert len(storage.append_calls) == 1
    assert storage.append_calls[0][0][1] == "assistant"
    assert storage.append_calls[0][0][2] == "partial text"


async def _return_async(value):
    return value
