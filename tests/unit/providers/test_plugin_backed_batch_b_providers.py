"""Tests for plugin-backed Zhipu/VolcEngine provider wiring."""

import pytest

from src.providers.builtin import (
    _builtin_provider_map,
    _plugin_builtin_provider_source_map,
    get_builtin_provider,
    get_builtin_provider_plugin_source,
)
from src.providers.registry import AdapterRegistry


def test_builtin_zhipu_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    _plugin_builtin_provider_source_map.cache_clear()

    definition = get_builtin_provider("zhipu")
    source = get_builtin_provider_plugin_source("zhipu")

    assert definition is not None
    assert definition.sdk_class == "zhipu"
    assert definition.base_url == "https://open.bigmodel.cn/api/paas/v4"
    assert definition.default_endpoint_profile_id == "zhipu-cn"
    assert any(profile.id == "zhipu-cn" for profile in definition.endpoint_profiles)
    assert source is not None
    assert source.get("plugin_id") == "zhipu"


def test_builtin_volcengine_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    _plugin_builtin_provider_source_map.cache_clear()

    definition = get_builtin_provider("volcengine")
    source = get_builtin_provider_plugin_source("volcengine")

    assert definition is not None
    assert definition.sdk_class == "volcengine"
    assert definition.base_url == "https://ark.cn-beijing.volces.com/api/v3"
    assert source is not None
    assert source.get("plugin_id") == "volcengine"


def test_registry_resolves_zhipu_and_volcengine_adapters_from_plugin():
    AdapterRegistry._plugins_loaded = False

    zhipu_adapter = AdapterRegistry.get("zhipu")
    volcengine_adapter = AdapterRegistry.get("volcengine")

    assert zhipu_adapter.__class__.__name__ == "ZhipuAdapter"
    assert volcengine_adapter.__class__.__name__ == "VolcEngineAdapter"


def test_registry_raises_when_strict_batch_b_plugin_missing(monkeypatch):
    snapshot = dict(AdapterRegistry._adapters)
    snapshot.pop("zhipu", None)
    snapshot.pop("volcengine", None)

    monkeypatch.setattr(AdapterRegistry, "_plugins_loaded", True)
    monkeypatch.setattr(AdapterRegistry, "_adapters", snapshot)

    with pytest.raises(RuntimeError, match="Provider plugin adapter 'zhipu' is not loaded"):
        AdapterRegistry.get("zhipu")

    with pytest.raises(RuntimeError, match="Provider plugin adapter 'volcengine' is not loaded"):
        AdapterRegistry.get("volcengine")
