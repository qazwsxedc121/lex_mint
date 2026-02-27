"""Unit tests for in-memory FlowEvent stream replay runtime."""

import pytest

from src.api.services.flow_stream_runtime import (
    FlowReplayCursorGoneError,
    FlowStreamContextMismatchError,
    FlowStreamNotFoundError,
    FlowStreamRuntime,
)


def _payload(event_id: str, seq: int, event_type: str = "assistant_text_delta"):
    payload = {
        "flow_event": {
            "event_id": event_id,
            "seq": seq,
            "stream_id": "stream-1",
            "event_type": event_type,
            "stage": "content",
            "payload": {},
        }
    }
    if event_type == "stream_ended":
        payload["done"] = True
        payload["flow_event"]["stage"] = "transport"
        payload["flow_event"]["payload"] = {"done": True}
    return payload


def test_resume_replays_after_last_event_and_subscribes_to_live_events():
    runtime = FlowStreamRuntime(ttl_seconds=60, max_events_per_stream=50, max_active_streams=5)
    runtime.create_stream(
        stream_id="stream-1",
        conversation_id="session-1",
        context_type="chat",
        project_id=None,
    )
    runtime.append_payload("stream-1", _payload("e1", 1))
    runtime.append_payload("stream-1", _payload("e2", 2))

    subscriber_id, queue, replay_payloads = runtime.resume_subscribe(
        stream_id="stream-1",
        last_event_id="e1",
        conversation_id="session-1",
        context_type="chat",
        project_id=None,
    )
    assert [item["flow_event"]["event_id"] for item in replay_payloads] == ["e2"]

    runtime.append_payload("stream-1", _payload("e3", 3))
    live_payload = queue.get_nowait()
    assert live_payload["flow_event"]["event_id"] == "e3"
    runtime.unsubscribe("stream-1", subscriber_id)


def test_resume_raises_when_cursor_is_missing():
    runtime = FlowStreamRuntime(ttl_seconds=60, max_events_per_stream=50, max_active_streams=5)
    runtime.create_stream(
        stream_id="stream-1",
        conversation_id="session-1",
        context_type="chat",
        project_id=None,
    )
    runtime.append_payload("stream-1", _payload("e1", 1))

    with pytest.raises(FlowReplayCursorGoneError):
        runtime.resume_subscribe(
            stream_id="stream-1",
            last_event_id="missing",
            conversation_id="session-1",
            context_type="chat",
            project_id=None,
        )


def test_resume_raises_when_context_does_not_match():
    runtime = FlowStreamRuntime(ttl_seconds=60, max_events_per_stream=50, max_active_streams=5)
    runtime.create_stream(
        stream_id="stream-1",
        conversation_id="session-1",
        context_type="chat",
        project_id=None,
    )
    runtime.append_payload("stream-1", _payload("e1", 1))

    with pytest.raises(FlowStreamContextMismatchError):
        runtime.resume_subscribe(
            stream_id="stream-1",
            last_event_id="e1",
            conversation_id="session-1",
            context_type="project",
            project_id="proj-1",
        )


def test_completed_stream_is_evicted_after_ttl():
    runtime = FlowStreamRuntime(ttl_seconds=0, max_events_per_stream=50, max_active_streams=5)
    runtime.create_stream(
        stream_id="stream-1",
        conversation_id="session-1",
        context_type="chat",
        project_id=None,
    )
    runtime.append_payload("stream-1", _payload("e1", 1, event_type="stream_ended"))
    runtime._gc()

    with pytest.raises(FlowStreamNotFoundError):
        runtime.get_stream("stream-1")
