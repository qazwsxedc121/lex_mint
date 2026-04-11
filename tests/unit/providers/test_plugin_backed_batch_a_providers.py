"""Tests for plugin-backed StepFun/Together/MiniMax provider definitions."""

from src.providers.builtin import (
    _builtin_provider_map,
    _plugin_builtin_provider_source_map,
    get_builtin_provider,
    get_builtin_provider_plugin_source,
)


def test_builtin_stepfun_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    _plugin_builtin_provider_source_map.cache_clear()

    definition = get_builtin_provider("stepfun")
    source = get_builtin_provider_plugin_source("stepfun")

    assert definition is not None
    assert definition.sdk_class == "openai"
    assert definition.base_url == "https://api.stepfun.com/v1"
    assert definition.default_endpoint_profile_id == "stepfun-cn"
    assert any(profile.id == "stepfun-global" for profile in definition.endpoint_profiles)
    assert source is not None
    assert source.get("plugin_id") == "stepfun"


def test_builtin_together_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    _plugin_builtin_provider_source_map.cache_clear()

    definition = get_builtin_provider("together")
    source = get_builtin_provider_plugin_source("together")

    assert definition is not None
    assert definition.sdk_class == "openai"
    assert definition.base_url == "https://api.together.xyz/v1"
    assert source is not None
    assert source.get("plugin_id") == "together"


def test_builtin_minimax_definition_is_available_from_plugin():
    _builtin_provider_map.cache_clear()
    _plugin_builtin_provider_source_map.cache_clear()

    definition = get_builtin_provider("minimax")
    source = get_builtin_provider_plugin_source("minimax")

    assert definition is not None
    assert definition.sdk_class == "openai"
    assert definition.base_url == "https://api.minimax.chat/v1"
    assert source is not None
    assert source.get("plugin_id") == "minimax"
