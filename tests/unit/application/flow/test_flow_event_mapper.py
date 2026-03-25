"""Unit tests for legacy stream -> flow_event mapping."""

from src.application.flow.flow_event_mapper import FlowEventMapper


def test_mapper_wraps_text_chunk_with_flow_event():
    mapper = FlowEventMapper(stream_id="stream-1", conversation_id="session-1")

    payload = mapper.to_sse_payload("hello")

    flow_event = payload["flow_event"]
    assert set(payload.keys()) == {"flow_event"}
    assert flow_event["event_type"] == "text_delta"
    assert flow_event["stage"] == "content"
    assert flow_event["seq"] == 1
    assert flow_event["stream_id"] == "stream-1"
    assert flow_event["conversation_id"] == "session-1"
    assert flow_event["payload"]["text"] == "hello"


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


def test_mapper_uses_external_sequence_provider():
    state = {"seq": 41}

    def _next_seq() -> int:
        state["seq"] += 1
        return state["seq"]

    mapper = FlowEventMapper(stream_id="stream-4", seq_provider=_next_seq)
    payload = mapper.to_sse_payload("hello")
    assert payload["flow_event"]["seq"] == 42


def test_mapper_unknown_event_type_maps_to_stream_error():
    mapper = FlowEventMapper(stream_id="stream-5")

    payload = mapper.to_sse_payload({"type": "unknown_event", "foo": "bar"})

    flow_event = payload["flow_event"]
    assert flow_event["event_type"] == "stream_error"
    assert flow_event["stage"] == "transport"
    assert flow_event["payload"]["error"] == "unsupported stream event type: unknown_event"


def test_mapper_maps_compare_events():
    mapper = FlowEventMapper(stream_id="stream-6")

    start_payload = mapper.to_sse_payload({"type": "model_start", "model_id": "m1", "model_name": "Model-1"})
    chunk_payload = mapper.to_sse_payload({"type": "model_chunk", "model_id": "m1", "chunk": "A"})
    done_payload = mapper.to_sse_payload(
        {
            "type": "model_done",
            "model_id": "m1",
            "model_name": "Model-1",
            "content": "Answer A",
            "usage": {"total_tokens": 2},
        }
    )
    complete_payload = mapper.to_sse_payload(
        {"type": "compare_complete", "model_results": {"m1": {"content": "Answer A"}}, "reason": "completed"}
    )

    assert start_payload["flow_event"]["event_type"] == "compare_model_started"
    assert start_payload["flow_event"]["stage"] == "orchestration"
    assert chunk_payload["flow_event"]["event_type"] == "text_delta"
    assert chunk_payload["flow_event"]["payload"]["model_id"] == "m1"
    assert chunk_payload["flow_event"]["payload"]["text"] == "A"
    assert done_payload["flow_event"]["event_type"] == "compare_model_finished"
    assert done_payload["flow_event"]["payload"]["content"] == "Answer A"
    assert complete_payload["flow_event"]["event_type"] == "compare_completed"


def test_mapper_maps_compression_complete_event():
    mapper = FlowEventMapper(stream_id="stream-7")

    payload = mapper.to_sse_payload(
        {
            "type": "compression_complete",
            "message_id": "msg-1",
            "compressed_count": 12,
            "compression_meta": {"ratio": 0.42},
        }
    )

    flow_event = payload["flow_event"]
    assert flow_event["event_type"] == "compression_completed"
    assert flow_event["stage"] == "meta"
    assert flow_event["payload"]["message_id"] == "msg-1"


def test_mapper_maps_tool_diagnostics_event():
    mapper = FlowEventMapper(stream_id="stream-8", conversation_id="session-8")

    payload = mapper.to_sse_payload(
        {
            "type": "tool_diagnostics",
            "assistant_id": "assistant-1",
            "assistant_turn_id": "turn-1",
            "tool_search_count": 3,
            "tool_search_unique_count": 2,
            "tool_read_count": 1,
            "tool_finalize_reason": "fallback_empty_answer",
        }
    )

    flow_event = payload["flow_event"]
    assert flow_event["event_type"] == "tool_diagnostics_reported"
    assert flow_event["stage"] == "meta"
    assert flow_event["conversation_id"] == "session-8"
    assert flow_event["turn_id"] == "turn-1"
    assert flow_event["payload"]["assistant_id"] == "assistant-1"
    assert flow_event["payload"]["tool_search_count"] == 3
    assert flow_event["payload"]["tool_search_unique_count"] == 2
    assert flow_event["payload"]["tool_read_count"] == 1
    assert flow_event["payload"]["tool_finalize_reason"] == "fallback_empty_answer"
