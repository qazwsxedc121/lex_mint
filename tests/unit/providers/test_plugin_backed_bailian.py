"""Tests for plugin-backed Bailian provider wiring."""

import pytest

from src.providers.builtin import _builtin_provider_map, get_builtin_provider
from src.providers.registry import AdapterRegistry


def test_builtin_bailian_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    definition = get_builtin_provider("bailian")

    assert definition is not None
    assert definition.sdk_class == "bailian"
    assert definition.base_url == "https://dashscope.aliyuncs.com/compatible-mode/v1"


def test_registry_resolves_bailian_adapter_from_plugin():
    AdapterRegistry._plugins_loaded = False
    adapter = AdapterRegistry.get("bailian")
    assert adapter.__class__.__name__ == "BailianAdapter"


def test_registry_raises_when_strict_bailian_plugin_missing(monkeypatch):
    snapshot = dict(AdapterRegistry._adapters)
    snapshot.pop("bailian", None)

    monkeypatch.setattr(AdapterRegistry, "_plugins_loaded", True)
    monkeypatch.setattr(AdapterRegistry, "_adapters", snapshot)

    with pytest.raises(RuntimeError, match="Provider plugin adapter 'bailian' is not loaded"):
        AdapterRegistry.get("bailian")
