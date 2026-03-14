from __future__ import annotations

from pathlib import Path

import pytest

from src.application.orchestration import InMemoryRunStore, RunCheckpoint, SqliteRunStore


@pytest.mark.asyncio
async def test_in_memory_run_store_round_trip_and_latest():
    store = InMemoryRunStore()

    first = RunCheckpoint(
        checkpoint_id="cp-1",
        run_id="run-1",
        seq=1,
        step=0,
        event_type="started",
    )
    second = RunCheckpoint(
        checkpoint_id="cp-2",
        run_id="run-1",
        seq=2,
        step=1,
        event_type="node_started",
        node_id="n1",
    )

    await store.append_checkpoint(first)
    await store.append_checkpoint(second)

    listed = await store.list_checkpoints(run_id="run-1")
    assert [item.checkpoint_id for item in listed] == ["cp-1", "cp-2"]

    latest = await store.get_latest_checkpoint(run_id="run-1")
    assert latest is not None
    assert latest.checkpoint_id == "cp-2"

    fetched = await store.get_checkpoint(run_id="run-1", checkpoint_id="cp-1")
    assert fetched is not None
    assert fetched.event_type == "started"


@pytest.mark.asyncio
async def test_sqlite_run_store_round_trip(tmp_path: Path):
    db_path = tmp_path / "orchestration_checkpoints.sqlite3"
    store = SqliteRunStore(db_path=db_path)

    checkpoint = RunCheckpoint(
        checkpoint_id="cp-sqlite-1",
        run_id="run-sqlite",
        seq=1,
        step=0,
        event_type="started",
        metadata={"mode": "test"},
    )
    await store.append_checkpoint(checkpoint)

    latest = await store.get_latest_checkpoint(run_id="run-sqlite")
    assert latest is not None
    assert latest.checkpoint_id == "cp-sqlite-1"
    assert latest.metadata["mode"] == "test"

    listed = await store.list_checkpoints(run_id="run-sqlite")
    assert len(listed) == 1
    assert listed[0].run_id == "run-sqlite"

    await store.clear_run(run_id="run-sqlite")
    assert await store.get_latest_checkpoint(run_id="run-sqlite") is None
