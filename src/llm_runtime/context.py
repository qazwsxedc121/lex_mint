"""Context planning and token-budget helpers for LLM runtime calls."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage, trim_messages

from .context_planner import ContextPlan, ContextPlanner

logger = logging.getLogger(__name__)


DEFAULT_CONTEXT_LENGTH = 4096
DEFAULT_OUTPUT_RESERVE_RATIO = 0.25
MIN_OUTPUT_RESERVE = 1024
MAX_OUTPUT_RESERVE = 32000
APPROX_CHARS_PER_TOKEN = 4


def calculate_output_reserve(context_length: int, from_profile: bool) -> int:
    """Calculate how many tokens to reserve for model output."""
    if from_profile:
        return int(context_length * 0.05)
    reserve = int(context_length * DEFAULT_OUTPUT_RESERVE_RATIO)
    return max(MIN_OUTPUT_RESERVE, min(MAX_OUTPUT_RESERVE, reserve))


def get_context_limit(llm: Any, capabilities: Any) -> tuple[int, int]:
    """Determine the max input tokens allowed before calling the LLM."""
    profile_limit = None
    try:
        profile = getattr(llm, "profile", None)
        if profile and isinstance(profile, dict):
            profile_limit = profile.get("max_input_tokens")
    except Exception:
        profile_limit = None

    if profile_limit and isinstance(profile_limit, int) and profile_limit > 0:
        reserve = calculate_output_reserve(profile_limit, from_profile=True)
        budget = profile_limit - reserve
        logger.info(
            "[CONTEXT] Using profile max_input_tokens=%s, reserve=%s, budget=%s",
            profile_limit,
            reserve,
            budget,
        )
        return budget, profile_limit

    config_limit = getattr(capabilities, "context_length", None)
    if config_limit and isinstance(config_limit, int) and config_limit > 0:
        reserve = calculate_output_reserve(config_limit, from_profile=False)
        budget = config_limit - reserve
        logger.info(
            "[CONTEXT] Using config context_length=%s, reserve=%s, budget=%s",
            config_limit,
            reserve,
            budget,
        )
        return budget, config_limit

    reserve = calculate_output_reserve(DEFAULT_CONTEXT_LENGTH, from_profile=False)
    budget = DEFAULT_CONTEXT_LENGTH - reserve
    logger.info(
        "[CONTEXT] Using default context_length=%s, reserve=%s, budget=%s",
        DEFAULT_CONTEXT_LENGTH,
        reserve,
        budget,
    )
    return budget, DEFAULT_CONTEXT_LENGTH


def trim_to_context_limit(messages: list[BaseMessage], max_input_tokens: int) -> list[BaseMessage]:
    """Trim messages to fit within the token budget using approximate counting."""
    trimmed = trim_messages(
        messages,
        max_tokens=max_input_tokens,
        strategy="last",
        token_counter="approximate",
        include_system=True,
        start_on="human",
    )
    if len(trimmed) < len(messages):
        logger.info(
            "[TRIM] Messages trimmed: %s -> %s (budget: %s tokens)",
            len(messages),
            len(trimmed),
            max_input_tokens,
        )
        print(
            f"[TRIM] Messages trimmed to fit context window: "
            f"{len(messages)} -> {len(trimmed)} messages "
            f"(budget: {max_input_tokens} tokens)"
        )
    return trimmed


def estimate_total_tokens(messages: list[dict[str, Any]]) -> int:
    """Estimate total token count for raw message dicts."""
    total = 0
    for msg in messages:
        role = msg.get("role", "")
        if role not in ("user", "assistant"):
            continue

        if role == "assistant":
            usage = msg.get("usage")
            if usage and isinstance(usage, dict):
                completion_tokens = usage.get("completion_tokens")
                if completion_tokens and completion_tokens > 0:
                    total += completion_tokens
                    continue

        content = msg.get("content", "")
        total += max(1, len(content) // APPROX_CHARS_PER_TOKEN)

    return total


def estimate_langchain_messages_tokens(messages: list[BaseMessage]) -> int:
    """Estimate prompt tokens for LangChain messages using the same rough heuristic."""
    total = 0
    for msg in messages:
        content = getattr(msg, "content", "")
        if isinstance(content, str):
            total += max(1, len(content) // APPROX_CHARS_PER_TOKEN) if content else 0
            continue
        total += max(1, len(str(content)) // APPROX_CHARS_PER_TOKEN)
    return total


def build_context_plan(
    *,
    messages: list[dict[str, Any]],
    system_prompt: str | None,
    context_segments: dict[str, str | None] | None,
    summary_content: str | None,
    max_rounds: int | None,
    context_budget_tokens: int,
) -> ContextPlan:
    """Build the ordered context plan for a model call."""
    segments = context_segments or {}
    planner = ContextPlanner()
    return planner.plan(
        context_budget_tokens=context_budget_tokens,
        base_system_prompt=segments.get("base_system_prompt", system_prompt),
        compressed_history_summary=summary_content,
        recent_messages=messages,
        max_rounds=max_rounds,
        memory_context=segments.get("memory_context"),
        webpage_context=segments.get("webpage_context"),
        search_context=segments.get("search_context"),
        rag_context=segments.get("rag_context"),
        structured_source_context=segments.get("structured_source_context"),
    )


def build_context_info_event(
    *,
    context_plan: ContextPlan,
    context_budget: int,
    context_window: int,
    estimated_prompt_tokens: int,
) -> dict[str, Any]:
    """Build the frontend-facing context budget event."""
    return {
        "type": "context_info",
        "context_budget": context_budget,
        "context_window": context_window,
        "estimated_prompt_tokens": estimated_prompt_tokens,
        "remaining_tokens": context_budget - estimated_prompt_tokens,
        "segments": [segment.to_dict() for segment in context_plan.segment_reports],
    }


def context_segment_to_system_content(name: str, content: str) -> str:
    """Serialize a planned system segment into final system message content."""
    if name == "summary":
        return f"<compressed_history_summary>\n{content}\n</compressed_history_summary>"
    return content


def truncate_by_rounds(
    messages: list[Any],
    max_rounds: int,
    system_prompt: str | None = None,
) -> list[Any]:
    """Truncate message list by conversation rounds."""
    _ = system_prompt
    system_messages: list[Any] = []
    conversation_messages = list(messages)
    while conversation_messages and isinstance(conversation_messages[0], SystemMessage):
        system_messages.append(conversation_messages.pop(0))

    human_indexes = [
        index for index, msg in enumerate(conversation_messages) if isinstance(msg, HumanMessage)
    ]
    current_rounds = len(human_indexes)

    if current_rounds <= max_rounds:
        return messages

    print(
        f"[WARN] Conversation rounds exceed limit ({current_rounds} > {max_rounds}), "
        f"truncating to recent {max_rounds} rounds..."
    )

    start_index = human_indexes[-max_rounds]
    kept_conversation = conversation_messages[start_index:]

    result: list[Any] = []
    result.extend(system_messages)
    result.extend(kept_conversation)

    print(
        f"      Truncation complete: kept {len(kept_conversation)} messages ({max_rounds} rounds)"
    )
    return result


def filter_messages_by_context_boundary(
    messages: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], str | None]:
    """Keep only messages after the last summary/separator boundary."""
    last_boundary_index = -1
    boundary_is_summary = False

    for index in range(len(messages) - 1, -1, -1):
        role = messages[index].get("role")
        if role in {"separator", "summary"}:
            last_boundary_index = index
            boundary_is_summary = role == "summary"
            break

    if last_boundary_index == -1:
        return messages, None

    summary_content = None
    if boundary_is_summary:
        summary_content = messages[last_boundary_index].get("content", "")

    return messages[last_boundary_index + 1 :], summary_content
