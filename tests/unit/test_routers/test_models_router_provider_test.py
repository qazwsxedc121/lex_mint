"""Unit tests for provider stored-connection test route behavior."""

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from src.api.models.model_config import (
    Provider,
    ProviderTestStoredRequest,
    ProviderEndpointProbeRequest,
    ProviderEndpointProbeResponse,
    ProviderEndpointProbeResult,
)
from src.api.routers import models as models_router
from src.providers.types import ApiProtocol, CallMode, ProviderType, EndpointProfile


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
    stepfun = next(p for p in providers if p.id == "stepfun")
    siliconflow = next(p for p in providers if p.id == "siliconflow")
    xai = next(p for p in providers if p.id == "xai")
    kimi = next(p for p in providers if p.id == "kimi")

    assert deepseek.supports_model_list is True
    assert anthropic.supports_model_list is True
    assert stepfun.supports_model_list is True
    assert siliconflow.supports_model_list is True
    assert xai.supports_model_list is True
    assert kimi.supports_model_list is True
    assert deepseek.default_capabilities.requires_interleaved_thinking is False
    assert kimi.default_capabilities.requires_interleaved_thinking is False
    assert "builtin_models" not in deepseek.model_dump()
    assert "builtin_models" not in anthropic.model_dump()
    assert "builtin_models" not in stepfun.model_dump()
    assert "builtin_models" not in siliconflow.model_dump()
    assert "builtin_models" not in xai.model_dump()
    assert "builtin_models" not in kimi.model_dump()


@pytest.mark.asyncio
async def test_builtin_provider_info_hides_static_model_list():
    info = await models_router.get_builtin_provider_info("volcengine")
    assert "builtin_models" not in info.model_dump()


@pytest.mark.asyncio
async def test_builtin_provider_catalog_includes_minimax_and_endpoint_profiles():
    providers = await models_router.get_builtin_providers()
    minimax = next(p for p in providers if p.id == "minimax")
    stepfun = next(p for p in providers if p.id == "stepfun")

    assert minimax.supports_model_list is True
    assert minimax.base_url.startswith("https://api.minimax")
    assert len(stepfun.endpoint_profiles) >= 2
    assert any(profile.id == "stepfun-global" for profile in stepfun.endpoint_profiles)


@pytest.mark.asyncio
async def test_probe_provider_endpoints_uses_stored_key(monkeypatch):
    service = Mock()
    provider = _provider(
        provider_id="stepfun",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.stepfun.com/v1",
    )
    provider.endpoint_profile_id = "stepfun-cn"
    provider.endpoint_profiles = [
        EndpointProfile(
            id="stepfun-cn",
            label="CN",
            base_url="https://api.stepfun.com/v1",
            region_tags=["cn"],
            priority=10,
            probe_method="openai_models",
        )
    ]

    service.get_provider = AsyncMock(return_value=provider)
    service.get_api_key = AsyncMock(return_value="stored-key")
    service.provider_requires_api_key = Mock(return_value=True)

    class FakeProbeService:
        def __init__(self, _service):
            self._service = _service

        async def probe(self, _provider, request, api_key):
            assert request.mode == "auto"
            assert api_key == "stored-key"
            return ProviderEndpointProbeResponse(
                provider_id="stepfun",
                results=[
                    ProviderEndpointProbeResult(
                        endpoint_profile_id="stepfun-cn",
                        label="CN",
                        base_url="https://api.stepfun.com/v1",
                        success=True,
                        classification="ok",
                        http_status=200,
                        latency_ms=18,
                        message="Connection successful",
                        detected_model_count=2,
                        priority=10,
                        region_tags=["cn"],
                    )
                ],
                recommended_endpoint_profile_id="stepfun-cn",
                recommended_base_url="https://api.stepfun.com/v1",
                summary="Found 1 reachable endpoint(s)",
            )

    monkeypatch.setattr(models_router, "ProviderProbeService", FakeProbeService)

    response = await models_router.probe_provider_endpoints(
        "stepfun",
        ProviderEndpointProbeRequest(mode="auto", use_stored_key=True, strict=True),
        service,
    )

    assert response.recommended_endpoint_profile_id == "stepfun-cn"
    assert response.results[0].success is True


@pytest.mark.asyncio
async def test_fetch_provider_models_for_kimi_returns_model_infos():
    service = Mock()
    provider = _provider(
        provider_id="kimi",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.moonshot.cn/v1",
    )
    adapter = Mock()
    adapter.fetch_models = AsyncMock(
        return_value=[
            {"id": "kimi-k2.5", "name": "Kimi K2.5"},
            {"id": "kimi-k2-thinking", "name": "Kimi K2 Thinking"},
        ]
    )

    service.get_provider = AsyncMock(return_value=provider)
    service.get_api_key = AsyncMock(return_value="test-key")
    service.get_adapter_for_provider = Mock(return_value=adapter)

    result = await models_router.fetch_provider_models("kimi", service)

    assert [item.id for item in result] == ["kimi-k2.5", "kimi-k2-thinking"]
    assert result[0].capabilities is not None
    assert result[0].capabilities["reasoning"] is True
    assert result[0].capabilities["requires_interleaved_thinking"] is True
    assert result[0].capabilities["reasoning_controls"]["mode"] == "toggle"
    adapter.fetch_models.assert_awaited_once_with("https://api.moonshot.cn/v1", "test-key")


@pytest.mark.asyncio
async def test_fetch_provider_models_returns_400_when_no_key_and_empty_result():
    service = Mock()
    provider = _provider(
        provider_id="kimi",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.moonshot.cn/v1",
    )
    adapter = Mock()
    adapter.fetch_models = AsyncMock(return_value=[])

    service.get_provider = AsyncMock(return_value=provider)
    service.get_api_key = AsyncMock(return_value=None)
    service.get_adapter_for_provider = Mock(return_value=adapter)

    with pytest.raises(HTTPException) as exc:
        await models_router.fetch_provider_models("kimi", service)

    assert exc.value.status_code == 400
    assert "Try configuring an API key" in exc.value.detail
