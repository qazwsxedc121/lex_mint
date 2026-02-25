"""Post-turn persistence and background side effects for chat flows."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Awaitable, Callable, List, Optional

from src.providers.types import CostInfo, TokenUsage

from .service_contracts import (
    FollowupServiceLike,
    MessagePayload,
    SourcePayload,
    TaskScheduler,
    TitleServiceLike,
)

logger = logging.getLogger(__name__)


def _default_task_scheduler(task: Awaitable[Any]) -> asyncio.Task[Any]:
    """Bridge generic awaitables to asyncio task scheduling."""
    async def _run() -> Any:
        return await task

    return asyncio.create_task(_run())


class PostTurnService:
    """Handles assistant persistence and post-turn async workflows."""

    def __init__(
        self,
        *,
        storage: Any,
        memory_service: Any,
        task_scheduler: TaskScheduler = _default_task_scheduler,
        title_service_factory: Optional[Callable[..., TitleServiceLike]] = None,
        followup_service_factory: Optional[Callable[[], FollowupServiceLike]] = None,
    ):
        self.storage = storage
        self.memory_service = memory_service
        self.task_scheduler = task_scheduler
        self._title_service_factory = title_service_factory
        self._followup_service_factory = followup_service_factory

    async def save_partial_assistant_message(
        self,
        *,
        session_id: str,
        assistant_message: str,
        context_type: str,
        project_id: Optional[str],
    ) -> None:
        """Persist partial assistant content for cancelled streams."""
        if not assistant_message:
            return
        await self.storage.append_message(
            session_id,
            "assistant",
            assistant_message,
            context_type=context_type,
            project_id=project_id,
        )

    async def finalize_single_turn(
        self,
        *,
        session_id: str,
        assistant_message: str,
        usage_data: Optional[TokenUsage],
        cost_data: Optional[CostInfo],
        sources: Optional[List[SourcePayload]],
        raw_user_message: str,
        assistant_id: Optional[str],
        is_legacy_assistant: bool,
        assistant_memory_enabled: bool,
        user_message_id: Optional[str],
        context_type: str,
        project_id: Optional[str],
    ) -> str:
        """Persist final assistant message and schedule post-turn background tasks."""
        assistant_message_id = await self.storage.append_message(
            session_id,
            "assistant",
            assistant_message,
            usage=usage_data,
            cost=cost_data,
            sources=sources if sources else None,
            context_type=context_type,
            project_id=project_id,
        )

        self._schedule_memory_extraction(
            raw_user_message=raw_user_message,
            assistant_message=assistant_message,
            assistant_id=assistant_id,
            is_legacy_assistant=is_legacy_assistant,
            assistant_memory_enabled=assistant_memory_enabled,
            session_id=session_id,
            user_message_id=user_message_id,
        )
        await self.schedule_title_generation(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )
        return assistant_message_id

    async def schedule_title_generation(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: Optional[str],
    ) -> None:
        """Schedule title generation when trigger conditions are met."""
        try:
            title_service = self._build_title_service()
            updated_session = await self.storage.get_session(
                session_id,
                context_type=context_type,
                project_id=project_id,
            )
            is_temporary = updated_session.get("temporary", False)
            message_count = len(updated_session["state"]["messages"])
            current_title = updated_session["title"]
            if not is_temporary and title_service.should_generate_title(message_count, current_title):
                self.task_scheduler(title_service.generate_title_async(session_id))
        except Exception as e:
            logger.warning("Failed to schedule title generation: %s", e)

    async def generate_followup_questions(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: Optional[str],
    ) -> Optional[List[str]]:
        """Generate optional follow-up question suggestions from latest session state."""
        try:
            followup_service = self._build_followup_service()
            config = getattr(followup_service, "config", None)
            enabled = bool(getattr(config, "enabled", False))
            count = int(getattr(config, "count", 0) or 0)
            if not enabled or count <= 0:
                return None

            updated_session = await self.storage.get_session(
                session_id,
                context_type=context_type,
                project_id=project_id,
            )
            messages_for_followup: List[MessagePayload] = updated_session["state"]["messages"]
            questions = await followup_service.generate_followups_async(messages_for_followup)
            return questions or None
        except Exception as e:
            logger.warning("Failed to generate follow-up questions: %s", e)
            return None

    def _schedule_memory_extraction(
        self,
        *,
        raw_user_message: str,
        assistant_message: str,
        assistant_id: Optional[str],
        is_legacy_assistant: bool,
        assistant_memory_enabled: bool,
        session_id: str,
        user_message_id: Optional[str],
    ) -> None:
        if not raw_user_message or not assistant_message:
            return
        try:
            self.task_scheduler(
                self.memory_service.extract_and_persist_from_turn(
                    user_message=raw_user_message,
                    assistant_message=assistant_message,
                    assistant_id=assistant_id if not is_legacy_assistant else None,
                    source_session_id=session_id,
                    source_message_id=user_message_id,
                    assistant_memory_enabled=assistant_memory_enabled,
                )
            )
        except Exception as e:
            logger.warning("Failed to schedule memory extraction: %s", e)

    def _build_title_service(self) -> TitleServiceLike:
        if self._title_service_factory is not None:
            return self._title_service_factory(storage=self.storage)
        from .title_generation_service import TitleGenerationService

        return TitleGenerationService(storage=self.storage)

    def _build_followup_service(self) -> FollowupServiceLike:
        if self._followup_service_factory is not None:
            return self._followup_service_factory()
        from .followup_service import FollowupService

        return FollowupService()
