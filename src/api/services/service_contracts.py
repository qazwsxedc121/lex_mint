"""Shared lightweight type contracts for service-layer composition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Protocol, Sequence, Tuple, Union

SourcePayload = Dict[str, Any]
MessagePayload = Dict[str, Any]
StreamEvent = Dict[str, Any]
StreamItem = Union[str, StreamEvent]


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
    def model_id(self) -> str: ...

    @property
    def system_prompt(self) -> Optional[str]: ...

    @property
    def temperature(self) -> Optional[float]: ...

    @property
    def max_tokens(self) -> Optional[int]: ...

    @property
    def top_p(self) -> Optional[float]: ...

    @property
    def top_k(self) -> Optional[int]: ...

    @property
    def frequency_penalty(self) -> Optional[float]: ...

    @property
    def presence_penalty(self) -> Optional[float]: ...

    @property
    def max_rounds(self) -> Optional[int]: ...

    @property
    def memory_enabled(self) -> bool: ...

    @property
    def knowledge_base_ids(self) -> Optional[List[str]]: ...

    @property
    def enabled(self) -> bool: ...


class SessionStorageLike(Protocol):
    """Conversation storage APIs consumed by context assembly."""

    async def get_session(
        self,
        session_id: str,
        *,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> Dict[str, Any]: ...


class MemoryContextServiceLike(Protocol):
    """Memory context APIs consumed during context assembly."""

    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: Optional[str],
        include_global: bool,
        include_assistant: bool,
    ) -> Tuple[Optional[str], List[SourcePayload]]: ...


class MemoryServiceLike(Protocol):
    """Memory service APIs consumed by context and post-turn services."""

    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: Optional[str],
        include_global: bool,
        include_assistant: bool,
    ) -> Tuple[Optional[str], List[SourcePayload]]: ...

    async def extract_and_persist_from_turn(
        self,
        *,
        user_message: str,
        assistant_message: str,
        assistant_id: Optional[str],
        source_session_id: str,
        source_message_id: Optional[str],
        assistant_memory_enabled: bool,
    ) -> None: ...


class WebpageServiceLike(Protocol):
    """Webpage parsing APIs consumed during context assembly."""

    async def build_context(
        self,
        query: str,
        /,
    ) -> Tuple[Optional[str], Sequence[SupportsModelDump]]: ...


class SearchServiceLike(Protocol):
    """Web search APIs consumed by chat/group flows."""

    async def search(self, query: str, /) -> Sequence[SupportsModelDump]: ...

    def build_search_context(
        self,
        query: str,
        sources: Sequence[SupportsModelDump],
        /,
    ) -> Optional[str]: ...


class SourceContextServiceLike(Protocol):
    """Structured source-context APIs injected into prompts."""

    def build_source_tags(
        self,
        query: str,
        sources: List[SourcePayload],
        /,
    ) -> Any: ...

    def apply_template(
        self,
        query: str,
        source_context: Any,
        /,
    ) -> Optional[str]: ...


class RagConfigServiceLike(Protocol):
    """Minimal retrieval config access used for structured source context."""

    config: Any

    def reload_config(self) -> None: ...


class TitleServiceLike(Protocol):
    """Title generation API required by post-turn service."""

    def should_generate_title(self, message_count: int, current_title: str, /) -> bool: ...

    def generate_title_async(self, session_id: str) -> Awaitable[Optional[str]]: ...


class FollowupServiceLike(Protocol):
    """Follow-up question API required by post-turn service."""

    config: Any

    async def generate_followups_async(self, messages: List[MessagePayload], /) -> List[str]: ...


TaskScheduler = Callable[[Awaitable[Any]], Any]


@dataclass(frozen=True)
class ContextPayload:
    """Resolved context package consumed by chat/comparison flows."""

    messages: List[MessagePayload]
    system_prompt: Optional[str]
    assistant_params: Dict[str, Any]
    all_sources: List[SourcePayload]
    model_id: str
    assistant_id: Optional[str]
    assistant_obj: Optional[AssistantLike]
    is_legacy_assistant: bool
    assistant_memory_enabled: bool
    max_rounds: Optional[int]
