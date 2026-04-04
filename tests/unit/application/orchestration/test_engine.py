from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

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
            NodeSpec(
                node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=_start_actor)
            ),
            NodeSpec(
                node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=_end_actor)
            ),
        ),
        edges=(EdgeSpec(source_id="start", target_id="end"),),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    event_types = [event["type"] for event in events]
    assert event_types == [
        "started",
        "node_started",
        "node_finished",
        "node_started",
        "node_finished",
        "completed",
    ]
    assert events[-1]["terminal_reason"] == "done"


def test_validate_run_spec_rejects_unreachable_nodes():
    spec = RunSpec(
        run_id="run-graph",
        entry_node_id="start",
        nodes=(
            NodeSpec(
                node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=_start_actor)
            ),
            NodeSpec(
                node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=_end_actor)
            ),
            NodeSpec(
                node_id="orphan", actor=ActorRef(actor_id="orphan", kind="test", handler=_end_actor)
            ),
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
            NodeSpec(
                node_id="loop", actor=ActorRef(actor_id="loop", kind="test", handler=loop_actor)
            ),
        ),
        edges=(EdgeSpec(source_id="loop", target_id="loop"),),
    )
    validate_run_spec(spec)

    engine = OrchestrationEngine()
    events = [
        event async for event in engine.run_stream(spec, RunContext(run_id="run-loop", max_steps=5))
    ]

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
    context = RunContext(
        run_id="run-cancel", cancel_event=cancel_event, cancel_reason="user cancelled"
    )

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
            NodeSpec(
                node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=_start_actor)
            ),
            NodeSpec(
                node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=_end_actor)
            ),
        ),
        edges=(EdgeSpec(source_id="start", target_id="end"),),
    )
    engine = OrchestrationEngine(run_store=store)

    events = [event async for event in engine.run_stream(spec)]
    checkpoints = await store.list_checkpoints(run_id="run-with-checkpoints")

    assert len(checkpoints) >= 6
    assert checkpoints[0].event_type == "started"
    assert checkpoints[-1].event_type == "completed"
    assert all(
        "checkpoint_id" in event
        for event in events
        if event["type"] in {"started", "node_started", "node_finished", "completed"}
    )


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
            NodeSpec(
                node_id="start", actor=ActorRef(actor_id="start", kind="test", handler=start_actor)
            ),
            NodeSpec(node_id="end", actor=ActorRef(actor_id="end", kind="test", handler=end_actor)),
        ),
        edges=(EdgeSpec(source_id="start", target_id="end"),),
    )
    store = InMemoryRunStore()
    engine = OrchestrationEngine(run_store=store)

    _ = [event async for event in engine.run_stream(spec)]
    checkpoints = await store.list_checkpoints(run_id="run-resume")
    start_finished = next(
        item
        for item in checkpoints
        if item.event_type == "node_finished" and item.node_id == "start"
    )

    resumed_events = [
        event
        async for event in engine.resume_stream(
            spec,
            from_checkpoint_id=start_finished.checkpoint_id,
        )
    ]

    assert resumed_events[0]["type"] == "resumed"
    assert resumed_events[1]["type"] == "node_started"
    assert resumed_events[1]["node_id"] == "end"
    assert state["start_calls"] == 1
    assert state["end_calls"] == 2


@pytest.mark.asyncio
async def test_engine_resume_requires_run_store():
    spec = RunSpec(
        run_id="run-resume-no-store",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=_end_actor),
            ),
        ),
    )
    engine = OrchestrationEngine()

    with pytest.raises(ValueError, match="Cannot resume run without a RunStore"):
        _ = [event async for event in engine.resume_stream(spec, from_checkpoint_id="cp-1")]


@pytest.mark.asyncio
async def test_engine_resume_from_terminal_checkpoint_returns_terminal_event():
    state = {"calls": 0}

    async def terminal_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        state["calls"] += 1
        yield ActorResult(
            terminal_status="completed",
            terminal_reason="done",
            payload={"result": "ok"},
        )

    spec = RunSpec(
        run_id="run-resume-terminal",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=terminal_actor),
            ),
        ),
    )
    store = InMemoryRunStore()
    engine = OrchestrationEngine(run_store=store)

    _ = [event async for event in engine.run_stream(spec)]
    checkpoints = await store.list_checkpoints(run_id="run-resume-terminal")
    terminal_checkpoint = checkpoints[-1]

    resumed_events = [
        event
        async for event in engine.resume_stream(
            spec,
            from_checkpoint_id=terminal_checkpoint.checkpoint_id,
        )
    ]

    assert state["calls"] == 1
    assert resumed_events[0]["type"] == "resumed"
    assert resumed_events[1]["type"] == "completed"
    assert resumed_events[1]["payload"] == {"result": "ok"}
    assert resumed_events[1]["terminal_reason"] == "done"


