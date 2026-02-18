"""
Shared utilities for LLM adapters.
"""
from typing import Any, List


def extract_tool_calls(payload: Any) -> List[Any]:
    """Extract tool call payload from LangChain chunks/responses.

    Priority order (first non-empty wins):
      1. tool_call_chunks  – streaming partial fragments (need accumulation)
      2. tool_calls        – complete tool calls (non-streaming or fully merged)
      3. additional_kwargs – raw provider data fallback

    Only ONE source is returned to avoid mixing partial and complete data.

    Args:
        payload: A LangChain chunk or response object.

    Returns:
        List of tool call objects found in the payload.
    """
    # 1) Streaming chunks: partial fragments with args as JSON string pieces
    if hasattr(payload, "tool_call_chunks") and payload.tool_call_chunks:
        return list(payload.tool_call_chunks)

    # 2) Complete tool calls (non-streaming invoke, or fully merged)
    if hasattr(payload, "tool_calls") and payload.tool_calls:
        return list(payload.tool_calls)

    # 3) Fallback: raw provider data in additional_kwargs
    if hasattr(payload, "additional_kwargs") and payload.additional_kwargs:
        ak = payload.additional_kwargs
        if isinstance(ak, dict):
            ak_tool_calls = ak.get("tool_calls")
            if ak_tool_calls:
                return list(ak_tool_calls)

    return []
