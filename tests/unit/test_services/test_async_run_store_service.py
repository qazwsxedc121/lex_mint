from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.api.models.async_run import AsyncRunRecord, RunStatus
from src.api.services.async_run_store_service import AsyncRunStoreService


def _make_record(*, run_id: str, status: RunStatus, workflow_id: str) -> AsyncRunRecord:
    now = datetime.now(timezone.utc)
    return AsyncRunRecord(
        run_id=run_id,
        stream_id=run_id,
        kind="workflow",
        status=status,
        context_type="workflow",
        workflow_id=workflow_id,
        created_at=now,
        updated_at=now,
        request_payload={"inputs": {"input": run_id}},
    )


@pytest.mark.asyncio
async def test_async_run_store_save_get_and_list_filters(tmp_path):
    store = AsyncRunStoreService(base_dir=tmp_path / "async_runs")

    record_one = _make_record(run_id="run-1", status="running", workflow_id="wf-a")
    record_two = _make_record(run_id="run-2", status="succeeded", workflow_id="wf-b")
    await store.save_run(record_one)
    await store.save_run(record_two)

    loaded = await store.get_run("run-1")
    assert loaded is not None
    assert loaded.run_id == "run-1"
    assert loaded.workflow_id == "wf-a"

    running = await store.list_runs(limit=10, status="running")
    assert [item.run_id for item in running] == ["run-1"]

    wf_b = await store.list_runs(limit=10, workflow_id="wf-b")
    assert [item.run_id for item in wf_b] == ["run-2"]


@pytest.mark.asyncio
async def test_async_run_store_retries_replace_on_permission_error(tmp_path, monkeypatch):
    store = AsyncRunStoreService(base_dir=tmp_path / "async_runs")
    record = _make_record(run_id="run-retry", status="running", workflow_id="wf-r")

    original_replace = Path.replace
    state = {"calls": 0}

    def flaky_replace(self: Path, target: Path):
        if self.name.endswith(".json.tmp") and state["calls"] == 0:
            state["calls"] += 1
            raise PermissionError("file is busy")
        return original_replace(self, target)

    monkeypatch.setattr(Path, "replace", flaky_replace)

    await store.save_run(record)
    loaded = await store.get_run("run-retry")
    assert loaded is not None
    assert loaded.run_id == "run-retry"
    assert state["calls"] == 1
