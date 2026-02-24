"""Unit tests for single-chat flow service extraction."""

from types import SimpleNamespace

import pytest

from src.api.services.chat_input_service import PreparedUserInput
from src.api.services.service_contracts import ContextPayload
from src.api.services.single_chat_flow_service import (
    SingleChatFlowDeps,
    SingleChatFlowService,
)
from src.providers.types import CostInfo, TokenUsage


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


class _FakeSingleTurnOrchestrator:
    async def stream(self, _request):
        usage = TokenUsage(prompt_tokens=5, completion_tokens=7, total_tokens=12)
        cost = CostInfo(input_cost=0.01, output_cost=0.02, total_cost=0.03, currency="USD")
        yield {"type": "assistant_chunk", "chunk": "hello"}
        yield {"type": "usage", "usage": usage, "cost": cost}
        yield {
            "type": "single_turn_complete",
            "content": "hello",
            "usage": usage.model_dump(),
            "cost": cost.model_dump(),
        }


class _FakePostTurnService:
    def __init__(self):
        self.finalize_calls = []

    async def save_partial_assistant_message(self, **_kwargs):
        return None

    async def finalize_single_turn(self, **kwargs):
        self.finalize_calls.append(kwargs)
        return "assistant-msg-1"

    async def generate_followup_questions(self, **_kwargs):
        return ["next question"]


class _FakeInputService:
    async def prepare_user_input(self, **_kwargs):
        return PreparedUserInput(
            raw_user_message="hello",
            full_message_content="hello",
            attachment_metadata=[],
            user_message_id="user-msg-1",
        )


@pytest.mark.asyncio
async def test_single_chat_flow_streams_events_and_finalizes(monkeypatch):
    post_turn = _FakePostTurnService()
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: None),
        chat_input_service=_FakeInputService(),
        post_turn_service=post_turn,
        single_turn_orchestrator=_FakeSingleTurnOrchestrator(),
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt=None,
                assistant_params={},
                all_sources=[{"type": "memory"}],
                max_rounds=None,
                is_legacy_assistant=False,
                assistant_memory_enabled=True,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
        merge_tool_diagnostics_into_sources=lambda all_sources, _diag: all_sources,
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(
        service,
        "_maybe_auto_compress",
        lambda **kwargs: _return_async((kwargs["messages"], None)),
    )
    monkeypatch.setattr(
        service,
        "_resolve_tools",
        lambda **_kwargs: _return_async((None, None)),
    )

    events = await _collect_events(
        service.process_message_stream(
            session_id="s1",
            user_message="hello",
            context_type="chat",
            project_id=None,
        )
    )

    assert events[0] == {"type": "user_message_id", "message_id": "user-msg-1"}
    assert events[1] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[2] == "hello"
    assert events[3]["type"] == "usage"
    assert events[4] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[5] == {"type": "assistant_message_id", "message_id": "assistant-msg-1"}
    assert events[6] == {"type": "followup_questions", "questions": ["next question"]}
    assert len(post_turn.finalize_calls) == 1
    assert post_turn.finalize_calls[0]["assistant_message"] == "hello"


async def _return_async(value):
    return value
