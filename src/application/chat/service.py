"""Application-facing chat entry service."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, List, Optional

from .orchestration_gateway import ChatOrchestrationGateway, ChatOrchestrationGatewayDeps


@dataclass(frozen=True)
class ChatApplicationDeps:
    """Dependencies required by ChatApplicationService."""

    storage: Any
    single_chat_flow_service: Any
    compare_flow_service: Any
    group_chat_service: Any
    orchestration_gateway: Optional[ChatOrchestrationGateway] = None


class ChatApplicationService:
    """Owns application-level chat entrypoints used by API routes."""

    def __init__(self, deps: ChatApplicationDeps):
        self.storage = deps.storage
        self._orchestration_gateway = deps.orchestration_gateway or ChatOrchestrationGateway(
            ChatOrchestrationGatewayDeps(
                single_chat_flow_service=deps.single_chat_flow_service,
                compare_flow_service=deps.compare_flow_service,
                group_chat_service=deps.group_chat_service,
            )
        )

    async def process_message(
        self,
        session_id: str,
        user_message: str,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
        active_file_path: Optional[str] = None,
        active_file_hash: Optional[str] = None,
    ) -> tuple[str, List[Dict[str, Any]]]:
        """Run the single-chat use case and collect the final response."""
        return await self._orchestration_gateway.run_single_message(
            session_id=session_id,
            user_message=user_message,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
            active_file_path=active_file_path,
            active_file_hash=active_file_hash,
        )

    async def process_message_stream(
        self,
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
        active_file_path: Optional[str] = None,
        active_file_hash: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        """Stream the single-chat use case."""
        async for event in self._orchestration_gateway.stream_single(
            session_id=session_id,
            user_message=user_message,
            skip_user_append=skip_user_append,
            reasoning_effort=reasoning_effort,
            attachments=attachments,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
            active_file_path=active_file_path,
            active_file_hash=active_file_hash,
        ):
            yield event

    async def process_chat_stream(
        self,
        session_id: str,
        user_message: str,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
        active_file_path: Optional[str] = None,
        active_file_hash: Optional[str] = None,
    ) -> AsyncIterator[Any]:
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
            async for event in self._orchestration_gateway.stream_group(
                session_id=session_id,
                user_message=user_message,
                group_assistants=group_assistants,
                group_mode=group_mode,
                group_settings=group_settings if isinstance(group_settings, dict) else None,
                skip_user_append=skip_user_append,
                reasoning_effort=reasoning_effort,
                attachments=attachments,
                context_type=context_type,
                project_id=project_id,
                use_web_search=use_web_search,
                search_query=search_query,
                file_references=file_references,
            ):
                yield event
            return

        async for event in self._orchestration_gateway.stream_single(
            session_id=session_id,
            user_message=user_message,
            skip_user_append=skip_user_append,
            reasoning_effort=reasoning_effort,
            attachments=attachments,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
            active_file_path=active_file_path,
            active_file_hash=active_file_hash,
        ):
            yield event

    async def process_group_message_stream(
        self,
        session_id: str,
        user_message: str,
        group_assistants: List[str],
        group_mode: str = "round_robin",
        group_settings: Optional[Dict[str, Any]] = None,
        skip_user_append: bool = False,
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[Any]:
        """Stream the group-chat use case."""
        async for event in self._orchestration_gateway.stream_group(
            session_id=session_id,
            user_message=user_message,
            group_assistants=group_assistants,
            group_mode=group_mode,
            group_settings=group_settings,
            skip_user_append=skip_user_append,
            reasoning_effort=reasoning_effort,
            attachments=attachments,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
        ):
            yield event

    async def process_compare_stream(
        self,
        session_id: str,
        user_message: str,
        model_ids: List[str],
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[Dict[str, Any]]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[Any]:
        """Stream the compare-model use case."""
        async for event in self._orchestration_gateway.stream_compare(
            session_id=session_id,
            user_message=user_message,
            model_ids=model_ids,
            reasoning_effort=reasoning_effort,
            attachments=attachments,
            context_type=context_type,
            project_id=project_id,
            use_web_search=use_web_search,
            search_query=search_query,
            file_references=file_references,
        ):
            yield event
