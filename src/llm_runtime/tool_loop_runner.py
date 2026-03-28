"""Tool-loop state and helpers for streamed LLM calls."""

from __future__ import annotations

import inspect
import json
import logging
import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

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

_WEB_READ_PROMPT_TEMPLATE = (
    "Web research is not complete yet. Before your final answer, call read_webpage on the most relevant URL from "
    "the latest search results to verify the exact answer. Suggested URLs: {urls}.\n"
    "If that page still lacks the answer, continue with a more specific web_search instead of guessing."
)


@dataclass
class ToolLoopState:
    """Mutable state for multi-round tool calling."""

    current_messages: list[BaseMessage]
    tool_round: int = 0
    force_finalize_without_tools: bool = False
    evidence_intent: bool = False
    web_research_enabled: bool = False
    read_compensation_used: bool = False
    web_read_compensation_used: bool = False
    search_queries_seen: set[str] = field(default_factory=set)
    read_targets_seen: set[str] = field(default_factory=set)
    last_search_refs: list[str] = field(default_factory=list)
    last_web_search_urls: list[str] = field(default_factory=list)
    evidence_rows: list[dict[str, str]] = field(default_factory=list)
    tool_search_count: int = 0
    tool_search_unique_count: int = 0
    tool_search_duplicate_count: int = 0
    tool_read_count: int = 0
    tool_read_duplicate_count: int = 0
    web_search_count: int = 0
    web_read_count: int = 0
    tool_result_count: int = 0
    no_progress_rounds: int = 0
    max_tool_rounds: int = 0
    tool_finalize_reason: str = "normal_no_tools"


