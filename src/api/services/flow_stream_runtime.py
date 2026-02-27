"""In-memory runtime for chat FlowEvent stream replay and resume."""

from __future__ import annotations

import asyncio
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, List, Optional, Tuple


class FlowStreamError(Exception):
    """Base error for stream runtime operations."""


class FlowStreamNotFoundError(FlowStreamError):
    """Raised when stream id is unknown."""


class FlowReplayCursorGoneError(FlowStreamError):
    """Raised when last_event_id is not available in replay window."""


class FlowStreamContextMismatchError(FlowStreamError):
    """Raised when stream metadata does not match request context."""


@dataclass
class FlowStreamState:
    """Active or completed stream state used for replay and fanout."""

    stream_id: str
    conversation_id: str
    context_type: str
    project_id: Optional[str]
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    done: bool = False
    seq: int = 0
    events: Deque[Dict[str, Any]] = field(default_factory=deque)
    subscribers: Dict[str, asyncio.Queue] = field(default_factory=dict)

    def next_seq(self) -> int:
        self.seq += 1
        return self.seq


class FlowStreamRuntime:
    """Process-local stream event cache with replay and subscription support."""

    def __init__(
        self,
        *,
        ttl_seconds: int = 900,
        max_events_per_stream: int = 5000,
        max_active_streams: int = 200,
    ) -> None:
        self.ttl_seconds = int(ttl_seconds)
        self.max_events_per_stream = int(max_events_per_stream)
        self.max_active_streams = int(max_active_streams)
        self._streams: Dict[str, FlowStreamState] = {}

    def create_stream(
        self,
        *,
        stream_id: str,
        conversation_id: str,
        context_type: str,
        project_id: Optional[str],
    ) -> FlowStreamState:
        self._gc()
        if stream_id in self._streams:
            return self._streams[stream_id]

        if len(self._streams) >= self.max_active_streams:
            self._evict_completed_streams()
        if len(self._streams) >= self.max_active_streams:
            raise RuntimeError("too many active flow streams")

        state = FlowStreamState(
            stream_id=stream_id,
            conversation_id=conversation_id,
            context_type=context_type,
            project_id=project_id,
            events=deque(maxlen=self.max_events_per_stream),
        )
        self._streams[stream_id] = state
        return state

    def get_stream(self, stream_id: str) -> FlowStreamState:
        self._gc()
        state = self._streams.get(stream_id)
        if state is None:
            raise FlowStreamNotFoundError(stream_id)
        return state

    def next_seq(self, stream_id: str) -> int:
        state = self.get_stream(stream_id)
        return state.next_seq()

    def append_payload(self, stream_id: str, payload: Dict[str, Any]) -> None:
        state = self.get_stream(stream_id)
        state.updated_at = time.time()
        state.events.append(payload)

        flow_event = payload.get("flow_event")
        if isinstance(flow_event, dict):
            seq = flow_event.get("seq")
            if isinstance(seq, int) and seq > state.seq:
                state.seq = seq
            event_type = flow_event.get("event_type")
            if event_type in {"stream_ended", "stream_error"}:
                state.done = True
        elif payload.get("done") is True or "error" in payload:
            state.done = True

        for queue in state.subscribers.values():
            queue.put_nowait(payload)

    def subscribe(self, stream_id: str) -> Tuple[str, asyncio.Queue]:
        state = self.get_stream(stream_id)
        subscriber_id = str(uuid.uuid4())
        queue: asyncio.Queue = asyncio.Queue()
        state.subscribers[subscriber_id] = queue
        state.updated_at = time.time()
        return subscriber_id, queue

    def resume_subscribe(
        self,
        *,
        stream_id: str,
        last_event_id: str,
        conversation_id: str,
        context_type: str,
        project_id: Optional[str],
    ) -> Tuple[str, asyncio.Queue, List[Dict[str, Any]]]:
        state = self.get_stream(stream_id)

        if (
            state.conversation_id != conversation_id
            or state.context_type != context_type
            or (state.project_id or None) != (project_id or None)
        ):
            raise FlowStreamContextMismatchError(stream_id)

        events = list(state.events)
        replay_start = None
        for index, payload in enumerate(events):
            flow_event = payload.get("flow_event")
            if not isinstance(flow_event, dict):
                continue
            if flow_event.get("event_id") == last_event_id:
                replay_start = index + 1
                break
        if replay_start is None:
            raise FlowReplayCursorGoneError(last_event_id)

        replay_payloads = events[replay_start:]
        subscriber_id, queue = self.subscribe(stream_id)
        return subscriber_id, queue, replay_payloads

    def unsubscribe(self, stream_id: str, subscriber_id: str) -> None:
        state = self._streams.get(stream_id)
        if state is None:
            return
        state.subscribers.pop(subscriber_id, None)
        state.updated_at = time.time()
        self._gc()

    def _gc(self) -> None:
        if not self._streams:
            return
        now = time.time()
        to_delete: List[str] = []
        for stream_id, state in self._streams.items():
            if not state.done:
                continue
            if now - state.updated_at >= self.ttl_seconds:
                to_delete.append(stream_id)
        for stream_id in to_delete:
            self._streams.pop(stream_id, None)

    def _evict_completed_streams(self) -> None:
        completed = [state for state in self._streams.values() if state.done]
        completed.sort(key=lambda item: item.updated_at)
        while len(self._streams) >= self.max_active_streams and completed:
            state = completed.pop(0)
            self._streams.pop(state.stream_id, None)
