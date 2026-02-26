"""Tests for OpenRouter adapter registry resolution."""

from src.providers.registry import AdapterRegistry
from src.providers.types import ApiProtocol, ProviderConfig, ProviderType


def test_builtin_openrouter_resolves_to_openrouter_sdk():
    provider = ProviderConfig(
        id="openrouter",
        name="OpenRouter",
        type=ProviderType.BUILTIN,
        protocol=ApiProtocol.OPENAI,
        base_url="https://openrouter.ai/api/v1",
        enabled=True,
    )

    assert AdapterRegistry.resolve_sdk_type_for_provider(provider) == "openrouter"
