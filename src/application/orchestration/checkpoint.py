"""Checkpoint models for orchestration runtime recovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class RunCheckpoint:
    """One persisted checkpoint emitted by the orchestration engine."""

    checkpoint_id: str
    run_id: str
    seq: int
    step: int
    event_type: str
    node_id: str | None = None
    actor_id: str | None = None
    next_node_id: str | None = None
    branch: str | None = None
    terminal_status: str | None = None
    terminal_reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
