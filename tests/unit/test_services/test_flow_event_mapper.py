"""Unit tests for legacy stream -> flow_event mapping."""

from src.api.services.flow_event_mapper import FlowEventMapper


def test_mapper_wraps_text_chunk_with_flow_event():
    mapper = FlowEventMapper(stream_id="stream-1", conversation_id="session-1")

    payload = mapper.to_sse_payload("hello")

    assert payload["chunk"] == "hello"
    flow_event = payload["flow_event"]
    assert flow_event["event_type"] == "assistant_text_delta"
    assert flow_event["stage"] == "content"
    assert flow_event["seq"] == 1
    assert flow_event["stream_id"] == "stream-1"
    assert flow_event["conversation_id"] == "session-1"
    assert flow_event["payload"]["chunk"] == "hello"


def test_mapper_maps_usage_event():
    mapper = FlowEventMapper(stream_id="stream-2", conversation_id="session-2")

    usage_payload = mapper.to_sse_payload(
        {
            "type": "usage",
            "assistant_id": "assistant-1",
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
        }
    )

    flow_event = usage_payload["flow_event"]
    assert flow_event["event_type"] == "usage_reported"
    assert flow_event["stage"] == "meta"
    assert flow_event["payload"]["assistant_id"] == "assistant-1"
    assert flow_event["payload"]["usage"]["total_tokens"] == 15


def test_mapper_maps_transport_events_for_done_and_error():
    mapper = FlowEventMapper(stream_id="stream-3")

    done_payload = mapper.to_sse_payload({"done": True})
    done_event = done_payload["flow_event"]
    assert done_event["event_type"] == "stream_ended"
    assert done_event["stage"] == "transport"
    assert done_event["payload"]["done"] is True

    error_payload = mapper.to_sse_payload({"error": "boom"})
    error_event = error_payload["flow_event"]
    assert error_event["event_type"] == "stream_error"
    assert error_event["stage"] == "transport"
    assert error_event["payload"]["error"] == "boom"
    assert error_event["seq"] == done_event["seq"] + 1
