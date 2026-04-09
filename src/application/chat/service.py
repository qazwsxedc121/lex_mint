"""Application-facing chat entry service."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

from .orchestration_gateway import (
    ChatOrchestrationGateway,
    ChatOrchestrationGatewayDeps,
    CompareFlowServiceLike,
    GroupChatFlowServiceLike,
    SingleChatFlowServiceLike,
)
from .request_contexts import (
    CompareChatRequestContext,
    ContextCapabilitiesOptions,
    ConversationScope,
    EditorContext,
    GroupChatRequestContext,
    SingleChatRequestContext,
    StreamOptions,
    UserInputPayload,
)
from .service_contracts import SessionStorageLike, SourcePayload, StreamItem
from .session_command_service import ChatSessionCommandDeps, ChatSessionCommandService


@dataclass(frozen=True)
class ChatApplicationDeps:
    """Dependencies required by ChatApplicationService."""

    storage: SessionStorageLike
    single_chat_flow_service: SingleChatFlowServiceLike
    compare_flow_service: CompareFlowServiceLike
    group_chat_service: GroupChatFlowServiceLike
    session_command_service: ChatSessionCommandService | None = None
    orchestration_gateway: ChatOrchestrationGateway | None = None


class ChatApplicationService:
    """Owns application-level chat entrypoints used by API routes."""

    def __init__(self, deps: ChatApplicationDeps):
        self.storage = deps.storage
        self._single_chat_flow_service = deps.single_chat_flow_service
        self._session_commands = deps.session_command_service or ChatSessionCommandService(
            ChatSessionCommandDeps(storage=deps.storage)
        )
        self._orchestration_gateway = deps.orchestration_gateway or ChatOrchestrationGateway(
            ChatOrchestrationGatewayDeps(
                single_chat_flow_service=deps.single_chat_flow_service,
                compare_flow_service=deps.compare_flow_service,
                group_chat_service=deps.group_chat_service,
            )
        )

    @staticmethod
    def _build_scope(
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> ConversationScope:
        return ConversationScope(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )

    @staticmethod
    def _build_user_input(
        *,
        user_message: str,
        attachments: list[SourcePayload] | None = None,
        file_references: list[dict[str, str]] | None = None,
    ) -> UserInputPayload:
        return UserInputPayload(
            user_message=user_message,
            attachments=attachments,
            file_references=file_references,
        )

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        context_type: str = "chat",
        project_id: str | None = None,
        context_capabilities: list[str] | None = None,
        context_capability_args: dict[str, dict[str, object]] | None = None,
        file_references: list[dict[str, str]] | None = None,
        active_file_path: str | None = None,
        active_file_hash: str | None = None,
    ) -> tuple[str, list[SourcePayload]]:
        """Run the single-chat use case and collect the final response."""
        request = SingleChatRequestContext(
            scope=self._build_scope(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            ),
            user_input=self._build_user_input(
                user_message=user_message,
                file_references=file_references,
            ),
            context_capabilities=ContextCapabilitiesOptions(
                context_capabilities=list(context_capabilities or []),
                context_capability_args=dict(context_capability_args or {}),
            ),
            editor=EditorContext(
                active_file_path=active_file_path,
                active_file_hash=active_file_hash,
            ),
        )
        return await self._orchestration_gateway.run_single_message(request=request)

    async def process_chat_stream(
        self,
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        temporary_turn: bool = False,
        reasoning_effort: str | None = None,
        attachments: list[SourcePayload] | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
        context_capabilities: list[str] | None = None,
        context_capability_args: dict[str, dict[str, object]] | None = None,
        file_references: list[dict[str, str]] | None = None,
        active_file_path: str | None = None,
        active_file_hash: str | None = None,
    ) -> AsyncIterator[StreamItem]:
        """Stream chat with unified mode resolution through orchestration gateway."""
        session_data = await self.storage.get_session(
            session_id,
            context_type=context_type,
            project_id=project_id,
        )
        group_assistants = session_data.get("group_assistants")
        group_mode = session_data.get("group_mode", "round_robin")
        group_settings = session_data.get("group_settings")
        if isinstance(group_assistants, list) and len(group_assistants) >= 2:
            if temporary_turn:
                raise ValueError("temporary_turn is only supported for single-assistant chat")
            group_request = GroupChatRequestContext(
                scope=self._build_scope(
                    session_id=session_id,
                    context_type=context_type,
                    project_id=project_id,
                ),
                user_input=self._build_user_input(
                    user_message=user_message,
                    attachments=attachments,
                    file_references=file_references,
                ),
                group_assistants=group_assistants,
                group_mode=str(group_mode or "round_robin"),
                group_settings=group_settings if isinstance(group_settings, dict) else None,
                context_capabilities=ContextCapabilitiesOptions(
                    context_capabilities=list(context_capabilities or []),
                    context_capability_args=dict(context_capability_args or {}),
                ),
                stream=StreamOptions(
                    skip_user_append=skip_user_append,
                    temporary_turn=temporary_turn,
                    reasoning_effort=reasoning_effort,
                ),
            )
            async for event in self._orchestration_gateway.stream_group(
                request=group_request,
            ):
                yield event
            return

        single_request = SingleChatRequestContext(
            scope=self._build_scope(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            ),
            user_input=self._build_user_input(
                user_message=user_message,
                attachments=attachments,
                file_references=file_references,
            ),
            context_capabilities=ContextCapabilitiesOptions(
                context_capabilities=list(context_capabilities or []),
                context_capability_args=dict(context_capability_args or {}),
            ),
            stream=StreamOptions(
                skip_user_append=skip_user_append,
                temporary_turn=temporary_turn,
                reasoning_effort=reasoning_effort,
            ),
            editor=EditorContext(
                active_file_path=active_file_path,
                active_file_hash=active_file_hash,
            ),
        )
        async for event in self._orchestration_gateway.stream_single(
            request=single_request,
        ):
            yield event

    async def process_compare_stream(
        self,
        session_id: str,
        user_message: str,
        model_ids: list[str],
        reasoning_effort: str | None = None,
        attachments: list[SourcePayload] | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
        context_capabilities: list[str] | None = None,
        context_capability_args: dict[str, dict[str, object]] | None = None,
        file_references: list[dict[str, str]] | None = None,
    ) -> AsyncIterator[StreamItem]:
        """Stream the compare-model use case."""
        request = CompareChatRequestContext(
            scope=self._build_scope(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            ),
            user_input=self._build_user_input(
                user_message=user_message,
                attachments=attachments,
                file_references=file_references,
            ),
            model_ids=model_ids,
            context_capabilities=ContextCapabilitiesOptions(
                context_capabilities=list(context_capabilities or []),
                context_capability_args=dict(context_capability_args or {}),
            ),
            stream=StreamOptions(reasoning_effort=reasoning_effort),
        )
        async for event in self._orchestration_gateway.stream_compare(
            request=request,
        ):
            yield event

    async def truncate_messages_after(
        self,
        *,
        session_id: str,
        keep_until_index: int,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None:
        await self._session_commands.truncate_messages_after(
            session_id=session_id,
            keep_until_index=keep_until_index,
            context_type=context_type,
            project_id=project_id,
        )

    async def delete_message(
        self,
        *,
        session_id: str,
        message_index: int | None = None,
        message_id: str | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None:
        await self._session_commands.delete_message(
            session_id=session_id,
            message_index=message_index,
            message_id=message_id,
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
        project_id: str | None = None,
    ) -> None:
        await self._session_commands.update_message_content(
            session_id=session_id,
            message_id=message_id,
            content=content,
            context_type=context_type,
            project_id=project_id,
        )

    async def append_separator(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> str:
        return await self._session_commands.append_separator(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def clear_all_messages(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None:
        await self._session_commands.clear_all_messages(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def compress_context_stream(
        self,
        *,
        session_id: str,
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> AsyncIterator[StreamItem]:
        async for event in self._session_commands.compress_context_stream(
            session_id=session_id,
            context_type=context_type,
            project_id=project_id,
        ):
            yield event

    async def diagnose_chat_context(
        self,
        *,
        session_id: str,
        user_message: str,
        reasoning_effort: str | None = None,
        attachments: list[SourcePayload] | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
        context_capabilities: list[str] | None = None,
        context_capability_args: dict[str, dict[str, object]] | None = None,
        file_references: list[dict[str, str]] | None = None,
        active_file_path: str | None = None,
        active_file_hash: str | None = None,
    ) -> dict[str, object]:
        request = SingleChatRequestContext(
            scope=self._build_scope(
                session_id=session_id,
                context_type=context_type,
                project_id=project_id,
            ),
            user_input=self._build_user_input(
                user_message=user_message,
                attachments=attachments,
                file_references=file_references,
            ),
            context_capabilities=ContextCapabilitiesOptions(
                context_capabilities=list(context_capabilities or []),
                context_capability_args=dict(context_capability_args or {}),
            ),
            stream=StreamOptions(
                skip_user_append=True,
                temporary_turn=False,
                reasoning_effort=reasoning_effort,
            ),
            editor=EditorContext(
                active_file_path=active_file_path,
                active_file_hash=active_file_hash,
            ),
        )
        return await self._single_chat_flow_service.diagnose_request(request=request)
