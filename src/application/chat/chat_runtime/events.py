"""Structured orchestration event models and validation helpers."""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Type, Union

from pydantic import BaseModel, ConfigDict


class _EventBase(BaseModel):
    """Common base for all orchestration events."""

    model_config = ConfigDict(extra="allow")
    type: str


class AssistantStartEvent(_EventBase):
    type: str = "assistant_start"
    assistant_id: str
    assistant_turn_id: Optional[str] = None
    name: Optional[str] = None


class AssistantChunkEvent(_EventBase):
    type: str = "assistant_chunk"
    chunk: str


class AssistantDoneEvent(_EventBase):
    type: str = "assistant_done"


class AssistantMessageIdEvent(_EventBase):
    type: str = "assistant_message_id"
    message_id: str


class GroupRoundStartEvent(_EventBase):
    type: str = "group_round_start"
    round: int
    max_rounds: int
    supervisor_id: Optional[str] = None
    supervisor_name: Optional[str] = None


class GroupActionEvent(_EventBase):
    type: str = "group_action"
    round: int
    action: str
    supervisor_id: Optional[str] = None
    supervisor_name: Optional[str] = None


class GroupDoneEvent(_EventBase):
    type: str = "group_done"
    mode: str
    reason: str
    rounds: int


class UsageEvent(_EventBase):
    type: str = "usage"
    usage: Any


class SourcesEvent(_EventBase):
    type: str = "sources"
    sources: Any


class ContextInfoEvent(_EventBase):
    type: str = "context_info"
    context_budget: int
    context_window: Optional[int] = None
    estimated_prompt_tokens: Optional[int] = None
    remaining_tokens: Optional[int] = None
    segments: Optional[Any] = None


class ThinkingDurationEvent(_EventBase):
    type: str = "thinking_duration"
    duration_ms: int


class ToolCallsEvent(_EventBase):
    type: str = "tool_calls"
    calls: Any


class ToolResultsEvent(_EventBase):
    type: str = "tool_results"
    results: Any


class ToolDiagnosticsEvent(_EventBase):
    type: str = "tool_diagnostics"
    tool_search_count: Optional[int] = None
    tool_search_unique_count: Optional[int] = None
    tool_search_duplicate_count: Optional[int] = None
    tool_read_count: Optional[int] = None
    tool_read_duplicate_count: Optional[int] = None
    web_search_count: Optional[int] = None
    web_read_count: Optional[int] = None
    no_progress_rounds: Optional[int] = None
    max_tool_rounds: Optional[int] = None
    tool_finalize_reason: Optional[str] = None


class ModelStartEvent(_EventBase):
    type: str = "model_start"
    model_id: str
    model_name: str


class ModelChunkEvent(_EventBase):
    type: str = "model_chunk"
    model_id: str
    chunk: str


class ModelDoneEvent(_EventBase):
    type: str = "model_done"
    model_id: str
    model_name: Optional[str] = None
    content: str


class ModelErrorEvent(_EventBase):
    type: str = "model_error"
    model_id: str
    model_name: Optional[str] = None
    error: str


class CompareCompleteEvent(_EventBase):
    type: str = "compare_complete"
    model_results: Dict[str, Any]


OrchestrationEventModel = Union[
    AssistantStartEvent,
    AssistantChunkEvent,
    AssistantDoneEvent,
    AssistantMessageIdEvent,
    GroupRoundStartEvent,
    GroupActionEvent,
    GroupDoneEvent,
    UsageEvent,
    SourcesEvent,
    ContextInfoEvent,
    ThinkingDurationEvent,
    ToolCallsEvent,
    ToolResultsEvent,
    ToolDiagnosticsEvent,
    ModelStartEvent,
    ModelChunkEvent,
    ModelDoneEvent,
    ModelErrorEvent,
    CompareCompleteEvent,
]


_EVENT_MODEL_BY_TYPE: Dict[str, Type[_EventBase]] = {
    "assistant_start": AssistantStartEvent,
    "assistant_chunk": AssistantChunkEvent,
    "assistant_done": AssistantDoneEvent,
    "assistant_message_id": AssistantMessageIdEvent,
    "group_round_start": GroupRoundStartEvent,
    "group_action": GroupActionEvent,
    "group_done": GroupDoneEvent,
    "usage": UsageEvent,
    "sources": SourcesEvent,
    "context_info": ContextInfoEvent,
    "thinking_duration": ThinkingDurationEvent,
    "tool_calls": ToolCallsEvent,
    "tool_results": ToolResultsEvent,
    "tool_diagnostics": ToolDiagnosticsEvent,
    "model_start": ModelStartEvent,
    "model_chunk": ModelChunkEvent,
    "model_done": ModelDoneEvent,
    "model_error": ModelErrorEvent,
    "compare_complete": CompareCompleteEvent,
}


def normalize_orchestration_event(event: Union[_EventBase, Mapping[str, Any]]) -> Dict[str, Any]:
    """Validate and normalize one event into plain dict payload."""
    if isinstance(event, _EventBase):
        return event.model_dump(exclude_none=True)

    payload = dict(event)
    event_type = payload.get("type")
    if not isinstance(event_type, str) or not event_type:
        raise ValueError("orchestration event must include non-empty string field 'type'")

    model_cls = _EVENT_MODEL_BY_TYPE.get(event_type)
    if model_cls is None:
        raise ValueError(f"unsupported orchestration event type: {event_type}")

    return model_cls.model_validate(payload).model_dump(exclude_none=True)
