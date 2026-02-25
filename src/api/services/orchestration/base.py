"""Base contracts for pluggable orchestration engines."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Dict, List, Literal, Optional, Union

from .events import normalize_orchestration_event

OrchestrationMode = Literal["single_turn", "round_robin", "committee", "compare_models"]


@dataclass(frozen=True)
class RoundRobinSettings:
    """Settings for deterministic participant-by-participant execution."""

    max_turns: Optional[int] = None


@dataclass
class OrchestrationCancelToken:
    """Cooperative cancellation token for orchestrator control APIs."""

    is_cancelled: bool = False
    reason: str = "cancelled"

    def cancel(self, reason: Optional[str] = None) -> None:
        """Mark the token as cancelled with an optional reason."""
        self.is_cancelled = True
        if reason:
            self.reason = str(reason).strip() or self.reason


if TYPE_CHECKING:
    # Forward references keep runtime import graph light.
    from .compare_models import CompareModelsSettings
    from .settings import ResolvedCommitteeSettings
    from .single_turn import SingleTurnSettings


OrchestrationSettings = Union[
    "SingleTurnSettings",
    "ResolvedCommitteeSettings",
    "CompareModelsSettings",
    RoundRobinSettings,
    None,
]


@dataclass(frozen=True)
class OrchestrationRequest:
    """Normalized orchestration input shared by concrete orchestrators."""

    session_id: str
    mode: OrchestrationMode
    user_message: str
    participants: List[str]
    assistant_name_map: Dict[str, str]
    assistant_config_map: Dict[str, Any]
    settings: OrchestrationSettings
    reasoning_effort: Optional[str] = None
    context_type: str = "chat"
    project_id: Optional[str] = None
    search_context: Optional[str] = None
    search_sources: List[Dict[str, Any]] = field(default_factory=list)
    trace_id: Optional[str] = None

OrchestrationEvent = Dict[str, Any]


class BaseOrchestrator(ABC):
    """Abstract base for mode-specific orchestration engines."""

    mode: str = "unknown"

    @abstractmethod
    def stream(
        self,
        request: OrchestrationRequest,
        *,
        cancel_token: Optional[OrchestrationCancelToken] = None,
    ) -> AsyncIterator[OrchestrationEvent]:
        """Run orchestration and yield streaming events."""
        raise NotImplementedError

    async def run(
        self,
        request: OrchestrationRequest,
        *,
        cancel_token: Optional[OrchestrationCancelToken] = None,
    ) -> List[OrchestrationEvent]:
        """Collect all streamed events into a materialized result."""
        events: List[OrchestrationEvent] = []
        async for event in self.stream(request, cancel_token=cancel_token):
            events.append(event)
        return events

    @staticmethod
    def is_cancelled(cancel_token: Optional[OrchestrationCancelToken]) -> bool:
        """Return True when cooperative cancellation was requested."""
        return bool(cancel_token and cancel_token.is_cancelled)

    @staticmethod
    def normalize_event(event: Dict[str, Any]) -> OrchestrationEvent:
        """Validate one event against the shared event schema."""
        return normalize_orchestration_event(event)

