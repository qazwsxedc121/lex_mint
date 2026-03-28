"""Graph IR for the universal orchestration runtime."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Literal

from .context_manager import ContextManager

if TYPE_CHECKING:
    from .run_store import RunStore


TerminalStatus = Literal["completed", "failed", "cancelled"]


@dataclass(frozen=True)
class ActorEmit:
    """One runtime event emitted by an actor while a node is running."""

    event_type: str
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActorResult:
    """Terminal signal for one node execution attempt."""

    next_node_id: str | None = None
    branch: str | None = None
    terminal_status: TerminalStatus | None = None
    terminal_reason: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)


ActorSignal = ActorEmit | ActorResult


@dataclass
class ActorExecutionContext:
    """Execution scope passed to each actor."""

    run_id: str
    node_id: str
    actor_id: str
    run_context: RunContext
    metadata: dict[str, Any] = field(default_factory=dict)

    async def read_context(self, *, namespace: str = "default") -> dict[str, Any]:
        manager = self.run_context.context_manager
        if manager is None:
            return {}
        return await manager.read(
            run_id=self.run_id,
            actor_id=self.actor_id,
            namespace=namespace,
        )

    async def write_context(
        self,
        *,
        payload: dict[str, Any],
        namespace: str = "default",
    ) -> dict[str, Any]:
        manager = self.run_context.context_manager
        if manager is None:
            return dict(payload)
        return await manager.write(
            run_id=self.run_id,
            actor_id=self.actor_id,
            namespace=namespace,
            payload=payload,
        )

    async def patch_context(
        self,
        *,
        payload: dict[str, Any],
        namespace: str = "default",
    ) -> dict[str, Any]:
        manager = self.run_context.context_manager
        if manager is None:
            return dict(payload)
        return await manager.patch(
            run_id=self.run_id,
            actor_id=self.actor_id,
            namespace=namespace,
            payload=payload,
        )


ActorHandler = Callable[[ActorExecutionContext], AsyncIterator[ActorSignal]]


@dataclass(frozen=True)
class ActorRef:
    """Reference to one executable actor implementation."""

    actor_id: str
    kind: str
    handler: ActorHandler


@dataclass(frozen=True)
class RetryPolicy:
    """Per-node retry policy."""

    max_retries: int = 0
    backoff_ms: int = 0
    max_backoff_ms: int = 5000
    retry_only_if_no_events: bool = False
    is_retryable: Callable[[Exception], bool] | None = None


@dataclass(frozen=True)
class NodeSpec:
    """Node definition in graph IR."""

    node_id: str
    actor: ActorRef
    timeout_ms: int | None = None
    retry_policy: RetryPolicy = field(default_factory=RetryPolicy)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EdgeSpec:
    """Directed edge between nodes."""

    source_id: str
    target_id: str
    branch: str | None = None


@dataclass(frozen=True)
class RunSpec:
    """One executable graph run definition."""

    run_id: str
    entry_node_id: str
    nodes: tuple[NodeSpec, ...]
    edges: tuple[EdgeSpec, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RunContext:
    """Per-run execution controls and metadata."""

    run_id: str
    metadata: dict[str, Any] = field(default_factory=dict)
    trace_id: str | None = None
    timeout_ms: int | None = None
    max_steps: int = 100
    cancel_event: Any | None = None
    cancel_reason: str = "cancelled"
    context_manager: ContextManager | None = None
    run_store: RunStore | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_cancelled(self) -> bool:
        if self.cancel_event is None:
            return False
        return bool(getattr(self.cancel_event, "is_set", lambda: False)())


def validate_run_spec(spec: RunSpec) -> None:
    """Validate graph structure before execution."""

    if not spec.nodes:
        raise ValueError("RunSpec must include at least one node")

    node_map = {node.node_id: node for node in spec.nodes}
    if len(node_map) != len(spec.nodes):
        raise ValueError("RunSpec contains duplicate node ids")

    if spec.entry_node_id not in node_map:
        raise ValueError(f"RunSpec entry node '{spec.entry_node_id}' does not exist")

    adjacency: dict[str, list[str]] = {node.node_id: [] for node in spec.nodes}
    for edge in spec.edges:
        if edge.source_id not in node_map:
            raise ValueError(f"Edge source '{edge.source_id}' does not exist")
        if edge.target_id not in node_map:
            raise ValueError(f"Edge target '{edge.target_id}' does not exist")
        adjacency[edge.source_id].append(edge.target_id)

    reachable: set[str] = set()
    queue = [spec.entry_node_id]
    while queue:
        current = queue.pop()
        if current in reachable:
            continue
        reachable.add(current)
        for nxt in adjacency.get(current, []):
            if nxt not in reachable:
                queue.append(nxt)

    unreachable = sorted(set(node_map.keys()) - reachable)
    if unreachable:
        raise ValueError(
            "RunSpec contains unreachable nodes from entry node: " + ", ".join(unreachable)
        )

    # Cycles are allowed. Runtime progress is bounded by RunContext.max_steps and
    # optional terminal ActorResult signals.
