"""Shared lightweight type contracts for service-layer composition."""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Any, Protocol

SourcePayload = dict[str, Any]
MessagePayload = dict[str, Any]
StreamEvent = dict[str, Any]
StreamItem = str | StreamEvent


class SupportsModelDump(Protocol):
    """Minimal model-like shape that can be serialized to dict."""

    def model_dump(self) -> SourcePayload: ...


class AssistantLike(Protocol):
    """Minimal assistant shape required by orchestration services."""

    @property
    def id(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def icon(self) -> str | None: ...

    @property
    def model_id(self) -> str: ...

    @property
    def system_prompt(self) -> str | None: ...

    @property
    def temperature(self) -> float | None: ...

    @property
    def max_tokens(self) -> int | None: ...

    @property
    def top_p(self) -> float | None: ...

    @property
    def top_k(self) -> int | None: ...

    @property
    def frequency_penalty(self) -> float | None: ...

    @property
    def presence_penalty(self) -> float | None: ...

    @property
    def max_rounds(self) -> int | None: ...

    @property
    def memory_enabled(self) -> bool: ...

    @property
    def knowledge_base_ids(self) -> list[str] | None: ...

    @property
    def tool_enabled_map(self) -> dict[str, bool]: ...

    @property
    def enabled(self) -> bool: ...


class SessionStorageLike(Protocol):
    """Conversation storage APIs consumed by context assembly."""

    async def get_session(
        self,
        session_id: str,
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> dict[str, Any]: ...


class ImportConversationStorageLike(Protocol):
    """Conversation storage APIs consumed by import services."""

    async def create_session(
        self,
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> str: ...

    async def set_messages(
        self,
        session_id: str,
        messages: list[MessagePayload],
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...

    async def update_session_metadata(
        self,
        session_id: str,
        updates: dict[str, Any],
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...


class MemoryContextServiceLike(Protocol):
    """Memory context APIs consumed during context assembly."""

    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: str | None,
        include_global: bool,
        include_assistant: bool,
    ) -> tuple[str | None, list[SourcePayload]]: ...


class MemoryServiceLike(Protocol):
    """Memory service APIs consumed by context and post-turn services."""

    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: str | None,
        include_global: bool,
        include_assistant: bool,
    ) -> tuple[str | None, list[SourcePayload]]: ...

    async def extract_and_persist_from_turn(
        self,
        *,
        user_message: str,
        assistant_message: str,
        assistant_id: str | None,
        source_session_id: str,
        source_message_id: str | None,
        assistant_memory_enabled: bool,
    ) -> None: ...


class WebpageServiceLike(Protocol):
    """Webpage parsing APIs consumed during context assembly."""

    async def build_context(
        self,
        query: str,
        /,
    ) -> tuple[str | None, Sequence[SupportsModelDump]]: ...


class SearchServiceLike(Protocol):
    """Web search APIs consumed by chat/group flows."""

    async def search(self, query: str, /) -> Sequence[SupportsModelDump]: ...

    def build_search_context(
        self,
        query: str,
        sources: Sequence[SupportsModelDump],
        /,
    ) -> str | None: ...


class SourceContextServiceLike(Protocol):
    """Structured source-context APIs injected into prompts."""

    def build_source_tags(
        self,
        query: str,
        sources: list[SourcePayload],
        max_sources: int = 20,
        max_chars_per_source: int = 1200,
    ) -> Any: ...

    def apply_template(
        self,
        query: str,
        source_context: Any,
        template: str | None = None,
    ) -> str | None: ...


class RagConfigServiceLike(Protocol):
    """Minimal retrieval config access used for structured source context."""

    config: Any

    def reload_config(self) -> None: ...


class TitleServiceLike(Protocol):
    """Title generation API required by post-turn service."""

    def should_generate_title(self, message_count: int, current_title: str, /) -> bool: ...

    def generate_title_async(self, session_id: str) -> Awaitable[str | None]: ...


class FollowupServiceLike(Protocol):
    """Follow-up question API required by post-turn service."""

    config: Any

    async def generate_followups_async(self, messages: list[MessagePayload], /) -> list[str]: ...


TaskScheduler = Callable[[Awaitable[Any]], Any]


@dataclass(frozen=True)
class ContextPayload:
    """Resolved context package consumed by chat/comparison flows."""

    messages: list[MessagePayload]
    system_prompt: str | None
    assistant_params: dict[str, Any]
    all_sources: list[SourcePayload]
    model_id: str
    assistant_id: str | None
    assistant_obj: AssistantLike | None
    assistant_memory_enabled: bool
    max_rounds: int | None
    base_system_prompt: str | None = None
    memory_context: str | None = None
    webpage_context: str | None = None
    search_context: str | None = None
    capability_contexts: dict[str, str] | None = None
    rag_context: str | None = None
    structured_source_context: str | None = None
