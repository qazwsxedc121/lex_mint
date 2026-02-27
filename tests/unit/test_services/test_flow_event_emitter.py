"""Unit tests for FlowEventEmitter helpers."""

from src.api.services.flow_event_emitter import FlowEventEmitter
from src.api.services.flow_events import FlowEventStage


def test_emitter_emits_started_text_and_ended():
    emitter = FlowEventEmitter(stream_id="stream-1", conversation_id="session-1")

    started = emitter.emit_started(context_type="chat")["flow_event"]
    delta = emitter.emit_text_delta("hello")["flow_event"]
    ended = emitter.emit_ended()["flow_event"]

    assert started["event_type"] == "stream_started"
    assert started["stage"] == FlowEventStage.TRANSPORT.value
    assert started["payload"]["context_type"] == "chat"

    assert delta["event_type"] == "text_delta"
    assert delta["stage"] == FlowEventStage.CONTENT.value
    assert delta["payload"]["text"] == "hello"

    assert ended["event_type"] == "stream_ended"
    assert ended["payload"]["done"] is True
    assert [started["seq"], delta["seq"], ended["seq"]] == [1, 2, 3]


def test_emitter_uses_seq_provider_and_payload_merge():
    state = {"seq": 9}

    def _next_seq() -> int:
        state["seq"] += 2
        return state["seq"]

    emitter = FlowEventEmitter(stream_id="stream-2", seq_provider=_next_seq, default_turn_id="turn-default")
    delta = emitter.emit_text_delta("x", payload={"model_id": "m1"})["flow_event"]
    custom = emitter.emit(
        event_type="custom_event",
        stage=FlowEventStage.META,
        payload={"a": 1},
        turn_id="turn-override",
    )["flow_event"]
    err = emitter.emit_error("boom")["flow_event"]

    assert delta["seq"] == 11
    assert delta["turn_id"] == "turn-default"
    assert delta["payload"] == {"text": "x", "model_id": "m1"}

    assert custom["seq"] == 13
    assert custom["turn_id"] == "turn-override"
    assert custom["payload"]["a"] == 1

    assert err["seq"] == 15
    assert err["event_type"] == "stream_error"
    assert err["stage"] == FlowEventStage.TRANSPORT.value
    assert err["payload"]["error"] == "boom"
