"""Shared tool-loop runtime primitives for streamed LLM calls."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

from langchain_core.messages import BaseMessage

from src.llm_runtime.stream_call_policy import select_stream_llm
from src.llm_runtime.tool_loop_runner import ToolLoopRunner, ToolLoopState
from src.providers.types import TokenUsage

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class BoundToolLoopModel:
    """Tool-binding result for one streaming runtime."""

    llm_for_tools: Any
    tools_enabled: bool
    tool_names: set[str]


@dataclass(frozen=True)
class ToolLoopRoundResult:
    """Aggregated output from one tool-loop streaming round."""

    round_content: str
    round_reasoning: str
    round_reasoning_details: Any
    final_usage: TokenUsage | None
    merged_chunk: Any


@dataclass(frozen=True)
class ToolLoopDecision:
    """Branch decision after one tool-loop round completes."""

    branch: str
    full_response: str
    round_tool_calls: list[dict[str, Any]]


@dataclass(frozen=True)
class ToolLoopFinalizeResult:
    """Finalized tool-loop outputs after fallback and diagnostics handling."""

    full_response: str
    injected_text: str | None
    diagnostics_event: dict[str, Any]


def bind_tools_for_tool_loop(
    *,
    llm: Any,
    llm_tools: list[Any] | None,
    warning_message: str,
) -> BoundToolLoopModel:
    """Bind tools to an LLM when available, otherwise keep direct LLM access."""
    if not llm_tools:
        return BoundToolLoopModel(llm_for_tools=llm, tools_enabled=False, tool_names=set())

    try:
        return BoundToolLoopModel(
            llm_for_tools=llm.bind_tools(llm_tools),
            tools_enabled=True,
            tool_names=_tool_names(llm_tools),
        )
    except Exception as exc:
        logger.warning("%s: %s", warning_message, exc)
        return BoundToolLoopModel(llm_for_tools=llm, tools_enabled=False, tool_names=set())


def build_tool_loop_state(
    *,
    langchain_messages: list[BaseMessage],
    latest_user_text: str,
    tool_names: set[str],
) -> tuple[ToolLoopRunner, ToolLoopState]:
    """Create the shared tool-loop runner/state pair for one request."""
    from src.tools.registry import get_tool_registry

    try:
        web_tool_names_raw = get_tool_registry().get_tool_names_by_group("web")
    except Exception:
        web_tool_names_raw = set()
    web_tool_names = (
        set(web_tool_names_raw) if isinstance(web_tool_names_raw, (set, list, tuple)) else set()
    )
    max_tool_rounds = ToolLoopRunner.resolve_max_tool_rounds(
        tool_names=tool_names,
        latest_user_text=latest_user_text,
        default_max_tool_rounds=3,
    )
    tool_loop_runner = ToolLoopRunner(max_tool_rounds=max_tool_rounds)
    tool_loop_state = ToolLoopState(
        current_messages=list(langchain_messages),
        web_research_enabled=bool(tool_names.intersection(web_tool_names)),
        max_tool_rounds=max_tool_rounds,
    )
    tool_loop_state.evidence_intent = tool_loop_runner.detect_evidence_intent(latest_user_text)
    return tool_loop_runner, tool_loop_state


def resolve_active_stream_llm(
    *,
    runtime: Any,
    llm_for_tools: Any,
    tools_enabled: bool,
    tool_loop_state: ToolLoopState,
) -> Any:
    """Resolve the active LLM object for the current tool-loop round."""
    return select_stream_llm(
        llm=runtime.llm,
        llm_for_tools=llm_for_tools,
        tools_enabled=tools_enabled,
        force_finalize_without_tools=tool_loop_state.force_finalize_without_tools,
    )


async def stream_tool_loop_round(
    *,
    runtime: Any,
    active_llm: Any,
    current_messages: list[BaseMessage],
    stream_kwargs: dict[str, Any],
) -> AsyncIterator[str | dict[str, Any] | ToolLoopRoundResult]:
    """Stream one LLM round and aggregate the final round result."""
    in_thinking_phase = False
    thinking_ended = False
    thinking_start_time: float | None = None
    round_content = ""
    round_reasoning = ""
    final_usage: TokenUsage | None = None
    merged_chunk = None

    async for chunk in runtime.adapter.stream(
        active_llm,
        current_messages,
        **stream_kwargs,
    ):
        chunk_usage = getattr(chunk, "usage", None)
        if isinstance(chunk_usage, dict):
            chunk_usage = TokenUsage(**chunk_usage)
        if chunk_usage is not None:
            final_usage = chunk_usage

        if chunk.thinking and not runtime.reasoning_decision.disable_thinking:
            round_reasoning += chunk.thinking
            if not in_thinking_phase:
                in_thinking_phase = True
                thinking_start_time = time.time()
                yield "<think>"
            yield chunk.thinking

        if chunk.content:
            if in_thinking_phase and not thinking_ended:
                thinking_ended = True
                duration_ms = (
                    int((time.time() - thinking_start_time) * 1000) if thinking_start_time else 0
                )
                yield "</think>"
                yield {"type": "thinking_duration", "duration_ms": duration_ms}
            round_content += chunk.content
            yield chunk.content

        if chunk.raw is not None:
            try:
                merged_chunk = chunk.raw if merged_chunk is None else merged_chunk + chunk.raw
            except Exception:
                pass

    if in_thinking_phase and not thinking_ended:
        duration_ms = int((time.time() - thinking_start_time) * 1000) if thinking_start_time else 0
        yield "</think>"
        yield {"type": "thinking_duration", "duration_ms": duration_ms}

    round_reasoning_details = None
    if merged_chunk is not None:
        extracted_usage = TokenUsage.extract_from_chunk(merged_chunk)
        if extracted_usage and final_usage is None:
            final_usage = extracted_usage
        if not runtime.reasoning_decision.disable_thinking and not round_reasoning:
            round_reasoning = _merged_chunk_reasoning_content(merged_chunk)
        round_reasoning_details = _merged_chunk_reasoning_details(merged_chunk)

    yield ToolLoopRoundResult(
        round_content=round_content,
        round_reasoning=round_reasoning,
        round_reasoning_details=round_reasoning_details,
        final_usage=final_usage,
        merged_chunk=merged_chunk,
    )


def decide_tool_loop_branch(
    *,
    tool_loop_runner: ToolLoopRunner,
    tool_loop_state: ToolLoopState,
    round_result: ToolLoopRoundResult,
    full_response: str,
    tools_enabled: bool,
) -> ToolLoopDecision:
    """Resolve the next branch after one round of tool-loop streaming."""
    round_tool_calls = tool_loop_runner.extract_tool_calls(
        round_result.merged_chunk,
        tools_enabled=tools_enabled,
        force_finalize_without_tools=tool_loop_state.force_finalize_without_tools,
    )

    if tool_loop_runner.should_request_read_compensation(
        tool_loop_state,
        round_tool_calls=round_tool_calls,
    ):
        full_response = _remove_round_content(full_response, round_result.round_content)
        logger.info("Injecting read_knowledge compensation prompt for evidence-focused request")
        tool_loop_runner.apply_read_compensation_prompt(tool_loop_state)
        return ToolLoopDecision(
            branch="continue",
            full_response=full_response,
            round_tool_calls=round_tool_calls,
        )

    if tool_loop_runner.should_request_web_read_compensation(
        tool_loop_state,
        round_tool_calls=round_tool_calls,
    ):
        full_response = _remove_round_content(full_response, round_result.round_content)
        logger.info("Injecting read_webpage compensation prompt for web research request")
        tool_loop_runner.apply_web_read_compensation_prompt(tool_loop_state)
        return ToolLoopDecision(
            branch="continue",
            full_response=full_response,
            round_tool_calls=round_tool_calls,
        )

    if tool_loop_runner.should_finish_round(
        tool_loop_state,
        round_tool_calls=round_tool_calls,
        tools_enabled=tools_enabled,
    ):
        return ToolLoopDecision(
            branch="finalize",
            full_response=full_response,
            round_tool_calls=round_tool_calls,
        )

    if tool_loop_runner.advance_round_or_force_finalize(
        tool_loop_state,
        round_content=round_result.round_content,
        round_reasoning=round_result.round_reasoning,
        round_reasoning_details=round_result.round_reasoning_details,
    ):
        return ToolLoopDecision(
            branch="continue",
            full_response=full_response,
            round_tool_calls=round_tool_calls,
        )

    return ToolLoopDecision(
        branch="execute_tools",
        full_response=full_response,
        round_tool_calls=round_tool_calls,
    )


async def execute_tool_loop_round(
    *,
    tool_loop_runner: ToolLoopRunner,
    tool_loop_state: ToolLoopState,
    round_tool_calls: list[dict[str, Any]],
    tool_executor: Any | None,
    round_content: str,
    round_reasoning: str,
    round_reasoning_details: Any,
) -> list[dict[str, str]]:
    """Execute tools and append the resulting messages back into loop state."""
    tool_results = await tool_loop_runner.execute_tool_calls(
        round_tool_calls,
        tool_executor=tool_executor,
    )
    tool_loop_runner.record_round_activity(
        tool_loop_state,
        round_tool_calls=round_tool_calls,
        tool_results=tool_results,
    )
    tool_loop_runner.append_round_with_tool_results(
        tool_loop_state,
        round_content=round_content,
        round_tool_calls=round_tool_calls,
        tool_results=tool_results,
        round_reasoning=round_reasoning,
        round_reasoning_details=round_reasoning_details,
    )
    return tool_results


def finalize_tool_loop(
    *,
    tool_loop_runner: ToolLoopRunner,
    tool_loop_state: ToolLoopState,
    full_response: str,
) -> ToolLoopFinalizeResult:
    """Apply fallback answer injection and build final diagnostics payload."""
    injected_text: str | None = None
    if tool_loop_runner.should_inject_fallback_answer(tool_loop_state, full_response):
        injected_text = tool_loop_runner.build_fallback_answer(tool_loop_state)
        if full_response.strip():
            injected_text = f"\n\n{injected_text}"
        full_response += injected_text
        tool_loop_state.tool_finalize_reason = "fallback_empty_answer"

    diagnostics_event = tool_loop_runner.build_tool_diagnostics_event(tool_loop_state)
    return ToolLoopFinalizeResult(
        full_response=full_response,
        injected_text=injected_text,
        diagnostics_event=diagnostics_event,
    )


def _tool_names(tools: list[Any] | None) -> set[str]:
    return {
        str(getattr(tool, "name", "") or "").strip()
        for tool in (tools or [])
        if str(getattr(tool, "name", "") or "").strip()
    }


def _merged_chunk_reasoning_details(merged_chunk: Any) -> Any:
    merged_kwargs = getattr(merged_chunk, "additional_kwargs", None) or {}
    if not isinstance(merged_kwargs, dict):
        return None
    return merged_kwargs.get("reasoning_details")


def _merged_chunk_reasoning_content(merged_chunk: Any) -> str:
    merged_kwargs = getattr(merged_chunk, "additional_kwargs", None) or {}
    if not isinstance(merged_kwargs, dict):
        return ""
    merged_reasoning = merged_kwargs.get("reasoning_content")
    return merged_reasoning if isinstance(merged_reasoning, str) else ""


def _remove_round_content(full_response: str, round_content: str) -> str:
    if round_content and full_response.endswith(round_content):
        return full_response[: -len(round_content)]
    return full_response
