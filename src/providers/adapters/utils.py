"""
Shared utilities for LLM adapters.
"""
from typing import Any, List


def extract_tool_calls(payload: Any) -> List[Any]:
    """Extract tool call payload from LangChain chunks/responses.

    Checks tool_calls, tool_call_chunks, and additional_kwargs for tool call data.

    Args:
        payload: A LangChain chunk or response object.

    Returns:
        List of tool call objects found in the payload.
    """
    tool_calls: List[Any] = []

    if hasattr(payload, "tool_calls") and payload.tool_calls:
        tool_calls.extend(payload.tool_calls)

    if hasattr(payload, "tool_call_chunks") and payload.tool_call_chunks:
        tool_calls.extend(payload.tool_call_chunks)

    if hasattr(payload, "additional_kwargs") and payload.additional_kwargs:
        ak = payload.additional_kwargs
        if isinstance(ak, dict):
            ak_tool_calls = ak.get("tool_calls")
            if ak_tool_calls:
                tool_calls.extend(ak_tool_calls)

    return tool_calls
