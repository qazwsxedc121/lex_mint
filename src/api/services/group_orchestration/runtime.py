"""Committee runtime primitives for multi-assistant orchestration."""

from .types import CommitteeRuntimeConfig, CommitteeRuntimeState, CommitteeTurnRecord


class CommitteeRuntime:
    """Tracks committee rounds and records assistant outputs."""

    def __init__(self, config: CommitteeRuntimeConfig):
        self.config = config

    def has_remaining_rounds(self, state: CommitteeRuntimeState) -> bool:
        """Whether another speak round can still be executed."""
        return state.round_index < self.config.max_rounds

    def current_round(self, state: CommitteeRuntimeState) -> int:
        """1-based round index currently being orchestrated."""
        return state.round_index + 1

    def record_turn(self, state: CommitteeRuntimeState, turn: CommitteeTurnRecord) -> None:
        """Persist one completed turn and advance round count."""
        state.turns.append(turn)
        if turn.self_summary:
            state.member_notes[turn.assistant_id] = turn.self_summary
        state.round_index += 1
