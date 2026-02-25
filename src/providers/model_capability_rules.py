"""
Model capability inference helpers.

Rules in this module are intentionally model-id based so they work across
direct providers and aggregators (for example OpenRouter or Volcengine).
"""
from __future__ import annotations

from typing import Any, Dict, Optional


def normalize_model_id(model_id: str) -> str:
    """Normalize model identifiers for rule matching."""
    normalized = str(model_id or "").strip().lower()
    if not normalized:
        return ""
    normalized = normalized.replace("\\", "/")
    # Drop variant suffixes like ":free" or ":beta".
    return normalized.split(":", 1)[0]


def infer_requires_interleaved_thinking(model_id: str) -> Optional[bool]:
    """
    Infer whether a model requires interleaved thinking payload passthrough.

    Returns:
        True when a known model family requires interleaved reasoning passthrough;
        None when no rule applies.
    """
    normalized = normalize_model_id(model_id)
    if not normalized:
        return None

    kimi_match = normalized.startswith("kimi-") or "/kimi-" in normalized
    deepseek_match = normalized.startswith("deepseek-") or "/deepseek-" in normalized

    if kimi_match or deepseek_match:
        return True
    return None


def apply_interleaved_hint_to_capabilities(
    model_id: str,
    capabilities: Optional[Dict[str, Any]],
    *,
    provider_defaults: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Add inferred interleaved-thinking requirement to capability payloads.

    This only writes the field when a positive rule matches and the field is
    not explicitly set in existing capabilities.
    """
    inferred = infer_requires_interleaved_thinking(model_id)
    if inferred is not True:
        return capabilities

    if capabilities is not None:
        merged = dict(capabilities)
        merged.setdefault("requires_interleaved_thinking", True)
        return merged

    if provider_defaults:
        merged = dict(provider_defaults)
    else:
        merged = {}
    # Provider defaults are lower priority than model-id inference.
    merged["requires_interleaved_thinking"] = True
    return merged
