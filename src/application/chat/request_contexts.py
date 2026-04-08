"""Shared request context objects for chat entry and runtime flows."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, cast

from .service_contracts import AssistantLike, SourcePayload

if TYPE_CHECKING:
    from .chat_runtime.base import (
        ChatOrchestrationMode,
        ChatOrchestrationRequest,
        ChatOrchestrationSettings,
    )


@dataclass(frozen=True)
class ConversationScope:
    """Conversation identifiers reused across chat entrypoints."""

    session_id: str
    context_type: str = "chat"
    project_id: str | None = None


@dataclass(frozen=True)
class UserInputPayload:
    """User-provided message content and related context."""

    user_message: str
    attachments: list[SourcePayload] | None = None
    file_references: list[dict[str, str]] | None = None


@dataclass(frozen=True)
class ContextCapabilitiesOptions:
    """Optional context capability settings attached to one chat request."""

    context_capabilities: list[str] = field(default_factory=list)
    context_capability_args: dict[str, dict[str, Any]] = field(default_factory=dict)


@dataclass(frozen=True)
class StreamOptions:
    """Streaming execution controls for chat flows."""

    skip_user_append: bool = False
    temporary_turn: bool = False
    reasoning_effort: str | None = None


@dataclass(frozen=True)
class EditorContext:
    """Active editor file context for project chat flows."""

    active_file_path: str | None = None
    active_file_hash: str | None = None


@dataclass(frozen=True)
class SingleChatRequestContext:
    """Single-chat request composed from smaller reusable context blocks."""

    scope: ConversationScope
    user_input: UserInputPayload
    context_capabilities: ContextCapabilitiesOptions = field(
        default_factory=ContextCapabilitiesOptions
    )
    stream: StreamOptions = field(default_factory=StreamOptions)
    editor: EditorContext = field(default_factory=EditorContext)


@dataclass(frozen=True)
class GroupChatRequestContext:
    """Group-chat request composed from shared blocks plus group settings."""

    scope: ConversationScope
    user_input: UserInputPayload
    group_assistants: list[str]
    group_mode: str = "round_robin"
    group_settings: dict[str, object] | None = None
    context_capabilities: ContextCapabilitiesOptions = field(
        default_factory=ContextCapabilitiesOptions
    )
    stream: StreamOptions = field(default_factory=StreamOptions)


@dataclass(frozen=True)
class CompareChatRequestContext:
    """Compare-chat request composed from shared blocks plus model selection."""

    scope: ConversationScope
    user_input: UserInputPayload
    model_ids: list[str]
    context_capabilities: ContextCapabilitiesOptions = field(
        default_factory=ContextCapabilitiesOptions
    )
    stream: StreamOptions = field(default_factory=StreamOptions)

    def to_orchestration_request(
        self,
        *,
        settings: ChatOrchestrationSettings,
        user_message: str | None = None,
    ) -> ChatOrchestrationRequest:
        """Translate compare request context into one compare-model orchestrator request."""

        from .chat_runtime.base import ChatOrchestrationRequest

        return ChatOrchestrationRequest(
            session_id=self.scope.session_id,
            mode="compare_models",
            user_message=user_message if user_message is not None else self.user_input.user_message,
            participants=self.model_ids,
            assistant_name_map={},
            assistant_config_map={},
            settings=settings,
            reasoning_effort=self.stream.reasoning_effort,
            context_type=self.scope.context_type,
            project_id=self.scope.project_id,
        )


@dataclass(frozen=True)
class ToolResolutionContext:
    """Runtime context required to resolve callable tools for one single turn."""

    scope: ConversationScope
    editor: EditorContext
    assistant_id: str | None
    assistant_obj: AssistantLike | None
    model_id: str
    context_capabilities: list[str] = field(default_factory=list)
    user_message: str = ""


@dataclass(frozen=True)
class CommitteeExecutionContext:
    """Resolved committee execution inputs shared across group runtime helpers."""

    scope: ConversationScope
    raw_user_message: str
    group_assistants: list[str]
    assistant_name_map: dict[str, str]
    assistant_config_map: dict[str, AssistantLike]
    group_settings: dict[str, object] | None
    reasoning_effort: str | None
    search_context: str | None
    search_sources: list[SourcePayload]
    group_mode: str = "committee"
    trace_id: str | None = None

    @classmethod
    def from_orchestration_request(
        cls,
        request: ChatOrchestrationRequest,
        *,
        group_settings: dict[str, object] | None = None,
    ) -> CommitteeExecutionContext:
        """Project one orchestration request back into shared group execution inputs."""

        return cls(
            scope=ConversationScope(
                session_id=request.session_id,
                context_type=request.context_type,
                project_id=request.project_id,
            ),
            raw_user_message=request.user_message,
            group_assistants=request.participants,
            assistant_name_map=request.assistant_name_map,
            assistant_config_map=request.assistant_config_map,
            group_settings=group_settings,
            reasoning_effort=request.reasoning_effort,
            search_context=request.search_context,
            search_sources=request.search_sources,
            group_mode=str(request.mode),
            trace_id=request.trace_id,
        )

    def with_updates(self, **changes: Any) -> CommitteeExecutionContext:
        """Return a copy with selected execution fields updated."""

        return replace(self, **cast(Any, changes))

    def to_orchestration_request(
        self,
        *,
        mode: ChatOrchestrationMode,
        settings: ChatOrchestrationSettings,
        trace_id: str | None = None,
    ) -> ChatOrchestrationRequest:
        """Translate shared execution context into one orchestrator request."""

        from .chat_runtime.base import ChatOrchestrationRequest

        return ChatOrchestrationRequest(
            session_id=self.scope.session_id,
            mode=mode,
            user_message=self.raw_user_message,
            participants=self.group_assistants,
            assistant_name_map=self.assistant_name_map,
            assistant_config_map=self.assistant_config_map,
            settings=settings,
            reasoning_effort=self.reasoning_effort,
            context_type=self.scope.context_type,
            project_id=self.scope.project_id,
            search_context=self.search_context,
            search_sources=self.search_sources,
            trace_id=trace_id if trace_id is not None else self.trace_id,
        )


@dataclass(frozen=True)
class CommitteeMemberTurnContext:
    """Resolved member-turn inputs derived from one committee execution run."""

    execution: CommitteeExecutionContext
    assistant_id: str
    assistant_obj: AssistantLike
    instruction: str | None = None
    committee_turn_packet: dict[str, object] | None = None
    trace_round: int | None = None
    trace_mode: str | None = None
