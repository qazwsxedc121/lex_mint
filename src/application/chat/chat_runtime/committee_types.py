"""Data types for committee orchestration."""

from dataclasses import dataclass, field
from typing import Dict, List, Literal, Optional


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
    message_id: Optional[str] = None
    key_points: List[str] = field(default_factory=list)
    risks: List[str] = field(default_factory=list)
    actions: List[str] = field(default_factory=list)
    self_summary: str = ""


@dataclass
class CommitteeRuntimeState:
    """Mutable state used by committee runtime and supervisor."""

    user_message: str
    participants: Dict[str, str]
    round_index: int = 0
    turns: List[CommitteeTurnRecord] = field(default_factory=list)
    member_notes: Dict[str, str] = field(default_factory=dict)


@dataclass
class CommitteeDecision:
    """Supervisor decision for the next orchestration action."""

    action: CommitteeAction
    reason: str = ""
    assistant_id: Optional[str] = None
    assistant_ids: Optional[List[str]] = None
    instruction: Optional[str] = None
    final_response: Optional[str] = None
