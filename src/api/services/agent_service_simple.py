"""Agent service for processing chat messages - Simplified version (without LangGraph)"""

from dataclasses import dataclass
from typing import Dict, AsyncIterator, Optional, Any, List, Tuple, cast
import logging
import uuid
import re
import os
import json
from types import SimpleNamespace

from src.agents.llm_runtime import call_llm, call_llm_stream
from .agent_service_bootstrap import bootstrap_agent_service
from .chat_input_service import ChatInputService
from .chat_application_service import ChatApplicationService
from .chat_service_factory import (
    build_chat_application_service,
    build_compare_flow_service,
    build_single_chat_flow_service,
)
from .compare_flow_service import CompareFlowService
from .context_assembly_service import ContextAssemblyService
from .conversation_storage import ConversationStorage
from .group_participants import parse_group_participant
from .group_chat_service import GroupChatDeps, GroupChatService
from .orchestration import (
    CompareModelsOrchestrator,
    CommitteeOrchestrator,
    CommitteePolicy,
    GroupSettingsResolver,
    RoundRobinOrchestrator,
    SingleTurnOrchestrator,
    CommitteeRuntimeState,
    CommitteeTurnExecutor,
)
from .post_turn_service import PostTurnService
from .service_contracts import AssistantLike
from .single_chat_flow_service import SingleChatFlowDeps, SingleChatFlowService
from .orchestration.log_utils import build_messages_preview_for_log, truncate_log_text

logger = logging.getLogger(__name__)


@dataclass
class _RuntimeAssistant:
    id: str
    name: str
    model_id: str
    icon: str
    description: str
    system_prompt: Optional[str]
    temperature: Optional[float]
    max_tokens: Optional[int]
    top_p: Optional[float]
    top_k: Optional[int]
    frequency_penalty: Optional[float]
    presence_penalty: Optional[float]
    max_rounds: Optional[int]
    memory_enabled: bool
    knowledge_base_ids: Optional[List[str]]
    enabled: bool


