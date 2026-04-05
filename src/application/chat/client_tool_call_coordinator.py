"""Coordinator for tool calls that are executed on the client side."""

from __future__ import annotations

import asyncio


class ClientToolCallCoordinator:
    """Coordinate request/response handoff for client-executed tool calls."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._pending: dict[tuple[str, str], asyncio.Future[str]] = {}
        self._buffered: dict[tuple[str, str], str] = {}

    async def await_result(self, *, session_id: str, tool_call_id: str, timeout_s: float) -> str:
        key = (session_id, tool_call_id)
        async with self._lock:
            buffered = self._buffered.pop(key, None)
            if buffered is not None:
                return buffered
            loop = asyncio.get_running_loop()
            future = self._pending.get(key)
            if future is None or future.done():
                future = loop.create_future()
                self._pending[key] = future

        try:
            return await asyncio.wait_for(future, timeout=max(0.1, timeout_s))
        finally:
            async with self._lock:
                current = self._pending.get(key)
                if current is future:
                    self._pending.pop(key, None)

    async def submit_result(self, *, session_id: str, tool_call_id: str, result: str) -> None:
        key = (session_id, tool_call_id)
        async with self._lock:
            future = self._pending.get(key)
            if future is not None and not future.done():
                future.set_result(result)
                self._pending.pop(key, None)
                return
            self._buffered[key] = result


_coordinator = ClientToolCallCoordinator()


def get_client_tool_call_coordinator() -> ClientToolCallCoordinator:
    """Get singleton coordinator instance."""
    return _coordinator
