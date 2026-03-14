"""Universal graph orchestration runtime."""

from __future__ import annotations

import asyncio
import contextlib
from typing import Any, AsyncIterator, Dict, List, Optional

from .context_manager import InMemoryContextManager
from .ir import ActorEmit, ActorExecutionContext, ActorResult, EdgeSpec, NodeSpec, RunContext, RunSpec, validate_run_spec


class _NodeTimeoutError(Exception):
    """Raised when one node attempt exceeds configured timeout."""


class _RunCancelledError(Exception):
    """Raised for cooperative cancellation."""


class OrchestrationEngine:
    """Execute one graph run and emit lifecycle/runtime events."""

    def __init__(self, *, default_max_steps: int = 1000):
        self.default_max_steps = max(1, int(default_max_steps))

    async def run_stream(
        self,
        spec: RunSpec,
        context: Optional[RunContext] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """Run a graph and stream lifecycle events."""

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

        yield {
            "type": "started",
            "run_id": run_id,
            "metadata": dict(spec.metadata),
        }

        current_node_id = spec.entry_node_id
        step = 0

        while current_node_id:
            if run_context.is_cancelled:
                reason = self._normalize_reason(run_context.cancel_reason, fallback="cancelled")
                yield {
                    "type": "cancelled",
                    "run_id": run_id,
                    "terminal_reason": reason,
                }
                return

            step += 1
            if step > max_steps:
                yield {
                    "type": "failed",
                    "run_id": run_id,
                    "terminal_reason": (
                        f"run exceeded max steps ({max_steps}), possible loop detected"
                    ),
                }
                return

            node = node_map.get(current_node_id)
            if node is None:
                yield {
                    "type": "failed",
                    "run_id": run_id,
                    "terminal_reason": f"node '{current_node_id}' does not exist",
                }
                return

            yield {
                "type": "node_started",
                "run_id": run_id,
                "node_id": node.node_id,
                "actor_id": node.actor.actor_id,
            }

            result: Optional[ActorResult] = None
            max_attempts = node.retry_policy.max_retries + 1
            for attempt in range(1, max_attempts + 1):
                emitted_runtime_events = False
                stream = None
                try:
                    execution_context = ActorExecutionContext(
                        run_id=run_id,
                        node_id=node.node_id,
                        actor_id=node.actor.actor_id,
                        run_context=run_context,
                        metadata=dict(node.metadata),
                    )

                    result = ActorResult()
                    stream = node.actor.handler(execution_context)

                    async def _iterate_signals() -> AsyncIterator[Dict[str, Any]]:
                        nonlocal result
                        nonlocal emitted_runtime_events
                        async for signal in stream:
                            if run_context.is_cancelled:
                                raise _RunCancelledError(run_context.cancel_reason)

                            if isinstance(signal, ActorEmit):
                                emitted_runtime_events = True
                                yield {
                                    "type": "node_event",
                                    "run_id": run_id,
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
                    yield {
                        "type": "cancelled",
                        "run_id": run_id,
                        "terminal_reason": reason,
                    }
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

                    yield {
                        "type": "failed",
                        "run_id": run_id,
                        "node_id": node.node_id,
                        "terminal_reason": self._normalize_reason(str(exc), fallback="node_failed"),
                    }
                    return
                finally:
                    if stream is not None:
                        await self._close_stream(stream)
            else:
                yield {
                    "type": "failed",
                    "run_id": run_id,
                    "node_id": node.node_id,
                    "terminal_reason": f"node '{node.node_id}' failed after retries",
                }
                return

            if result is None:
                result = ActorResult()

            yield {
                "type": "node_finished",
                "run_id": run_id,
                "node_id": node.node_id,
                "actor_id": node.actor.actor_id,
                "payload": dict(result.payload),
            }

            terminal_status = result.terminal_status
            if terminal_status:
                terminal_reason = self._normalize_reason(
                    result.terminal_reason,
                    fallback=terminal_status,
                )
                yield {
                    "type": terminal_status,
                    "run_id": run_id,
                    "terminal_reason": terminal_reason,
                    "payload": dict(result.payload),
                }
                return

            next_node_id = result.next_node_id
            if next_node_id is None:
                next_node_id = self._resolve_next_node(
                    node_id=node.node_id,
                    branch=result.branch,
                    edges_by_source=edges_by_source,
                )

            if next_node_id is None:
                yield {
                    "type": "failed",
                    "run_id": run_id,
                    "node_id": node.node_id,
                    "terminal_reason": (
                        f"node '{node.node_id}' did not resolve next node"
                    ),
                }
                return

            current_node_id = next_node_id

        yield {
            "type": "completed",
            "run_id": run_id,
            "terminal_reason": "completed",
            "payload": {},
        }

    async def _close_stream(self, stream: Any) -> None:
        aclose = getattr(stream, "aclose", None)
        if callable(aclose):
            with contextlib.suppress(Exception):
                await aclose()

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
