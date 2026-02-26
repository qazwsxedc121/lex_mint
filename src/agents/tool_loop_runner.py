"""Tool-loop state and helpers for streamed LLM calls."""

from __future__ import annotations

import json
import inspect
import logging
import re
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)


_FINALIZE_WITHOUT_TOOLS_PROMPT = (
    "Tool-call limit reached. Provide the best possible final answer now "
    "using only the existing tool results and conversation context. "
    "Do not call any tools."
)

_EVIDENCE_READ_PROMPT_TEMPLATE = (
    "Evidence-focused request detected. Before your final answer, call read_knowledge for the most relevant refs "
    "to verify exact wording and citations. Suggested refs: {refs}.\n"
    "After reading, provide a grounded final answer."
)


@dataclass
class ToolLoopState:
    """Mutable state for multi-round tool calling."""

    current_messages: List[BaseMessage]
    tool_round: int = 0
    force_finalize_without_tools: bool = False
    evidence_intent: bool = False
    read_compensation_used: bool = False
    search_queries_seen: Set[str] = field(default_factory=set)
    last_search_refs: List[str] = field(default_factory=list)
    evidence_rows: List[Dict[str, str]] = field(default_factory=list)
    tool_search_count: int = 0
    tool_search_unique_count: int = 0
    tool_search_duplicate_count: int = 0
    tool_read_count: int = 0
    tool_result_count: int = 0
    tool_finalize_reason: str = "normal_no_tools"


