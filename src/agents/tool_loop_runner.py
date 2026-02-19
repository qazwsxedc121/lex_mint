"""Tool-loop state and helpers for streamed LLM calls."""

from __future__ import annotations

import inspect
import logging
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, List, Optional, Union

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, ToolMessage

logger = logging.getLogger(__name__)


_FINALIZE_WITHOUT_TOOLS_PROMPT = (
    "Tool-call limit reached. Provide the best possible final answer now "
    "using only the existing tool results and conversation context. "
    "Do not call any tools."
)


@dataclass
class ToolLoopState:
    """Mutable state for multi-round tool calling."""

    current_messages: List[BaseMessage]
    tool_round: int = 0
    force_finalize_without_tools: bool = False


class ToolLoopRunner:
    """Encapsulates tool-call loop transitions and execution."""

    def __init__(self, max_tool_rounds: int = 3):
        self.max_tool_rounds = max(1, max_tool_rounds)

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
    ) -> bool:
        """Advance tool round; force a final non-tool pass if limit is exceeded.

        Returns:
            True when finalization mode was entered and caller should continue
            to the next stream pass, False when normal tool execution should proceed.
        """
        state.tool_round += 1
        if state.tool_round <= self.max_tool_rounds:
            return False

        state.current_messages.append(AIMessage(content=round_content))
        state.current_messages.append(HumanMessage(content=_FINALIZE_WITHOUT_TOOLS_PROMPT))
        state.force_finalize_without_tools = True
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
    ) -> None:
        """Append tool-call AI message + tool result messages for next pass."""
        ai_tool_calls = [
            {"name": tc["name"], "args": tc["args"], "id": tc["id"]}
            for tc in round_tool_calls
        ]
        state.current_messages.append(AIMessage(content=round_content, tool_calls=ai_tool_calls))

        for tr in tool_results:
            state.current_messages.append(
                ToolMessage(content=tr["result"], tool_call_id=tr["tool_call_id"])
            )
