"""Factories for chat-related application services."""

from __future__ import annotations

from typing import Any

from .compare_flow_service import CompareFlowDeps, CompareFlowService
from .service import ChatApplicationDeps, ChatApplicationService
from .single_chat_flow_service import SingleChatFlowDeps, SingleChatFlowService


def build_single_chat_flow_service(
    *,
    storage: Any,
    chat_input_service: Any,
    post_turn_service: Any,
    call_llm_stream: Any,
    pricing_service: Any,
    file_service: Any,
    prepare_context: Any,
    build_file_context_block: Any,
    model_service_factory: Any = None,
    compression_config_service_factory: Any = None,
    compression_service_factory: Any = None,
    project_document_tool_service_factory: Any = None,
    project_knowledge_base_resolver_factory: Any = None,
    project_tool_policy_resolver_factory: Any = None,
    web_tool_service_factory: Any = None,
    tool_registry_getter: Any = None,
) -> SingleChatFlowService:
    """Build the single-chat application flow service."""
    return SingleChatFlowService(
        SingleChatFlowDeps(
            storage=storage,
            chat_input_service=chat_input_service,
            post_turn_service=post_turn_service,
            call_llm_stream=call_llm_stream,
            pricing_service=pricing_service,
            file_service=file_service,
            prepare_context=prepare_context,
            build_file_context_block=build_file_context_block,
            **(
                {"model_service_factory": model_service_factory}
                if model_service_factory is not None
                else {}
            ),
            **(
                {"compression_config_service_factory": compression_config_service_factory}
                if compression_config_service_factory is not None
                else {}
            ),
            **(
                {"compression_service_factory": compression_service_factory}
                if compression_service_factory is not None
                else {}
            ),
            **(
                {"project_document_tool_service_factory": project_document_tool_service_factory}
                if project_document_tool_service_factory is not None
                else {}
            ),
            **(
                {"project_knowledge_base_resolver_factory": project_knowledge_base_resolver_factory}
                if project_knowledge_base_resolver_factory is not None
                else {}
            ),
            **(
                {"project_tool_policy_resolver_factory": project_tool_policy_resolver_factory}
                if project_tool_policy_resolver_factory is not None
                else {}
            ),
            **(
                {"web_tool_service_factory": web_tool_service_factory}
                if web_tool_service_factory is not None
                else {}
            ),
            **(
                {"tool_registry_getter": tool_registry_getter}
                if tool_registry_getter is not None
                else {}
            ),
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