class ToolLoopRunner:
    """Encapsulates tool-call loop transitions and execution."""

    def __init__(self, max_tool_rounds: int = 3):
        self.max_tool_rounds = max(1, max_tool_rounds)

    @staticmethod
    def detect_evidence_intent(user_text: str) -> bool:
        text = (user_text or "").lower()
        if not text:
            return False
        patterns = (
            "原文",
            "逐字",
            "引用",
            "出处",
            "哪一段",
            "exact quote",
            "verbatim",
            "cite",
            "citation",
        )
        return any(pattern in text for pattern in patterns)

    @staticmethod
    def _normalize_query(value: str) -> str:
        normalized = (value or "").strip().lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        return " ".join(normalized.split())

    @staticmethod
    def _snippet(value: str, max_chars: int = 180) -> str:
        text = " ".join((value or "").split())
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars]}..."

    @staticmethod
    def _append_evidence_row(state: ToolLoopState, *, title: str, snippet: str) -> None:
        safe_title = (title or "").strip() or "source"
        safe_snippet = ToolLoopRunner._snippet(snippet or "")
        if not safe_snippet:
            return
        row = {"title": safe_title, "snippet": safe_snippet}
        if row in state.evidence_rows:
            return
        state.evidence_rows.append(row)
        if len(state.evidence_rows) > 8:
            state.evidence_rows = state.evidence_rows[-8:]

    def record_round_activity(
        self,
        state: ToolLoopState,
        *,
        round_tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, str]],
    ) -> None:
        for tool_call in round_tool_calls:
            name = str(tool_call.get("name") or "")
            raw_args = tool_call.get("args")
            args: Dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
            if name == "search_knowledge":
                state.tool_search_count += 1
                query_text = str(args.get("query") or "")
                normalized_query = self._normalize_query(query_text)
                if normalized_query and normalized_query in state.search_queries_seen:
                    state.tool_search_duplicate_count += 1
                elif normalized_query:
                    state.search_queries_seen.add(normalized_query)
                    state.tool_search_unique_count += 1
                continue
            if name == "read_knowledge":
                state.tool_read_count += 1

        for tool_result in tool_results:
            state.tool_result_count += 1
            name = str(tool_result.get("name") or "")
            raw_result = str(tool_result.get("result") or "")
            try:
                parsed = json.loads(raw_result)
            except Exception:
                continue
            if not isinstance(parsed, dict):
                continue

            if name == "search_knowledge":
                refs: List[str] = []
                raw_hits = parsed.get("hits")
                hits: List[Any] = list(raw_hits) if isinstance(raw_hits, list) else []
                for hit in hits[:4]:
                    if not isinstance(hit, dict):
                        continue
                    ref_id = str(hit.get("ref_id") or "").strip()
                    if ref_id:
                        refs.append(ref_id)
                    self._append_evidence_row(
                        state,
                        title=str(hit.get("filename") or hit.get("doc_id") or "search_hit"),
                        snippet=str(hit.get("snippet") or ""),
                    )
                if refs:
                    state.last_search_refs = refs
                continue

            if name == "read_knowledge":
                raw_sources = parsed.get("sources")
                sources: List[Any] = list(raw_sources) if isinstance(raw_sources, list) else []
                for source in sources[:4]:
                    if not isinstance(source, dict):
                        continue
                    self._append_evidence_row(
                        state,
                        title=str(source.get("filename") or source.get("ref_id") or "read_source"),
                        snippet=str(source.get("content") or ""),
                    )

    @staticmethod
    def should_request_read_compensation(
        state: ToolLoopState,
        *,
        round_tool_calls: List[Dict[str, Any]],
    ) -> bool:
        if state.force_finalize_without_tools:
            return False
        if round_tool_calls:
            return False
        if not state.evidence_intent:
            return False
        if state.read_compensation_used:
            return False
        if state.tool_search_count <= 0 or state.tool_read_count > 0:
            return False
        return bool(state.last_search_refs)

    @staticmethod
    def apply_read_compensation_prompt(state: ToolLoopState) -> None:
        refs_preview = ", ".join(state.last_search_refs[:3]) or "search refs"
        prompt = _EVIDENCE_READ_PROMPT_TEMPLATE.format(refs=refs_preview)
        state.current_messages.append(HumanMessage(content=prompt))
        state.read_compensation_used = True

    @staticmethod
    def should_inject_fallback_answer(state: ToolLoopState, final_text: str) -> bool:
        if state.tool_result_count <= 0:
            return False
        normalized = " ".join((final_text or "").split())
        if not normalized:
            return True
        if len(normalized) < 18 and normalized.lower() in {"ok", "done", "completed", "好的", "完成"}:
            return True
        return False

    @staticmethod
    def build_fallback_answer(state: ToolLoopState) -> str:
        lines = [
            "I could not finalize a complete answer from the model stream. Based on retrieved evidence:",
        ]
        if state.evidence_rows:
            for row in state.evidence_rows[:3]:
                lines.append(f"- {row['title']}: {row['snippet']}")
        else:
            lines.append("- Retrieved context exists, but it could not be summarized safely.")
        lines.append("Please ask a focused follow-up for a refined answer.")
        return "\n".join(lines)

    @staticmethod
    def build_tool_diagnostics_event(state: ToolLoopState) -> Dict[str, Any]:
        return {
            "type": "tool_diagnostics",
            "tool_search_count": state.tool_search_count,
            "tool_search_unique_count": state.tool_search_unique_count,
            "tool_search_duplicate_count": state.tool_search_duplicate_count,
            "tool_read_count": state.tool_read_count,
            "tool_finalize_reason": state.tool_finalize_reason,
        }

    @staticmethod
    def extract_tool_calls(
        merged_chunk: Any,
        *,
        tools_enabled: bool,
        force_finalize_without_tools: bool,
    ) -> List[Dict[str, Any]]:
        """Extract normalized tool calls from a merged adapter chunk."""
        if not tools_enabled or force_finalize_without_tools or merged_chunk is None:
            return []

        extracted: List[Dict[str, Any]] = []
        raw_tool_calls = getattr(merged_chunk, "tool_calls", None) or []
        for tc in raw_tool_calls:
            if isinstance(tc, dict):
                tc_name = tc.get("name", "")
                tc_args = tc.get("args", {})
                tc_id = tc.get("id", "")
            else:
                tc_name = getattr(tc, "name", "") or ""
                tc_args = getattr(tc, "args", {}) or {}
                tc_id = getattr(tc, "id", "") or ""
            if tc_name:
                extracted.append(
                    {
                        "name": tc_name,
                        "args": tc_args if isinstance(tc_args, dict) else {},
                        "id": tc_id or "",
                    }
                )
        return extracted

    @staticmethod
    def should_finish_round(
        state: ToolLoopState,
        *,
        round_tool_calls: List[Dict[str, Any]],
        tools_enabled: bool,
    ) -> bool:
        """Whether the stream loop should terminate after this pass."""
        if state.force_finalize_without_tools:
            return True
        if not round_tool_calls or not tools_enabled:
            return True
        return False

    def advance_round_or_force_finalize(
        self,
        state: ToolLoopState,
        *,
        round_content: str,
        round_reasoning: str = "",
        round_reasoning_details: Any = None,
    ) -> bool:
        """Advance tool round; force a final non-tool pass if limit is exceeded.

        Returns:
            True when finalization mode was entered and caller should continue
            to the next stream pass, False when normal tool execution should proceed.
        """
        state.tool_round += 1
        if state.tool_round <= self.max_tool_rounds:
            return False

        ai_kwargs: Dict[str, Any] = {}
        additional_kwargs: Dict[str, Any] = {}
        if round_reasoning:
            additional_kwargs["reasoning_content"] = round_reasoning
        if round_reasoning_details is not None:
            additional_kwargs["reasoning_details"] = round_reasoning_details
        if additional_kwargs:
            ai_kwargs["additional_kwargs"] = additional_kwargs
        state.current_messages.append(AIMessage(content=round_content, **ai_kwargs))
        state.current_messages.append(HumanMessage(content=_FINALIZE_WITHOUT_TOOLS_PROMPT))
        state.force_finalize_without_tools = True
        state.tool_finalize_reason = "max_round_force_finalize"
        return True

    @staticmethod
    def build_tool_calls_event(round_tool_calls: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build frontend event payload for announced tool calls."""
        return {
            "type": "tool_calls",
            "calls": [{"name": tc["name"], "args": tc["args"]} for tc in round_tool_calls],
        }

    @staticmethod
    def build_tool_results_event(tool_results: List[Dict[str, str]]) -> Dict[str, Any]:
        """Build frontend event payload for completed tool calls."""
        return {"type": "tool_results", "results": tool_results}

    @staticmethod
    async def execute_tool_calls(
        round_tool_calls: List[Dict[str, Any]],
        *,
        tool_executor: Optional[
            Callable[[str, Dict[str, Any]], Union[Optional[str], Awaitable[Optional[str]]]]
        ] = None,
    ) -> List[Dict[str, str]]:
        """Execute tool calls with request-scoped executor fallback to registry."""
        from src.tools.registry import get_tool_registry

        registry = get_tool_registry()
        tool_results: List[Dict[str, str]] = []

        for tc in round_tool_calls:
            result: Optional[str] = None
            if tool_executor is not None:
                try:
                    maybe_result = tool_executor(tc["name"], tc["args"])
                    if inspect.isawaitable(maybe_result):
                        maybe_result = await maybe_result
                    if maybe_result is not None:
                        result = str(maybe_result)
                except Exception as e:
                    logger.warning("Request-level tool executor failed (%s): %s", tc["name"], e)

            if result is None:
                result = registry.execute_tool(tc["name"], tc["args"])

            tool_results.append(
                {
                    "name": tc["name"],
                    "result": result,
                    "tool_call_id": tc["id"],
                }
            )

        return tool_results

    @staticmethod
    def append_round_with_tool_results(
        state: ToolLoopState,
        *,
        round_content: str,
        round_tool_calls: List[Dict[str, Any]],
        tool_results: List[Dict[str, str]],
        round_reasoning: str = "",
        round_reasoning_details: Any = None,
    ) -> None:
        """Append tool-call AI message + tool result messages for next pass."""
        ai_tool_calls = [
            {"name": tc["name"], "args": tc["args"], "id": tc["id"]}
            for tc in round_tool_calls
        ]
        ai_kwargs: Dict[str, Any] = {"tool_calls": ai_tool_calls}
        additional_kwargs: Dict[str, Any] = {}
        if round_reasoning:
            additional_kwargs["reasoning_content"] = round_reasoning
        if round_reasoning_details is not None:
            additional_kwargs["reasoning_details"] = round_reasoning_details
        if additional_kwargs:
            ai_kwargs["additional_kwargs"] = additional_kwargs
        state.current_messages.append(AIMessage(content=round_content, **ai_kwargs))

        for tr in tool_results:
            state.current_messages.append(
                ToolMessage(content=tr["result"], tool_call_id=tr["tool_call_id"])
            )
