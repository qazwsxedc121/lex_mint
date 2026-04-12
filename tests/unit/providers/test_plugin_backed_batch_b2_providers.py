"""Tests for plugin-backed SiliconFlow/Kimi provider wiring."""

import pytest

from src.providers.builtin import (
    _builtin_provider_map,
    _plugin_builtin_provider_source_map,
    get_builtin_provider,
    get_builtin_provider_plugin_source,
)
from src.providers.registry import AdapterRegistry


def test_builtin_siliconflow_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    _plugin_builtin_provider_source_map.cache_clear()

    definition = get_builtin_provider("siliconflow")
    source = get_builtin_provider_plugin_source("siliconflow")

    assert definition is not None
    assert definition.sdk_class == "siliconflow"
    assert definition.base_url == "https://api.siliconflow.cn/v1"
    assert source is not None
    assert source.get("plugin_id") == "siliconflow"


def test_builtin_kimi_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    _plugin_builtin_provider_source_map.cache_clear()

    definition = get_builtin_provider("kimi")
    source = get_builtin_provider_plugin_source("kimi")

    assert definition is not None
    assert definition.sdk_class == "kimi"
    assert definition.base_url == "https://api.moonshot.cn/v1"
    assert source is not None
    assert source.get("plugin_id") == "kimi"


def test_registry_resolves_siliconflow_and_kimi_adapters_from_plugin():
    AdapterRegistry._plugins_loaded = False

    siliconflow_adapter = AdapterRegistry.get("siliconflow")
    kimi_adapter = AdapterRegistry.get("kimi")

    assert siliconflow_adapter.__class__.__name__ == "SiliconFlowAdapter"
    assert kimi_adapter.__class__.__name__ == "KimiAdapter"


def test_registry_raises_when_strict_batch_b2_plugin_missing(monkeypatch):
    snapshot = dict(AdapterRegistry._adapters)
    snapshot.pop("siliconflow", None)
    snapshot.pop("kimi", None)

    monkeypatch.setattr(AdapterRegistry, "_plugins_loaded", True)
    monkeypatch.setattr(AdapterRegistry, "_adapters", snapshot)

    with pytest.raises(RuntimeError, match="Provider plugin adapter 'siliconflow' is not loaded"):
        AdapterRegistry.get("siliconflow")

    with pytest.raises(RuntimeError, match="Provider plugin adapter 'kimi' is not loaded"):
        AdapterRegistry.get("kimi")
