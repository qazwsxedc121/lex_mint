"""Turn execution primitives for committee orchestration."""

import asyncio
import logging
import re
import uuid
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Awaitable, Tuple

from src.agents.simple_llm import call_llm_stream

from .types import CommitteeRuntimeState

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
        assistant_params_from_config: Callable[[Any], Dict[str, Any]],
        build_group_history_hint: Callable[[List[Dict[str, Any]], str, Dict[str, str]], str],
        build_group_identity_prompt: Callable[[str, str, List[str], Dict[str, str]], str],
        build_group_instruction_prompt: Callable[[Optional[str], Optional[Dict[str, Any]]], Optional[str]],
        build_rag_context_and_sources: Callable[..., Awaitable[Tuple[Optional[str], List[Dict[str, Any]]]]],
        truncate_log_text: Callable[[Optional[str], int], str],
        build_messages_preview_for_log: Callable[[List[Dict[str, Any]]], List[Dict[str, Any]]],
        log_group_trace: Callable[[str, str, Dict[str, Any]], None],
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

    @staticmethod
    def extract_bullet_items(text: str, *, limit: int = 5) -> List[str]:
        """Extract concise bullet-like items from free-form text."""
        items: List[str] = []
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
        keywords: List[str],
        limit: int = 4,
    ) -> List[str]:
        """Extract short sentences containing any keyword."""
        if not text:
            return []
        normalized = re.sub(r"\s+", " ", text)
        sentences = re.split(r"(?<=[.!?。！？])\s+", normalized)
        results: List[str] = []
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
    def build_structured_turn_summary(content: str) -> Dict[str, Any]:
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
        assistant_name_map: Dict[str, str],
        instruction: Optional[str],
    ) -> Dict[str, Any]:
        """Build structured per-turn packet used as internal context for committee members."""
        recent_turns = state.turns[-6:]
        shared_turns: List[Dict[str, Any]] = []
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
                "instruction": instruction or "Provide your best contribution for the user request.",
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
        participant_name_map: Dict[str, str],
    ) -> Optional[str]:
        """Detect obvious cases where a speaker claims another participant identity."""
        head = (content or "")[:200]
        if not head:
            return None

        participant_tokens: Dict[str, set] = {}
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
                candidate_token = CommitteeTurnExecutor.normalize_identity_token(match.group(1).strip())
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
        base_instruction: Optional[str],
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
        message_id: Optional[str],
        context_type: str,
        project_id: Optional[str],
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
        session_id: str,
        assistant_id: str,
        assistant_obj: Any,
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
        assistant_turn_id = str(uuid.uuid4())
        assistant_name = assistant_obj.name
        yield {
            "type": "assistant_start",
            "assistant_id": assistant_id,
            "assistant_turn_id": assistant_turn_id,
            "name": assistant_name,
            "icon": assistant_obj.icon,
        }

        session = await self.storage.get_session(
            session_id, context_type=context_type, project_id=project_id
        )
        messages = session["state"]["messages"]
        model_id = assistant_obj.model_id

        history_hint = self.build_group_history_hint(
            messages=messages,
            current_assistant_id=assistant_id,
            assistant_name_map=assistant_name_map,
        )
        identity_prompt = self.build_group_identity_prompt(
            current_assistant_id=assistant_id,
            current_assistant_name=assistant_name,
            group_assistants=group_assistants,
            assistant_name_map=assistant_name_map,
        )
        instruction_prompt = self.build_group_instruction_prompt(
            instruction, committee_turn_packet
        )
        system_prompt = assistant_obj.system_prompt
        prompt_parts = [identity_prompt]
        if history_hint:
            prompt_parts.append(history_hint)
        if instruction_prompt:
            prompt_parts.append(instruction_prompt)
        if system_prompt:
            prompt_parts.append(system_prompt)
        system_prompt = "\n\n".join(prompt_parts)

        assistant_memory_enabled = bool(getattr(assistant_obj, "memory_enabled", True))
        try:
            memory_context, _ = self.memory_service.build_memory_context(
                query=raw_user_message,
                assistant_id=assistant_id,
                include_global=True,
                include_assistant=assistant_memory_enabled,
            )
            if memory_context:
                system_prompt = (
                    f"{system_prompt}\n\n{memory_context}" if system_prompt else memory_context
                )
        except Exception as e:
            logger.warning("[GroupChat] Memory retrieval failed for %s: %s", assistant_id, e)

        rag_context, _ = await self.build_rag_context_and_sources(
            raw_user_message=raw_user_message,
            assistant_id=assistant_id,
            assistant_obj=assistant_obj,
            runtime_model_id=model_id,
        )
        if rag_context:
            system_prompt = f"{system_prompt}\n\n{rag_context}" if system_prompt else rag_context
        if search_context:
            system_prompt = (
                f"{system_prompt}\n\n{search_context}" if system_prompt else search_context
            )

        if trace_id:
            self.log_group_trace(
                trace_id,
                "assistant_turn_request",
                {
                    "mode": trace_mode or "group",
                    "round": trace_round,
                    "assistant_id": assistant_id,
                    "assistant_name": assistant_name,
                    "assistant_turn_id": assistant_turn_id,
                    "model_id": model_id,
                    "instruction": self.truncate_log_text(instruction, self.group_trace_preview_chars),
                    "identity_prompt": self.truncate_log_text(identity_prompt, self.group_trace_preview_chars),
                    "history_hint": self.truncate_log_text(history_hint, self.group_trace_preview_chars),
                    "instruction_prompt": self.truncate_log_text(
                        instruction_prompt, self.group_trace_preview_chars
                    ),
                    "committee_turn_packet": committee_turn_packet,
                    "final_system_prompt": self.truncate_log_text(
                        system_prompt, self.group_trace_preview_chars
                    ),
                    "messages_preview": self.build_messages_preview_for_log(messages),
                },
            )

        full_response = ""
        usage_data = None
        cost_data = None
        assistant_params = self.assistant_params_from_config(assistant_obj)
        max_rounds = assistant_obj.max_rounds

        try:
            async for chunk in call_llm_stream(
                messages,
                session_id=session_id,
                model_id=model_id,
                system_prompt=system_prompt,
                max_rounds=max_rounds,
                reasoning_effort=reasoning_effort,
                file_service=self.file_service,
                **assistant_params,
            ):
                if isinstance(chunk, dict) and chunk.get("type") == "usage":
                    usage_data = chunk["usage"]
                    parts = model_id.split(":", 1)
                    provider_id = parts[0] if len(parts) > 1 else ""
                    simple_model_id = parts[1] if len(parts) > 1 else model_id
                    cost_data = self.pricing_service.calculate_cost(
                        provider_id, simple_model_id, usage_data
                    )
                    continue

                if isinstance(chunk, dict):
                    event = dict(chunk)
                    event["assistant_id"] = assistant_id
                    event["assistant_turn_id"] = assistant_turn_id
                    yield event
                    continue

                full_response += chunk
                yield {
                    "type": "assistant_chunk",
                    "assistant_id": assistant_id,
                    "assistant_turn_id": assistant_turn_id,
                    "chunk": chunk,
                }
        except asyncio.CancelledError:
            if full_response:
                await self.storage.append_message(
                    session_id,
                    "assistant",
                    full_response,
                    assistant_id=assistant_id,
                    context_type=context_type,
                    project_id=project_id,
                )
            raise

        assistant_message_id = await self.storage.append_message(
            session_id,
            "assistant",
            full_response,
            usage=usage_data,
            cost=cost_data,
            sources=search_sources if search_sources else None,
            assistant_id=assistant_id,
            context_type=context_type,
            project_id=project_id,
        )

        if trace_id:
            self.log_group_trace(
                trace_id,
                "assistant_turn_result",
                {
                    "mode": trace_mode or "group",
                    "round": trace_round,
                    "assistant_id": assistant_id,
                    "assistant_name": assistant_name,
                    "assistant_turn_id": assistant_turn_id,
                    "assistant_message_id": assistant_message_id,
                    "response_preview": self.truncate_log_text(
                        full_response, self.group_trace_preview_chars
                    ),
                    "usage": usage_data.model_dump() if usage_data else None,
                    "cost": cost_data.model_dump() if cost_data else None,
                },
            )

        if usage_data:
            usage_event = {
                "type": "usage",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
                "usage": usage_data.model_dump(),
            }
            if cost_data:
                usage_event["cost"] = cost_data.model_dump()
            yield usage_event

        if search_sources:
            yield {
                "type": "sources",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
                "sources": search_sources,
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

