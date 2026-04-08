"""Regex tool-gate evaluator for single-chat tool resolution."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

_RE_FLAG_MAP = {
    "i": re.IGNORECASE,
    "m": re.MULTILINE,
    "s": re.DOTALL,
}


@dataclass(frozen=True)
class ToolGateDecision:
    """Evaluation result for one user message."""

    final_allowed_tool_names: set[str]
    matched_rule_id: str | None = None
    matched_rule_priority: int | None = None
    applied: bool = False
    reason: str = "disabled_or_no_match"


def _compile_flags(flags: str) -> int:
    compiled = 0
    for char in str(flags or "").strip().lower():
        compiled |= _RE_FLAG_MAP.get(char, 0)
    return compiled


class ToolGateService:
    """Apply regex rules to filter allowed tool names for a request."""

    def apply(
        self,
        *,
        candidate_tool_names: set[str],
        user_message: str,
        config: Any,
    ) -> ToolGateDecision:
        base_allowed = {str(name) for name in candidate_tool_names if str(name).strip()}
        if not bool(getattr(config, "enabled", False)):
            return ToolGateDecision(final_allowed_tool_names=base_allowed)

        rules = list(getattr(config, "rules", []) or [])
        enabled_rules = [rule for rule in rules if bool(getattr(rule, "enabled", True))]
        enabled_rules.sort(
            key=lambda rule: int(getattr(rule, "priority", 0)),
            reverse=True,
        )

        message_text = str(user_message or "")
        for rule in enabled_rules:
            pattern = str(getattr(rule, "pattern", "") or "").strip()
            if not pattern:
                continue
            try:
                compiled = re.compile(pattern, _compile_flags(getattr(rule, "flags", "")))
            except re.error as exc:
                logger.warning(
                    "Skipping invalid tool-gate regex (id=%s): %s",
                    getattr(rule, "id", "(unknown)"),
                    exc,
                )
                continue
            if compiled.search(message_text) is None:
                continue

            include_tools = {
                str(name).strip()
                for name in list(getattr(rule, "include_tools", []) or [])
                if str(name).strip()
            }
            exclude_tools = {
                str(name).strip()
                for name in list(getattr(rule, "exclude_tools", []) or [])
                if str(name).strip()
            }

            allowed = set(base_allowed)
            if include_tools:
                allowed &= include_tools
            if exclude_tools:
                allowed -= exclude_tools

            return ToolGateDecision(
                final_allowed_tool_names=allowed,
                matched_rule_id=str(getattr(rule, "id", "") or "") or None,
                matched_rule_priority=int(getattr(rule, "priority", 0)),
                applied=True,
                reason="matched_rule",
            )

        return ToolGateDecision(
            final_allowed_tool_names=base_allowed,
            reason="no_rule_matched",
        )
