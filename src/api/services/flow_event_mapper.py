"""Legacy stream event to FlowEvent mapping helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Mapping, Optional, Tuple, Union

from .flow_events import FlowEventStage, new_flow_event


StreamChunk = Union[str, Mapping[str, Any]]


@dataclass
class FlowEventMapper:
    """Attach flow_event envelopes while preserving legacy stream payloads."""

    stream_id: str
    conversation_id: Optional[str] = None
    default_turn_id: Optional[str] = None
    seq_provider: Optional[Callable[[], int]] = None
    _seq: int = 0

    def to_sse_payload(self, chunk: StreamChunk) -> Dict[str, Any]:
        """Return flow_event-only payload mapped from stream chunk."""

        return {"flow_event": self._map_chunk_to_flow_event(chunk)}

    def make_stream_started_payload(self, *, context_type: Optional[str] = None) -> Dict[str, Any]:
        """Build an initial stream-start payload."""

        payload: Dict[str, Any] = {}
        if context_type:
            payload["context_type"] = context_type
        flow_event = self._create_event(
            event_type="stream_started",
            stage=FlowEventStage.TRANSPORT,
            payload=payload,
        )
        return {"flow_event": flow_event}

    def _next_seq(self) -> int:
        if self.seq_provider is not None:
            return int(self.seq_provider())
        self._seq += 1
        return self._seq

    def _create_event(
        self,
        *,
        event_type: str,
        stage: FlowEventStage,
        payload: Dict[str, Any],
        turn_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        event = new_flow_event(
            seq=self._next_seq(),
            stream_id=self.stream_id,
            conversation_id=self.conversation_id,
            turn_id=turn_id or self.default_turn_id,
            event_type=event_type,
            stage=stage,
            payload=payload,
        )
        return event.model_dump(exclude_none=True)

    def _map_chunk_to_flow_event(self, chunk: StreamChunk) -> Dict[str, Any]:
        if isinstance(chunk, Mapping):
            payload = dict(chunk)
            if payload.get("done") is True:
                return self._create_event(
                    event_type="stream_ended",
                    stage=FlowEventStage.TRANSPORT,
                    payload={"done": True},
                )
            if "error" in payload:
                return self._create_event(
                    event_type="stream_error",
                    stage=FlowEventStage.TRANSPORT,
                    payload={"error": str(payload.get("error"))},
                )
            return self._map_legacy_event(payload)

        return self._create_event(
            event_type="text_delta",
            stage=FlowEventStage.CONTENT,
            payload={"text": str(chunk)},
        )

    def _map_legacy_event(self, event: Dict[str, Any]) -> Dict[str, Any]:
        legacy_type = event.get("type")
        if isinstance(legacy_type, str):
            event_type, stage, payload = self._legacy_type_to_flow(legacy_type, event)
            turn_id = self._extract_turn_id(event)
            return self._create_event(
                event_type=event_type,
                stage=stage,
                payload=payload,
                turn_id=turn_id,
            )

        if "chunk" in event:
            return self._create_event(
                event_type="text_delta",
                stage=FlowEventStage.CONTENT,
                payload={"text": str(event.get("chunk") or "")},
            )

        return self._create_event(
            event_type="legacy_event",
            stage=FlowEventStage.META,
            payload={"legacy_type": "", "data": event},
        )

    @staticmethod
    def _extract_turn_id(event: Dict[str, Any]) -> Optional[str]:
        turn_id = event.get("assistant_turn_id")
        if isinstance(turn_id, str) and turn_id:
            return turn_id
        return None

    @staticmethod
    def _copy_selected_fields(event: Dict[str, Any], fields: Tuple[str, ...]) -> Dict[str, Any]:
        payload: Dict[str, Any] = {}
        for field in fields:
            if field in event:
                payload[field] = event[field]
        return payload

    def _legacy_type_to_flow(
        self,
        legacy_type: str,
        event: Dict[str, Any],
    ) -> Tuple[str, FlowEventStage, Dict[str, Any]]:
        if legacy_type == "assistant_chunk":
            payload = self._copy_selected_fields(
                event,
                ("chunk", "assistant_id", "assistant_turn_id"),
            )
            chunk = str(payload.pop("chunk", "") or "")
            payload["text"] = chunk
            return "text_delta", FlowEventStage.CONTENT, payload

        if legacy_type == "usage":
            payload = self._copy_selected_fields(
                event,
                ("usage", "cost", "assistant_id", "assistant_turn_id"),
            )
            return "usage_reported", FlowEventStage.META, payload

        if legacy_type == "sources":
            payload = self._copy_selected_fields(
                event,
                ("sources", "assistant_id", "assistant_turn_id"),
            )
            return "sources_reported", FlowEventStage.META, payload

        if legacy_type == "user_message_id":
            payload = self._copy_selected_fields(event, ("message_id",))
            return "user_message_identified", FlowEventStage.META, payload

        if legacy_type == "assistant_message_id":
            payload = self._copy_selected_fields(
                event,
                ("message_id", "assistant_id", "assistant_turn_id"),
            )
            return "assistant_message_identified", FlowEventStage.META, payload

        if legacy_type == "context_info":
            payload = dict(event)
            payload.pop("type", None)
            return "context_reported", FlowEventStage.META, payload

        if legacy_type == "thinking_duration":
            payload = self._copy_selected_fields(
                event,
                ("duration_ms", "assistant_id", "assistant_turn_id"),
            )
            return "reasoning_duration_reported", FlowEventStage.CONTENT, payload

        if legacy_type == "tool_calls":
            payload = self._copy_selected_fields(
                event,
                ("calls", "assistant_id", "assistant_turn_id"),
            )
            return "tool_call_started", FlowEventStage.TOOL, payload

        if legacy_type == "tool_results":
            payload = self._copy_selected_fields(
                event,
                ("results", "assistant_id", "assistant_turn_id"),
            )
            return "tool_call_finished", FlowEventStage.TOOL, payload

        if legacy_type == "assistant_start":
            payload = self._copy_selected_fields(
                event,
                ("assistant_id", "assistant_turn_id", "name", "icon"),
            )
            return "assistant_turn_started", FlowEventStage.ORCHESTRATION, payload

        if legacy_type == "assistant_done":
            payload = self._copy_selected_fields(
                event,
                ("assistant_id", "assistant_turn_id"),
            )
            return "assistant_turn_finished", FlowEventStage.ORCHESTRATION, payload

        if legacy_type == "group_round_start":
            payload = dict(event)
            payload.pop("type", None)
            return "group_round_started", FlowEventStage.ORCHESTRATION, payload

        if legacy_type == "group_action":
            payload = dict(event)
            payload.pop("type", None)
            return "group_action_reported", FlowEventStage.ORCHESTRATION, payload

        if legacy_type == "group_done":
            payload = dict(event)
            payload.pop("type", None)
            return "group_done_reported", FlowEventStage.ORCHESTRATION, payload

        if legacy_type == "followup_questions":
            payload = self._copy_selected_fields(event, ("questions",))
            return "followup_questions_reported", FlowEventStage.META, payload

        return "legacy_event", FlowEventStage.META, {
            "legacy_type": legacy_type,
            "data": event,
        }
