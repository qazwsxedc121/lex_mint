from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from src.application.orchestration import (
    ActorEmit,
    ActorRef,
    ActorResult,
    EdgeSpec,
    InMemoryRunStore,
    NodeSpec,
    OrchestrationEngine,
    RetryPolicy,
    RunContext,
    RunSpec,
    validate_run_spec,
)


async def _start_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
    yield ActorResult(next_node_id="end")


async def _end_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
    yield ActorResult(terminal_status="completed", terminal_reason="done")


@pytest.mark.asyncio
async def test_engine_runs_graph_and_emits_terminal_reason():
    spec = RunSpec(
        run_id="run-1",
        entry_node_id="start",
        nodes=(
            NodeSpec(node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=_start_actor)),
            NodeSpec(node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=_end_actor)),
        ),
        edges=(EdgeSpec(source_id="start", target_id="end"),),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    event_types = [event["type"] for event in events]
    assert event_types == ["started", "node_started", "node_finished", "node_started", "node_finished", "completed"]
    assert events[-1]["terminal_reason"] == "done"


def test_validate_run_spec_rejects_unreachable_nodes():
    spec = RunSpec(
        run_id="run-graph",
        entry_node_id="start",
        nodes=(
            NodeSpec(node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=_start_actor)),
            NodeSpec(node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=_end_actor)),
            NodeSpec(node_id="orphan", actor=ActorRef(actor_id="orphan", kind="test", handler=_end_actor)),
        ),
        edges=(EdgeSpec(source_id="start", target_id="end"),),
    )

    with pytest.raises(ValueError, match="unreachable"):
        validate_run_spec(spec)


@pytest.mark.asyncio
async def test_engine_allows_static_cycle_graphs_bounded_by_terminal_signal():
    state = {"calls": 0}

    async def loop_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        state["calls"] += 1
        if state["calls"] < 3:
            yield ActorResult(next_node_id="loop")
            return
        yield ActorResult(terminal_status="completed", terminal_reason="done")

    spec = RunSpec(
        run_id="run-loop",
        entry_node_id="loop",
        nodes=(
            NodeSpec(node_id="loop", actor=ActorRef(actor_id="loop", kind="test", handler=loop_actor)),
        ),
        edges=(EdgeSpec(source_id="loop", target_id="loop"),),
    )
    validate_run_spec(spec)

    engine = OrchestrationEngine()
    events = [event async for event in engine.run_stream(spec, RunContext(run_id="run-loop", max_steps=5))]

    assert state["calls"] == 3
    assert events[-1]["type"] == "completed"
    assert events[-1]["terminal_reason"] == "done"


@pytest.mark.asyncio
async def test_engine_retries_retryable_errors_and_emits_retrying_event():
    state = {"attempt": 0}

    async def flaky_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        state["attempt"] += 1
        if state["attempt"] == 1:
            raise TimeoutError("temporary timeout")
        yield ActorEmit(event_type="text_delta", payload={"text": "ok"})
        yield ActorResult(terminal_status="completed", terminal_reason="done")

    spec = RunSpec(
        run_id="run-retry",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=flaky_actor),
                retry_policy=RetryPolicy(
                    max_retries=1,
                    backoff_ms=0,
                    retry_only_if_no_events=True,
                    is_retryable=lambda exc: isinstance(exc, TimeoutError),
                ),
            ),
        ),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    assert state["attempt"] == 2
    assert any(event["type"] == "node_retrying" for event in events)
    assert events[-1]["type"] == "completed"


@pytest.mark.asyncio
async def test_engine_honors_node_timeout():
    async def slow_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        await asyncio.sleep(0.05)
        yield ActorResult(terminal_status="completed", terminal_reason="done")

    spec = RunSpec(
        run_id="run-timeout",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=slow_actor),
                timeout_ms=10,
                retry_policy=RetryPolicy(
                    max_retries=0,
                    is_retryable=lambda exc: isinstance(exc, TimeoutError),
                ),
            ),
        ),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    assert events[-1]["type"] == "failed"
    assert "timed out after 10 ms" in events[-1]["terminal_reason"]


@pytest.mark.asyncio
async def test_engine_stops_when_cancelled():
    cancel_event = asyncio.Event()
    cancel_event.set()

    spec = RunSpec(
        run_id="run-cancel",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=_end_actor),
            ),
        ),
    )
    engine = OrchestrationEngine()
    context = RunContext(run_id="run-cancel", cancel_event=cancel_event, cancel_reason="user cancelled")

    events = [event async for event in engine.run_stream(spec, context)]

    assert [event["type"] for event in events] == ["started", "cancelled"]
    assert events[-1]["terminal_reason"] == "user cancelled"


@pytest.mark.asyncio
async def test_engine_persists_checkpoints_for_lifecycle_events():
    store = InMemoryRunStore()
    spec = RunSpec(
        run_id="run-with-checkpoints",
        entry_node_id="start",
        nodes=(
            NodeSpec(node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=_start_actor)),
            NodeSpec(node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=_end_actor)),
        ),
        edges=(EdgeSpec(source_id="start", target_id="end"),),
    )
    engine = OrchestrationEngine(run_store=store)

    events = [event async for event in engine.run_stream(spec)]
    checkpoints = await store.list_checkpoints(run_id="run-with-checkpoints")

    assert len(checkpoints) >= 6
    assert checkpoints[0].event_type == "started"
    assert checkpoints[-1].event_type == "completed"
    assert all("checkpoint_id" in event for event in events if event["type"] in {"started", "node_started", "node_finished", "completed"})


@pytest.mark.asyncio
async def test_engine_resume_from_node_finished_checkpoint():
    state = {"start_calls": 0, "end_calls": 0}

    async def start_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        state["start_calls"] += 1
        yield ActorResult(next_node_id="end")

    async def end_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        state["end_calls"] += 1
        yield ActorResult(terminal_status="completed", terminal_reason="done")

    spec = RunSpec(
        run_id="run-resume",
        entry_node_id="start",
        nodes=(
            NodeSpec(node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=start_actor)),
            NodeSpec(node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=end_actor)),
        ),
        edges=(EdgeSpec(source_id="start", target_id="end"),),
    )
    store = InMemoryRunStore()
    engine = OrchestrationEngine(run_store=store)

    _ = [event async for event in engine.run_stream(spec)]
    checkpoints = await store.list_checkpoints(run_id="run-resume")
    start_finished = next(
        item for item in checkpoints
        if item.event_type == "node_finished" and item.node_id == "start"
    )

    resumed_events = [
        event async for event in engine.resume_stream(
            spec,
            from_checkpoint_id=start_finished.checkpoint_id,
        )
    ]

    assert resumed_events[0]["type"] == "resumed"
    assert resumed_events[1]["type"] == "node_started"
    assert resumed_events[1]["node_id"] == "end"
    assert state["start_calls"] == 1
    assert state["end_calls"] == 2
