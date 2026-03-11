"""File-backed storage service for async run records."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import List, Optional

import aiofiles

from src.api.models.async_run import AsyncRunRecord, RunKind, RunStatus
from src.core.paths import data_state_dir


class AsyncRunStoreService:
    """Persist/query async run records under data/state/async_runs."""

    _lock = asyncio.Lock()
    _replace_retry_delays = (0.02, 0.05, 0.1)

    def __init__(self, base_dir: Optional[Path] = None):
        self.base_dir = Path(base_dir or (data_state_dir() / "async_runs"))
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _path_for_run(self, run_id: str) -> Path:
        return self.base_dir / f"run_{run_id}.json"

    async def save_run(self, record: AsyncRunRecord) -> None:
        """Upsert one run record."""
        path = self._path_for_run(record.run_id)
        temp_path = path.with_suffix(".json.tmp")
        payload = record.model_dump(mode="json")
        async with self._lock:
            async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
                await f.write(json.dumps(payload, ensure_ascii=False, indent=2))
            await self._replace_with_retry(temp_path, path)

    async def get_run(self, run_id: str) -> Optional[AsyncRunRecord]:
        """Return one run by id."""
        path = self._path_for_run(run_id)
        async with self._lock:
            if not path.exists():
                return None
            async with aiofiles.open(path, "r", encoding="utf-8") as f:
                content = await f.read()
            if not content.strip():
                return None
            data = json.loads(content)
            return AsyncRunRecord(**data)

    async def list_runs(
        self,
        *,
        limit: int = 50,
        kind: Optional[RunKind] = None,
        status: Optional[RunStatus] = None,
        context_type: Optional[str] = None,
        project_id: Optional[str] = None,
        session_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
    ) -> List[AsyncRunRecord]:
        """List runs ordered by updated_at descending."""
        safe_limit = max(1, min(int(limit), 200))
        records: List[AsyncRunRecord] = []
        async with self._lock:
            for path in sorted(
                self.base_dir.glob("run_*.json"),
                key=lambda item: item.stat().st_mtime,
                reverse=True,
            ):
                try:
                    async with aiofiles.open(path, "r", encoding="utf-8") as f:
                        content = await f.read()
                    if not content.strip():
                        continue
                    record = AsyncRunRecord(**json.loads(content))
                except Exception:
                    continue

                if kind and record.kind != kind:
                    continue
                if status and record.status != status:
                    continue
                if context_type and record.context_type != context_type:
                    continue
                if project_id and (record.project_id or "") != project_id:
                    continue
                if session_id and (record.session_id or "") != session_id:
                    continue
                if workflow_id and (record.workflow_id or "") != workflow_id:
                    continue

                records.append(record)
                if len(records) >= safe_limit:
                    break
        return records

    async def _replace_with_retry(self, src: Path, dst: Path) -> None:
        last_error: Optional[Exception] = None
        for delay in self._replace_retry_delays:
            try:
                src.replace(dst)
                return
            except PermissionError as exc:
                last_error = exc
                await asyncio.sleep(delay)
        if last_error is not None:
            raise last_error
        src.replace(dst)
