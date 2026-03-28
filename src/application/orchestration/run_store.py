"""Checkpoint storage backends for orchestration runs."""

from __future__ import annotations

import asyncio
import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from src.core.paths import data_state_dir

from .checkpoint import RunCheckpoint


class RunStore(ABC):
    """Persistence contract for orchestration checkpoints."""

    @abstractmethod
    async def append_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        """Persist one checkpoint for a run."""
        raise NotImplementedError

    @abstractmethod
    async def get_checkpoint(self, *, run_id: str, checkpoint_id: str) -> RunCheckpoint | None:
        """Fetch one checkpoint by id within one run."""
        raise NotImplementedError

    @abstractmethod
    async def get_latest_checkpoint(self, *, run_id: str) -> RunCheckpoint | None:
        """Fetch the most recent checkpoint for one run."""
        raise NotImplementedError

    @abstractmethod
    async def list_checkpoints(self, *, run_id: str, limit: int = 200) -> list[RunCheckpoint]:
        """List checkpoints by sequence ascending."""
        raise NotImplementedError

    @abstractmethod
    async def clear_run(self, *, run_id: str) -> None:
        """Delete all checkpoints for one run."""
        raise NotImplementedError


class InMemoryRunStore(RunStore):
    """In-memory checkpoint store for tests/local runtime."""

    def __init__(self):
        self._by_run: dict[str, list[RunCheckpoint]] = {}
        self._by_id: dict[str, dict[str, RunCheckpoint]] = {}
        self._lock = asyncio.Lock()

    async def append_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        async with self._lock:
            self._by_run.setdefault(checkpoint.run_id, []).append(checkpoint)
            self._by_id.setdefault(checkpoint.run_id, {})[checkpoint.checkpoint_id] = checkpoint

    async def get_checkpoint(self, *, run_id: str, checkpoint_id: str) -> RunCheckpoint | None:
        async with self._lock:
            return self._by_id.get(run_id, {}).get(checkpoint_id)

    async def get_latest_checkpoint(self, *, run_id: str) -> RunCheckpoint | None:
        async with self._lock:
            checkpoints = self._by_run.get(run_id, [])
            if not checkpoints:
                return None
            return checkpoints[-1]

    async def list_checkpoints(self, *, run_id: str, limit: int = 200) -> list[RunCheckpoint]:
        safe_limit = max(1, int(limit))
        async with self._lock:
            checkpoints = self._by_run.get(run_id, [])
            return list(checkpoints[:safe_limit])

    async def clear_run(self, *, run_id: str) -> None:
        async with self._lock:
            self._by_run.pop(run_id, None)
            self._by_id.pop(run_id, None)