class AgentService:
    """Service layer for agent interactions with conversation storage.

    Coordinates the flow:
    1. Append user message to storage
    2. Load current conversation state
    3. Call LLM to generate response (direct call, without LangGraph)
    4. Append assistant response to storage
    5. Return response to caller
    """

    def __init__(self, storage: ConversationStorage):
        """Initialize agent service.

        Args:
            storage: ConversationStorage instance for persistence
        """
        bootstrap_agent_service(self, storage)
        logger.info("AgentService initialized (simplified version)")

    _GROUP_TRACE_PREVIEW_CHARS = 1600

    # Runtime-initialized service dependencies (set by bootstrap).
    storage: ConversationStorage
    pricing_service: Any
    file_service: Any
    search_service: Any
    webpage_service: Any
    memory_service: Any
    file_reference_config_service: Any
    file_reference_context_builder: Any
    rag_config_service: Any
    source_context_service: Any
    comparison_storage: Any
    _committee_policy: CommitteePolicy

    @staticmethod
    def _truncate_log_text(text: Optional[str], max_chars: int = 1600) -> str:
        """Trim text for debug logs while preserving head and tail context."""
        return truncate_log_text(text, max_chars)

    @staticmethod
    def _build_messages_preview_for_log(
        messages: List[Dict[str, Any]],
        *,
        max_messages: int = 10,
        max_chars: int = 220,
    ) -> List[Dict[str, Any]]:
        """Build a compact recent message view for group context debugging."""
        return build_messages_preview_for_log(
            messages,
            max_messages=max_messages,
            max_chars=max_chars,
        )

    @staticmethod
    def _is_group_trace_enabled() -> bool:
        """Enable verbose group trace logging via env variable."""
        value = os.getenv("LEX_MINT_GROUP_TRACE", "").strip().lower()
        return value in {"1", "true", "yes", "on"}

    def _log_group_trace(self, trace_id: str, stage: str, payload: Dict[str, Any]) -> None:
        """Emit structured group-trace logs when tracing is enabled."""
        if not self._is_group_trace_enabled():
            return
        try:
            serialized = json.dumps(payload, ensure_ascii=True, default=str)
        except Exception:
            serialized = str(payload)
        logger.info("[GroupTrace][%s][%s] %s", trace_id, stage, serialized)

    def _create_committee_turn_executor(self) -> CommitteeTurnExecutor:
        """Build turn executor with service dependencies and prompt/context callbacks."""
        return CommitteeTurnExecutor(
            storage=self.storage,
            pricing_service=self.pricing_service,
            memory_service=self.memory_service,
            file_service=self.file_service,
            assistant_params_from_config=self._assistant_params_from_config,
            build_group_history_hint=self._build_group_history_hint,
            build_group_identity_prompt=self._build_group_identity_prompt,
            build_group_instruction_prompt=self._build_group_instruction_prompt,
            build_rag_context_and_sources=self._build_rag_context_and_sources,
            truncate_log_text=self._truncate_log_text,
            build_messages_preview_for_log=self._build_messages_preview_for_log,
            log_group_trace=self._log_group_trace,
            group_trace_preview_chars=self._GROUP_TRACE_PREVIEW_CHARS,
        )

    def _get_committee_turn_executor(self) -> CommitteeTurnExecutor:
        """Lazily initialize turn executor for tests that construct AgentService via __new__."""
        executor = getattr(self, "_committee_turn_executor", None)
        if executor is None:
            executor = self._create_committee_turn_executor()
            self._committee_turn_executor = executor
        return executor

    def _create_committee_orchestrator(self) -> CommitteeOrchestrator:
        """Build committee orchestrator from current service callbacks."""
        return CommitteeOrchestrator(
            llm_call=call_llm,
            assistant_params_from_config=self._assistant_params_from_config,
            stream_group_assistant_turn=self._stream_group_assistant_turn,
            get_message_content_by_id=self._get_message_content_by_id,
            build_structured_turn_summary=self._build_structured_turn_summary,
            build_committee_turn_packet=self._build_committee_turn_packet,
            detect_group_role_drift=self._detect_group_role_drift,
            build_role_retry_instruction=self._build_role_retry_instruction,
            truncate_log_text=self._truncate_log_text,
            log_group_trace=self._log_group_trace,
            group_trace_preview_chars=self._GROUP_TRACE_PREVIEW_CHARS,
        )

    def _create_round_robin_orchestrator(self) -> RoundRobinOrchestrator:
        """Build round-robin orchestrator from current service callbacks."""
        return RoundRobinOrchestrator(
            stream_group_assistant_turn=self._stream_group_assistant_turn,
        )

    def _create_single_turn_orchestrator(self) -> SingleTurnOrchestrator:
        """Build single-turn orchestrator for standard chat streaming."""
        return SingleTurnOrchestrator(
            call_llm_stream=call_llm_stream,
            pricing_service=self.pricing_service,
            file_service=self.file_service,
        )

    def _create_compare_models_orchestrator(self) -> CompareModelsOrchestrator:
        """Build compare-models orchestrator for multi-model streaming."""
        return CompareModelsOrchestrator(
            call_llm_stream=call_llm_stream,
            pricing_service=self.pricing_service,
            file_service=self.file_service,
            resolve_model_name=self._resolve_compare_model_name,
        )

    def _get_single_turn_orchestrator(self) -> SingleTurnOrchestrator:
        """Lazily initialize single-turn orchestrator for tests using __new__."""
        orchestrator = getattr(self, "_single_turn_orchestrator", None)
        if orchestrator is None:
            orchestrator = self._create_single_turn_orchestrator()
            self._single_turn_orchestrator = orchestrator
        return orchestrator

    def _get_compare_models_orchestrator(self) -> CompareModelsOrchestrator:
        """Lazily initialize compare-models orchestrator for tests using __new__."""
        orchestrator = getattr(self, "_compare_models_orchestrator", None)
        if orchestrator is None:
            orchestrator = self._create_compare_models_orchestrator()
            self._compare_models_orchestrator = orchestrator
        return orchestrator

    def _create_group_chat_service(self) -> GroupChatService:
        """Build group chat service facade for group-mode runtime flow."""
        chat_input_service = getattr(self, "chat_input_service", None)
        if chat_input_service is None and hasattr(self, "storage") and hasattr(self, "file_service"):
            chat_input_service = self._get_chat_input_service()

        post_turn_service = getattr(self, "post_turn_service", None)
        if post_turn_service is None and hasattr(self, "storage") and hasattr(self, "memory_service"):
            post_turn_service = self._get_post_turn_service()

        if chat_input_service is None:
            async def _missing_prepare_user_input(**_kwargs):
                raise RuntimeError("chat_input_service is not initialized")

            chat_input_service = SimpleNamespace(prepare_user_input=_missing_prepare_user_input)

        if post_turn_service is None:
            async def _noop_schedule_title_generation(**_kwargs):
                return None

            post_turn_service = SimpleNamespace(schedule_title_generation=_noop_schedule_title_generation)

        search_service = getattr(self, "search_service", None)
        if search_service is None:
            async def _empty_search(_query):
                return []

            search_service = SimpleNamespace(
                search=_empty_search,
                build_search_context=lambda _query, _sources: None,
            )

        return GroupChatService(
            GroupChatDeps(
                chat_input_service=cast(ChatInputService, chat_input_service),
                post_turn_service=cast(PostTurnService, post_turn_service),
                search_service=cast(Any, search_service),
                build_file_context_block=self.file_reference_context_builder.build_context_block,
                build_group_runtime_assistant=self._build_group_runtime_assistant,
                resolve_group_settings=self._resolve_group_settings,
                create_committee_orchestrator=self._create_committee_orchestrator,
                create_round_robin_orchestrator=self._create_round_robin_orchestrator,
                is_group_trace_enabled=self._is_group_trace_enabled,
                log_group_trace=self._log_group_trace,
                truncate_log_text=self._truncate_log_text,
                group_trace_preview_chars=self._GROUP_TRACE_PREVIEW_CHARS,
            )
        )

    def _get_group_chat_service(self) -> GroupChatService:
        """Lazily initialize group chat service for tests using __new__."""
        service = getattr(self, "_group_chat_service", None)
        if service is None:
            service = self._create_group_chat_service()
            self._group_chat_service = service
        return service

    def _create_chat_application_service(self) -> ChatApplicationService:
        """Build application-facing chat entry service for API routes."""
        return build_chat_application_service(
            storage=self.storage,
            single_chat_flow_service=self._get_single_chat_flow_service(),
            compare_flow_service=self._get_compare_flow_service(),
            group_chat_service=self._get_group_chat_service(),
        )

    def _get_chat_application_service(self) -> ChatApplicationService:
        """Lazily initialize chat application service for tests using __new__."""
        service = getattr(self, "_chat_application_service", None)
        if service is None:
            service = self._create_chat_application_service()
            self._chat_application_service = service
        return service

    def _create_single_chat_flow_service(self) -> SingleChatFlowService:
        """Build single-chat flow service facade for standard chat stream."""
        return build_single_chat_flow_service(
            storage=self.storage,
            chat_input_service=self._get_chat_input_service(),
            post_turn_service=self._get_post_turn_service(),
            single_turn_orchestrator=self._get_single_turn_orchestrator(),
            prepare_context=self._get_context_assembly_service().prepare_context,
            build_file_context_block=self.file_reference_context_builder.build_context_block,
        )

    def _get_single_chat_flow_service(self) -> SingleChatFlowService:
        """Lazily initialize single-chat flow service for tests using __new__."""
        service = getattr(self, "_single_chat_flow_service", None)
        if service is None:
            service = self._create_single_chat_flow_service()
            self._single_chat_flow_service = service
        return service

    def _create_compare_flow_service(self) -> CompareFlowService:
        """Build compare flow service facade for compare-model stream."""
        return build_compare_flow_service(
            storage=self.storage,
            comparison_storage=self.comparison_storage,
            chat_input_service=self._get_chat_input_service(),
            compare_models_orchestrator=self._get_compare_models_orchestrator(),
            prepare_context=self._get_context_assembly_service().prepare_context,
            build_file_context_block=self.file_reference_context_builder.build_context_block,
        )

    def _get_compare_flow_service(self) -> CompareFlowService:
        """Lazily initialize compare flow service for tests using __new__."""
        service = getattr(self, "_compare_flow_service", None)
        if service is None:
            service = self._create_compare_flow_service()
            self._compare_flow_service = service
        return service

    def _create_chat_input_service(self) -> ChatInputService:
        """Build shared chat-input service for attachments and user append."""
        return ChatInputService(self.storage, self.file_service)

    def _get_chat_input_service(self) -> ChatInputService:
        """Lazily initialize chat-input service for tests using __new__."""
        service = getattr(self, "chat_input_service", None)
        if service is None:
            service = self._create_chat_input_service()
            self.chat_input_service = service
        return service

    def _create_post_turn_service(self) -> PostTurnService:
        """Build post-turn service for persistence and background tasks."""
        return PostTurnService(
            storage=self.storage,
            memory_service=self.memory_service,
        )

    def _get_post_turn_service(self) -> PostTurnService:
        """Lazily initialize post-turn service for tests using __new__."""
        service = getattr(self, "post_turn_service", None)
        if service is None:
            service = self._create_post_turn_service()
            self.post_turn_service = service
        return service

    def _create_context_assembly_service(self) -> ContextAssemblyService:
        """Build context assembly service for single/compare flows."""
        return ContextAssemblyService(
            storage=self.storage,
            memory_service=self.memory_service,
            webpage_service=self.webpage_service,
            search_service=self.search_service,
            source_context_service=self.source_context_service,
            rag_config_service=self.rag_config_service,
            rag_context_builder=self._build_rag_context_and_sources,
        )

    def _get_context_assembly_service(self) -> ContextAssemblyService:
        """Lazily initialize context assembly service for tests using __new__."""
        service = getattr(self, "context_assembly_service", None)
        if service is None:
            service = self._create_context_assembly_service()
            self.context_assembly_service = service
        return service

    async def _build_rag_context_and_sources(
        self,
        *,
        raw_user_message: str,
        assistant_id: Optional[str],
        assistant_obj: Optional[AssistantLike] = None,
        runtime_model_id: Optional[str] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> Tuple[Optional[str], List[Dict[str, Any]]]:
        """Build RAG context and source metadata for the current assistant/project."""
        rag_sources: List[Dict[str, Any]] = []

        try:
            assistant_for_rag = assistant_obj
            if assistant_for_rag is None and assistant_id and not assistant_id.startswith("__legacy_model_"):
                from .assistant_config_service import AssistantConfigService

                assistant_service = AssistantConfigService()
                assistant_for_rag = await assistant_service.get_assistant(assistant_id)

            from .project_knowledge_base_resolver import ProjectKnowledgeBaseResolver

            kb_ids = await ProjectKnowledgeBaseResolver().resolve_effective_kb_ids(
                assistant_id=assistant_id,
                assistant_obj=assistant_for_rag,
                context_type=context_type,
                project_id=project_id,
            )
            if not kb_ids:
                return None, rag_sources

            from .rag_service import RagService

            rag_service = RagService()
            rag_results, rag_diagnostics = await rag_service.retrieve_with_diagnostics(
                raw_user_message,
                kb_ids,
                runtime_model_id=runtime_model_id,
            )
            rag_sources.append(rag_service.build_rag_diagnostics_source(rag_diagnostics))
            if not rag_results:
                return None, rag_sources

            rag_context = rag_service.build_rag_context(raw_user_message, rag_results)
            rag_sources.extend([r.to_dict() for r in rag_results])
            return rag_context, rag_sources
        except Exception as e:
            logger.warning(f"RAG retrieval failed: {e}")
            return None, rag_sources

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
        """Compatibility wrapper around ChatApplicationService.process_message.

        Kept only for compatibility while API routes migrate to the dedicated
        chat application entry service.
        """
        return await self._get_chat_application_service().process_message(
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
        """Compatibility wrapper around ChatApplicationService.process_message_stream.

        Kept only for compatibility while API routes migrate to the dedicated
        chat application entry service.
        """
        async for event in self._get_chat_application_service().process_message_stream(
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

    @staticmethod
    def _build_group_identity_prompt(
        current_assistant_id: str,
        current_assistant_name: str,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
    ) -> str:
        """Build explicit role and participant instructions for group chat rounds."""
        participants: List[str] = []
        for index, participant_id in enumerate(group_assistants, start=1):
            participant_name = assistant_name_map.get(participant_id, participant_id)
            marker = " (you)" if participant_id == current_assistant_id else ""
            participants.append(f"{index}. {participant_name} [{participant_id}]{marker}")

        participants_block = "\n".join(participants) if participants else "unknown"
        return (
            "Group chat identity:\n"
            f"You are {current_assistant_name} [{current_assistant_id}] in a multi-assistant discussion.\n"
            "Participants and speaking order:\n"
            f"{participants_block}\n\n"
            "Role rules:\n"
            "- Do not claim other assistants' statements as your own.\n"
            "- When responding, continue from your own perspective and style.\n"
            "- Never output internal role labels or metadata markers to the user."
        )

    @staticmethod
    def _build_group_history_hint(
        messages: List[Dict[str, Any]],
        current_assistant_id: str,
        assistant_name_map: Dict[str, str],
        max_turns: int = 12,
    ) -> str:
        """Build a compact speaker-labeled assistant turn summary for disambiguation."""
        turn_lines: List[str] = []
        for message in messages:
            if message.get("role") != "assistant":
                continue

            speaker_id = message.get("assistant_id")
            if not speaker_id:
                continue

            speaker_name = assistant_name_map.get(speaker_id, speaker_id)
            ownership = "self" if speaker_id == current_assistant_id else "other"
            content = (message.get("content") or "").replace("\n", " ").strip()
            if len(content) > 120:
                content = f"{content[:120]}..."
            turn_lines.append(f"- {speaker_name} ({ownership}): {content}")

        if not turn_lines:
            return ""

        recent_lines = turn_lines[-max_turns:]
        return (
            "Assistant turn history:\n"
            "Use this speaker mapping to distinguish your own prior replies from other assistants:\n"
            f"{chr(10).join(recent_lines)}\n"
            "These labels are internal guidance only; do not output them verbatim."
        )

    @staticmethod
    def _assistant_params_from_config(assistant_obj: AssistantLike) -> Dict[str, Any]:
        """Extract generation params from assistant config object."""
        return {
            "temperature": assistant_obj.temperature,
            "max_tokens": assistant_obj.max_tokens,
            "top_p": assistant_obj.top_p,
            "top_k": assistant_obj.top_k,
            "frequency_penalty": assistant_obj.frequency_penalty,
            "presence_penalty": assistant_obj.presence_penalty,
        }

    @staticmethod
    def _resolve_compare_model_name(model_id: str) -> str:
        """Resolve best-effort display name for compare stream model events."""
        try:
            from .model_config_service import ModelConfigService

            model_service = ModelConfigService()
            parts = model_id.split(":", 1)
            simple_id = parts[1] if len(parts) > 1 else model_id
            model_cfg, _ = model_service.get_model_and_provider_sync(model_id)
            return getattr(model_cfg, "name", simple_id) if model_cfg else simple_id
        except Exception:
            return model_id

    @staticmethod
    def _extract_model_template_params(model_obj: Any) -> Dict[str, Any]:
        """Extract per-model chat template params for runtime participant creation."""
        template = getattr(model_obj, "chat_template", None)
        if not template:
            return {}
        if hasattr(template, "model_dump"):
            raw_template = template.model_dump(exclude_none=True)
        elif isinstance(template, dict):
            raw_template = {k: v for k, v in template.items() if v is not None}
        else:
            return {}
        return {
            "temperature": raw_template.get("temperature"),
            "max_tokens": raw_template.get("max_tokens"),
            "top_p": raw_template.get("top_p"),
            "top_k": raw_template.get("top_k"),
            "frequency_penalty": raw_template.get("frequency_penalty"),
            "presence_penalty": raw_template.get("presence_penalty"),
        }

    async def _build_group_runtime_assistant(
        self,
        participant_token: str,
    ) -> Optional[Tuple[str, AssistantLike, str]]:
        """Resolve assistant/model participant token to runtime assistant object."""
        try:
            participant = parse_group_participant(participant_token)
        except ValueError:
            return None

        if participant.kind == "assistant":
            from .assistant_config_service import AssistantConfigService

            assistant_service = AssistantConfigService()
            try:
                assistant_obj = await assistant_service.require_enabled_assistant(participant.value)
            except ValueError:
                return None
            return participant.token, assistant_obj, assistant_obj.name

        from .model_config_service import ModelConfigService

        model_service = ModelConfigService()
        try:
            model_obj, _provider_obj = await model_service.require_enabled_model(participant.value)
        except ValueError:
            return None

        composite_model_id = f"{model_obj.provider_id}:{model_obj.id}"
        template_params = self._extract_model_template_params(model_obj)
        runtime_assistant = _RuntimeAssistant(
            id=participant.token,
            name=model_obj.name or model_obj.id,
            icon="CpuChip",
            description=f"Direct model participant: {composite_model_id}",
            model_id=composite_model_id,
            system_prompt=None,
            temperature=template_params.get("temperature", 0.7),
            max_tokens=template_params.get("max_tokens"),
            top_p=template_params.get("top_p"),
            top_k=template_params.get("top_k"),
            frequency_penalty=template_params.get("frequency_penalty"),
            presence_penalty=template_params.get("presence_penalty"),
            max_rounds=None,
            memory_enabled=False,
            knowledge_base_ids=[],
            enabled=True,
        )
        return participant.token, runtime_assistant, runtime_assistant.name

    @staticmethod
    def _resolve_group_round_limit(raw_limit: Optional[int], *, fallback: int = 3, hard_cap: int = 6) -> int:
        """Normalize assistant max_rounds for committee orchestration loops."""
        return CommitteePolicy.resolve_group_round_limit(
            raw_limit,
            fallback=fallback,
            hard_cap=hard_cap,
        )

    @staticmethod
    def _resolve_committee_round_policy(
        raw_limit: Optional[int],
        *,
        participant_count: int,
    ) -> Dict[str, int]:
        """Derive round/depth policy for committee mode to avoid premature convergence."""
        return CommitteePolicy.resolve_committee_round_policy(
            raw_limit,
            participant_count=participant_count,
        )

    def _resolve_group_settings(
        self,
        *,
        group_mode: Optional[str],
        group_assistants: List[str],
        group_settings: Optional[Dict[str, Any]],
        assistant_config_map: Dict[str, AssistantLike],
    ):
        """Resolve runtime group settings with backward-compatible defaults."""
        return GroupSettingsResolver.resolve(
            group_mode=group_mode,
            group_assistants=group_assistants,
            group_settings=group_settings,
            assistant_config_map=assistant_config_map,
            resolve_round_policy=self._resolve_committee_round_policy,
        )

    @staticmethod
    def _build_group_instruction_prompt(
        instruction: Optional[str],
        structured_packet: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Wrap internal directives; optionally attach structured committee turn packet."""
        if not instruction and not structured_packet:
            return None

        sections: List[str] = []
        if instruction:
            cleaned = instruction.strip()
            if cleaned:
                sections.append(
                    "Committee instruction:\n"
                    f"{cleaned}\n\n"
                    "Follow this instruction while keeping role consistency and factual grounding."
                )
        if structured_packet:
            try:
                payload = json.dumps(structured_packet, ensure_ascii=True, default=str)
            except Exception:
                payload = str(structured_packet)
            sections.append(
                "Committee turn packet (JSON):\n"
                f"```json\n{payload}\n```\n\n"
                "Use this packet for planning and role consistency. "
                "Do not output JSON unless the user explicitly asks for it."
            )

        if not sections:
            return None
        return "\n\n".join(sections)

    @staticmethod
    def _extract_bullet_items(text: str, *, limit: int = 5) -> List[str]:
        """Extract concise bullet-like items from free-form text."""
        return CommitteeTurnExecutor.extract_bullet_items(text, limit=limit)

    @staticmethod
    def _extract_keyword_sentences(
        text: str,
        *,
        keywords: List[str],
        limit: int = 4,
    ) -> List[str]:
        """Extract short sentences containing any keyword."""
        return CommitteeTurnExecutor.extract_keyword_sentences(
            text,
            keywords=keywords,
            limit=limit,
        )

    def _build_structured_turn_summary(self, content: str) -> Dict[str, Any]:
        """Build lightweight structured summary from assistant natural-language output."""
        return CommitteeTurnExecutor.build_structured_turn_summary(content)

    def _build_committee_turn_packet(
        self,
        *,
        state: CommitteeRuntimeState,
        target_assistant_id: str,
        assistant_name_map: Dict[str, str],
        instruction: Optional[str],
    ) -> Dict[str, Any]:
        """Build structured per-turn packet used as internal context for committee members."""
        return CommitteeTurnExecutor.build_committee_turn_packet(
            state=state,
            target_assistant_id=target_assistant_id,
            assistant_name_map=assistant_name_map,
            instruction=instruction,
        )

    @staticmethod
    def _normalize_identity_token(value: str) -> str:
        """Normalize identity labels for lightweight role-drift checks."""
        return CommitteeTurnExecutor.normalize_identity_token(value)

    def _detect_group_role_drift(
        self,
        *,
        content: str,
        expected_assistant_id: str,
        expected_assistant_name: str,
        participant_name_map: Dict[str, str],
    ) -> Optional[str]:
        """Detect obvious cases where a speaker claims another participant identity."""
        return CommitteeTurnExecutor.detect_group_role_drift(
            content=content,
            expected_assistant_id=expected_assistant_id,
            expected_assistant_name=expected_assistant_name,
            participant_name_map=participant_name_map,
        )

    @staticmethod
    def _build_role_retry_instruction(
        *,
        base_instruction: Optional[str],
        expected_assistant_name: str,
    ) -> str:
        return CommitteeTurnExecutor.build_role_retry_instruction(
            base_instruction=base_instruction,
            expected_assistant_name=expected_assistant_name,
        )

    async def _get_message_content_by_id(
        self,
        *,
        session_id: str,
        message_id: Optional[str],
        context_type: str,
        project_id: Optional[str],
    ) -> str:
        """Read one message content from session state by message_id."""
        return await self._get_committee_turn_executor().get_message_content_by_id(
            session_id=session_id,
            message_id=message_id,
            context_type=context_type,
            project_id=project_id,
        )

    async def _stream_group_assistant_turn(
        self,
        *,
        session_id: str,
        assistant_id: str,
        assistant_obj: AssistantLike,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
        raw_user_message: str,
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        instruction: Optional[str] = None,
        committee_turn_packet: Optional[Dict[str, Any]] = None,
        trace_id: Optional[str] = None,
        trace_round: Optional[int] = None,
        trace_mode: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Execute one assistant turn in group mode and stream structured events."""
        async for event in self._get_committee_turn_executor().stream_group_assistant_turn(
            session_id=session_id,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
            raw_user_message=raw_user_message,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            instruction=instruction,
            committee_turn_packet=committee_turn_packet,
            trace_id=trace_id,
            trace_round=trace_round,
            trace_mode=trace_mode,
        ):
            yield event

    async def _process_committee_group_message_stream(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        group_assistants: List[str],
        assistant_name_map: Dict[str, str],
        assistant_config_map: Dict[str, AssistantLike],
        group_settings: Optional[Dict[str, Any]],
        reasoning_effort: Optional[str],
        context_type: str,
        project_id: Optional[str],
        search_context: Optional[str],
        search_sources: List[Dict[str, Any]],
        trace_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Committee mode orchestration delegate."""
        async for event in self._get_group_chat_service().process_committee_group_message_stream(
            session_id=session_id,
            raw_user_message=raw_user_message,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
            assistant_config_map=assistant_config_map,
            group_settings=group_settings,
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
            search_context=search_context,
            search_sources=search_sources,
            trace_id=trace_id,
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
        file_references: Optional[List[Dict[str, str]]] = None
    ) -> AsyncIterator[Any]:
        """Compatibility wrapper around ChatApplicationService.process_group_message_stream."""
        async for event in self._get_chat_application_service().process_group_message_stream(
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
        """Compatibility wrapper around ChatApplicationService.process_compare_stream."""
        async for event in self._get_chat_application_service().process_compare_stream(
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
