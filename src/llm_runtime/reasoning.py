"""Reasoning-mode resolution helpers for streaming LLM calls."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReasoningDecision:
    """Resolved reasoning controls passed to the provider adapter."""

    requested_mode: str
    thinking_enabled: bool
    disable_thinking: bool
    effective_reasoning_option: Optional[str]
    effective_reasoning_effort: Optional[str]


def build_reasoning_decision_payload(
    *,
    session_id: str,
    provider_id: str,
    model_id: str,
    call_mode: str,
    requested_reasoning_mode: str,
    capabilities: Any,
    reasoning_controls: Any,
    thinking_enabled: bool,
    disable_thinking: bool,
    effective_reasoning_option: Optional[str],
    effective_reasoning_effort: Optional[str],
) -> Dict[str, Any]:
    """Build a structured reasoning decision log payload."""
    def _coerce_bool(value: Any, default: bool = False) -> bool:
        return value if isinstance(value, bool) else default

    def _coerce_str(value: Any) -> Optional[str]:
        if value is None:
            return None
        return value if isinstance(value, str) else None

    raw_options = getattr(reasoning_controls, "options", []) if reasoning_controls is not None else []
    options = [str(option) for option in raw_options] if isinstance(raw_options, list) else []
    controls_mode = getattr(reasoning_controls, "mode", None) if reasoning_controls is not None else None
    controls_param = getattr(reasoning_controls, "param", None) if reasoning_controls is not None else None
    disable_supported = (
        getattr(reasoning_controls, "disable_supported", None)
        if reasoning_controls is not None
        else None
    )
    requires_interleaved = _coerce_bool(getattr(capabilities, "requires_interleaved_thinking", False))

    return {
        "session_id": session_id,
        "provider_id": provider_id,
        "model_id": model_id,
        "call_mode": call_mode,
        "requested_reasoning_mode": requested_reasoning_mode or "default",
        "capabilities_reasoning": _coerce_bool(getattr(capabilities, "reasoning", False)),
        "requires_interleaved_thinking": requires_interleaved,
        "reasoning_controls": {
            "mode": _coerce_str(controls_mode),
            "param": _coerce_str(controls_param),
            "options": options,
            "disable_supported": disable_supported if isinstance(disable_supported, bool) else None,
        },
        "decision": {
            "thinking_enabled": thinking_enabled,
            "disable_thinking": disable_thinking,
            "effective_reasoning_option": effective_reasoning_option,
            "effective_reasoning_effort": effective_reasoning_effort,
        },
        "adapter_args": {
            "thinking_enabled": thinking_enabled,
            "reasoning_option": effective_reasoning_option,
            "reasoning_effort": effective_reasoning_effort,
            "disable_thinking": disable_thinking,
            "requires_interleaved_thinking": requires_interleaved,
        },
    }


def log_reasoning_decision(
    *,
    session_id: str,
    provider_id: str,
    model_id: str,
    call_mode: str,
    capabilities: Any,
    reasoning_controls: Any,
    decision: ReasoningDecision,
) -> None:
    """Emit the structured reasoning decision log."""
    payload = build_reasoning_decision_payload(
        session_id=session_id,
        provider_id=provider_id,
        model_id=model_id,
        call_mode=call_mode,
        requested_reasoning_mode=decision.requested_mode,
        capabilities=capabilities,
        reasoning_controls=reasoning_controls,
        thinking_enabled=decision.thinking_enabled,
        disable_thinking=decision.disable_thinking,
        effective_reasoning_option=decision.effective_reasoning_option,
        effective_reasoning_effort=decision.effective_reasoning_effort,
    )
    logger.info("Reasoning decision: %s", json.dumps(payload, ensure_ascii=True, sort_keys=True))


def resolve_reasoning_decision(
    *,
    capabilities: Any,
    reasoning_effort: Optional[str],
    model_id: str,
) -> ReasoningDecision:
    """Resolve reasoning request into adapter-ready flags."""
    reasoning_mode = (reasoning_effort or "").strip().lower()
    explicit_disable_reasoning = reasoning_mode == "none"

    reasoning_controls = getattr(capabilities, "reasoning_controls", None)
    reasoning_controls_mode: Optional[str] = None
    if reasoning_controls is not None:
        raw_mode = getattr(reasoning_controls, "mode", None)
        if isinstance(raw_mode, str):
            reasoning_controls_mode = raw_mode.strip().lower()
        else:
            raw_mode_value = getattr(raw_mode, "value", None)
            if isinstance(raw_mode_value, str):
                reasoning_controls_mode = raw_mode_value.strip().lower()

    disable_reasoning_supported = True
    if reasoning_controls is not None:
        raw_disable_supported = getattr(reasoning_controls, "disable_supported", True)
        if isinstance(raw_disable_supported, bool):
            disable_reasoning_supported = raw_disable_supported

    disable_thinking = explicit_disable_reasoning and disable_reasoning_supported
    raw_reasoning_options = getattr(reasoning_controls, "options", []) if reasoning_controls is not None else []
    options_iterable = raw_reasoning_options if isinstance(raw_reasoning_options, list) else []
    allowed_reasoning_options = [
        str(option).strip().lower()
        for option in options_iterable
        if str(option).strip()
    ]

    thinking_enabled = False
    effective_reasoning_effort: Optional[str] = None
    effective_reasoning_option: Optional[str] = None

    if explicit_disable_reasoning:
        if not disable_reasoning_supported:
            logger.warning("Reasoning disable is not supported for %s; ignoring 'none'", model_id)
        else:
            logger.info("Reasoning explicitly disabled for %s", model_id)
    elif reasoning_mode and reasoning_mode != "default":
        if not getattr(capabilities, "reasoning", False):
            logger.warning(
                "Model %s does not support reasoning mode, ignoring reasoning_effort=%s",
                model_id,
                reasoning_mode,
            )
        elif allowed_reasoning_options:
            if reasoning_mode in allowed_reasoning_options:
                thinking_enabled = True
                effective_reasoning_option = reasoning_mode
                if reasoning_controls_mode == "enum":
                    effective_reasoning_effort = reasoning_mode
                logger.info(
                    "Thinking mode enabled for %s (%s=%s)",
                    model_id,
                    reasoning_controls.param if reasoning_controls else "reasoning",
                    effective_reasoning_option,
                )
            elif reasoning_controls_mode == "toggle" and reasoning_mode in {"low", "medium", "high", "minimal"}:
                thinking_enabled = True
                effective_reasoning_option = allowed_reasoning_options[0]
                logger.info(
                    "Mapped legacy reasoning option '%s' to toggle value '%s' for %s",
                    reasoning_mode,
                    effective_reasoning_option,
                    model_id,
                )
            else:
                logger.warning(
                    "Unsupported reasoning option '%s' for %s; allowed=%s",
                    reasoning_mode,
                    model_id,
                    ",".join(allowed_reasoning_options),
                )
        elif reasoning_mode in {"low", "medium", "high", "minimal"}:
            thinking_enabled = True
            effective_reasoning_option = reasoning_mode
            effective_reasoning_effort = reasoning_mode
            logger.info("Thinking mode enabled for %s (effort: %s)", model_id, effective_reasoning_effort)
        else:
            logger.warning(
                "Unknown reasoning_effort '%s', falling back to model default behavior",
                reasoning_mode,
            )

    return ReasoningDecision(
        requested_mode=reasoning_mode,
        thinking_enabled=thinking_enabled,
        disable_thinking=disable_thinking,
        effective_reasoning_option=effective_reasoning_option,
        effective_reasoning_effort=effective_reasoning_effort,
    )
