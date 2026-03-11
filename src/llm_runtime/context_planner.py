"""Budget-aware context planning for prompt assembly."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence


def _default_optional_segment_ratios() -> Dict[str, float]:
    return {
        "memory": 0.16,
        "rag": 0.18,
        "webpage": 0.10,
        "search": 0.10,
        "sources": 0.08,
    }


def _default_min_segment_tokens_by_name() -> Dict[str, int]:
    return {
        "sources": 32,
    }


@dataclass(frozen=True)
class ContextPlannerPolicy:
    approx_chars_per_token: int = 4
    history_floor_ratio: float = 0.35
    min_history_floor_tokens: int = 128
    summary_max_ratio: float = 0.15
    min_summary_tokens: int = 32
    optional_segment_ratios: Dict[str, float] = field(default_factory=_default_optional_segment_ratios)
    default_optional_segment_ratio: float = 0.08
    min_segment_tokens: int = 24
    min_segment_tokens_by_name: Dict[str, int] = field(default_factory=_default_min_segment_tokens_by_name)


@dataclass(frozen=True)
class PlannedSegment:
    name: str
    kind: str
    included: bool
    content: str = ""
    estimated_tokens_before: int = 0
    estimated_tokens_after: int = 0
    truncated: bool = False
    drop_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "kind": self.kind,
            "included": self.included,
            "estimated_tokens_before": self.estimated_tokens_before,
            "estimated_tokens_after": self.estimated_tokens_after,
            "truncated": self.truncated,
            "drop_reason": self.drop_reason,
        }


@dataclass(frozen=True)
class ContextUsageSummary:
    context_budget: int
    estimated_prompt_tokens: int
    remaining_tokens: int


@dataclass(frozen=True)
class ContextPlan:
    system_segments: List[PlannedSegment]
    chat_messages: List[Dict[str, Any]]
    segment_reports: List[PlannedSegment]
    usage_summary: ContextUsageSummary


class ContextPlanner:
    """Plans prompt assembly before the final LangChain safety trim."""

    def __init__(self, *, policy: Optional[ContextPlannerPolicy] = None):
        self.policy = policy or ContextPlannerPolicy()

    def _estimate_text_tokens(self, text: Optional[str]) -> int:
        cleaned = (text or "").strip()
        if not cleaned:
            return 0
        chars_per_token = max(1, int(self.policy.approx_chars_per_token or 1))
        return max(1, len(cleaned) // chars_per_token)

    def _estimate_message_tokens(self, messages: Sequence[Dict[str, Any]]) -> int:
        total = 0
        for msg in messages:
            role = msg.get("role", "")
            if role not in ("user", "assistant"):
                continue
            usage = msg.get("usage") if role == "assistant" else None
            if isinstance(usage, dict):
                completion_tokens = usage.get("completion_tokens")
                if isinstance(completion_tokens, int) and completion_tokens > 0:
                    total += completion_tokens
                    continue
            total += self._estimate_text_tokens(str(msg.get("content") or ""))
        return total

    def _truncate_text_to_tokens(self, text: Optional[str], max_tokens: int) -> str:
        cleaned = (text or "").strip()
        if not cleaned:
            return ""
        if max_tokens <= 0:
            return ""

        estimated = self._estimate_text_tokens(cleaned)
        if estimated <= max_tokens:
            return cleaned

        chars_per_token = max(1, int(self.policy.approx_chars_per_token or 1))
        max_chars = max(1, max_tokens * chars_per_token)
        if len(cleaned) <= max_chars:
            return cleaned
        if max_chars <= 3:
            return cleaned[:max_chars]
        return cleaned[: max_chars - 3].rstrip() + "..."

    @staticmethod
    def _truncate_messages_by_rounds(messages: List[Dict[str, Any]], max_rounds: Optional[int]) -> List[Dict[str, Any]]:
        if not max_rounds or max_rounds <= 0:
            return list(messages)

        human_indexes = [
            index for index, msg in enumerate(messages)
            if msg.get("role") == "user"
        ]
        if len(human_indexes) <= max_rounds:
            return list(messages)

        start_index = human_indexes[-max_rounds]
        return list(messages[start_index:])

    def _plan_segment(
        self,
        *,
        name: str,
        kind: str,
        content: Optional[str],
        max_tokens: int,
        required: bool = False,
    ) -> PlannedSegment:
        estimated_before = self._estimate_text_tokens(content)
        cleaned = (content or "").strip()
        if not cleaned:
            return PlannedSegment(
                name=name,
                kind=kind,
                included=False,
                estimated_tokens_before=0,
                estimated_tokens_after=0,
                drop_reason="empty",
            )

        min_tokens = self.policy.min_segment_tokens_by_name.get(name, self.policy.min_segment_tokens)
        if max_tokens < min_tokens and not required:
            return PlannedSegment(
                name=name,
                kind=kind,
                included=False,
                estimated_tokens_before=estimated_before,
                estimated_tokens_after=0,
                drop_reason="budget_exhausted",
            )

        truncated_content = self._truncate_text_to_tokens(cleaned, max_tokens)
        estimated_after = self._estimate_text_tokens(truncated_content)
        return PlannedSegment(
            name=name,
            kind=kind,
            included=bool(truncated_content),
            content=truncated_content,
            estimated_tokens_before=estimated_before,
            estimated_tokens_after=estimated_after,
            truncated=estimated_after < estimated_before,
            drop_reason=None if truncated_content else "budget_exhausted",
        )

    def plan(
        self,
        *,
        context_budget_tokens: int,
        base_system_prompt: Optional[str],
        compressed_history_summary: Optional[str],
        recent_messages: List[Dict[str, Any]],
        max_rounds: Optional[int] = None,
        memory_context: Optional[str] = None,
        webpage_context: Optional[str] = None,
        search_context: Optional[str] = None,
        rag_context: Optional[str] = None,
        structured_source_context: Optional[str] = None,
    ) -> ContextPlan:
        budget = max(1, int(context_budget_tokens or 0))
        planned_messages = self._truncate_messages_by_rounds(recent_messages, max_rounds)
        history_tokens = self._estimate_message_tokens(planned_messages)
        history_report = PlannedSegment(
            name="history",
            kind="history",
            included=bool(planned_messages),
            estimated_tokens_before=history_tokens,
            estimated_tokens_after=history_tokens,
            truncated=len(planned_messages) < len(recent_messages),
            drop_reason=None,
        )

        system_segment = self._plan_segment(
            name="system",
            kind="system",
            content=base_system_prompt,
            max_tokens=max(1, self._estimate_text_tokens(base_system_prompt)),
            required=True,
        )

        history_floor = (
            min(
                history_tokens,
                max(self.policy.min_history_floor_tokens, int(budget * self.policy.history_floor_ratio)),
            )
            if history_tokens
            else 0
        )
        summary_budget = max(self.policy.min_summary_tokens, int(budget * self.policy.summary_max_ratio))
        summary_segment = self._plan_segment(
            name="summary",
            kind="summary",
            content=compressed_history_summary,
            max_tokens=summary_budget,
            required=bool(compressed_history_summary),
        )

        reserved_tokens = (
            system_segment.estimated_tokens_after
            + summary_segment.estimated_tokens_after
            + history_floor
        )
        remaining_pool = max(0, budget - reserved_tokens)

        optional_segments: List[PlannedSegment] = []
        for name, kind, content in [
            ("memory", "context", memory_context),
            ("rag", "context", rag_context),
            ("webpage", "context", webpage_context),
            ("search", "context", search_context),
            ("sources", "context", structured_source_context),
        ]:
            estimated_before = self._estimate_text_tokens(content)
            if not content or estimated_before <= 0:
                optional_segments.append(
                    PlannedSegment(
                        name=name,
                        kind=kind,
                        included=False,
                        estimated_tokens_before=0,
                        estimated_tokens_after=0,
                        drop_reason="empty",
                    )
                )
                continue

            cap_tokens = max(
                self.policy.min_segment_tokens,
                int(budget * self.policy.optional_segment_ratios.get(name, self.policy.default_optional_segment_ratio)),
            )
            allowance = min(cap_tokens, remaining_pool) if remaining_pool > 0 else 0
            segment = self._plan_segment(
                name=name,
                kind=kind,
                content=content,
                max_tokens=allowance,
            )
            optional_segments.append(segment)
            remaining_pool = max(0, remaining_pool - segment.estimated_tokens_after)

        system_segments = [
            segment
            for segment in [system_segment, summary_segment, *optional_segments]
            if segment.included
        ]
        estimated_prompt_tokens = history_tokens + sum(segment.estimated_tokens_after for segment in system_segments)
        usage_summary = ContextUsageSummary(
            context_budget=budget,
            estimated_prompt_tokens=estimated_prompt_tokens,
            remaining_tokens=budget - estimated_prompt_tokens,
        )

        return ContextPlan(
            system_segments=system_segments,
            chat_messages=planned_messages,
            segment_reports=[system_segment, summary_segment, history_report, *optional_segments],
            usage_summary=usage_summary,
        )
