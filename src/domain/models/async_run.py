"""Async run models for background workflow/chat execution."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Literal, Optional

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
    project_id: Optional[str] = None
    session_id: Optional[str] = None
    workflow_id: Optional[str] = None

    created_at: datetime
    updated_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    request_payload: Dict[str, Any] = Field(default_factory=dict)
    result_summary: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str] = None

    last_event_id: Optional[str] = None
    last_seq: int = 0


class AsyncRunListResponse(BaseModel):
    """List response wrapper for async runs."""

    runs: list[AsyncRunRecord] = Field(default_factory=list)

