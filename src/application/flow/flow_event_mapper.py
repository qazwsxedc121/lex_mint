"""Stream event to FlowEvent mapping helpers."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from .flow_event_types import (
    ASSISTANT_MESSAGE_IDENTIFIED,
    ASSISTANT_TURN_FINISHED,
    ASSISTANT_TURN_STARTED,
    COMPARE_COMPLETED,
    COMPARE_MODEL_FAILED,
    COMPARE_MODEL_FINISHED,
    COMPARE_MODEL_STARTED,
    COMPRESSION_COMPLETED,
    CONTEXT_REPORTED,
    FOLLOWUP_QUESTIONS_REPORTED,
    GROUP_ACTION_REPORTED,
    GROUP_DONE_REPORTED,
    GROUP_ROUND_STARTED,
    REASONING_DURATION_REPORTED,
    SOURCES_REPORTED,
    STREAM_ENDED,
    STREAM_ERROR,
    STREAM_STARTED,
    TEXT_DELTA,
    TOOL_CALL_FINISHED,
    TOOL_CALL_STARTED,
    TOOL_DIAGNOSTICS_REPORTED,
    USAGE_REPORTED,
    USER_MESSAGE_IDENTIFIED,
)
from .flow_events import FlowEventStage, new_flow_event

StreamChunk = str | Mapping[str, Any]


@dataclass
class FlowEventMapper:
    """Attach flow_event envelopes while enforcing known stream event contracts."""

    stream_id: str
    conversation_id: str | None = None
    default_turn_id: str | None = None
    seq_provider: Callable[[], int] | None = None
    _seq: int = 0

    def to_sse_payload(self, chunk: StreamChunk) -> dict[str, Any]:
        """Return flow_event-only payload mapped from stream chunk."""

        return {"flow_event": self._map_chunk_to_flow_event(chunk)}

    def make_stream_started_payload(self, *, context_type: str | None = None) -> dict[str, Any]:
        """Build an initial stream-start payload."""

        payload: dict[str, Any] = {}
        if context_type:
            payload["context_type"] = context_type
        flow_event = self._create_event(
            event_type=STREAM_STARTED,
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
        payload: dict[str, Any],
        turn_id: str | None = None,
    ) -> dict[str, Any]:
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

    def _map_chunk_to_flow_event(self, chunk: StreamChunk) -> dict[str, Any]:
        if isinstance(chunk, Mapping):
            payload = dict(chunk)
            if payload.get("done") is True:
                return self._create_event(
                    event_type=STREAM_ENDED,
                    stage=FlowEventStage.TRANSPORT,
                    payload={"done": True},
                )
            if "error" in payload:
                return self._create_event(
                    event_type=STREAM_ERROR,
                    stage=FlowEventStage.TRANSPORT,
                    payload={"error": str(payload.get("error"))},
                )
            return self._map_event(payload)

        return self._create_event(
            event_type=TEXT_DELTA,
            stage=FlowEventStage.CONTENT,
            payload={"text": str(chunk)},
        )

    def _map_event(self, event: dict[str, Any]) -> dict[str, Any]:
        raw_type = event.get("type")
        if isinstance(raw_type, str):
            event_type, stage, payload = self._event_type_to_flow(raw_type, event)
            if event_type == STREAM_ERROR:
                return self._create_event(
                    event_type=STREAM_ERROR,
                    stage=FlowEventStage.TRANSPORT,
                    payload=payload,
                )
            turn_id = self._extract_turn_id(event)
            return self._create_event(
                event_type=event_type,
                stage=stage,
                payload=payload,
                turn_id=turn_id,
            )

        if "chunk" in event:
            return self._create_event(
                event_type=TEXT_DELTA,
                stage=FlowEventStage.CONTENT,
                payload={"text": str(event.get("chunk") or "")},
            )

        return self._create_event(
            event_type=STREAM_ERROR,
            stage=FlowEventStage.TRANSPORT,
            payload={"error": "unsupported stream event: missing type/chunk"},
        )

    @staticmethod
    def _extract_turn_id(event: dict[str, Any]) -> str | None:
        turn_id = event.get("assistant_turn_id")
        if isinstance(turn_id, str) and turn_id:
            return turn_id
        return None

    @staticmethod
    def _copy_selected_fields(event: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        for field in fields:
            if field in event:
                payload[field] = event[field]
        return payload

    def _event_type_to_flow(
        self,
        event_type: str,
        event: dict[str, Any],
    ) -> tuple[str, FlowEventStage, dict[str, Any]]:
        if event_type == "assistant_chunk":
            payload = self._copy_selected_fields(
                event,
                ("chunk", "assistant_id", "assistant_turn_id"),
            )
            chunk = str(payload.pop("chunk", "") or "")
            payload["text"] = chunk
            return TEXT_DELTA, FlowEventStage.CONTENT, payload

        if event_type == "usage":
            payload = self._copy_selected_fields(
                event,
                ("usage", "cost", "assistant_id", "assistant_turn_id"),
            )
            return USAGE_REPORTED, FlowEventStage.META, payload

        if event_type == "sources":
            payload = self._copy_selected_fields(
                event,
                ("sources", "assistant_id", "assistant_turn_id"),
            )
            return SOURCES_REPORTED, FlowEventStage.META, payload

        if event_type == "user_message_id":
            payload = self._copy_selected_fields(event, ("message_id",))
            return USER_MESSAGE_IDENTIFIED, FlowEventStage.META, payload

        if event_type == "assistant_message_id":
            payload = self._copy_selected_fields(
                event,
                ("message_id", "assistant_id", "assistant_turn_id"),
            )
            return ASSISTANT_MESSAGE_IDENTIFIED, FlowEventStage.META, payload

        if event_type == "context_info":
            payload = dict(event)
            payload.pop("type", None)
            return CONTEXT_REPORTED, FlowEventStage.META, payload

        if event_type == "thinking_duration":
            payload = self._copy_selected_fields(
                event,
                ("duration_ms", "assistant_id", "assistant_turn_id"),
            )
            return REASONING_DURATION_REPORTED, FlowEventStage.CONTENT, payload

        if event_type == "tool_calls":
            payload = self._copy_selected_fields(
                event,
                ("calls", "assistant_id", "assistant_turn_id"),
            )
            return TOOL_CALL_STARTED, FlowEventStage.TOOL, payload

        if event_type == "tool_results":
            payload = self._copy_selected_fields(
                event,
                ("results", "assistant_id", "assistant_turn_id"),
            )
            return TOOL_CALL_FINISHED, FlowEventStage.TOOL, payload

        if event_type == "tool_diagnostics":
            payload = self._copy_selected_fields(
                event,
                (
                    "assistant_id",
                    "assistant_turn_id",
                    "tool_search_count",
                    "tool_search_unique_count",
                    "tool_search_duplicate_count",
                    "tool_read_count",
                    "tool_read_duplicate_count",
                    "web_search_count",
                    "web_read_count",
                    "no_progress_rounds",
                    "max_tool_rounds",
                    "tool_finalize_reason",
                ),
            )
            return TOOL_DIAGNOSTICS_REPORTED, FlowEventStage.META, payload

        if event_type == "assistant_start":
            payload = self._copy_selected_fields(
                event,
                ("assistant_id", "assistant_turn_id", "name", "icon"),
            )
            return ASSISTANT_TURN_STARTED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "assistant_done":
            payload = self._copy_selected_fields(
                event,
                ("assistant_id", "assistant_turn_id"),
            )
            return ASSISTANT_TURN_FINISHED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "model_start":
            payload = self._copy_selected_fields(event, ("model_id", "model_name"))
            return COMPARE_MODEL_STARTED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "model_chunk":
            payload = self._copy_selected_fields(event, ("model_id",))
            payload["text"] = str(event.get("chunk") or "")
            return TEXT_DELTA, FlowEventStage.CONTENT, payload

        if event_type == "model_done":
            payload = self._copy_selected_fields(
                event,
                ("model_id", "model_name", "content", "usage", "cost"),
            )
            return COMPARE_MODEL_FINISHED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "model_error":
            payload = self._copy_selected_fields(
                event,
                ("model_id", "model_name", "error"),
            )
            return COMPARE_MODEL_FAILED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "compare_complete":
            payload = self._copy_selected_fields(event, ("model_results", "reason"))
            return COMPARE_COMPLETED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "group_round_start":
            payload = dict(event)
            payload.pop("type", None)
            return GROUP_ROUND_STARTED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "group_action":
            payload = dict(event)
            payload.pop("type", None)
            return GROUP_ACTION_REPORTED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "group_done":
            payload = dict(event)
            payload.pop("type", None)
            return GROUP_DONE_REPORTED, FlowEventStage.ORCHESTRATION, payload

        if event_type == "followup_questions":
            payload = self._copy_selected_fields(event, ("questions",))
            return FOLLOWUP_QUESTIONS_REPORTED, FlowEventStage.META, payload

        if event_type == "compression_complete":
            payload = self._copy_selected_fields(
                event,
                ("message_id", "compressed_count", "compression_meta"),
            )
            return COMPRESSION_COMPLETED, FlowEventStage.META, payload

        return (
            STREAM_ERROR,
            FlowEventStage.TRANSPORT,
            {
                "error": f"unsupported stream event type: {event_type}",
            },
        )
