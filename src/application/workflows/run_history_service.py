"""Workflow run history storage service."""

from __future__ import annotations

import asyncio
import json
import re
from pathlib import Path
from typing import List, Optional

import aiofiles

from src.domain.models.workflow import WorkflowRunHistory, WorkflowRunRecord
from src.core.paths import data_state_dir


def _safe_workflow_id(workflow_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]", "_", workflow_id.strip())


class WorkflowRunHistoryService:
    """Persist and query workflow run history per workflow id."""

    _locks: dict[str, asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    def __init__(self, history_dir: Optional[Path] = None, max_runs_per_workflow: int = 50):
        if history_dir is None:
            history_dir = data_state_dir() / "workflow_runs"
        self.history_dir = Path(history_dir)
        self.max_runs_per_workflow = max(1, int(max_runs_per_workflow))
        self.history_dir.mkdir(parents=True, exist_ok=True)

    def _history_path(self, workflow_id: str) -> Path:
        return self.history_dir / f"{_safe_workflow_id(workflow_id)}.json"

    async def _get_lock(self, workflow_id: str) -> asyncio.Lock:
        key = str(self._history_path(workflow_id).resolve())
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def _read_history(self, workflow_id: str) -> WorkflowRunHistory:
        path = self._history_path(workflow_id)
        if not path.exists():
            return WorkflowRunHistory(runs=[])
        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()
        if not content.strip():
            return WorkflowRunHistory(runs=[])
        data = json.loads(content)
        if "runs" not in data:
            data["runs"] = []
        return WorkflowRunHistory(**data)

    async def _write_history(self, workflow_id: str, history: WorkflowRunHistory) -> None:
        path = self._history_path(workflow_id)
        temp_path = path.with_suffix(".json.tmp")
        async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
            payload = history.model_dump(mode="json")
            await f.write(json.dumps(payload, ensure_ascii=False, indent=2))
        temp_path.replace(path)

    async def append_run(self, record: WorkflowRunRecord) -> None:
        """Append one run record and keep latest N entries."""
        lock = await self._get_lock(record.workflow_id)
        async with lock:
            history = await self._read_history(record.workflow_id)
            history.runs.insert(0, record)
            history.runs = history.runs[: self.max_runs_per_workflow]
            await self._write_history(record.workflow_id, history)

    async def list_runs(self, workflow_id: str, limit: int = 50) -> List[WorkflowRunRecord]:
        """Return latest run records for a workflow."""
        history = await self._read_history(workflow_id)
        safe_limit = max(1, min(int(limit), self.max_runs_per_workflow))
        return history.runs[:safe_limit]

    async def get_run(self, workflow_id: str, run_id: str) -> Optional[WorkflowRunRecord]:
        """Return one run record by id."""
        history = await self._read_history(workflow_id)
        for record in history.runs:
            if record.run_id == run_id:
                return record
        return None

    async def delete_runs(self, workflow_id: str) -> None:
        """Delete all run history for one workflow."""
        lock = await self._get_lock(workflow_id)
        async with lock:
            path = self._history_path(workflow_id)
            if path.exists():
                path.unlink()
