"""Data types for committee orchestration."""

from dataclasses import dataclass, field
from typing import Literal

CommitteeAction = Literal["speak", "parallel_speak", "finish"]


@dataclass(frozen=True)
class CommitteeRuntimeConfig:
    """Runtime configuration for committee orchestration."""

    supervisor_id: str
    max_rounds: int = 3


@dataclass
class CommitteeTurnRecord:
    """A completed assistant turn in committee mode."""

    assistant_id: str
    assistant_name: str
    content_preview: str
    message_id: str | None = None
    key_points: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    actions: list[str] = field(default_factory=list)
    self_summary: str = ""


@dataclass
class CommitteeRuntimeState:
    """Mutable state used by committee runtime and supervisor."""

    user_message: str
    participants: dict[str, str]
    round_index: int = 0
    turns: list[CommitteeTurnRecord] = field(default_factory=list)
    member_notes: dict[str, str] = field(default_factory=dict)


@dataclass
class CommitteeDecision:
    """Supervisor decision for the next orchestration action."""

    action: CommitteeAction
    reason: str = ""
    assistant_id: str | None = None
    assistant_ids: list[str] | None = None
    instruction: str | None = None
    final_response: str | None = None
