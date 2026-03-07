"""Tests for optional provider SDK handling in the adapter registry."""

import pytest

from src.providers.registry import AdapterRegistry, MissingDependencyAdapter


def test_registry_returns_placeholder_for_missing_lmstudio_dependency():
    adapter = AdapterRegistry.get("lmstudio")

    if adapter.__class__.__name__ == "LmStudioAdapter":
        return

    assert isinstance(adapter, MissingDependencyAdapter)


@pytest.mark.asyncio
async def test_missing_dependency_adapter_reports_clear_connection_error():
    adapter = AdapterRegistry.get("lmstudio")

    if adapter.__class__.__name__ == "LmStudioAdapter":
        return

    success, message = await adapter.test_connection("http://localhost:1234", "")

    assert success is False
    assert "Optional dependency 'lmstudio'" in message
