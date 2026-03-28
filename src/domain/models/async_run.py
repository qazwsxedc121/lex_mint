"""Async run models for background workflow/chat execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

RunKind = Literal["workflow", "chat"]
RunStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]


class AsyncRunRecord(BaseModel):
    """Persisted async run record."""

    run_id: str
    stream_id: str
    kind: RunKind
    status: RunStatus

    context_type: Literal["workflow", "chat", "project"] = "workflow"
    project_id: str | None = None
    session_id: str | None = None
    workflow_id: str | None = None

    created_at: datetime
    updated_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    request_payload: dict[str, Any] = Field(default_factory=dict)
    result_summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None

    last_event_id: str | None = None
    last_seq: int = 0


class AsyncRunListResponse(BaseModel):
    """List response wrapper for async runs."""

    runs: list[AsyncRunRecord] = Field(default_factory=list)
