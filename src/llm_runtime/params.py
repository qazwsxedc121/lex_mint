"""Shared request-parameter helpers for LLM runtime calls."""

from __future__ import annotations

from typing import Any


def build_llm_request_params(
    temperature: float | None = None,
    max_tokens: int | None = None,
    top_p: float | None = None,
    top_k: int | None = None,
    frequency_penalty: float | None = None,
    presence_penalty: float | None = None,
) -> dict[str, Any]:
    """Build sanitized request params for logging."""
    params: dict[str, Any] = {
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
