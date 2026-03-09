"""LLM runtime package with explicit responsibility boundaries."""

from .context import (
    build_context_info_event,
    build_context_plan,
    calculate_output_reserve,
    context_segment_to_system_content,
    estimate_langchain_messages_tokens,
    estimate_total_tokens,
    filter_messages_by_context_boundary,
    get_context_limit,
    trim_to_context_limit,
    truncate_by_rounds,
)
from .messages import convert_to_langchain_messages
from .reasoning import (
    ReasoningDecision,
    build_reasoning_decision_payload,
    log_reasoning_decision,
    resolve_reasoning_decision,
)
from .streaming_client import call_llm_stream
from .sync_client import call_llm

_build_context_plan = build_context_plan
_build_reasoning_decision_payload = build_reasoning_decision_payload
_calculate_output_reserve = calculate_output_reserve
_context_segment_to_system_content = context_segment_to_system_content
_estimate_langchain_messages_tokens = estimate_langchain_messages_tokens
_estimate_total_tokens = estimate_total_tokens
_filter_messages_by_context_boundary = filter_messages_by_context_boundary
_get_context_limit = get_context_limit
_trim_to_context_limit = trim_to_context_limit
_truncate_by_rounds = truncate_by_rounds

__all__ = [
    "ReasoningDecision",
    "build_context_info_event",
    "build_context_plan",
    "build_reasoning_decision_payload",
    "calculate_output_reserve",
    "call_llm",
    "call_llm_stream",
    "context_segment_to_system_content",
    "convert_to_langchain_messages",
    "estimate_langchain_messages_tokens",
    "estimate_total_tokens",
    "filter_messages_by_context_boundary",
    "get_context_limit",
    "log_reasoning_decision",
    "resolve_reasoning_decision",
    "trim_to_context_limit",
    "truncate_by_rounds",
    "_build_context_plan",
    "_build_reasoning_decision_payload",
    "_calculate_output_reserve",
    "_context_segment_to_system_content",
    "_estimate_langchain_messages_tokens",
    "_estimate_total_tokens",
    "_filter_messages_by_context_boundary",
    "_get_context_limit",
    "_trim_to_context_limit",
    "_truncate_by_rounds",
]
