"""Minimal fallback capability inference helpers.

Capability resolution is metadata-first. This module only keeps a very small
set of fallback rules for dynamic models that cannot be fully declared ahead of
time, primarily local GGUF discovery.
"""

from __future__ import annotations

from typing import Any


def normalize_model_id(model_id: str) -> str:
    """Normalize model identifiers for fallback matching."""
    normalized = str(model_id or "").strip().lower()
    if not normalized:
        return ""
    normalized = normalized.replace("\\", "/")
    # Drop variant suffixes like ":free" or ":beta".
    return normalized.split(":", 1)[0]


def _normalize_provider_id(provider_id: str | None) -> str:
    return str(provider_id or "").strip().lower()


def _is_local_qwen3_model(normalized_model_id: str, normalized_provider_id: str) -> bool:
    if normalized_provider_id != "local_gguf":
        return False
    if "qwen3.5" in normalized_model_id or "qwen35" in normalized_model_id:
        return False
    return "qwen3" in normalized_model_id


def _is_kimi_k2_family_model(normalized_model_id: str, normalized_provider_id: str) -> bool:
    if normalized_provider_id == "kimi":
        return normalized_model_id.startswith("kimi-k2")
    return "/kimi-k2" in normalized_model_id or normalized_model_id.startswith("kimi-k2")


def infer_capability_overrides(
    model_id: str,
    provider_id: str | None = None,
) -> dict[str, Any]:
    """Return sparse fallback capability overrides.

    These overrides are intentionally minimal and should only cover dynamic
    discovery scenarios that cannot reliably ship explicit metadata.
    """
    normalized_model_id = normalize_model_id(model_id)
    normalized_provider_id = _normalize_provider_id(provider_id)
    if not normalized_model_id:
        return {}

    if _is_local_qwen3_model(normalized_model_id, normalized_provider_id):
        return {
            "reasoning": True,
            "function_calling": True,
            "reasoning_controls": {
                "mode": "toggle",
                "param": "enable_thinking",
                "options": [],
                "default_option": None,
                "disable_supported": True,
            },
        }

    if _is_kimi_k2_family_model(normalized_model_id, normalized_provider_id):
        return {
            "reasoning": True,
            "requires_interleaved_thinking": True,
            "reasoning_controls": {
                "mode": "toggle",
                "param": "thinking",
                "options": [],
                "default_option": None,
                "disable_supported": True,
            },
        }

    return {}


def infer_requires_interleaved_thinking(
    model_id: str,
    provider_id: str | None = None,
) -> bool | None:
    overrides = infer_capability_overrides(model_id, provider_id=provider_id)
    value = overrides.get("requires_interleaved_thinking")
    return value if isinstance(value, bool) else None


def infer_reasoning_support(
    model_id: str,
    provider_id: str | None = None,
) -> bool | None:
    overrides = infer_capability_overrides(model_id, provider_id=provider_id)
    value = overrides.get("reasoning")
    return value if isinstance(value, bool) else None


def infer_function_calling_support(
    model_id: str,
    provider_id: str | None = None,
) -> bool | None:
    overrides = infer_capability_overrides(model_id, provider_id=provider_id)
    value = overrides.get("function_calling")
    return value if isinstance(value, bool) else None


def infer_reasoning_controls(
    model_id: str,
    provider_id: str | None = None,
) -> dict[str, Any] | None:
    overrides = infer_capability_overrides(model_id, provider_id=provider_id)
    value = overrides.get("reasoning_controls")
    return value if isinstance(value, dict) else None


def apply_model_capability_hints(
    model_id: str,
    capabilities: dict[str, Any] | None,
    *,
    provider_defaults: dict[str, Any] | None = None,
    provider_id: str | None = None,
) -> dict[str, Any] | None:
    """Apply sparse fallback hints without overriding explicit capability metadata."""
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
    capabilities: dict[str, Any] | None,
    *,
    provider_defaults: dict[str, Any] | None = None,
    provider_id: str | None = None,
) -> dict[str, Any] | None:
    """Backward-compatible alias for older call sites."""
    return apply_model_capability_hints(
        model_id,
        capabilities,
        provider_defaults=provider_defaults,
        provider_id=provider_id,
    )
