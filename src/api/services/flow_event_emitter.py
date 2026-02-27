"""Helpers to emit canonical FlowEvent SSE payloads."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

from .flow_events import FlowEventStage, new_flow_event


@dataclass
class FlowEventEmitter:
    """Build flow_event-only payloads with stable sequencing."""

    stream_id: str
    conversation_id: Optional[str] = None
    default_turn_id: Optional[str] = None
    seq_provider: Optional[Callable[[], int]] = None
    _seq: int = 0

    def _next_seq(self) -> int:
        if self.seq_provider is not None:
            return int(self.seq_provider())
        self._seq += 1
        return self._seq

    def emit(
        self,
        *,
        event_type: str,
        stage: FlowEventStage,
        payload: Optional[Dict[str, Any]] = None,
        turn_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        event = new_flow_event(
            seq=self._next_seq(),
            stream_id=self.stream_id,
            conversation_id=self.conversation_id,
            turn_id=turn_id or self.default_turn_id,
            event_type=event_type,
            stage=stage,
            payload=payload or {},
        )
        return {"flow_event": event.model_dump(exclude_none=True)}

    def emit_started(self, *, context_type: Optional[str] = None) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        if context_type:
            payload["context_type"] = context_type
        return self.emit(
            event_type="stream_started",
            stage=FlowEventStage.TRANSPORT,
            payload=payload,
        )

    def emit_ended(self) -> Dict[str, Any]:
        return self.emit(
            event_type="stream_ended",
            stage=FlowEventStage.TRANSPORT,
            payload={"done": True},
        )

    def emit_error(self, message: str) -> Dict[str, Any]:
        return self.emit(
            event_type="stream_error",
            stage=FlowEventStage.TRANSPORT,
            payload={"error": str(message)},
        )

    def emit_text_delta(self, text: str, *, payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        body = {"text": str(text)}
        if payload:
            body.update(payload)
        return self.emit(
            event_type="text_delta",
            stage=FlowEventStage.CONTENT,
            payload=body,
        )
