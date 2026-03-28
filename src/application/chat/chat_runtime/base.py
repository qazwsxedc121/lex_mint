"""Base contracts for chat runtime orchestrators."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Literal, Union

from .events import normalize_orchestration_event

ChatOrchestrationMode = Literal["round_robin", "committee", "compare_models"]


@dataclass(frozen=True)
class RoundRobinSettings:
    """Settings for deterministic participant-by-participant execution."""

    max_turns: int | None = None


@dataclass
class ChatOrchestrationCancelToken:
    """Cooperative cancellation token for orchestrator control APIs."""

    is_cancelled: bool = False
    reason: str = "cancelled"

    def cancel(self, reason: str | None = None) -> None:
        """Mark the token as cancelled with an optional reason."""
        self.is_cancelled = True
        if reason:
            self.reason = str(reason).strip() or self.reason


if TYPE_CHECKING:
    # Forward references keep runtime import graph light.
    from .compare_models import CompareModelsSettings
    from .settings import ResolvedCommitteeSettings


ChatOrchestrationSettings = Union[
    "ResolvedCommitteeSettings",
    "CompareModelsSettings",
    RoundRobinSettings,
    None,
]


@dataclass(frozen=True)
class ChatOrchestrationRequest:
    """Normalized orchestration input shared by concrete orchestrators."""

    session_id: str
    mode: ChatOrchestrationMode
    user_message: str
    participants: list[str]
    assistant_name_map: dict[str, str]
    assistant_config_map: dict[str, Any]
    settings: ChatOrchestrationSettings
    reasoning_effort: str | None = None
    context_type: str = "chat"
    project_id: str | None = None
    search_context: str | None = None
    search_sources: list[dict[str, Any]] = field(default_factory=list)
    trace_id: str | None = None


ChatOrchestrationEvent = dict[str, Any]


class BaseChatOrchestrator(ABC):
    """Abstract base for mode-specific orchestration engines."""

    mode: str = "unknown"

    @abstractmethod
    def stream(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> AsyncIterator[ChatOrchestrationEvent]:
        """Run orchestration and yield streaming events."""
        raise NotImplementedError

    async def run(
        self,
        request: ChatOrchestrationRequest,
        *,
        cancel_token: ChatOrchestrationCancelToken | None = None,
    ) -> list[ChatOrchestrationEvent]:
        """Collect all streamed events into a materialized result."""
        events: list[ChatOrchestrationEvent] = []
        async for event in self.stream(request, cancel_token=cancel_token):
            events.append(event)
        return events

    @staticmethod
    def is_cancelled(cancel_token: ChatOrchestrationCancelToken | None) -> bool:
        """Return True when cooperative cancellation was requested."""
        return bool(cancel_token and cancel_token.is_cancelled)

    @staticmethod
    def normalize_event(event: dict[str, Any]) -> ChatOrchestrationEvent:
        """Validate one event against the shared event schema."""
        return normalize_orchestration_event(event)
