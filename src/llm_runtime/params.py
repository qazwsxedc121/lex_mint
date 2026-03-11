"""Shared request-parameter helpers for LLM runtime calls."""

from __future__ import annotations

from typing import Any, Dict, Optional


def build_llm_request_params(
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    top_k: Optional[int] = None,
    frequency_penalty: Optional[float] = None,
    presence_penalty: Optional[float] = None,
) -> Dict[str, Any]:
    """Build sanitized request params for logging."""
    params: Dict[str, Any] = {
        "temperature": 0.7 if temperature is None else temperature,
    }
    for key, value in {
        "max_tokens": max_tokens,
        "top_p": top_p,
        "top_k": top_k,
        "frequency_penalty": frequency_penalty,
        "presence_penalty": presence_penalty,
    }.items():
        if value is not None:
            params[key] = value
    return params
