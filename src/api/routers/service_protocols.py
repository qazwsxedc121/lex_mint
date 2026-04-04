"""Lightweight protocols for API router dependency typing."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from src.domain.models.assistant_config import Assistant
from src.domain.models.prompt_template import PromptTemplate
from src.infrastructure.config.folder_service import Folder


class ConfigSaveServiceLike(Protocol):
    """Config service shape used by config routers."""

    config: Any

    def save_config(self, updates: dict[str, Any]) -> None: ...


class FlatConfigServiceLike(Protocol):
    def get_flat_config(self) -> dict[str, Any]: ...

    def save_flat_config(self, updates: dict[str, Any]) -> None: ...


class AssistantConfigServiceLike(Protocol):
    async def get_assistants(self, *, enabled_only: bool = False) -> list[Assistant]: ...

    async def get_assistant(self, assistant_id: str) -> Assistant | None: ...

    async def add_assistant(self, assistant: Assistant) -> None: ...

    async def update_assistant(self, assistant_id: str, assistant: Assistant) -> None: ...

    async def delete_assistant(self, assistant_id: str) -> None: ...

    async def get_default_assistant_id(self) -> str: ...

    async def get_default_assistant(self) -> Assistant: ...

    async def set_default_assistant(self, assistant_id: str) -> None: ...


class FollowupServiceLike(Protocol):
    config: Any

    def save_config(self, updates: dict[str, Any]) -> None: ...

    async def generate_followups_async(self, messages: list[dict[str, Any]]) -> list[str]: ...


class TitleGenerationServiceLike(Protocol):
    config: Any

    def save_config(self, updates: dict[str, Any]) -> None: ...

    async def generate_title_async(self, session_id: str) -> str | None: ...


class SessionStorageLike(Protocol):
    async def get_session(
        self,
        session_id: str,
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> dict[str, Any]: ...


class UploadFileLike(Protocol):
    @property
    def filename(self) -> str | None: ...

    async def read(self) -> bytes: ...


class ConversationQueryStorageLike(Protocol):
    async def _find_session_file(
        self,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> Path | None: ...

    async def list_sessions(
        self,
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def search_sessions(
        self,
        query: str,
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> list[dict[str, Any]]: ...

    async def get_session(
        self,
        session_id: str,
        *,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> dict[str, Any]: ...


class ConversationImportStorageLike(Protocol):
    async def create_session(
        self,
        *,
        assistant_id: str | None = None,
        model_id: str | None = None,
        title: str = "",
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> str: ...

    async def set_messages(
        self,
        session_id: str,
        messages: list[dict[str, Any]],
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


class SessionApplicationServiceLike(Protocol):
    async def create_session(
        self,
        *,
        assistant_id: str | None = None,
        model_id: str | None = None,
        target_type: str | None = None,
        temporary: bool = False,
        group_assistants: list[str] | None = None,
        group_mode: str | None = None,
        group_settings: dict[str, Any] | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> str: ...

    async def delete_session(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...

    async def save_temporary_session(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...

    async def update_session_target(
        self,
        *,
        session_id: str,
        target_type: str,
        assistant_id: str | None = None,
        model_id: str | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...

    async def update_group_assistants(
        self,
        *,
        session_id: str,
        group_assistants: list[str],
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...

    async def get_group_settings(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def update_group_settings(
        self,
        *,
        session_id: str,
        group_assistants: list[str] | None = None,
        group_mode: str | None = None,
        group_settings: dict[str, Any] | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> dict[str, Any]: ...

    async def update_session_title(
        self,
        *,
        session_id: str,
        title: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...

    async def update_param_overrides(
        self,
        *,
        session_id: str,
        overrides: dict[str, Any],
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...

    async def branch_session(
        self,
        *,
        session_id: str,
        message_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> str: ...

    async def duplicate_session(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> str: ...

    async def move_session(
        self,
        *,
        session_id: str,
        source_context_type: str,
        source_project_id: str | None = None,
        target_context_type: str,
        target_project_id: str | None = None,
    ) -> None: ...

    async def copy_session(
        self,
        *,
        session_id: str,
        source_context_type: str,
        source_project_id: str | None = None,
        target_context_type: str,
        target_project_id: str | None = None,
    ) -> str: ...

    async def update_session_folder(
        self,
        *,
        session_id: str,
        folder_id: str | None,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...


class FolderServiceLike(Protocol):
    async def list_folders(self) -> list[Folder]: ...

    async def create_folder(self, name: str) -> Folder: ...

    async def update_folder(self, folder_id: str, name: str) -> Folder: ...

    async def reorder_folder(self, folder_id: str, new_order: int) -> Folder: ...

    async def delete_folder(self, folder_id: str) -> None: ...


class FolderStorageLike(Protocol):
    async def list_sessions(self, context_type: str = "chat") -> list[dict[str, Any]]: ...

    async def update_session_folder(
        self,
        *,
        session_id: str,
        folder_id: str | None,
        context_type: str = "chat",
    ) -> None: ...


class PromptTemplateConfigServiceLike(Protocol):
    async def get_templates(self) -> list[PromptTemplate]: ...

    async def get_template(self, template_id: str) -> PromptTemplate | None: ...

    async def add_template(self, template: PromptTemplate) -> None: ...

    async def update_template(self, template_id: str, template: PromptTemplate) -> None: ...

    async def delete_template(self, template_id: str) -> None: ...


class MemoryServiceLike(Protocol):
    def list_memories(
        self,
        *,
        profile_id: str | None,
        scope: str | None,
        assistant_id: str | None,
        layer: str | None,
        limit: int,
        include_inactive: bool,
    ) -> list[dict[str, Any]]: ...

    def upsert_memory(
        self,
        *,
        content: str,
        scope: str,
        layer: str,
        assistant_id: str | None,
        profile_id: str | None,
        confidence: float,
        importance: float,
        source_session_id: str | None,
        source_message_id: str | None,
        pinned: bool,
    ) -> dict[str, Any]: ...

    def update_memory(self, memory_id: str, **updates: Any) -> dict[str, Any]: ...

    def delete_memory(self, memory_id: str) -> None: ...

    def search_memories(
        self,
        *,
        query: str,
        profile_id: str | None,
        scope: str,
        assistant_id: str | None,
        layer: str | None,
        top_k: int,
    ) -> list[dict[str, Any]]: ...

    def search_memories_for_scopes(
        self,
        *,
        query: str,
        assistant_id: str | None,
        profile_id: str | None,
        include_global: bool,
        include_assistant: bool,
        layer: str | None,
        limit: int,
    ) -> list[dict[str, Any]]: ...

    def build_memory_context(
        self,
        *,
        query: str,
        assistant_id: str | None,
        profile_id: str | None,
        include_global: bool,
        include_assistant: bool,
    ) -> tuple[str | None, list[dict[str, Any]]]: ...
