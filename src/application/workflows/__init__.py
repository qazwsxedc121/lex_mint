"""Workflow application layer exports."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .execution_service import WorkflowExecutionService
    from .run_history_service import WorkflowRunHistoryService


__all__ = ["WorkflowExecutionService", "WorkflowRunHistoryService"]


def __getattr__(name: str) -> Any:
    if name == "WorkflowExecutionService":
        from .execution_service import WorkflowExecutionService

        return WorkflowExecutionService
    if name == "WorkflowRunHistoryService":
        from .run_history_service import WorkflowRunHistoryService

        return WorkflowRunHistoryService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
