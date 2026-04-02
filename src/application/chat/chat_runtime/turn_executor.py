"""Turn execution primitives for committee orchestration."""

from __future__ import annotations

import asyncio
import logging
import re
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from src.application.chat.request_contexts import CommitteeMemberTurnContext
from src.application.chat.source_diagnostics import merge_tool_diagnostics_into_sources

from .committee_types import CommitteeRuntimeState
from .turn_context_builder import GroupTurnContextBuilder
from .turn_stream_runner import GroupTurnStreamRunner, GroupTurnStreamState

logger = logging.getLogger(__name__)


class CommitteeTurnExecutor:
    """Executes member turns and exposes reusable role/summary helpers."""

    def __init__(
        self,
        *,
        storage: Any,
        pricing_service: Any,
        memory_service: Any,
        file_service: Any,
        assistant_params_from_config: Callable[[Any], dict[str, Any]],
        build_group_history_hint: Callable[[list[dict[str, Any]], str, dict[str, str]], str],
        build_group_identity_prompt: Callable[[str, str, list[str], dict[str, str]], str],
        build_group_instruction_prompt: Callable[[str | None, dict[str, Any] | None], str | None],
        build_rag_context_and_sources: Callable[
            ..., Awaitable[tuple[str | None, list[dict[str, Any]]]]
        ],
        truncate_log_text: Callable[[str | None, int], str],
        build_messages_preview_for_log: Callable[[list[dict[str, Any]]], list[dict[str, Any]]],
        log_group_trace: Callable[[str, str, dict[str, Any]], None],
        group_trace_preview_chars: int = 1600,
    ):
        self.storage = storage
        self.pricing_service = pricing_service
        self.memory_service = memory_service
        self.file_service = file_service
        self.assistant_params_from_config = assistant_params_from_config
        self.build_group_history_hint = build_group_history_hint
        self.build_group_identity_prompt = build_group_identity_prompt
        self.build_group_instruction_prompt = build_group_instruction_prompt
        self.build_rag_context_and_sources = build_rag_context_and_sources
        self.truncate_log_text = truncate_log_text
        self.build_messages_preview_for_log = build_messages_preview_for_log
        self.log_group_trace = log_group_trace
        self.group_trace_preview_chars = group_trace_preview_chars
        self._context_builder = GroupTurnContextBuilder(
            storage=storage,
            memory_service=memory_service,
            build_rag_context_and_sources=build_rag_context_and_sources,
            build_group_history_hint=build_group_history_hint,
            build_group_identity_prompt=build_group_identity_prompt,
            build_group_instruction_prompt=build_group_instruction_prompt,
        )
        self._stream_runner = GroupTurnStreamRunner(
            pricing_service=pricing_service,
            file_service=file_service,
            assistant_params_from_config=assistant_params_from_config,
        )

    @staticmethod
    def extract_bullet_items(text: str, *, limit: int = 5) -> list[str]:
        """Extract concise bullet-like items from free-form text."""
        items: list[str] = []
        seen = set()
        for raw_line in (text or "").splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if line[:1] in {"-", "*", "•"}:
                candidate = line[1:].strip()
            elif re.match(r"^\d+[).]\s+", line):
                candidate = re.sub(r"^\d+[).]\s+", "", line)
            else:
                continue
            candidate = re.sub(r"\s+", " ", candidate).strip(" -")
            if len(candidate) < 8:
                continue
            key = candidate.lower()
            if key in seen:
                continue
            seen.add(key)
            items.append(candidate[:220])
            if len(items) >= limit:
                break
        return items

    @staticmethod
    def extract_keyword_sentences(
        text: str,
        *,
        keywords: list[str],
        limit: int = 4,
    ) -> list[str]:
        """Extract short sentences containing any keyword."""
        if not text:
            return []
        normalized = re.sub(r"\s+", " ", text)
        sentences = re.split(r"(?<=[.!?。！？])\s+", normalized)
        results: list[str] = []
        seen = set()
        for sentence in sentences:
            s = sentence.strip()
            if len(s) < 12:
                continue
            lower = s.lower()
            if not any(keyword in lower for keyword in keywords):
                continue
            key = lower[:180]
            if key in seen:
                continue
            seen.add(key)
            results.append(s[:240])
            if len(results) >= limit:
                break
        return results

    @staticmethod
    def build_structured_turn_summary(content: str) -> dict[str, Any]:
        """Build lightweight structured summary from assistant natural-language output."""
        key_points = CommitteeTurnExecutor.extract_bullet_items(content, limit=5)
        if not key_points:
            key_points = CommitteeTurnExecutor.extract_keyword_sentences(
                content,
                keywords=["should", "need", "must", "plan", "建议", "需要", "应该", "步骤"],
                limit=3,
            )

        risks = CommitteeTurnExecutor.extract_keyword_sentences(
            content,
            keywords=[
                "risk",
                "trade-off",
                "tradeoff",
                "security",
                "compliance",
                "latency",
                "成本",
                "风险",
                "安全",
                "合规",
            ],
            limit=4,
        )
        actions = CommitteeTurnExecutor.extract_keyword_sentences(
            content,
            keywords=[
                "next",
                "action",
                "implement",
                "step",
                "recommend",
                "建议",
                "实施",
                "下一步",
            ],
            limit=4,
        )

        if key_points:
            self_summary = key_points[0]
        else:
            normalized = re.sub(r"\s+", " ", content or "").strip()
            self_summary = normalized[:180]

        normalized_preview = re.sub(r"\s+", " ", content or "").strip()[:240]
        return {
            "key_points": key_points,
            "risks": risks,
            "actions": actions,
            "self_summary": self_summary[:240],
            "content_preview": normalized_preview,
        }

    @staticmethod
    def build_committee_turn_packet(
        *,
        state: CommitteeRuntimeState,
        target_assistant_id: str,
        assistant_name_map: dict[str, str],
        instruction: str | None,
    ) -> dict[str, Any]:
        """Build structured per-turn packet used as internal context for committee members."""
        recent_turns = state.turns[-6:]
        shared_turns: list[dict[str, Any]] = []
        for turn in recent_turns:
            shared_turns.append(
                {
                    "assistant_id": turn.assistant_id,
                    "assistant_name": turn.assistant_name,
                    "self_summary": turn.self_summary or turn.content_preview,
                    "key_points": turn.key_points[:3],
                    "risks": turn.risks[:2],
                    "actions": turn.actions[:2],
                }
            )

        self_turns = [turn for turn in state.turns if turn.assistant_id == target_assistant_id]
        self_summaries = [turn.self_summary or turn.content_preview for turn in self_turns[-3:]]
        latest_other_turn = next(
            (turn for turn in reversed(state.turns) if turn.assistant_id != target_assistant_id),
            None,
        )
        avoid_repeat = latest_other_turn.key_points[:3] if latest_other_turn else []

        target_name = assistant_name_map.get(target_assistant_id, target_assistant_id)
        return {
            "identity": {
                "assistant_id": target_assistant_id,
                "assistant_name": target_name,
            },
            "user_goal": state.user_message,
            "shared_state": {
                "round_index": state.round_index,
                "participants": state.participants,
                "recent_turns": shared_turns,
            },
            "self_state": {
                "latest_note": state.member_notes.get(target_assistant_id, ""),
                "recent_self_summaries": self_summaries,
            },
            "task": {
                "instruction": instruction
                or "Provide your best contribution for the user request.",
            },
            "constraints": {
                "output_mode": "natural_language",
                "avoid_role_drift": True,
                "avoid_repeating_recent_points": avoid_repeat,
            },
        }

    @staticmethod
    def normalize_identity_token(value: str) -> str:
        """Normalize identity labels for lightweight role-drift checks."""
        return "".join(ch.lower() for ch in (value or "") if ch.isalnum())

    @staticmethod
    def detect_group_role_drift(
        *,
        content: str,
        expected_assistant_id: str,
        expected_assistant_name: str,
        participant_name_map: dict[str, str],
    ) -> str | None:
        """Detect obvious cases where a speaker claims another participant identity."""
        head = (content or "")[:200]
        if not head:
            return None

        participant_tokens: dict[str, set] = {}
        for participant_id, participant_name in participant_name_map.items():
            participant_tokens[participant_id] = {
                CommitteeTurnExecutor.normalize_identity_token(participant_id),
                CommitteeTurnExecutor.normalize_identity_token(participant_name),
            }

        expected_tokens = {
            CommitteeTurnExecutor.normalize_identity_token(expected_assistant_id),
            CommitteeTurnExecutor.normalize_identity_token(expected_assistant_name),
        }

        patterns = [
            r"^\s*(?:\*\*)?\[\s*([^\]\n:]{2,80})\s*\](?:\*\*)?",
            r"^\s*\[\s*as\s+([^\]\n:]{2,80})\s*\]",
            r"^\s*as\s+([^\n:,.]{2,80})",
            r"^\s*i\s+am\s+([^\n:,.]{2,80})",
        ]
        for pattern in patterns:
            match = re.search(pattern, head, re.IGNORECASE)
            if match:
                candidate_token = CommitteeTurnExecutor.normalize_identity_token(
                    match.group(1).strip()
                )
                if not candidate_token:
                    continue
                if candidate_token in expected_tokens:
                    return None
                for participant_id, tokens in participant_tokens.items():
                    if candidate_token in tokens and participant_id != expected_assistant_id:
                        return f"role_drift_claimed_{participant_id}"
        return None

    @staticmethod
    def build_role_retry_instruction(
        *,
        base_instruction: str | None,
        expected_assistant_name: str,
    ) -> str:
        correction = (
            "Role correction required:\n"
            f"- You must answer strictly as {expected_assistant_name}.\n"
            "- Do not claim to be any other participant.\n"
            "- If your previous turn used another role label, restate from your own role."
        )
        if base_instruction and base_instruction.strip():
            return f"{base_instruction.strip()}\n\n{correction}"
        return correction

    async def get_message_content_by_id(
        self,
        *,
        session_id: str,
        message_id: str | None,
        context_type: str,
        project_id: str | None,
    ) -> str:
        """Read one message content from session state by message_id."""
        if not message_id:
            return ""
        try:
            session = await self.storage.get_session(
                session_id, context_type=context_type, project_id=project_id
            )
            for message in reversed(session["state"]["messages"]):
                if message.get("message_id") == message_id:
                    return (message.get("content") or "").strip()
        except Exception as e:
            logger.warning("[GroupChat] Failed to read message content for %s: %s", message_id, e)
        return ""

    async def stream_group_assistant_turn(
        self,
        *,
        turn_context: CommitteeMemberTurnContext,
        trace_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute one assistant turn in group mode and stream structured events."""
        member_turn = turn_context
        execution = member_turn.execution
        session_id = execution.scope.session_id
        context_type = execution.scope.context_type
        project_id = execution.scope.project_id
        assistant_id = member_turn.assistant_id
        assistant_obj = member_turn.assistant_obj
        assistant_turn_id = str(uuid.uuid4())
        prompt_context = await self._context_builder.build(
            turn_context=member_turn,
        )

        yield {
            "type": "assistant_start",
            "assistant_id": assistant_id,
            "assistant_turn_id": assistant_turn_id,
            "name": prompt_context.assistant_name,
            "icon": assistant_obj.icon,
        }

        if trace_id:
            self.log_group_trace(
                trace_id,
                "assistant_turn_request",
                {
                    "mode": member_turn.trace_mode or "group",
                    "round": member_turn.trace_round,
                    "assistant_id": assistant_id,
                    "assistant_name": prompt_context.assistant_name,
                    "assistant_turn_id": assistant_turn_id,
                    "model_id": prompt_context.model_id,
                    "instruction": self.truncate_log_text(
                        member_turn.instruction, self.group_trace_preview_chars
                    ),
                    "identity_prompt": self.truncate_log_text(
                        prompt_context.identity_prompt, self.group_trace_preview_chars
                    ),
                    "history_hint": self.truncate_log_text(
                        prompt_context.history_hint, self.group_trace_preview_chars
                    ),
                    "instruction_prompt": self.truncate_log_text(
                        prompt_context.instruction_prompt, self.group_trace_preview_chars
                    ),
                    "committee_turn_packet": member_turn.committee_turn_packet,
                    "final_system_prompt": self.truncate_log_text(
                        prompt_context.system_prompt, self.group_trace_preview_chars
                    ),
                    "messages_preview": self.build_messages_preview_for_log(prompt_context.messages),
                },
            )

        stream_state = GroupTurnStreamState()
        try:
            async for event in self._stream_runner.stream_turn(
                state=stream_state,
                session_id=session_id,
                assistant_id=assistant_id,
                assistant_turn_id=assistant_turn_id,
                assistant_obj=assistant_obj,
                model_id=prompt_context.model_id,
                messages=prompt_context.messages,
                system_prompt=prompt_context.system_prompt,
                reasoning_effort=execution.reasoning_effort,
            ):
                yield event
        except asyncio.CancelledError:
            if stream_state.full_response:
                await self.storage.append_message(
                    session_id,
                    "assistant",
                    stream_state.full_response,
                    assistant_id=assistant_id,
                    context_type=context_type,
                    project_id=project_id,
                )
            raise

        all_sources = merge_tool_diagnostics_into_sources(
            prompt_context.sources,
            stream_state.tool_diagnostics,
        )

        assistant_message_id = await self.storage.append_message(
            session_id,
            "assistant",
            stream_state.full_response,
            usage=stream_state.usage_data,
            cost=stream_state.cost_data,
            sources=all_sources if all_sources else None,
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id,
        )

        if trace_id:
            self.log_group_trace(
                trace_id,
                "assistant_turn_result",
                {
                    "mode": member_turn.trace_mode or "group",
                    "round": member_turn.trace_round,
                    "assistant_id": assistant_id,
                    "assistant_name": prompt_context.assistant_name,
                    "assistant_turn_id": assistant_turn_id,
                    "assistant_message_id": assistant_message_id,
                    "response_preview": self.truncate_log_text(
                        stream_state.full_response, self.group_trace_preview_chars
                    ),
                    "usage": stream_state.usage_data.model_dump()
                    if stream_state.usage_data
                    else None,
                    "cost": stream_state.cost_data.model_dump() if stream_state.cost_data else None,
                },
            )

        if stream_state.usage_data:
            usage_event = {
                "type": "usage",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
                "usage": stream_state.usage_data.model_dump(),
            }
            if stream_state.cost_data:
                usage_event["cost"] = stream_state.cost_data.model_dump()
            yield usage_event

        if all_sources:
            yield {
                "type": "sources",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
                "sources": all_sources,
            }

        yield {
            "type": "assistant_message_id",
            "assistant_id": assistant_id,
            "assistant_turn_id": assistant_turn_id,
            "message_id": assistant_message_id,
        }
        yield {
            "type": "assistant_done",
            "assistant_id": assistant_id,
            "assistant_turn_id": assistant_turn_id,
        }
