"""Shared request context objects for chat entry and runtime flows."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .service_contracts import AssistantLike, SourcePayload


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
class SearchOptions:
    """Optional web-search settings attached to one chat request."""

    use_web_search: bool = False
    search_query: str | None = None


@dataclass(frozen=True)
class StreamOptions:
    """Streaming execution controls for chat flows."""

    skip_user_append: bool = False
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
    search: SearchOptions = field(default_factory=SearchOptions)
    stream: StreamOptions = field(default_factory=StreamOptions)
    editor: EditorContext = field(default_factory=EditorContext)


@dataclass(frozen=True)
class GroupChatRequestContext:
    """Group-chat request composed from shared blocks plus group settings."""

    scope: ConversationScope
    user_input: UserInputPayload
    group_assistants: list[str]
    group_mode: str = "round_robin"
    group_settings: dict[str, Any] | None = None
    search: SearchOptions = field(default_factory=SearchOptions)
    stream: StreamOptions = field(default_factory=StreamOptions)


@dataclass(frozen=True)
class CompareChatRequestContext:
    """Compare-chat request composed from shared blocks plus model selection."""

    scope: ConversationScope
    user_input: UserInputPayload
    model_ids: list[str]
    search: SearchOptions = field(default_factory=SearchOptions)
    stream: StreamOptions = field(default_factory=StreamOptions)


@dataclass(frozen=True)
class ToolResolutionContext:
    """Runtime context required to resolve callable tools for one single turn."""

    scope: ConversationScope
    editor: EditorContext
    assistant_id: str | None
    assistant_obj: AssistantLike | None
    model_id: str
    use_web_search: bool


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
