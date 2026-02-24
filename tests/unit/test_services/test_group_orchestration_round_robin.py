"""Unit tests for round-robin orchestrator contract."""

from types import SimpleNamespace

import pytest

from src.api.services.group_orchestration import (
    OrchestrationCancelToken,
    OrchestrationRequest,
    RoundRobinSettings,
    RoundRobinOrchestrator,
)


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


@pytest.mark.asyncio
async def test_round_robin_streams_participants_in_order():
    call_order = []

    async def fake_stream_group_assistant_turn(**kwargs):
        assistant_id = kwargs["assistant_id"]
        call_order.append(assistant_id)
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    orchestrator = RoundRobinOrchestrator(
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
    )
    request = OrchestrationRequest(
        session_id="s1",
        mode="round_robin",
        user_message="hello",
        participants=["a1", "ghost", "a2"],
        assistant_name_map={"a1": "A1", "a2": "A2"},
        assistant_config_map={
            "a1": SimpleNamespace(name="A1"),
            "a2": SimpleNamespace(name="A2"),
        },
        settings=RoundRobinSettings(),
    )

    events = await _collect_events(orchestrator.stream(request))
    assert [e["assistant_id"] for e in events if e["type"] == "assistant_start"] == ["a1", "a2"]
    assert call_order == ["a1", "a2"]


@pytest.mark.asyncio
async def test_round_robin_honors_cancel_token_between_turns():
    cancel_token = OrchestrationCancelToken()
    call_order = []

    async def fake_stream_group_assistant_turn(**kwargs):
        assistant_id = kwargs["assistant_id"]
        call_order.append(assistant_id)
        yield {"type": "assistant_start", "assistant_id": assistant_id}
        cancel_token.cancel("user_stop")
        yield {"type": "assistant_done", "assistant_id": assistant_id}

    orchestrator = RoundRobinOrchestrator(
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
    )
    request = OrchestrationRequest(
        session_id="s2",
        mode="round_robin",
        user_message="hello",
        participants=["a1", "a2"],
        assistant_name_map={"a1": "A1", "a2": "A2"},
        assistant_config_map={
            "a1": SimpleNamespace(name="A1"),
            "a2": SimpleNamespace(name="A2"),
        },
        settings=RoundRobinSettings(),
    )

    events = await _collect_events(orchestrator.stream(request, cancel_token=cancel_token))
    assert call_order == ["a1"]
    assert [e["assistant_id"] for e in events if e["type"] == "assistant_start"] == ["a1"]


@pytest.mark.asyncio
async def test_round_robin_rejects_mismatched_mode():
    async def fake_stream_group_assistant_turn(**kwargs):
        yield {"type": "assistant_start", "assistant_id": kwargs["assistant_id"]}

    orchestrator = RoundRobinOrchestrator(
        stream_group_assistant_turn=fake_stream_group_assistant_turn,
    )
    request = OrchestrationRequest(
        session_id="s3",
        mode="committee",
        user_message="hello",
        participants=["a1", "a2"],
        assistant_name_map={"a1": "A1", "a2": "A2"},
        assistant_config_map={
            "a1": SimpleNamespace(name="A1"),
            "a2": SimpleNamespace(name="A2"),
        },
        settings=RoundRobinSettings(),
    )

    with pytest.raises(ValueError, match="mode=round_robin"):
        await _collect_events(orchestrator.stream(request))