class ToolLoopRunner:
    """Encapsulates tool-call loop transitions and execution."""

    def __init__(self, max_tool_rounds: int = 3):
        self.max_tool_rounds = max(1, max_tool_rounds)

    @staticmethod
    def resolve_max_tool_rounds(
        *,
        tool_names: set[str],
        latest_user_text: str,
        default_max_tool_rounds: int = 3,
    ) -> int:
        max_rounds = max(1, int(default_max_tool_rounds))
        normalized_tool_names = {
            str(name or "").strip() for name in tool_names if str(name or "").strip()
        }
        if not normalized_tool_names.intersection({"web_search", "read_webpage"}):
            return max_rounds
        max_rounds = max(max_rounds, 5)
        if ToolLoopRunner.detect_multihop_web_research_intent(latest_user_text):
            max_rounds = max(max_rounds, 6)
        return max_rounds

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
    def detect_multihop_web_research_intent(user_text: str) -> bool:
        text = " ".join((user_text or "").lower().split())
        if not text:
            return False
        patterns = (
            "how many",
            "which",
            "who",
            "what country",
            "first name",
            "last name",
            "award number",
            "between ",
            "as of ",
            "published",
            "promoted",
            "find this paper",
            "olympics",
            "discography",
            "roster",
            "table",
            "wikipedia",
        )
        return len(text) >= 80 or any(pattern in text for pattern in patterns)

    @staticmethod
    def _normalize_query(value: str) -> str:
        normalized = (value or "").strip().lower()
        normalized = re.sub(r"[^\w\s]", " ", normalized)
        return " ".join(normalized.split())

    @staticmethod
    def _normalize_target(value: str) -> str:
        return " ".join((value or "").strip().lower().split())

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
        round_tool_calls: list[dict[str, Any]],
        tool_results: list[dict[str, str]],
    ) -> None:
        progress_made = False
        evidence_count_before = len(state.evidence_rows)

        for tool_call in round_tool_calls:
            name = str(tool_call.get("name") or "")
            raw_args = tool_call.get("args")
            args: dict[str, Any] = raw_args if isinstance(raw_args, dict) else {}
            if name in {"search_knowledge", "web_search"}:
                state.tool_search_count += 1
                if name == "web_search":
                    state.web_search_count += 1
                query_text = str(args.get("query") or "")
                normalized_query = self._normalize_query(query_text)
                if normalized_query and normalized_query in state.search_queries_seen:
                    state.tool_search_duplicate_count += 1
                elif normalized_query:
                    state.search_queries_seen.add(normalized_query)
                    state.tool_search_unique_count += 1
                    progress_made = True
                continue
            if name in {"read_knowledge", "read_webpage"}:
                state.tool_read_count += 1
                if name == "read_webpage":
                    state.web_read_count += 1
                read_target = ""
                if name == "read_webpage":
                    read_target = str(args.get("url") or "")
                elif name == "read_knowledge":
                    raw_refs = args.get("refs")
                    if isinstance(raw_refs, list):
                        read_target = "|".join(str(ref or "") for ref in raw_refs)
                normalized_target = self._normalize_target(read_target)
                if normalized_target and normalized_target in state.read_targets_seen:
                    state.tool_read_duplicate_count += 1
                elif normalized_target:
                    state.read_targets_seen.add(normalized_target)
                    progress_made = True

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
                refs: list[str] = []
                raw_hits = parsed.get("hits")
                hits: list[Any] = list(raw_hits) if isinstance(raw_hits, list) else []
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

            if name == "web_search":
                urls: list[str] = []
                raw_results = parsed.get("results")
                results: list[Any] = list(raw_results) if isinstance(raw_results, list) else []
                for item in results[:4]:
                    if not isinstance(item, dict):
                        continue
                    url = str(item.get("url") or "").strip()
                    if url:
                        urls.append(url)
                    self._append_evidence_row(
                        state,
                        title=str(item.get("title") or item.get("domain") or "web_result"),
                        snippet=str(item.get("snippet") or url),
                    )
                if urls:
                    state.last_web_search_urls = urls
                continue

            if name == "read_knowledge":
                raw_sources = parsed.get("sources")
                sources: list[Any] = list(raw_sources) if isinstance(raw_sources, list) else []
                for source in sources[:4]:
                    if not isinstance(source, dict):
                        continue
                    self._append_evidence_row(
                        state,
                        title=str(source.get("filename") or source.get("ref_id") or "read_source"),
                        snippet=str(source.get("content") or ""),
                    )
                continue

            if name == "read_webpage":
                page_title = str(parsed.get("title") or parsed.get("domain") or "webpage")
                page_snippet = str(parsed.get("preview") or parsed.get("content") or "")
                if page_snippet:
                    self._append_evidence_row(
                        state,
                        title=page_title,
                        snippet=page_snippet,
                    )

        if len(state.evidence_rows) > evidence_count_before:
            progress_made = True

        if progress_made:
            state.no_progress_rounds = 0
        else:
            state.no_progress_rounds += 1

    @staticmethod
    def should_request_read_compensation(
        state: ToolLoopState,
        *,
        round_tool_calls: list[dict[str, Any]],
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
    def should_request_web_read_compensation(
        state: ToolLoopState,
        *,
        round_tool_calls: list[dict[str, Any]],
    ) -> bool:
        if state.force_finalize_without_tools:
            return False
        if round_tool_calls:
            return False
        if not state.web_research_enabled:
            return False
        if state.web_read_compensation_used:
            return False
        if state.web_search_count <= 0 or state.web_read_count > 0:
            return False
        return bool(state.last_web_search_urls)

    @staticmethod
    def apply_read_compensation_prompt(state: ToolLoopState) -> None:
        refs_preview = ", ".join(state.last_search_refs[:3]) or "search refs"
        prompt = _EVIDENCE_READ_PROMPT_TEMPLATE.format(refs=refs_preview)
        state.current_messages.append(HumanMessage(content=prompt))
        state.read_compensation_used = True

    @staticmethod
    def apply_web_read_compensation_prompt(state: ToolLoopState) -> None:
        urls_preview = ", ".join(state.last_web_search_urls[:3]) or "latest search result URLs"
        prompt = _WEB_READ_PROMPT_TEMPLATE.format(urls=urls_preview)
        state.current_messages.append(HumanMessage(content=prompt))
        state.web_read_compensation_used = True

    @staticmethod
    def should_inject_fallback_answer(state: ToolLoopState, final_text: str) -> bool:
        if state.tool_result_count <= 0:
            return False
        normalized = " ".join((final_text or "").split())
        if not normalized:
            return True
        if len(normalized) < 18 and normalized.lower() in {
            "ok",
            "done",
            "completed",
            "好的",
            "完成",
        }:
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
    def build_tool_diagnostics_event(state: ToolLoopState) -> dict[str, Any]:
        return {
            "type": "tool_diagnostics",
            "tool_search_count": state.tool_search_count,
            "tool_search_unique_count": state.tool_search_unique_count,
            "tool_search_duplicate_count": state.tool_search_duplicate_count,
            "tool_read_count": state.tool_read_count,
            "tool_read_duplicate_count": state.tool_read_duplicate_count,
            "web_search_count": state.web_search_count,
            "web_read_count": state.web_read_count,
            "no_progress_rounds": state.no_progress_rounds,
            "max_tool_rounds": state.max_tool_rounds or None,
            "tool_finalize_reason": state.tool_finalize_reason,
        }

    @staticmethod
    def extract_tool_calls(
        merged_chunk: Any,
        *,
        tools_enabled: bool,
        force_finalize_without_tools: bool,
    ) -> list[dict[str, Any]]:
        """Extract normalized tool calls from a merged adapter chunk."""
        if not tools_enabled or force_finalize_without_tools or merged_chunk is None:
            return []

        extracted: list[dict[str, Any]] = []
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
        round_tool_calls: list[dict[str, Any]],
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
        if state.no_progress_rounds >= 2 and state.tool_result_count > 0:
            ai_kwargs: dict[str, Any] = {}
            additional_kwargs: dict[str, Any] = {}
            if round_reasoning:
                additional_kwargs["reasoning_content"] = round_reasoning
            if round_reasoning_details is not None:
                additional_kwargs["reasoning_details"] = round_reasoning_details
            if additional_kwargs:
                ai_kwargs["additional_kwargs"] = additional_kwargs
            state.current_messages.append(AIMessage(content=round_content, **ai_kwargs))
            state.current_messages.append(HumanMessage(content=_FINALIZE_WITHOUT_TOOLS_PROMPT))
            state.force_finalize_without_tools = True
            state.tool_finalize_reason = "stalled_research_force_finalize"
            return True

        state.tool_round += 1
        if state.tool_round <= self.max_tool_rounds:
            return False

        finalize_ai_kwargs: dict[str, Any] = {}
        finalize_additional_kwargs: dict[str, Any] = {}
        if round_reasoning:
            finalize_additional_kwargs["reasoning_content"] = round_reasoning
        if round_reasoning_details is not None:
            finalize_additional_kwargs["reasoning_details"] = round_reasoning_details
        if finalize_additional_kwargs:
            finalize_ai_kwargs["additional_kwargs"] = finalize_additional_kwargs
        state.current_messages.append(AIMessage(content=round_content, **finalize_ai_kwargs))
        state.current_messages.append(HumanMessage(content=_FINALIZE_WITHOUT_TOOLS_PROMPT))
        state.force_finalize_without_tools = True
        state.tool_finalize_reason = "max_round_force_finalize"
        return True

    @staticmethod
    def build_tool_calls_event(round_tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
        """Build frontend event payload for announced tool calls."""
        return {
            "type": "tool_calls",
            "calls": [
                {
                    "id": tc.get("id") or "",
                    "name": tc["name"],
                    "args": tc["args"],
                }
                for tc in round_tool_calls
            ],
        }

    @staticmethod
    def build_tool_results_event(tool_results: list[dict[str, str]]) -> dict[str, Any]:
        """Build frontend event payload for completed tool calls."""
        return {"type": "tool_results", "results": tool_results}

    @staticmethod
    async def execute_tool_calls(
        round_tool_calls: list[dict[str, Any]],
        *,
        tool_executor: Callable[[str, dict[str, Any]], str | None | Awaitable[str | None]]
        | None = None,
    ) -> list[dict[str, str]]:
        """Execute tool calls with request-scoped executor fallback to registry."""
        from src.tools.registry import get_tool_registry

        registry = get_tool_registry()
        tool_results: list[dict[str, str]] = []

        for tc in round_tool_calls:
            result: str | None = None
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
        round_tool_calls: list[dict[str, Any]],
        tool_results: list[dict[str, str]],
        round_reasoning: str = "",
        round_reasoning_details: Any = None,
    ) -> None:
        """Append tool-call AI message + tool result messages for next pass."""
        ai_tool_calls = [
            {"name": tc["name"], "args": tc["args"], "id": tc["id"]} for tc in round_tool_calls
        ]
        ai_kwargs: dict[str, Any] = {"tool_calls": ai_tool_calls}
        additional_kwargs: dict[str, Any] = {}
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
