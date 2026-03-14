from __future__ import annotations

import asyncio
from typing import AsyncIterator

import pytest

from src.application.orchestration import (
    ActorEmit,
    ActorRef,
    ActorResult,
    EdgeSpec,
    NodeSpec,
    OrchestrationEngine,
    RetryPolicy,
    RunContext,
    RunSpec,
    validate_run_spec,
)


async def _start_actor(_: object) -> AsyncIterator[object]:
    yield ActorResult(next_node_id="end")


async def _end_actor(_: object) -> AsyncIterator[object]:
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
async def test_engine_retries_retryable_errors_and_emits_retrying_event():
    state = {"attempt": 0}

    async def flaky_actor(_: object) -> AsyncIterator[object]:
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
    async def slow_actor(_: object) -> AsyncIterator[object]:
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
