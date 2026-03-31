"""Universal graph orchestration runtime."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
import uuid
from collections.abc import AsyncIterator, Awaitable
from dataclasses import dataclass
from typing import Any, cast

from .checkpoint import RunCheckpoint
from .context_manager import InMemoryContextManager
from .ir import (
    ActorEmit,
    ActorExecutionContext,
    ActorResult,
    ActorSignal,
    EdgeSpec,
    NodeSpec,
    RunContext,
    RunSpec,
    validate_run_spec,
)
from .run_store import RunStore


class _NodeTimeoutError(Exception):
    """Raised when one node attempt exceeds configured timeout."""


class _RunCancelledError(Exception):
    """Raised for cooperative cancellation."""


@dataclass
class _RunExecutionState:
    run_id: str
    node_map: dict[str, NodeSpec]
    edges_by_source: dict[str, list[EdgeSpec]]
    max_steps: int
    run_store: RunStore | None
    checkpoint_seq: int = 0
    step: int = 0
    current_node_id: str | None = None


@dataclass
class _NodeExecutionOutcome:
    result: ActorResult | None = None
    terminal_event: dict[str, Any] | None = None


class OrchestrationEngine:
    """Execute one graph run and emit lifecycle/runtime events."""

    def __init__(
        self,
        *,
        default_max_steps: int = 1000,
        run_store: RunStore | None = None,
    ):
        self.default_max_steps = max(1, int(default_max_steps))
        self.run_store = run_store

    async def run_stream(
        self,
        spec: RunSpec,
        context: RunContext | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Run a graph and stream lifecycle events from the entry node."""

        async for event in self._run_stream_internal(
            spec=spec,
            context=context,
            resume_from_checkpoint_id=None,
        ):
            yield event

    async def resume_stream(
        self,
        spec: RunSpec,
        *,
        context: RunContext | None = None,
        from_checkpoint_id: str | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """Resume one run from a persisted checkpoint."""

        async for event in self._run_stream_internal(
            spec=spec,
            context=context,
            resume_from_checkpoint_id=from_checkpoint_id,
        ):
            yield event

    def _prepare_run_state(
        self,
        *,
        spec: RunSpec,
        context: RunContext | None,
    ) -> tuple[RunContext, _RunExecutionState]:
        validate_run_spec(spec)

        run_context = context or RunContext(run_id=spec.run_id)
        if not run_context.run_id:
            run_context.run_id = spec.run_id
        if run_context.context_manager is None:
            run_context.context_manager = InMemoryContextManager()

        return run_context, _RunExecutionState(
            run_id=run_context.run_id,
            node_map={node.node_id: node for node in spec.nodes},
            edges_by_source=self._index_edges(spec.edges),
            max_steps=max(1, int(run_context.max_steps or self.default_max_steps)),
            run_store=run_context.run_store or self.run_store,
            current_node_id=spec.entry_node_id,
        )

    async def _start_or_resume_run(
        self,
        *,
        spec: RunSpec,
        run_context: RunContext,
        state: _RunExecutionState,
        resume_from_checkpoint_id: str | None,
    ) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
        if resume_from_checkpoint_id is None and not run_context.metadata.get("resume", False):
            started_event = await self._build_started_event(
                state=state,
                metadata=dict(spec.metadata),
            )
            return [started_event], None

        if state.run_store is None:
            raise ValueError("Cannot resume run without a RunStore")

        checkpoint = await self._resolve_resume_checkpoint(
            run_store=state.run_store,
            run_id=state.run_id,
            checkpoint_id=resume_from_checkpoint_id,
        )
        state.checkpoint_seq = checkpoint.seq
        state.step = checkpoint.step
        state.current_node_id = self._resolve_resume_node(
            checkpoint=checkpoint,
            entry_node_id=spec.entry_node_id,
            edges_by_source=state.edges_by_source,
        )
        resumed_event = {
            "type": "resumed",
            "run_id": state.run_id,
            "checkpoint_id": checkpoint.checkpoint_id,
            "from_event_type": checkpoint.event_type,
            "node_id": state.current_node_id,
            "step": state.step,
        }
        terminal_event = await self._resume_terminal_event(state=state, checkpoint=checkpoint)
        return [resumed_event], terminal_event

    async def _build_started_event(
        self,
        *,
        state: _RunExecutionState,
        metadata: dict[str, Any],
    ) -> dict[str, Any]:
        next_seq = self._advance_checkpoint_seq(state)
        checkpoint_id = await self._save_checkpoint(
            run_store=state.run_store,
            run_id=state.run_id,
            seq=next_seq,
            step=state.step,
            event_type="started",
            metadata=metadata,
        )
        event = {
            "type": "started",
            "run_id": state.run_id,
            "metadata": metadata,
        }
        if checkpoint_id:
            event["checkpoint_id"] = checkpoint_id
        return event

    async def _resume_terminal_event(
        self,
        *,
        state: _RunExecutionState,
        checkpoint: RunCheckpoint,
    ) -> dict[str, Any] | None:
        if checkpoint.event_type not in {"completed", "failed", "cancelled"}:
            return None
        terminal_status = checkpoint.terminal_status or checkpoint.event_type
        terminal_reason = self._normalize_reason(
            checkpoint.terminal_reason,
            fallback=terminal_status,
        )
        return {
            "type": terminal_status,
            "run_id": state.run_id,
            "terminal_reason": terminal_reason,
            "payload": dict(checkpoint.payload),
            "checkpoint_id": checkpoint.checkpoint_id,
        }

    async def _build_terminal_event(
        self,
        *,
        state: _RunExecutionState,
        event_type: str,
        terminal_reason: str,
        node_id: str | None = None,
        actor_id: str | None = None,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        next_seq = self._advance_checkpoint_seq(state)
        checkpoint_id = await self._save_checkpoint(
            run_store=state.run_store,
            run_id=state.run_id,
            seq=next_seq,
            step=state.step,
            event_type=event_type,
            node_id=node_id,
            actor_id=actor_id,
            terminal_status=event_type,
            terminal_reason=terminal_reason,
            payload=payload,
        )
        event = {
            "type": event_type,
            "run_id": state.run_id,
            "terminal_reason": terminal_reason,
        }
        if node_id is not None:
            event["node_id"] = node_id
        if payload is not None:
            event["payload"] = dict(payload)
        elif event_type in {"completed", "failed", "cancelled"} and "payload" not in event:
            event["payload"] = {}
        if checkpoint_id:
            event["checkpoint_id"] = checkpoint_id
        return event

    async def _checkpointed_node_event(
        self,
        *,
        state: _RunExecutionState,
        event_type: str,
        node: NodeSpec,
        next_node_id: str | None = None,
        branch: str | None = None,
        payload: dict[str, Any] | None = None,
        terminal_status: str | None = None,
        terminal_reason: str | None = None,
    ) -> dict[str, Any]:
        next_seq = self._advance_checkpoint_seq(state)
        checkpoint_id = await self._save_checkpoint(
            run_store=state.run_store,
            run_id=state.run_id,
            seq=next_seq,
            step=state.step,
            event_type=event_type,
            node_id=node.node_id,
            actor_id=node.actor.actor_id,
            next_node_id=next_node_id,
            branch=branch,
            payload=payload,
            terminal_status=terminal_status,
            terminal_reason=terminal_reason,
        )
        event = {
            "type": event_type,
            "run_id": state.run_id,
            "node_id": node.node_id,
            "actor_id": node.actor.actor_id,
        }
        if payload is not None:
            event["payload"] = dict(payload)
        if checkpoint_id:
            event["checkpoint_id"] = checkpoint_id
        return event

    @staticmethod
    def _advance_checkpoint_seq(state: _RunExecutionState) -> int:
        state.checkpoint_seq += 1
        return state.checkpoint_seq

    async def _pre_node_terminal_event(
        self,
        *,
        state: _RunExecutionState,
        run_context: RunContext,
    ) -> dict[str, Any] | None:
        if run_context.is_cancelled:
            reason = self._normalize_reason(run_context.cancel_reason, fallback="cancelled")
            return await self._build_terminal_event(
                state=state,
                event_type="cancelled",
                terminal_reason=reason,
            )

        state.step += 1
        if state.step <= state.max_steps:
            return None

        reason = f"run exceeded max steps ({state.max_steps}), possible loop detected"
        return await self._build_terminal_event(
            state=state,
            event_type="failed",
            terminal_reason=reason,
        )

    async def _missing_node_terminal_event(
        self,
        *,
        state: _RunExecutionState,
        node_id: str,
    ) -> dict[str, Any]:
        return await self._build_terminal_event(
            state=state,
            event_type="failed",
            terminal_reason=f"node '{node_id}' does not exist",
            node_id=node_id,
        )

    async def _execute_node_stream(
        self,
        *,
        state: _RunExecutionState,
        run_context: RunContext,
        node: NodeSpec,
        outcome: _NodeExecutionOutcome,
    ) -> AsyncIterator[dict[str, Any]]:
        max_attempts = node.retry_policy.max_retries + 1
        for attempt in range(1, max_attempts + 1):
            emitted_runtime_events = False
            stream: AsyncIterator[ActorSignal] | None = None
            try:
                execution_context = ActorExecutionContext(
                    run_id=state.run_id,
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                    run_context=run_context,
                    metadata=dict(node.metadata),
                )
                result = ActorResult()
                stream = node.actor.handler(execution_context)

                async def _iterate_signals(
                    active_stream: AsyncIterator[ActorSignal] = stream,
                ) -> AsyncIterator[dict[str, Any]]:
                    nonlocal result
                    nonlocal emitted_runtime_events
                    async for signal in active_stream:
                        if run_context.is_cancelled:
                            raise _RunCancelledError(run_context.cancel_reason)
                        if isinstance(signal, ActorEmit):
                            emitted_runtime_events = True
                            yield {
                                "type": "node_event",
                                "run_id": state.run_id,
                                "node_id": node.node_id,
                                "actor_id": node.actor.actor_id,
                                "event_type": signal.event_type,
                                "payload": dict(signal.payload),
                            }
                            continue
                        if isinstance(signal, ActorResult):
                            result = signal
                            continue
                        raise ValueError(
                            f"Actor '{node.actor.actor_id}' returned unsupported signal type "
                            f"'{type(signal).__name__}'"
                        )

                if node.timeout_ms is None:
                    async for event in _iterate_signals():
                        yield event
                else:
                    timeout_seconds = max(1, int(node.timeout_ms)) / 1000.0
                    try:
                        async with asyncio.timeout(timeout_seconds):
                            async for event in _iterate_signals():
                                yield event
                    except TimeoutError as exc:
                        if str(exc):
                            raise
                        raise _NodeTimeoutError(
                            f"node '{node.node_id}' timed out after {node.timeout_ms} ms"
                        ) from exc

                outcome.result = result
                break
            except _RunCancelledError as exc:
                reason = self._normalize_reason(str(exc), fallback="cancelled")
                outcome.terminal_event = await self._build_terminal_event(
                    state=state,
                    event_type="cancelled",
                    terminal_reason=reason,
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                )
                return
            except Exception as exc:
                if attempt < max_attempts and self._should_retry(
                    node=node,
                    error=exc,
                    emitted_runtime_events=emitted_runtime_events,
                ):
                    delay_ms = self._compute_backoff_delay_ms(
                        base_delay_ms=node.retry_policy.backoff_ms,
                        retry_index=attempt,
                        max_backoff_ms=node.retry_policy.max_backoff_ms,
                    )
                    yield {
                        "type": "node_retrying",
                        "run_id": state.run_id,
                        "node_id": node.node_id,
                        "actor_id": node.actor.actor_id,
                        "attempt": attempt + 1,
                        "max_attempts": max_attempts,
                        "delay_ms": delay_ms,
                        "error": str(exc),
                    }
                    if delay_ms > 0:
                        await asyncio.sleep(delay_ms / 1000.0)
                    continue

                reason = self._normalize_reason(str(exc), fallback="node_failed")
                outcome.terminal_event = await self._build_terminal_event(
                    state=state,
                    event_type="failed",
                    terminal_reason=reason,
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                )
                return
            finally:
                if stream is not None:
                    await self._close_stream(stream)
        else:
            outcome.terminal_event = await self._build_terminal_event(
                state=state,
                event_type="failed",
                terminal_reason=f"node '{node.node_id}' failed after retries",
                node_id=node.node_id,
                actor_id=node.actor.actor_id,
            )

    async def _run_stream_internal(
        self,
        *,
        spec: RunSpec,
        context: RunContext | None,
        resume_from_checkpoint_id: str | None,
    ) -> AsyncIterator[dict[str, Any]]:
        run_context, state = self._prepare_run_state(spec=spec, context=context)
        initial_events, terminal_event = await self._start_or_resume_run(
            spec=spec,
            run_context=run_context,
            state=state,
            resume_from_checkpoint_id=resume_from_checkpoint_id,
        )
        for event in initial_events:
            yield event
        if terminal_event is not None:
            yield terminal_event
            return

        while state.current_node_id:
            terminal_event = await self._pre_node_terminal_event(
                state=state,
                run_context=run_context,
            )
            if terminal_event is not None:
                yield terminal_event
                return

            node = state.node_map.get(state.current_node_id)
            if node is None:
                yield await self._missing_node_terminal_event(
                    state=state,
                    node_id=str(state.current_node_id),
                )
                return

            yield await self._checkpointed_node_event(
                state=state,
                event_type="node_started",
                node=node,
            )

            outcome = _NodeExecutionOutcome()
            async for event in self._execute_node_stream(
                state=state,
                run_context=run_context,
                node=node,
                outcome=outcome,
            ):
                yield event
            if outcome.terminal_event is not None:
                yield outcome.terminal_event
                return

            result = outcome.result or ActorResult()
            next_node_id = result.next_node_id
            if result.terminal_status is None and next_node_id is None:
                next_node_id = self._resolve_next_node(
                    node_id=node.node_id,
                    branch=result.branch,
                    edges_by_source=state.edges_by_source,
                )

            yield await self._checkpointed_node_event(
                state=state,
                event_type="node_finished",
                node=node,
                next_node_id=next_node_id,
                branch=result.branch,
                payload=dict(result.payload),
                terminal_status=result.terminal_status,
                terminal_reason=result.terminal_reason,
            )

            if result.terminal_status:
                yield await self._build_terminal_event(
                    state=state,
                    event_type=result.terminal_status,
                    terminal_reason=self._normalize_reason(
                        result.terminal_reason,
                        fallback=result.terminal_status,
                    ),
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                    payload=dict(result.payload),
                )
                return

            if next_node_id is None:
                yield await self._build_terminal_event(
                    state=state,
                    event_type="failed",
                    terminal_reason=f"node '{node.node_id}' did not resolve next node",
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                )
                return

            state.current_node_id = next_node_id

        yield await self._build_terminal_event(
            state=state,
            event_type="completed",
            terminal_reason="completed",
            payload={},
        )

    async def _resolve_resume_checkpoint(
        self,
        *,
        run_store: RunStore,
        run_id: str,
        checkpoint_id: str | None,
    ) -> RunCheckpoint:
        if checkpoint_id:
            checkpoint = await run_store.get_checkpoint(run_id=run_id, checkpoint_id=checkpoint_id)
            if checkpoint is None:
                raise ValueError(f"checkpoint '{checkpoint_id}' not found for run '{run_id}'")
            return checkpoint

        checkpoint = await run_store.get_latest_checkpoint(run_id=run_id)
        if checkpoint is None:
            raise ValueError(f"run '{run_id}' has no persisted checkpoints")
        return checkpoint

    def _resolve_resume_node(
        self,
        *,
        checkpoint: RunCheckpoint,
        entry_node_id: str,
        edges_by_source: dict[str, list[EdgeSpec]],
    ) -> str:
        event_type = checkpoint.event_type
        if event_type == "started":
            return entry_node_id

        if event_type in {"node_started", "node_retrying", "node_event"}:
            if checkpoint.node_id:
                return checkpoint.node_id
            return entry_node_id

        if event_type == "node_finished":
            if checkpoint.next_node_id:
                return checkpoint.next_node_id
            if checkpoint.node_id:
                resolved = self._resolve_next_node(
                    node_id=checkpoint.node_id,
                    branch=checkpoint.branch,
                    edges_by_source=edges_by_source,
                )
                if resolved:
                    return resolved
            return entry_node_id

        return entry_node_id

    async def _save_checkpoint(
        self,
        *,
        run_store: RunStore | None,
        run_id: str,
        seq: int,
        step: int,
        event_type: str,
        node_id: str | None = None,
        actor_id: str | None = None,
        next_node_id: str | None = None,
        branch: str | None = None,
        terminal_status: str | None = None,
        terminal_reason: str | None = None,
        payload: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str | None:
        if run_store is None:
            return None

        checkpoint_id = str(uuid.uuid4())
        checkpoint = RunCheckpoint(
            checkpoint_id=checkpoint_id,
            run_id=run_id,
            seq=int(seq),
            step=int(step),
            event_type=event_type,
            node_id=node_id,
            actor_id=actor_id,
            next_node_id=next_node_id,
            branch=branch,
            terminal_status=terminal_status,
            terminal_reason=terminal_reason,
            payload=dict(payload or {}),
            metadata=dict(metadata or {}),
        )
        await run_store.append_checkpoint(checkpoint)
        return checkpoint_id

    async def _close_stream(self, stream: Any) -> None:
        aclose = getattr(stream, "aclose", None)
        if callable(aclose):
            with contextlib.suppress(Exception):
                close_result = aclose()
                if inspect.isawaitable(close_result):
                    await cast(Awaitable[Any], close_result)

    @staticmethod
    def _index_edges(edges: tuple[EdgeSpec, ...]) -> dict[str, list[EdgeSpec]]:
        indexed: dict[str, list[EdgeSpec]] = {}
        for edge in edges:
            indexed.setdefault(edge.source_id, []).append(edge)
        return indexed

    @staticmethod
    def _resolve_next_node(
        *,
        node_id: str,
        branch: str | None,
        edges_by_source: dict[str, list[EdgeSpec]],
    ) -> str | None:
        options = edges_by_source.get(node_id, [])
        if not options:
            return None
        if branch is not None:
            for edge in options:
                if edge.branch == branch:
                    return edge.target_id
        for edge in options:
            if edge.branch is None:
                return edge.target_id
        return options[0].target_id

    @staticmethod
    def _should_retry(
        *,
        node: NodeSpec,
        error: Exception,
        emitted_runtime_events: bool,
    ) -> bool:
        retry_policy = node.retry_policy
        if retry_policy.retry_only_if_no_events and emitted_runtime_events:
            return False
        if retry_policy.is_retryable is None:
            return False
        return bool(retry_policy.is_retryable(error))

    @staticmethod
    def _compute_backoff_delay_ms(
        *,
        base_delay_ms: int,
        retry_index: int,
        max_backoff_ms: int,
    ) -> int:
        if base_delay_ms <= 0:
            return 0
        delay = int(base_delay_ms * (2 ** max(0, retry_index - 1)))
        cap = max(0, int(max_backoff_ms))
        if cap <= 0:
            return delay
        return min(delay, cap)

    @staticmethod
    def _normalize_reason(reason: str | None, *, fallback: str) -> str:
        normalized = str(reason or "").strip()
        if normalized:
            return normalized
        fallback_normalized = str(fallback).strip()
        return fallback_normalized or "unknown"
