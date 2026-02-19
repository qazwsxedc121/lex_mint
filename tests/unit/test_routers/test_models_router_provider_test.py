"""Unit tests for provider stored-connection test route behavior."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.api.models.model_config import Provider, ProviderTestStoredRequest
from src.api.routers import models as models_router
from src.providers.types import ApiProtocol, CallMode, ProviderType


def _provider(
    *,
    provider_id: str = "ollama",
    protocol: ApiProtocol = ApiProtocol.OLLAMA,
    base_url: str = "http://localhost:11434",
) -> Provider:
    return Provider(
        id=provider_id,
        name=provider_id,
        type=ProviderType.BUILTIN,
        protocol=protocol,
        call_mode=CallMode.AUTO,
        base_url=base_url,
        enabled=True,
    )


@pytest.mark.asyncio
async def test_stored_connection_allows_empty_key_when_provider_does_not_require_it():
    service = Mock()
    provider = _provider()

    service.get_provider = AsyncMock(return_value=provider)
    service.get_api_key = AsyncMock(return_value=None)
    service.provider_requires_api_key = Mock(return_value=False)
    service.test_provider_connection = AsyncMock(return_value=(True, "Connection successful"))

    request = ProviderTestStoredRequest(provider_id="ollama", base_url="http://localhost:11434")
    response = await models_router.test_provider_stored_connection(request, service)

    assert response.success is True
    assert response.message == "Connection successful"
    service.test_provider_connection.assert_awaited_once_with(
        base_url="http://localhost:11434",
        api_key="",
        model_id=None,
        provider=provider,
    )


@pytest.mark.asyncio
async def test_stored_connection_requires_key_when_provider_needs_it():
    service = Mock()
    provider = _provider(provider_id="deepseek", protocol=ApiProtocol.OPENAI, base_url="https://api.deepseek.com")

    service.get_provider = AsyncMock(return_value=provider)
    service.get_api_key = AsyncMock(return_value=None)
    service.provider_requires_api_key = Mock(return_value=True)
    service.test_provider_connection = AsyncMock()

    request = ProviderTestStoredRequest(provider_id="deepseek", base_url="https://api.deepseek.com")
    response = await models_router.test_provider_stored_connection(request, service)

    assert response.success is False
    assert "No API key found" in response.message
    service.test_provider_connection.assert_not_called()


@pytest.mark.asyncio
async def test_builtin_provider_catalog_uses_dynamic_model_discovery():
    providers = await models_router.get_builtin_providers()

    deepseek = next(p for p in providers if p.id == "deepseek")
    anthropic = next(p for p in providers if p.id == "anthropic")
    xai = next(p for p in providers if p.id == "xai")

    assert deepseek.supports_model_list is True
    assert anthropic.supports_model_list is True
    assert xai.supports_model_list is True
    assert "builtin_models" not in deepseek.model_dump()
    assert "builtin_models" not in anthropic.model_dump()
    assert "builtin_models" not in xai.model_dump()


@pytest.mark.asyncio
async def test_builtin_provider_info_hides_static_model_list():
    info = await models_router.get_builtin_provider_info("volcengine")
    assert "builtin_models" not in info.model_dump()
