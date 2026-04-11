"""Unit tests for provider stored-connection test route behavior."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from src.api.routers import models as models_router
from src.domain.models.model_config import (
    Provider,
    ProviderEndpointProbeRequest,
    ProviderEndpointProbeResponse,
    ProviderEndpointProbeResult,
    ProviderTestRequest,
    ProviderTestStoredRequest,
)
from src.providers.types import ApiProtocol, CallMode, EndpointProfile, ProviderType


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
async def test_direct_connection_request_accepts_empty_key_for_local_provider():
    service = Mock()
    provider = _provider(
        provider_id="lmstudio", protocol=ApiProtocol.LMSTUDIO, base_url="http://localhost:1234"
    )

    service.get_provider = AsyncMock(return_value=provider)
    service.test_provider_connection = AsyncMock(return_value=(True, "Connection successful"))

    request = ProviderTestRequest(
        provider_id="lmstudio",
        base_url="http://localhost:1234",
        api_key="",
    )
    response = await models_router.test_provider_connection(request, service)

    assert response.success is True
    service.test_provider_connection.assert_awaited_once_with(
        base_url="http://localhost:1234",
        api_key="",
        model_id=None,
        provider=provider,
    )


@pytest.mark.asyncio
async def test_stored_connection_requires_key_when_provider_needs_it():
    service = Mock()
    provider = _provider(
        provider_id="deepseek", protocol=ApiProtocol.OPENAI, base_url="https://api.deepseek.com"
    )

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
    zhipu = next(p for p in providers if p.id == "zhipu")

    assert minimax.supports_model_list is True
    assert minimax.base_url.startswith("https://api.minimax")
    assert len(stepfun.endpoint_profiles) >= 2
    assert any(profile.id == "stepfun-global" for profile in stepfun.endpoint_profiles)
    assert len(zhipu.endpoint_profiles) >= 1
    assert zhipu.default_endpoint_profile_id == "zhipu-cn"


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
async def test_builtin_provider_catalog_includes_local_gguf():
    providers = await models_router.get_builtin_providers()
    local_gguf = next(p for p in providers if p.id == "local_gguf")

    assert local_gguf.supports_model_list is True
    assert local_gguf.sdk_class == "local_gguf"
    assert local_gguf.protocol == "local_gguf"


@pytest.mark.asyncio
async def test_builtin_provider_catalog_includes_lmstudio():
    providers = await models_router.get_builtin_providers()
    lmstudio = next(p for p in providers if p.id == "lmstudio")

    assert lmstudio.supports_model_list is True
    assert lmstudio.sdk_class == "lmstudio"
    assert lmstudio.protocol == "lmstudio"
    assert lmstudio.base_url == "http://localhost:1234"


@pytest.mark.asyncio
async def test_builtin_provider_info_includes_plugin_source_for_bailian():
    info = await models_router.get_builtin_provider_info("bailian")

    assert info.source_plugin_id == "bailian"
    assert info.source_plugin_name == "Alibaba Cloud (Qwen)"


@pytest.mark.asyncio
async def test_fetch_provider_models_for_local_gguf_returns_results_without_api_key_prompt():
    service = Mock()
    provider = _provider(
        provider_id="local_gguf",
        protocol=ApiProtocol.LOCAL_GGUF,
        base_url="local://gguf",
    )
    adapter = Mock()
    adapter.fetch_models = AsyncMock(
        return_value=[
            {
                "id": "llm/qwen3.gguf",
                "name": "qwen3",
                "tags": ["local", "gguf", "chat"],
            }
        ]
    )

    service.get_provider = AsyncMock(return_value=provider)
    service.get_api_key = AsyncMock(return_value=None)
    service.get_adapter_for_provider = Mock(return_value=adapter)
    service.provider_requires_api_key = Mock(return_value=False)

    result = await models_router.fetch_provider_models("local_gguf", service)

    assert [item.id for item in result] == ["llm/qwen3.gguf"]
    assert result[0].tags == ["local", "gguf", "chat"]
    assert result[0].capabilities is not None
    assert result[0].capabilities["function_calling"] is True
    assert result[0].capabilities["reasoning"] is True
    assert result[0].capabilities["reasoning_controls"]["disable_supported"] is True
    adapter.fetch_models.assert_awaited_once_with("local://gguf", "")


@pytest.mark.asyncio
async def test_fetch_provider_models_for_lmstudio_returns_results_without_api_key_prompt():
    service = Mock()
    provider = _provider(
        provider_id="lmstudio",
        protocol=ApiProtocol.LMSTUDIO,
        base_url="http://localhost:1234",
    )
    adapter = Mock()
    adapter.fetch_models = AsyncMock(
        return_value=[
            {
                "id": "qwen3-30b",
                "name": "Qwen 3 30B",
                "tags": ["chat", "reasoning"],
                "capabilities": {
                    "context_length": 32768,
                    "vision": False,
                    "function_calling": False,
                    "reasoning": True,
                    "requires_interleaved_thinking": False,
                    "streaming": True,
                    "file_upload": False,
                    "image_output": False,
                    "reasoning_controls": {
                        "mode": "enum",
                        "param": "reasoning",
                        "options": ["none", "low", "medium", "high"],
                        "default_option": "medium",
                        "disable_supported": True,
                    },
                },
            }
        ]
    )

    service.get_provider = AsyncMock(return_value=provider)
    service.get_api_key = AsyncMock(return_value=None)
    service.get_adapter_for_provider = Mock(return_value=adapter)
    service.provider_requires_api_key = Mock(return_value=False)

    result = await models_router.fetch_provider_models("lmstudio", service)

    assert [item.id for item in result] == ["qwen3-30b"]
    assert result[0].capabilities is not None
    assert result[0].capabilities["reasoning"] is True
    assert result[0].capabilities["reasoning_controls"]["mode"] == "enum"
    adapter.fetch_models.assert_awaited_once_with("http://localhost:1234", "")


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


@pytest.mark.asyncio
async def test_get_provider_plugins_returns_plugin_statuses(monkeypatch):
    monkeypatch.setattr(
        models_router.AdapterRegistry,
        "get_plugin_statuses",
        lambda: [
            SimpleNamespace(
                id="bailian",
                name="Alibaba Cloud (Qwen)",
                version="1.0.0",
                entrypoint="plugin.py:register_provider",
                plugin_dir="D:/work/pythonProjects/lex_mint/plugins/bailian",
                enabled=True,
                loaded=True,
                adapters_count=1,
                builtin_providers_count=1,
                error=None,
            )
        ],
    )

    response = await models_router.get_provider_plugins()

    assert len(response) == 1
    item = response[0]
    assert item.id == "bailian"
    assert item.loaded is True
    assert item.adapters_count == 1


@pytest.mark.asyncio
async def test_list_providers_attaches_plugin_source_metadata():
    service = Mock()
    service.get_providers = AsyncMock(
        return_value=[
            _provider(
                provider_id="bailian",
                protocol=ApiProtocol.OPENAI,
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            )
        ]
    )

    result = await models_router.list_providers(enabled_only=False, service=service)

    assert len(result) == 1
    item = result[0]
    assert item.id == "bailian"
    assert item.source_plugin_id == "bailian"
