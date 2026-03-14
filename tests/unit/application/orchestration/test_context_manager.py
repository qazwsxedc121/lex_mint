from __future__ import annotations

import pytest

from src.application.orchestration import InMemoryContextManager


@pytest.mark.asyncio
async def test_context_manager_isolates_by_run_actor_and_namespace():
    manager = InMemoryContextManager()

    await manager.write(
        run_id="run-1",
        actor_id="actor-a",
        namespace="default",
        payload={"value": 1},
    )
    await manager.write(
        run_id="run-1",
        actor_id="actor-b",
        namespace="default",
        payload={"value": 2},
    )
    await manager.write(
        run_id="run-2",
        actor_id="actor-a",
        namespace="default",
        payload={"value": 3},
    )
    await manager.write(
        run_id="run-1",
        actor_id="actor-a",
        namespace="meta",
        payload={"flag": True},
    )

    scope_1 = await manager.read(run_id="run-1", actor_id="actor-a", namespace="default")
    scope_2 = await manager.read(run_id="run-1", actor_id="actor-b", namespace="default")
    scope_3 = await manager.read(run_id="run-2", actor_id="actor-a", namespace="default")
    scope_4 = await manager.read(run_id="run-1", actor_id="actor-a", namespace="meta")

    assert scope_1 == {"value": 1}
    assert scope_2 == {"value": 2}
    assert scope_3 == {"value": 3}
    assert scope_4 == {"flag": True}


@pytest.mark.asyncio
async def test_context_manager_patch_merges_values():
    manager = InMemoryContextManager()

    await manager.write(
        run_id="run-1",
        actor_id="actor-a",
        namespace="default",
        payload={"a": 1},
    )
    patched = await manager.patch(
        run_id="run-1",
        actor_id="actor-a",
        namespace="default",
        payload={"b": 2},
    )

    assert patched == {"a": 1, "b": 2}
    assert await manager.read(run_id="run-1", actor_id="actor-a", namespace="default") == {
        "a": 1,
        "b": 2,
    }
