"""Plugin-local adapter utilities."""

from typing import Any


def extract_tool_calls(payload: Any) -> list[Any]:
    if hasattr(payload, "tool_call_chunks") and payload.tool_call_chunks:
        return list(payload.tool_call_chunks)
    if hasattr(payload, "tool_calls") and payload.tool_calls:
        return list(payload.tool_calls)
    if hasattr(payload, "additional_kwargs") and payload.additional_kwargs:
        ak = payload.additional_kwargs
        if isinstance(ak, dict):
            ak_tool_calls = ak.get("tool_calls")
            if ak_tool_calls:
                return list(ak_tool_calls)
    return []
