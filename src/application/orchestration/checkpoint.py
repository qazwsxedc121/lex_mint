"""Checkpoint models for orchestration runtime recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass(frozen=True)
class RunCheckpoint:
    """One persisted checkpoint emitted by the orchestration engine."""

    checkpoint_id: str
    run_id: str
    seq: int
    step: int
    event_type: str
    node_id: Optional[str] = None
    actor_id: Optional[str] = None
    next_node_id: Optional[str] = None
    branch: Optional[str] = None
    terminal_status: Optional[str] = None
    terminal_reason: Optional[str] = None
    payload: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