class SqliteRunStore(RunStore):
    """SQLite-backed checkpoint store for runtime recovery."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = Path(
            db_path or (data_state_dir() / "orchestration" / "runtime_checkpoints.sqlite3")
        )
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=30, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS orchestration_checkpoints (
                        checkpoint_id TEXT PRIMARY KEY,
                        run_id TEXT NOT NULL,
                        seq INTEGER NOT NULL,
                        step INTEGER NOT NULL,
                        event_type TEXT NOT NULL,
                        node_id TEXT,
                        actor_id TEXT,
                        next_node_id TEXT,
                        branch TEXT,
                        terminal_status TEXT,
                        terminal_reason TEXT,
                        payload_json TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        created_at TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_orch_checkpoints_run_seq
                    ON orchestration_checkpoints (run_id, seq)
                    """
                )
                conn.commit()

    async def append_checkpoint(self, checkpoint: RunCheckpoint) -> None:
        await asyncio.to_thread(self._append_checkpoint_sync, checkpoint)

    def _append_checkpoint_sync(self, checkpoint: RunCheckpoint) -> None:
        payload = asdict(checkpoint)
        payload_json = json.dumps(payload["payload"], ensure_ascii=False)
        metadata_json = json.dumps(payload["metadata"], ensure_ascii=False)
        created_at = checkpoint.created_at.isoformat()
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO orchestration_checkpoints (
                        checkpoint_id,
                        run_id,
                        seq,
                        step,
                        event_type,
                        node_id,
                        actor_id,
                        next_node_id,
                        branch,
                        terminal_status,
                        terminal_reason,
                        payload_json,
                        metadata_json,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        checkpoint.checkpoint_id,
                        checkpoint.run_id,
                        int(checkpoint.seq),
                        int(checkpoint.step),
                        checkpoint.event_type,
                        checkpoint.node_id,
                        checkpoint.actor_id,
                        checkpoint.next_node_id,
                        checkpoint.branch,
                        checkpoint.terminal_status,
                        checkpoint.terminal_reason,
                        payload_json,
                        metadata_json,
                        created_at,
                    ),
                )
                conn.commit()

    async def get_checkpoint(self, *, run_id: str, checkpoint_id: str) -> RunCheckpoint | None:
        return await asyncio.to_thread(
            self._get_checkpoint_sync,
            run_id,
            checkpoint_id,
        )

    def _get_checkpoint_sync(self, run_id: str, checkpoint_id: str) -> RunCheckpoint | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM orchestration_checkpoints
                    WHERE run_id = ? AND checkpoint_id = ?
                    LIMIT 1
                    """,
                    (run_id, checkpoint_id),
                ).fetchone()
        return self._row_to_checkpoint(row) if row else None

    async def get_latest_checkpoint(self, *, run_id: str) -> RunCheckpoint | None:
        return await asyncio.to_thread(self._get_latest_checkpoint_sync, run_id)

    def _get_latest_checkpoint_sync(self, run_id: str) -> RunCheckpoint | None:
        with self._lock:
            with self._connect() as conn:
                row = conn.execute(
                    """
                    SELECT * FROM orchestration_checkpoints
                    WHERE run_id = ?
                    ORDER BY seq DESC, created_at DESC
                    LIMIT 1
                    """,
                    (run_id,),
                ).fetchone()
        return self._row_to_checkpoint(row) if row else None

    async def list_checkpoints(self, *, run_id: str, limit: int = 200) -> list[RunCheckpoint]:
        safe_limit = max(1, int(limit))
        return await asyncio.to_thread(self._list_checkpoints_sync, run_id, safe_limit)

    def _list_checkpoints_sync(self, run_id: str, limit: int) -> list[RunCheckpoint]:
        with self._lock:
            with self._connect() as conn:
                rows = conn.execute(
                    """
                    SELECT * FROM orchestration_checkpoints
                    WHERE run_id = ?
                    ORDER BY seq ASC, created_at ASC
                    LIMIT ?
                    """,
                    (run_id, limit),
                ).fetchall()
        return [self._row_to_checkpoint(row) for row in rows]

    async def clear_run(self, *, run_id: str) -> None:
        await asyncio.to_thread(self._clear_run_sync, run_id)

    def _clear_run_sync(self, run_id: str) -> None:
        with self._lock:
            with self._connect() as conn:
                conn.execute(
                    "DELETE FROM orchestration_checkpoints WHERE run_id = ?",
                    (run_id,),
                )
                conn.commit()

    @staticmethod
    def _row_to_checkpoint(row: sqlite3.Row) -> RunCheckpoint:
        created_at_raw = str(row["created_at"])
        try:
            created_at = datetime.fromisoformat(created_at_raw)
        except ValueError:
            created_at = datetime.now(timezone.utc)
        return RunCheckpoint(
            checkpoint_id=str(row["checkpoint_id"]),
            run_id=str(row["run_id"]),
            seq=int(row["seq"]),
            step=int(row["step"]),
            event_type=str(row["event_type"]),
            node_id=row["node_id"],
            actor_id=row["actor_id"],
            next_node_id=row["next_node_id"],
            branch=row["branch"],
            terminal_status=row["terminal_status"],
            terminal_reason=row["terminal_reason"],
            payload=json.loads(row["payload_json"] or "{}"),
            metadata=json.loads(row["metadata_json"] or "{}"),
            created_at=created_at,
        )
