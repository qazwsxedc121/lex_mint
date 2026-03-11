"""Bootstrap the production ChatApplicationService graph."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

from src.agents.llm_runtime import call_llm, call_llm_stream
from src.core.config import settings
from src.application.chat.chat_input_service import ChatInputService
from src.application.chat.file_reference_context_builder import FileReferenceContextBuilder
from src.application.chat.rag_context_builder_service import RagContextBuilderService
from src.application.chat.source_context_service import SourceContextService
from src.infrastructure.compression.compression_config_service import CompressionConfigService
from src.infrastructure.compression.compression_service import CompressionService
from src.infrastructure.config.file_reference_config_service import FileReferenceConfigService
from src.infrastructure.config.pricing_service import PricingService
from src.infrastructure.files.file_service import FileService
from src.infrastructure.memory.memory_service import MemoryService
from src.application.chat.orchestration import (
    CommitteePolicy,
    CompareModelsOrchestrator,
)
from src.application.chat.orchestration.log_utils import (
    build_messages_preview_for_log,
    truncate_log_text,
)
from src.infrastructure.projects.project_document_tool_service import ProjectDocumentToolService
from src.infrastructure.projects.project_knowledge_base_resolver import ProjectKnowledgeBaseResolver
from src.infrastructure.projects.project_tool_policy_resolver import ProjectToolPolicyResolver
from src.infrastructure.config.rag_config_service import RagConfigService
from src.infrastructure.config.model_config_service import ModelConfigService
from src.infrastructure.storage.comparison_storage import ComparisonStorage
from src.infrastructure.web.search_service import SearchService
from src.infrastructure.web.web_tool_service import WebToolService
from src.infrastructure.web.webpage_service import WebpageService
from src.tools.registry import get_tool_registry

from .factory import (
    build_chat_application_service,
    build_compare_flow_service,
    build_single_chat_flow_service,
)
from .context_assembly_service import ContextAssemblyService
from .group_chat_service import GroupChatDeps, GroupChatService
from .group_orchestration_support_service import GroupOrchestrationSupportService
from .group_runtime_support_service import GroupRuntimeSupportService
from .post_turn_service import PostTurnService
from .service import ChatApplicationService

logger = logging.getLogger(__name__)

_GROUP_TRACE_PREVIEW_CHARS = 1600


def _is_group_trace_enabled() -> bool:
    value = os.getenv("LEX_MINT_GROUP_TRACE", "").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _log_group_trace(trace_id: str, stage: str, payload: Dict[str, Any]) -> None:
    if not _is_group_trace_enabled():
        return
    try:
        serialized = json.dumps(payload, ensure_ascii=True, default=str)
    except Exception:
        serialized = str(payload)
    logger.info("[GroupTrace][%s][%s] %s", trace_id, stage, serialized)


def _resolve_compare_model_name(model_id: str) -> str:
    try:
        model_service = ModelConfigService()
        parts = model_id.split(":", 1)
        simple_id = parts[1] if len(parts) > 1 else model_id
        model_cfg, _ = model_service.get_model_and_provider_sync(model_id)
        return getattr(model_cfg, "name", simple_id) if model_cfg else simple_id
    except Exception:
        return model_id


def build_default_chat_application_service(
    *,
    storage: Any,
    file_service: Optional[FileService] = None,
) -> ChatApplicationService:
    """Build the production chat application service graph directly."""
    pricing_service = PricingService()
    resolved_file_service = file_service or FileService(
        settings.attachments_dir,
        settings.max_file_size_mb,
    )
    search_service = SearchService()
    webpage_service = WebpageService()
    memory_service = MemoryService()
    file_reference_config_service = FileReferenceConfigService()
    file_reference_context_builder = FileReferenceContextBuilder(file_reference_config_service)
    rag_config_service = RagConfigService()
    source_context_service = SourceContextService()
    comparison_storage = ComparisonStorage(storage)
    chat_input_service = ChatInputService(storage, resolved_file_service)
    rag_context_builder_service = RagContextBuilderService()

    post_turn_service = PostTurnService(
        storage=storage,
        memory_service=memory_service,
    )
    context_assembly_service = ContextAssemblyService(
        storage=storage,
        memory_service=memory_service,
        webpage_service=webpage_service,
        search_service=search_service,
        source_context_service=source_context_service,
        rag_config_service=rag_config_service,
        rag_context_builder=rag_context_builder_service.build_context_and_sources,
    )

    group_orchestration_support_service = GroupOrchestrationSupportService(
        storage=storage,
        pricing_service=pricing_service,
        memory_service=memory_service,
        file_service=resolved_file_service,
        build_rag_context_and_sources=rag_context_builder_service.build_context_and_sources,
        truncate_log_text=truncate_log_text,
        build_messages_preview_for_log=build_messages_preview_for_log,
        log_group_trace=_log_group_trace,
        group_trace_preview_chars=_GROUP_TRACE_PREVIEW_CHARS,
    )
    committee_turn_executor = group_orchestration_support_service.create_committee_turn_executor()
    group_runtime_support_service = GroupRuntimeSupportService()

    compare_models_orchestrator = CompareModelsOrchestrator(
        call_llm_stream=call_llm_stream,
        pricing_service=pricing_service,
        file_service=resolved_file_service,
        resolve_model_name=_resolve_compare_model_name,
    )
    group_chat_service = GroupChatService(
        GroupChatDeps(
            chat_input_service=chat_input_service,
            post_turn_service=post_turn_service,
            search_service=search_service,
            build_file_context_block=file_reference_context_builder.build_context_block,
            build_group_runtime_assistant=group_runtime_support_service.build_group_runtime_assistant,
            resolve_group_settings=lambda **kwargs: group_runtime_support_service.resolve_group_settings(
                **kwargs,
                resolve_round_policy=CommitteePolicy.resolve_committee_round_policy,
            ),
            create_committee_orchestrator=lambda: group_orchestration_support_service.create_committee_orchestrator(
                llm_call=call_llm,
                stream_group_assistant_turn=committee_turn_executor.stream_group_assistant_turn,
                get_message_content_by_id=committee_turn_executor.get_message_content_by_id,
            ),
            create_round_robin_orchestrator=lambda: group_orchestration_support_service.create_round_robin_orchestrator(
                stream_group_assistant_turn=committee_turn_executor.stream_group_assistant_turn,
            ),
            is_group_trace_enabled=_is_group_trace_enabled,
            log_group_trace=_log_group_trace,
            truncate_log_text=truncate_log_text,
            group_trace_preview_chars=_GROUP_TRACE_PREVIEW_CHARS,
        )
    )

    single_chat_flow_service = build_single_chat_flow_service(
        storage=storage,
        chat_input_service=chat_input_service,
        post_turn_service=post_turn_service,
        call_llm_stream=call_llm_stream,
        pricing_service=pricing_service,
        file_service=resolved_file_service,
        prepare_context=context_assembly_service.prepare_context,
        build_file_context_block=file_reference_context_builder.build_context_block,
        model_service_factory=ModelConfigService,
        compression_config_service_factory=CompressionConfigService,
        compression_service_factory=CompressionService,
        project_document_tool_service_factory=ProjectDocumentToolService,
        project_knowledge_base_resolver_factory=ProjectKnowledgeBaseResolver,
        project_tool_policy_resolver_factory=ProjectToolPolicyResolver,
        web_tool_service_factory=WebToolService,
        tool_registry_getter=get_tool_registry,
    )
    compare_flow_service = build_compare_flow_service(
        storage=storage,
        comparison_storage=comparison_storage,
        chat_input_service=chat_input_service,
        compare_models_orchestrator=compare_models_orchestrator,
        prepare_context=context_assembly_service.prepare_context,
        build_file_context_block=file_reference_context_builder.build_context_block,
    )
    return build_chat_application_service(
        storage=storage,
        single_chat_flow_service=single_chat_flow_service,
        compare_flow_service=compare_flow_service,
        group_chat_service=group_chat_service,
    )
