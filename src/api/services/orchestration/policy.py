"""Policy helpers for committee orchestration limits and depth gates."""

from typing import Dict, Optional


class CommitteePolicy:
    """Pure policy helpers so orchestration logic can stay focused on control flow."""

    @staticmethod
    def resolve_group_round_limit(
        raw_limit: Optional[int],
        *,
        fallback: int = 3,
        hard_cap: int = 6,
    ) -> int:
        """Normalize assistant max_rounds for committee orchestration loops."""
        if raw_limit is None:
            return fallback
        if raw_limit == -1:
            return fallback
        try:
            value = int(raw_limit)
        except Exception:
            return fallback
        if value <= 0:
            return fallback
        return min(value, hard_cap)

    @staticmethod
    def resolve_committee_round_policy(
        raw_limit: Optional[int],
        *,
        participant_count: int,
    ) -> Dict[str, int]:
        """Derive round/depth policy for committee mode to avoid premature convergence."""
        member_count = max(participant_count - 1, 0)
        min_member_turns_before_finish = 2 if member_count >= 2 else 1
        min_total_rounds_before_finish = member_count * min_member_turns_before_finish
        fallback_rounds = max(6, min_total_rounds_before_finish)
        max_rounds = CommitteePolicy.resolve_group_round_limit(
            raw_limit,
            fallback=fallback_rounds,
            hard_cap=18,
        )
        if member_count > 0:
            max_rounds = max(max_rounds, min_total_rounds_before_finish)
        return {
            "max_rounds": max_rounds,
            "min_member_turns_before_finish": min_member_turns_before_finish,
            "min_total_rounds_before_finish": min_total_rounds_before_finish,
        }

