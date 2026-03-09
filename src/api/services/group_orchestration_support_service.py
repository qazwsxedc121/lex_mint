"""Support helpers for group-turn execution and committee orchestration."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from .orchestration import (
    CommitteeOrchestrator,
    CommitteeRuntimeState,
    CommitteeTurnExecutor,
    RoundRobinOrchestrator,
)
from .service_contracts import AssistantLike


class GroupOrchestrationSupportService:
    """Owns group prompt helpers plus orchestration factory wiring."""

    def __init__(
        self,
        *,
        storage: Any,
        pricing_service: Any,
        memory_service: Any,
        file_service: Any,
        build_rag_context_and_sources: Any,
        truncate_log_text: Any,
        build_messages_preview_for_log: Any,
        log_group_trace: Any,
        group_trace_preview_chars: int = 1600,
    ):
        self.storage = storage
        self.pricing_service = pricing_service
        self.memory_service = memory_service
        self.file_service = file_service
        self.build_rag_context_and_sources = build_rag_context_and_sources
        self.truncate_log_text = truncate_log_text
        self.build_messages_preview_for_log = build_messages_preview_for_log
        self.log_group_trace = log_group_trace
        self.group_trace_preview_chars = group_trace_preview_chars

    def create_committee_turn_executor(self) -> CommitteeTurnExecutor:
        """Build turn executor with runtime dependencies and prompt helpers."""
        return CommitteeTurnExecutor(
            storage=self.storage,
            pricing_service=self.pricing_service,
            memory_service=self.memory_service,
            file_service=self.file_service,
            assistant_params_from_config=self.assistant_params_from_config,
            build_group_history_hint=self.build_group_history_hint,
            build_group_identity_prompt=self.build_group_identity_prompt,
            build_group_instruction_prompt=self.build_group_instruction_prompt,
            build_rag_context_and_sources=self.build_rag_context_and_sources,
            truncate_log_text=self.truncate_log_text,
            build_messages_preview_for_log=self.build_messages_preview_for_log,
            log_group_trace=self.log_group_trace,
            group_trace_preview_chars=self.group_trace_preview_chars,
        )

    def create_committee_orchestrator(
        self,
        *,
        llm_call: Any,
        stream_group_assistant_turn: Any,
        get_message_content_by_id: Any,
    ) -> CommitteeOrchestrator:
        """Build committee orchestrator using AgentService-owned runtime callbacks."""
        return CommitteeOrchestrator(
            llm_call=llm_call,
            assistant_params_from_config=self.assistant_params_from_config,
            stream_group_assistant_turn=stream_group_assistant_turn,
            get_message_content_by_id=get_message_content_by_id,
            build_structured_turn_summary=self.build_structured_turn_summary,
            build_committee_turn_packet=self.build_committee_turn_packet,
            detect_group_role_drift=self.detect_group_role_drift,
            build_role_retry_instruction=self.build_role_retry_instruction,
            truncate_log_text=self.truncate_log_text,
            log_group_trace=self.log_group_trace,
            group_trace_preview_chars=self.group_trace_preview_chars,
        )

    @staticmethod
    def create_round_robin_orchestrator(
        *,
        stream_group_assistant_turn: Any,
    ) -> RoundRobinOrchestrator:
        """Build round-robin orchestrator using shared turn-stream callback."""
        return RoundRobinOrchestrator(
            stream_group_assistant_turn=stream_group_assistant_turn,
        )

    @staticmethod
    def build_group_identity_prompt(
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
    def build_group_history_hint(
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
    def assistant_params_from_config(assistant_obj: AssistantLike) -> Dict[str, Any]:
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
    def build_group_instruction_prompt(
        instruction: Optional[str],
        structured_packet: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Wrap internal directives and optional committee packet into one prompt."""
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
    def extract_bullet_items(text: str, *, limit: int = 5) -> List[str]:
        """Extract concise bullet-like items from free-form text."""
        return CommitteeTurnExecutor.extract_bullet_items(text, limit=limit)

    @staticmethod
    def extract_keyword_sentences(
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

    @staticmethod
    def build_structured_turn_summary(content: str) -> Dict[str, Any]:
        """Build lightweight structured summary from assistant natural-language output."""
        return CommitteeTurnExecutor.build_structured_turn_summary(content)

    @staticmethod
    def build_committee_turn_packet(
        *,
        state: CommitteeRuntimeState,
        target_assistant_id: str,
        assistant_name_map: Dict[str, str],
        instruction: Optional[str],
    ) -> Dict[str, Any]:
        """Build structured per-turn packet used as internal committee context."""
        return CommitteeTurnExecutor.build_committee_turn_packet(
            state=state,
            target_assistant_id=target_assistant_id,
            assistant_name_map=assistant_name_map,
            instruction=instruction,
        )

    @staticmethod
    def normalize_identity_token(value: str) -> str:
        """Normalize identity labels for lightweight role-drift checks."""
        return CommitteeTurnExecutor.normalize_identity_token(value)

    @staticmethod
    def detect_group_role_drift(
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
    def build_role_retry_instruction(
        *,
        base_instruction: Optional[str],
        expected_assistant_name: str,
    ) -> str:
        """Build a retry instruction when role drift is detected."""
        return CommitteeTurnExecutor.build_role_retry_instruction(
            base_instruction=base_instruction,
            expected_assistant_name=expected_assistant_name,
        )
