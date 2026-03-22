"""Application-facing session mutation commands for chat."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Optional


def _default_compression_service_factory(storage: Any) -> Any:
    from src.infrastructure.compression.compression_service import CompressionService

    return CompressionService(storage)


@dataclass(frozen=True)
class ChatSessionCommandDeps:
    """Dependencies required by ChatSessionCommandService."""

    storage: Any
    compression_service_factory: Callable[[Any], Any] = _default_compression_service_factory


class ChatSessionCommandService:
    """Owns session-level chat mutations used by API routes."""

    def __init__(self, deps: ChatSessionCommandDeps):
        self._storage = deps.storage
        self._compression_service_factory = deps.compression_service_factory

    async def truncate_messages_after(
        self,
        *,
        session_id: str,
        keep_until_index: int,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.truncate_messages_after(
            session_id,
            keep_until_index,
            context_type=context_type,
            project_id=project_id,
        )

    async def delete_message(
        self,
        *,
        session_id: str,
        message_index: Optional[int] = None,
        message_id: Optional[str] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        if message_id:
            await self._storage.delete_message_by_id(
                session_id,
                message_id,
                context_type=context_type,
                project_id=project_id,
            )
            return

        if message_index is None:
            raise ValueError("Either message_id or message_index must be provided")

        await self._storage.delete_message(
            session_id,
            message_index,
            context_type=context_type,
            project_id=project_id,
        )

    async def update_message_content(
        self,
        *,
        session_id: str,
        message_id: str,
        content: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.update_message_content(
            session_id,
            message_id,
            content,
            context_type=context_type,
            project_id=project_id,
        )

    async def append_separator(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> str:
        return await self._storage.append_separator(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def clear_all_messages(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None:
        await self._storage.clear_all_messages(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def compress_context_stream(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        compression_service = self._compression_service_factory(self._storage)
        async for chunk in compression_service.compress_context_stream(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        ):
            yield chunk
