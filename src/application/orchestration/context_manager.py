"""Context storage contracts for orchestration runs."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from collections.abc import Mapping
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any


class ContextManager(ABC):
    """Read/write context scoped by run_id + actor_id + namespace."""

    @abstractmethod
    async def read(
        self,
        *,
        run_id: str,
        actor_id: str,
        namespace: str,
    ) -> dict[str, Any]:
        """Return a copy of the context payload for one scope."""
        raise NotImplementedError

    @abstractmethod
    async def write(
        self,
        *,
        run_id: str,
        actor_id: str,
        namespace: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Replace one context namespace payload and return the stored value."""
        raise NotImplementedError

    @abstractmethod
    async def patch(
        self,
        *,
        run_id: str,
        actor_id: str,
        namespace: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Merge payload into one namespace and return the stored value."""
        raise NotImplementedError


@dataclass
class InMemoryContextManager(ContextManager):
    """In-memory ContextManager with run/actor/namespace isolation."""

    _store: dict[str, dict[str, dict[str, dict[str, Any]]]] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def read(
        self,
        *,
        run_id: str,
        actor_id: str,
        namespace: str,
    ) -> dict[str, Any]:
        async with self._lock:
            stored = self._store.get(run_id, {}).get(actor_id, {}).get(namespace, {})
            return deepcopy(stored)

    async def write(
        self,
        *,
        run_id: str,
        actor_id: str,
        namespace: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            run_scope = self._store.setdefault(run_id, {})
            actor_scope = run_scope.setdefault(actor_id, {})
            actor_scope[namespace] = dict(payload)
            return deepcopy(actor_scope[namespace])

    async def patch(
        self,
        *,
        run_id: str,
        actor_id: str,
        namespace: str,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        async with self._lock:
            run_scope = self._store.setdefault(run_id, {})
            actor_scope = run_scope.setdefault(actor_id, {})
            target = actor_scope.setdefault(namespace, {})
            target.update(dict(payload))
            return deepcopy(target)
