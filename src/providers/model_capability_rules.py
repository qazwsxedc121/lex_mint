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


def infer_reasoning_support(model_id: str) -> Optional[bool]:
    """
    Infer whether the model supports reasoning/thinking mode.

    Returns:
        True when a known model family supports reasoning mode; None when no
        reliable rule applies.
    """
    normalized = normalize_model_id(model_id)
    if not normalized:
        return None

    kimi_match = normalized.startswith("kimi-") or "/kimi-" in normalized
    deepseek_match = normalized.startswith("deepseek-") or "/deepseek-" in normalized
    if kimi_match or deepseek_match:
        return True
    return None


def infer_capability_overrides(model_id: str) -> Dict[str, Any]:
    """Return sparse model capability overrides inferred from model ID."""
    overrides: Dict[str, Any] = {}

    inferred_reasoning = infer_reasoning_support(model_id)
    if inferred_reasoning is not None:
        overrides["reasoning"] = inferred_reasoning

    inferred_interleaved = infer_requires_interleaved_thinking(model_id)
    if inferred_interleaved is not None:
        overrides["requires_interleaved_thinking"] = inferred_interleaved

    return overrides


def apply_model_capability_hints(
    model_id: str,
    capabilities: Optional[Dict[str, Any]],
    *,
    provider_defaults: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Add inferred model-level capability hints to capability payloads.

    For explicit model capabilities, inferred fields are only filled when
    missing. For provider defaults, inferred fields override defaults because
    model-level inference is higher priority.
    """
    overrides = infer_capability_overrides(model_id)
    if not overrides:
        return capabilities

    if capabilities is not None:
        merged = dict(capabilities)
        for key, value in overrides.items():
            merged.setdefault(key, value)
        return merged

    if provider_defaults:
        merged = dict(provider_defaults)
    else:
        merged = {}
    for key, value in overrides.items():
        merged[key] = value
    return merged


def apply_interleaved_hint_to_capabilities(
    model_id: str,
    capabilities: Optional[Dict[str, Any]],
    *,
    provider_defaults: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Backward-compatible alias for older call sites."""
    return apply_model_capability_hints(
        model_id,
        capabilities,
        provider_defaults=provider_defaults,
    )
