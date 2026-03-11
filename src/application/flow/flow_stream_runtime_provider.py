"""Shared FlowStreamRuntime singleton provider."""

from __future__ import annotations

from src.core.config import settings
from .flow_stream_runtime import FlowStreamRuntime

_flow_stream_runtime = FlowStreamRuntime(
    ttl_seconds=settings.flow_stream_ttl_seconds,
    max_events_per_stream=settings.flow_stream_max_events,
    max_active_streams=settings.flow_stream_max_active,
)


def get_flow_stream_runtime() -> FlowStreamRuntime:
    """Dependency provider for in-memory FlowEvent replay runtime."""
    return _flow_stream_runtime

