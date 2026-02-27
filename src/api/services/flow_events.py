"""Flow event schema and helpers for streaming orchestration output."""

from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class FlowEventStage(str, Enum):
    """Top-level stage classification for one flow event."""

    TRANSPORT = "transport"
    CONTENT = "content"
    TOOL = "tool"
    ORCHESTRATION = "orchestration"
    META = "meta"


class FlowEvent(BaseModel):
    """Canonical stream event payload consumed by frontend and replay layers."""

    model_config = ConfigDict(extra="forbid")

    event_id: str = Field(min_length=1)
    seq: int = Field(ge=1)
    ts: int = Field(ge=0)
    stream_id: str = Field(min_length=1)
    conversation_id: Optional[str] = None
    turn_id: Optional[str] = None
    event_type: str = Field(min_length=1)
    stage: FlowEventStage
    payload: Dict[str, Any] = Field(default_factory=dict)


def now_ms() -> int:
    """Return current timestamp in milliseconds."""

    return int(time.time() * 1000)


def new_flow_event(
    *,
    seq: int,
    stream_id: str,
    event_type: str,
    stage: FlowEventStage,
    payload: Optional[Dict[str, Any]] = None,
    conversation_id: Optional[str] = None,
    turn_id: Optional[str] = None,
) -> FlowEvent:
    """Create one validated flow event with generated ids/timestamp."""

    return FlowEvent(
        event_id=str(uuid.uuid4()),
        seq=seq,
        ts=now_ms(),
        stream_id=stream_id,
        conversation_id=conversation_id,
        turn_id=turn_id,
        event_type=event_type,
        stage=stage,
        payload=payload or {},
    )