@pytest.mark.asyncio
async def test_engine_does_not_retry_when_runtime_events_already_emitted():
    state = {"attempt": 0}

    async def emits_then_fails(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        state["attempt"] += 1
        yield ActorEmit(event_type="partial", payload={"text": "hello"})
        raise TimeoutError("temporary timeout")

    spec = RunSpec(
        run_id="run-no-retry-after-events",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=emits_then_fails),
                retry_policy=RetryPolicy(
                    max_retries=2,
                    backoff_ms=0,
                    retry_only_if_no_events=True,
                    is_retryable=lambda exc: isinstance(exc, TimeoutError),
                ),
            ),
        ),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    assert state["attempt"] == 1
    assert not any(event["type"] == "node_retrying" for event in events)
    assert events[-1]["type"] == "failed"
    assert "temporary timeout" in events[-1]["terminal_reason"]


@pytest.mark.asyncio
async def test_engine_resolve_next_node_uses_branch_result():
    async def branch_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        yield ActorResult(branch="yes")

    async def yes_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        yield ActorResult(terminal_status="completed", terminal_reason="yes branch")

    async def no_actor(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        yield ActorResult(terminal_status="completed", terminal_reason="no branch")

    spec = RunSpec(
        run_id="run-branch",
        entry_node_id="decide",
        nodes=(
            NodeSpec(
                node_id="decide",
                actor=ActorRef(actor_id="decide", kind="test", handler=branch_actor),
            ),
            NodeSpec(node_id="yes", actor=ActorRef(actor_id="yes", kind="test", handler=yes_actor)),
            NodeSpec(node_id="no", actor=ActorRef(actor_id="no", kind="test", handler=no_actor)),
        ),
        edges=(
            EdgeSpec(source_id="decide", target_id="no", branch=None),
            EdgeSpec(source_id="decide", target_id="yes", branch="yes"),
        ),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    decide_finished = next(
        event for event in events if event["type"] == "node_finished" and event["node_id"] == "decide"
    )
    assert decide_finished["payload"] == {}
    assert decide_finished["node_id"] == "decide"
    assert events[-1]["type"] == "completed"
    assert events[-1]["terminal_reason"] == "yes branch"


@pytest.mark.asyncio
async def test_engine_fails_when_next_node_missing():
    async def jump_to_missing(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        yield ActorResult(next_node_id="ghost-node")

    spec = RunSpec(
        run_id="run-missing-node",
        entry_node_id="start",
        nodes=(
            NodeSpec(
                node_id="start",
                actor=ActorRef(actor_id="start", kind="test", handler=jump_to_missing),
            ),
        ),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    assert events[-1]["type"] == "failed"
    assert events[-1]["node_id"] == "ghost-node"
    assert "does not exist" in events[-1]["terminal_reason"]


@pytest.mark.asyncio
async def test_engine_fails_when_node_does_not_resolve_next_node():
    async def no_next(_: object) -> AsyncIterator[ActorEmit | ActorResult]:
        yield ActorResult()

    spec = RunSpec(
        run_id="run-no-next",
        entry_node_id="start",
        nodes=(
            NodeSpec(
                node_id="start",
                actor=ActorRef(actor_id="start", kind="test", handler=no_next),
            ),
        ),
    )
    engine = OrchestrationEngine()

    events = [event async for event in engine.run_stream(spec)]

    assert events[-1]["type"] == "failed"
    assert events[-1]["node_id"] == "start"
    assert "did not resolve next node" in events[-1]["terminal_reason"]


@pytest.mark.asyncio
async def test_engine_resume_with_unknown_checkpoint_raises():
    store = InMemoryRunStore()
    spec = RunSpec(
        run_id="run-resume-unknown-checkpoint",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=_end_actor),
            ),
        ),
    )
    engine = OrchestrationEngine(run_store=store)

    with pytest.raises(ValueError, match="not found"):
        _ = [
            event
            async for event in engine.resume_stream(
                spec,
                from_checkpoint_id="checkpoint-does-not-exist",
            )
        ]


@pytest.mark.asyncio
async def test_engine_resume_without_checkpoints_raises():
    store = InMemoryRunStore()
    spec = RunSpec(
        run_id="run-resume-no-checkpoints",
        entry_node_id="node-1",
        nodes=(
            NodeSpec(
                node_id="node-1",
                actor=ActorRef(actor_id="node-1", kind="test", handler=_end_actor),
            ),
        ),
    )
    engine = OrchestrationEngine(run_store=store)
    context = RunContext(run_id="run-resume-no-checkpoints", metadata={"resume": True})

    with pytest.raises(ValueError, match="has no persisted checkpoints"):
        _ = [event async for event in engine.resume_stream(spec, context=context)]


def test_engine_static_backoff_delay_and_reason_normalization():
    assert (
        OrchestrationEngine._compute_backoff_delay_ms(
            base_delay_ms=100,
            retry_index=1,
            max_backoff_ms=1000,
        )
        == 100
    )
    assert (
        OrchestrationEngine._compute_backoff_delay_ms(
            base_delay_ms=1000,
            retry_index=4,
            max_backoff_ms=1500,
        )
        == 1500
    )
    assert (
        OrchestrationEngine._normalize_reason("  ", fallback="failed") == "failed"
    )
