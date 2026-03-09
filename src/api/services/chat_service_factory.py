"""Factories for chat-related application services."""

from __future__ import annotations

from typing import Any

from .chat_application_service import ChatApplicationDeps, ChatApplicationService
from .compare_flow_service import CompareFlowDeps, CompareFlowService
from .single_chat_flow_service import SingleChatFlowDeps, SingleChatFlowService


def build_single_chat_flow_service(
    *,
    storage: Any,
    chat_input_service: Any,
    post_turn_service: Any,
    single_turn_orchestrator: Any,
    prepare_context: Any,
    build_file_context_block: Any,
) -> SingleChatFlowService:
    """Build the single-chat application flow service."""
    return SingleChatFlowService(
        SingleChatFlowDeps(
            storage=storage,
            chat_input_service=chat_input_service,
            post_turn_service=post_turn_service,
            single_turn_orchestrator=single_turn_orchestrator,
            prepare_context=prepare_context,
            build_file_context_block=build_file_context_block,
        )
    )


def build_compare_flow_service(
    *,
    storage: Any,
    comparison_storage: Any,
    chat_input_service: Any,
    compare_models_orchestrator: Any,
    prepare_context: Any,
    build_file_context_block: Any,
) -> CompareFlowService:
    """Build the compare-model application flow service."""
    return CompareFlowService(
        CompareFlowDeps(
            storage=storage,
            comparison_storage=comparison_storage,
            chat_input_service=chat_input_service,
            compare_models_orchestrator=compare_models_orchestrator,
            prepare_context=prepare_context,
            build_file_context_block=build_file_context_block,
        )
    )


def build_chat_application_service(
    *,
    storage: Any,
    single_chat_flow_service: Any,
    compare_flow_service: Any,
    group_chat_service: Any,
) -> ChatApplicationService:
    """Build the application-facing chat entry service."""
    return ChatApplicationService(
        ChatApplicationDeps(
            storage=storage,
            single_chat_flow_service=single_chat_flow_service,
            compare_flow_service=compare_flow_service,
            group_chat_service=group_chat_service,
        )
    )
