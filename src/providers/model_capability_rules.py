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


def _normalize_provider_id(provider_id: Optional[str]) -> str:
    return str(provider_id or "").strip().lower()


def infer_requires_interleaved_thinking(
    model_id: str,
    provider_id: Optional[str] = None,
) -> Optional[bool]:
    """
    Infer whether a model requires interleaved thinking payload passthrough.

    Returns:
        True when a known model family requires interleaved reasoning passthrough;
        None when no rule applies.
    """
    normalized = normalize_model_id(model_id)
    if not normalized:
        return None

    normalized_provider = _normalize_provider_id(provider_id)
    kimi_match = normalized.startswith("kimi-") or "/kimi-" in normalized
    deepseek_match = normalized.startswith("deepseek-") or "/deepseek-" in normalized

    if normalized_provider in {"kimi", "deepseek"} and (kimi_match or deepseek_match):
        return True
    if kimi_match or deepseek_match:
        return True
    return None


def infer_reasoning_support(
    model_id: str,
    provider_id: Optional[str] = None,
) -> Optional[bool]:
    """
    Infer whether the model supports reasoning/thinking mode.

    Returns:
        True when a known model family supports reasoning mode; None when no
        reliable rule applies.
    """
    normalized = normalize_model_id(model_id)
    if not normalized:
        return None

    normalized_provider = _normalize_provider_id(provider_id)
    kimi_match = normalized.startswith("kimi-") or "/kimi-" in normalized
    deepseek_match = normalized.startswith("deepseek-") or "/deepseek-" in normalized
    if normalized_provider in {"kimi", "deepseek"} and (kimi_match or deepseek_match):
        return True
    if kimi_match or deepseek_match:
        return True
    return None


def infer_reasoning_controls(
    model_id: str,
    provider_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Infer native reasoning control schema for a specific provider/model pair.

    The returned dict mirrors ReasoningControls fields so it can be merged into
    capability payloads without direct coupling here.
    """
    normalized = normalize_model_id(model_id)
    if not normalized:
        return None

    normalized_provider = _normalize_provider_id(provider_id)
    kimi_match = normalized.startswith("kimi-") or "/kimi-" in normalized
    deepseek_match = normalized.startswith("deepseek-") or "/deepseek-" in normalized

    if normalized_provider == "volcengine":
        return {
            "mode": "enum",
            "param": "reasoning_effort",
            "options": ["minimal", "low", "medium", "high"],
            "default_option": "medium",
            "disable_supported": True,
        }

    if normalized_provider == "openai":
        return {
            "mode": "enum",
            "param": "reasoning.effort",
            "options": ["low", "medium", "high"],
            "default_option": "medium",
            "disable_supported": True,
        }

    if normalized_provider == "openrouter":
        return {
            "mode": "enum",
            "param": "reasoning.effort",
            "options": ["minimal", "low", "medium", "high", "xhigh"],
            "default_option": "medium",
            "disable_supported": True,
        }

    # DeepSeek/Kimi model families are currently toggle-based in our adapters.
    if kimi_match or deepseek_match:
        return {
            "mode": "toggle",
            "param": "thinking.type",
            "options": ["enabled"],
            "default_option": "enabled",
            "disable_supported": True,
        }
    return None


def infer_capability_overrides(
    model_id: str,
    provider_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Return sparse model capability overrides inferred from model ID."""
    overrides: Dict[str, Any] = {}

    inferred_reasoning = infer_reasoning_support(model_id, provider_id=provider_id)
    if inferred_reasoning is not None:
        overrides["reasoning"] = inferred_reasoning

    inferred_controls = infer_reasoning_controls(model_id, provider_id=provider_id)
    if inferred_controls is not None:
        overrides["reasoning_controls"] = inferred_controls

    inferred_interleaved = infer_requires_interleaved_thinking(
        model_id,
        provider_id=provider_id,
    )
    if inferred_interleaved is not None:
        overrides["requires_interleaved_thinking"] = inferred_interleaved

    return overrides


def apply_model_capability_hints(
    model_id: str,
    capabilities: Optional[Dict[str, Any]],
    *,
    provider_defaults: Optional[Dict[str, Any]] = None,
    provider_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Add inferred model-level capability hints to capability payloads.

    For explicit model capabilities, inferred fields are only filled when
    missing. For provider defaults, inferred fields override defaults because
    model-level inference is higher priority.
    """
    overrides = infer_capability_overrides(model_id, provider_id=provider_id)
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
    provider_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Backward-compatible alias for older call sites."""
    return apply_model_capability_hints(
        model_id,
        capabilities,
        provider_defaults=provider_defaults,
        provider_id=provider_id,
    )
