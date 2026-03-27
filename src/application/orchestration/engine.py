"""Universal graph orchestration runtime."""

from __future__ import annotations

import asyncio
import contextlib
import inspect
from typing import Any, AsyncIterator, Awaitable, Dict, List, Optional, cast
import uuid

from .checkpoint import RunCheckpoint
from .context_manager import InMemoryContextManager
from .ir import ActorEmit, ActorExecutionContext, ActorResult, ActorSignal, EdgeSpec, NodeSpec, RunContext, RunSpec, validate_run_spec
from .run_store import RunStore


class _NodeTimeoutError(Exception):
    """Raised when one node attempt exceeds configured timeout."""


class _RunCancelledError(Exception):
    """Raised for cooperative cancellation."""


class OrchestrationEngine:
    """Execute one graph run and emit lifecycle/runtime events."""

    def __init__(
        self,
        *,
        default_max_steps: int = 1000,
        run_store: Optional[RunStore] = None,
    ):
        self.default_max_steps = max(1, int(default_max_steps))
        self.run_store = run_store

    async def run_stream(
        self,
        spec: RunSpec,
        context: Optional[RunContext] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
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
        context: Optional[RunContext] = None,
        from_checkpoint_id: Optional[str] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Resume one run from a persisted checkpoint."""

        async for event in self._run_stream_internal(
            spec=spec,
            context=context,
            resume_from_checkpoint_id=from_checkpoint_id,
        ):
            yield event

    async def _run_stream_internal(
        self,
        *,
        spec: RunSpec,
        context: Optional[RunContext],
        resume_from_checkpoint_id: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        validate_run_spec(spec)

        run_context = context or RunContext(run_id=spec.run_id)
        if not run_context.run_id:
            run_context.run_id = spec.run_id
        if run_context.context_manager is None:
            run_context.context_manager = InMemoryContextManager()

        run_id = run_context.run_id
        node_map = {node.node_id: node for node in spec.nodes}
        edges_by_source = self._index_edges(spec.edges)
        max_steps = max(1, int(run_context.max_steps or self.default_max_steps))
        run_store = run_context.run_store or self.run_store

        checkpoint_seq = 0
        step = 0
        current_node_id = spec.entry_node_id

        if resume_from_checkpoint_id is not None or run_context.metadata.get("resume", False):
            if run_store is None:
                raise ValueError("Cannot resume run without a RunStore")
            checkpoint = await self._resolve_resume_checkpoint(
                run_store=run_store,
                run_id=run_id,
                checkpoint_id=resume_from_checkpoint_id,
            )
            checkpoint_seq = checkpoint.seq
            step = checkpoint.step
            current_node_id = self._resolve_resume_node(
                checkpoint=checkpoint,
                entry_node_id=spec.entry_node_id,
                edges_by_source=edges_by_source,
            )
            resumed_event = {
                "type": "resumed",
                "run_id": run_id,
                "checkpoint_id": checkpoint.checkpoint_id,
                "from_event_type": checkpoint.event_type,
                "node_id": current_node_id,
                "step": step,
            }
            yield resumed_event

            if checkpoint.event_type in {"completed", "failed", "cancelled"}:
                terminal_status = checkpoint.terminal_status or checkpoint.event_type
                terminal_reason = self._normalize_reason(
                    checkpoint.terminal_reason,
                    fallback=terminal_status,
                )
                yield {
                    "type": terminal_status,
                    "run_id": run_id,
                    "terminal_reason": terminal_reason,
                    "payload": dict(checkpoint.payload),
                    "checkpoint_id": checkpoint.checkpoint_id,
                }
                return
        else:
            started_checkpoint_id = await self._save_checkpoint(
                run_store=run_store,
                run_id=run_id,
                seq=(checkpoint_seq := checkpoint_seq + 1),
                step=step,
                event_type="started",
                metadata=dict(spec.metadata),
            )
            started_event = {
                "type": "started",
                "run_id": run_id,
                "metadata": dict(spec.metadata),
            }
            if started_checkpoint_id:
                started_event["checkpoint_id"] = started_checkpoint_id
            yield started_event

        while current_node_id:
            if run_context.is_cancelled:
                reason = self._normalize_reason(run_context.cancel_reason, fallback="cancelled")
                cancelled_checkpoint_id = await self._save_checkpoint(
                    run_store=run_store,
                    run_id=run_id,
                    seq=(checkpoint_seq := checkpoint_seq + 1),
                    step=step,
                    event_type="cancelled",
                    terminal_status="cancelled",
                    terminal_reason=reason,
                )
                cancelled_event = {
                    "type": "cancelled",
                    "run_id": run_id,
                    "terminal_reason": reason,
                }
                if cancelled_checkpoint_id:
                    cancelled_event["checkpoint_id"] = cancelled_checkpoint_id
                yield cancelled_event
                return

            step += 1
            if step > max_steps:
                reason = f"run exceeded max steps ({max_steps}), possible loop detected"
                failed_checkpoint_id = await self._save_checkpoint(
                    run_store=run_store,
                    run_id=run_id,
                    seq=(checkpoint_seq := checkpoint_seq + 1),
                    step=step,
                    event_type="failed",
                    terminal_status="failed",
                    terminal_reason=reason,
                )
                failed_event = {
                    "type": "failed",
                    "run_id": run_id,
                    "terminal_reason": reason,
                }
                if failed_checkpoint_id:
                    failed_event["checkpoint_id"] = failed_checkpoint_id
                yield failed_event
                return

            node = node_map.get(current_node_id)
            if node is None:
                reason = f"node '{current_node_id}' does not exist"
                failed_checkpoint_id = await self._save_checkpoint(
                    run_store=run_store,
                    run_id=run_id,
                    seq=(checkpoint_seq := checkpoint_seq + 1),
                    step=step,
                    event_type="failed",
                    terminal_status="failed",
                    terminal_reason=reason,
                )
                failed_event = {
                    "type": "failed",
                    "run_id": run_id,
                    "terminal_reason": reason,
                }
                if failed_checkpoint_id:
                    failed_event["checkpoint_id"] = failed_checkpoint_id
                yield failed_event
                return
            assert node is not None

            node_started_checkpoint_id = await self._save_checkpoint(
                run_store=run_store,
                run_id=run_id,
                seq=(checkpoint_seq := checkpoint_seq + 1),
                step=step,
                event_type="node_started",
                node_id=node.node_id,
                actor_id=node.actor.actor_id,
            )
            node_started_event = {
                "type": "node_started",
                "run_id": run_id,
                "node_id": node.node_id,
                "actor_id": node.actor.actor_id,
            }
            if node_started_checkpoint_id:
                node_started_event["checkpoint_id"] = node_started_checkpoint_id
            yield node_started_event

            result: Optional[ActorResult] = None
            max_attempts = node.retry_policy.max_retries + 1
            for attempt in range(1, max_attempts + 1):
                emitted_runtime_events = False
                stream: AsyncIterator[ActorSignal] | None = None
                try:
                    execution_context = ActorExecutionContext(
                        run_id=run_id,
                        node_id=node.node_id,
                        actor_id=node.actor.actor_id,
                        run_context=run_context,
                        metadata=dict(node.metadata),
                    )

                    result = ActorResult()
                    active_node = node
                    active_stream = active_node.actor.handler(execution_context)
                    stream = active_stream

                    async def _iterate_signals() -> AsyncIterator[Dict[str, Any]]:
                        nonlocal result
                        nonlocal emitted_runtime_events
                        async for signal in active_stream:
                            if run_context.is_cancelled:
                                raise _RunCancelledError(run_context.cancel_reason)

                            if isinstance(signal, ActorEmit):
                                emitted_runtime_events = True
                                yield {
                                    "type": "node_event",
                                    "run_id": run_id,
                                    "node_id": active_node.node_id,
                                    "actor_id": active_node.actor.actor_id,
                                    "event_type": signal.event_type,
                                    "payload": dict(signal.payload),
                                }
                                continue

                            if isinstance(signal, ActorResult):
                                result = signal
                                continue

                            raise ValueError(
                                f"Actor '{active_node.actor.actor_id}' returned unsupported signal type "
                                f"'{type(signal).__name__}'"
                            )

                    if node.timeout_ms is None:
                        async for node_event in _iterate_signals():
                            yield node_event
                    else:
                        timeout_seconds = max(1, int(node.timeout_ms)) / 1000.0
                        try:
                            async with asyncio.timeout(timeout_seconds):
                                async for node_event in _iterate_signals():
                                    yield node_event
                        except TimeoutError as exc:
                            if str(exc):
                                raise
                            raise _NodeTimeoutError(
                                f"node '{node.node_id}' timed out after {node.timeout_ms} ms"
                            ) from exc

                    break
                except _RunCancelledError as exc:
                    reason = self._normalize_reason(str(exc), fallback="cancelled")
                    cancelled_checkpoint_id = await self._save_checkpoint(
                        run_store=run_store,
                        run_id=run_id,
                        seq=(checkpoint_seq := checkpoint_seq + 1),
                        step=step,
                        event_type="cancelled",
                        node_id=node.node_id,
                        actor_id=node.actor.actor_id,
                        terminal_status="cancelled",
                        terminal_reason=reason,
                    )
                    cancelled_event = {
                        "type": "cancelled",
                        "run_id": run_id,
                        "terminal_reason": reason,
                    }
                    if cancelled_checkpoint_id:
                        cancelled_event["checkpoint_id"] = cancelled_checkpoint_id
                    yield cancelled_event
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
                            "run_id": run_id,
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
                    failed_checkpoint_id = await self._save_checkpoint(
                        run_store=run_store,
                        run_id=run_id,
                        seq=(checkpoint_seq := checkpoint_seq + 1),
                        step=step,
                        event_type="failed",
                        node_id=node.node_id,
                        actor_id=node.actor.actor_id,
                        terminal_status="failed",
                        terminal_reason=reason,
                    )
                    failed_event = {
                        "type": "failed",
                        "run_id": run_id,
                        "node_id": node.node_id,
                        "terminal_reason": reason,
                    }
                    if failed_checkpoint_id:
                        failed_event["checkpoint_id"] = failed_checkpoint_id
                    yield failed_event
                    return
                finally:
                    if stream is not None:
                        await self._close_stream(stream)
            else:
                reason = f"node '{node.node_id}' failed after retries"
                failed_checkpoint_id = await self._save_checkpoint(
                    run_store=run_store,
                    run_id=run_id,
                    seq=(checkpoint_seq := checkpoint_seq + 1),
                    step=step,
                    event_type="failed",
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                    terminal_status="failed",
                    terminal_reason=reason,
                )
                failed_event = {
                    "type": "failed",
                    "run_id": run_id,
                    "node_id": node.node_id,
                    "terminal_reason": reason,
                }
                if failed_checkpoint_id:
                    failed_event["checkpoint_id"] = failed_checkpoint_id
                yield failed_event
                return

            if result is None:
                result = ActorResult()

            terminal_status = result.terminal_status
            computed_next_node_id = result.next_node_id
            if terminal_status is None and computed_next_node_id is None:
                computed_next_node_id = self._resolve_next_node(
                    node_id=node.node_id,
                    branch=result.branch,
                    edges_by_source=edges_by_source,
                )

            node_finished_checkpoint_id = await self._save_checkpoint(
                run_store=run_store,
                run_id=run_id,
                seq=(checkpoint_seq := checkpoint_seq + 1),
                step=step,
                event_type="node_finished",
                node_id=node.node_id,
                actor_id=node.actor.actor_id,
                next_node_id=computed_next_node_id,
                branch=result.branch,
                payload=dict(result.payload),
                terminal_status=terminal_status,
                terminal_reason=result.terminal_reason,
            )

            node_finished_event = {
                "type": "node_finished",
                "run_id": run_id,
                "node_id": node.node_id,
                "actor_id": node.actor.actor_id,
                "payload": dict(result.payload),
            }
            if node_finished_checkpoint_id:
                node_finished_event["checkpoint_id"] = node_finished_checkpoint_id
            yield node_finished_event

            if terminal_status:
                terminal_reason = self._normalize_reason(
                    result.terminal_reason,
                    fallback=terminal_status,
                )
                terminal_checkpoint_id = await self._save_checkpoint(
                    run_store=run_store,
                    run_id=run_id,
                    seq=(checkpoint_seq := checkpoint_seq + 1),
                    step=step,
                    event_type=terminal_status,
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                    terminal_status=terminal_status,
                    terminal_reason=terminal_reason,
                    payload=dict(result.payload),
                )
                terminal_event = {
                    "type": terminal_status,
                    "run_id": run_id,
                    "terminal_reason": terminal_reason,
                    "payload": dict(result.payload),
                }
                if terminal_checkpoint_id:
                    terminal_event["checkpoint_id"] = terminal_checkpoint_id
                yield terminal_event
                return

            next_node_id = computed_next_node_id
            if next_node_id is None:
                reason = f"node '{node.node_id}' did not resolve next node"
                failed_checkpoint_id = await self._save_checkpoint(
                    run_store=run_store,
                    run_id=run_id,
                    seq=(checkpoint_seq := checkpoint_seq + 1),
                    step=step,
                    event_type="failed",
                    node_id=node.node_id,
                    actor_id=node.actor.actor_id,
                    terminal_status="failed",
                    terminal_reason=reason,
                )
                failed_event = {
                    "type": "failed",
                    "run_id": run_id,
                    "node_id": node.node_id,
                    "terminal_reason": reason,
                }
                if failed_checkpoint_id:
                    failed_event["checkpoint_id"] = failed_checkpoint_id
                yield failed_event
                return

            current_node_id = next_node_id

        completed_checkpoint_id = await self._save_checkpoint(
            run_store=run_store,
            run_id=run_id,
            seq=(checkpoint_seq := checkpoint_seq + 1),
            step=step,
            event_type="completed",
            terminal_status="completed",
            terminal_reason="completed",
            payload={},
        )
        completed_event = {
            "type": "completed",
            "run_id": run_id,
            "terminal_reason": "completed",
            "payload": {},
        }
        if completed_checkpoint_id:
            completed_event["checkpoint_id"] = completed_checkpoint_id
        yield completed_event

    async def _resolve_resume_checkpoint(
        self,
        *,
        run_store: RunStore,
        run_id: str,
        checkpoint_id: Optional[str],
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
        edges_by_source: Dict[str, List[EdgeSpec]],
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
        run_store: Optional[RunStore],
        run_id: str,
        seq: int,
        step: int,
        event_type: str,
        node_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        next_node_id: Optional[str] = None,
        branch: Optional[str] = None,
        terminal_status: Optional[str] = None,
        terminal_reason: Optional[str] = None,
        payload: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
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
    def _index_edges(edges: tuple[EdgeSpec, ...]) -> Dict[str, List[EdgeSpec]]:
        indexed: Dict[str, List[EdgeSpec]] = {}
        for edge in edges:
            indexed.setdefault(edge.source_id, []).append(edge)
        return indexed

    @staticmethod
    def _resolve_next_node(
        *,
        node_id: str,
        branch: Optional[str],
        edges_by_source: Dict[str, List[EdgeSpec]],
    ) -> Optional[str]:
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
    def _normalize_reason(reason: Optional[str], *, fallback: str) -> str:
        normalized = str(reason or "").strip()
        if normalized:
            return normalized
        fallback_normalized = str(fallback).strip()
        return fallback_normalized or "unknown"
