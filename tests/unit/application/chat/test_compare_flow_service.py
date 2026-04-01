"""Unit tests for compare flow service extraction."""

import pytest

from src.application.chat.chat_input_service import PreparedUserInput
from src.application.chat.compare_flow_service import CompareFlowDeps, CompareFlowService
from src.application.chat.request_contexts import (
    CompareChatRequestContext,
    ConversationScope,
    UserInputPayload,
)
from src.application.chat.service_contracts import ContextPayload


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


class _FakeInputService:
    async def prepare_user_input(self, **_kwargs):
        return PreparedUserInput(
            raw_user_message="hello",
            full_message_content="hello",
            attachment_metadata=[],
            user_message_id="user-msg-1",
        )


class _FakeCompareOrchestrator:
    async def stream(self, request):
        _ = request
        yield {"type": "model_start", "model_id": "m1", "model_name": "M1"}
        yield {"type": "model_done", "model_id": "m1", "content": "A"}
        yield {
            "type": "compare_complete",
            "model_results": {
                "m1": {"content": "A", "usage": None, "cost": None},
                "m2": {"content": "B", "usage": None, "cost": None},
            },
        }


@pytest.mark.asyncio
async def test_compare_flow_streams_and_persists():
    append_calls = []
    save_calls = []

    async def _append_message(*args, **kwargs):
        append_calls.append((args, kwargs))
        return "assistant-msg-1"

    async def _save(*args, **kwargs):
        save_calls.append((args, kwargs))

    class _FakeStorage:
        async def append_message(self, *args, **kwargs):
            return await _append_message(*args, **kwargs)

    class _FakeComparisonStorage:
        async def save(self, *args, **kwargs):
            await _save(*args, **kwargs)

    deps = CompareFlowDeps(
        storage=_FakeStorage(),
        comparison_storage=_FakeComparisonStorage(),
        chat_input_service=_FakeInputService(),
        compare_models_orchestrator=_FakeCompareOrchestrator(),
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                system_prompt=None,
                assistant_params={},
                all_sources=[{"type": "memory"}],
                model_id="provider:model-a",
                assistant_id="assistant-1",
                assistant_obj=None,
                assistant_memory_enabled=True,
                max_rounds=None,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = CompareFlowService(deps)

    events = await _collect_events(
        service.process_compare_stream(
            request=CompareChatRequestContext(
                scope=ConversationScope(session_id="s1", context_type="chat"),
                user_input=UserInputPayload(user_message="hello"),
                model_ids=["m1", "m2"],
            )
        )
    )

    assert events[0] == {"type": "user_message_id", "message_id": "user-msg-1"}
    assert events[1] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[2]["type"] == "model_start"
    assert events[3]["type"] == "model_done"
    assert events[4] == {"type": "assistant_message_id", "message_id": "assistant-msg-1"}
    assert len(append_calls) == 1
    assert len(save_calls) == 1


async def _return_async(value):
    return value
