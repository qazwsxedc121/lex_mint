"""Additional CRUD and error-path tests for the models router."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException

from src.api.routers import models as models_router
from src.domain.models.model_config import (
    DefaultConfig,
    Model,
    ModelTestRequest,
    Provider,
    ProviderCreate,
    ProviderUpdate,
)
from src.providers.types import ApiProtocol, CallMode, ModelCapabilities, ProviderType


def _provider(
    provider_id: str = "custom-provider", *, base_url: str = "https://example.com/v1"
) -> Provider:
    return Provider(
        id=provider_id,
        name=provider_id,
        type=ProviderType.CUSTOM,
        protocol=ApiProtocol.OPENAI,
        call_mode=CallMode.AUTO,
        base_url=base_url,
        enabled=True,
    )


def _model(model_id: str = "model-1", *, provider_id: str = "custom-provider") -> Model:
    return Model(id=model_id, name=model_id, provider_id=provider_id, tags=["chat"])


@pytest.mark.asyncio
async def test_provider_crud_routes_and_endpoint_profile_paths():
    service = Mock()
    provider = _provider()
    service.get_providers = AsyncMock(return_value=[provider])

    async def _get_provider(provider_id: str, include_masked_key: bool = False):
        _ = include_masked_key
        return None if provider_id == "missing" else provider

    service.get_provider = AsyncMock(side_effect=_get_provider)
    service.add_provider = AsyncMock()
    service.set_api_key = AsyncMock()
    service.update_provider = AsyncMock()
    service.resolve_endpoint_profile_id_for_base_url = Mock(return_value="resolved-profile")
    service.resolve_endpoint_profile_base_url = Mock(return_value="https://resolved.example.com/v1")
    service.get_endpoint_profiles_for_provider = Mock(return_value=[])
    service.recommend_endpoint_profile_id = Mock(return_value="recommended-profile")
    service.delete_provider = AsyncMock()
    service.delete_api_key = AsyncMock()

    providers = await models_router.list_providers(enabled_only=True, service=service)  # type: ignore[arg-type]
    assert providers[0].id == "custom-provider"

    got = await models_router.get_provider(
        "custom-provider", include_masked_key=True, service=service
    )  # type: ignore[arg-type]
    assert got.id == "custom-provider"

    created = await models_router.create_provider(
        ProviderCreate(
            id="custom-provider",
            name="Custom",
            type=ProviderType.CUSTOM,
            protocol=ApiProtocol.OPENAI,
            call_mode=CallMode.AUTO,
            base_url="https://example.com/v1",
            api_key="secret",
        ),
        service=service,  # type: ignore[arg-type]
    )
    assert created["id"] == "custom-provider"
    service.add_provider.assert_awaited_once()
    service.set_api_key.assert_awaited_once_with("custom-provider", "secret")

    updated = await models_router.update_provider(
        "custom-provider",
        ProviderUpdate(
            name="Updated",
            base_url="https://new.example.com/v1",
            enabled=False,
            auto_append_path=False,
            api_key="new-secret",
        ),
        service=service,  # type: ignore[arg-type]
    )
    assert updated["message"] == "Provider updated successfully"
    service.update_provider.assert_awaited_once()
    service.set_api_key.assert_awaited_with("custom-provider", "new-secret")

    with pytest.raises(HTTPException) as exc_info:
        await models_router.get_provider("missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    endpoint_profiles = await models_router.get_provider_endpoint_profiles(
        "custom-provider",
        client_region_hint="cn",
        service=service,  # type: ignore[arg-type]
    )
    assert endpoint_profiles.recommended_endpoint_profile_id == "recommended-profile"

    deleted = await models_router.delete_provider("custom-provider", service=service)  # type: ignore[arg-type]
    assert deleted["message"] == "Provider deleted successfully"
    service.delete_api_key.assert_awaited_once_with("custom-provider")


@pytest.mark.asyncio
async def test_provider_route_errors_and_probe_paths(monkeypatch):
    service = Mock()
    provider = _provider()
    service.get_provider = AsyncMock(side_effect=[None, provider, provider, provider, provider])
    service.add_provider = AsyncMock(side_effect=ValueError("duplicate"))
    service.get_api_key = AsyncMock(return_value=None)
    service.provider_requires_api_key = Mock(return_value=True)
    service.delete_provider = AsyncMock(side_effect=ValueError("cannot delete"))
    service.delete_api_key = AsyncMock()
    service.resolve_endpoint_profile_base_url = Mock(return_value=None)

    with pytest.raises(HTTPException) as exc_info:
        await models_router.create_provider(
            ProviderCreate(
                id="builtin-ish",
                name="Builtin",
                type=ProviderType.BUILTIN,
                protocol=ApiProtocol.OPENAI,
                call_mode=CallMode.AUTO,
                base_url="https://example.com/v1",
                api_key="secret",
            ),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    custom_create = ProviderCreate(
        id="duplicate",
        name="Duplicate",
        type=ProviderType.CUSTOM,
        protocol=ApiProtocol.OPENAI,
        call_mode=CallMode.AUTO,
        base_url="https://example.com/v1",
        api_key="secret",
    )
    with pytest.raises(HTTPException) as exc_info:
        await models_router.create_provider(custom_create, service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await models_router.update_provider(
            "missing",
            ProviderUpdate(name="Updated", api_key=None),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await models_router.update_provider(
            "custom-provider",
            ProviderUpdate(endpoint_profile_id="unknown-profile", api_key=None),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await models_router.probe_provider_endpoints(
            "custom-provider",
            models_router.ProviderEndpointProbeRequest(mode="auto", strict=False),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await models_router.probe_provider_endpoints(
            "custom-provider",
            models_router.ProviderEndpointProbeRequest(
                mode="auto", strict=True, use_stored_key=True
            ),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    class _ProbeService:
        def __init__(self, _service):
            self._service = _service

        async def probe(self, provider, request, api_key):
            _ = provider, request, api_key
            raise ValueError("probe failed")

    monkeypatch.setattr(models_router, "ProviderProbeService", _ProbeService)
    with pytest.raises(HTTPException) as exc_info:
        await models_router.probe_provider_endpoints(
            "custom-provider",
            models_router.ProviderEndpointProbeRequest(
                mode="auto", strict=True, use_stored_key=False, api_key="secret"
            ),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await models_router.delete_provider("custom-provider", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400


@pytest.mark.asyncio
async def test_model_crud_default_and_capabilities_routes():
    service = Mock()
    provider = _provider()
    model = _model()
    service.get_models = AsyncMock(return_value=[model])

    async def _get_model(model_id: str):
        return None if model_id == "missing" else model

    async def _get_provider(provider_id: str, include_masked_key: bool = False):
        _ = include_masked_key
        return None if provider_id in {"missing", "missing-provider"} else provider

    service.get_model = AsyncMock(side_effect=_get_model)
    service.add_model = AsyncMock()
    service.update_model = AsyncMock(
        side_effect=[None, ValueError("Model not found"), ValueError("invalid model")]
    )
    service.delete_model = AsyncMock(side_effect=[None, ValueError("delete failed")])
    service.test_provider_connection = AsyncMock(return_value=(True, "connected"))
    service.get_provider = AsyncMock(side_effect=_get_provider)
    service.get_api_key = AsyncMock(side_effect=["stored-key", None])
    service.get_default_config = AsyncMock(
        return_value=DefaultConfig(provider="custom-provider", model="model-1")
    )
    service.set_default_model = AsyncMock(side_effect=[None, ValueError("bad default")])
    service.get_reasoning_supported_patterns = AsyncMock(return_value=["gpt-*"])
    service.get_merged_capabilities = Mock(return_value=ModelCapabilities(reasoning=True))

    listed = await models_router.list_models(
        provider_id="custom-provider", enabled_only=True, service=service
    )  # type: ignore[arg-type]
    assert listed[0].id == "model-1"

    got = await models_router.get_model("model-1", service=service)  # type: ignore[arg-type]
    assert got.provider_id == "custom-provider"

    created = await models_router.create_model(model, service=service)  # type: ignore[arg-type]
    assert created["id"] == "model-1"

    updated = await models_router.update_model("model-1", model, service=service)  # type: ignore[arg-type]
    assert updated["message"] == "Model updated successfully"

    with pytest.raises(HTTPException) as exc_info:
        await models_router.get_model("missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await models_router.update_model("missing", model, service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await models_router.update_model("invalid", model, service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400

    deleted = await models_router.delete_model("model-1", service=service)  # type: ignore[arg-type]
    assert deleted["message"] == "Model deleted successfully"

    with pytest.raises(HTTPException) as exc_info:
        await models_router.delete_model("model-1", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400

    success = await models_router.test_model_connection(
        ModelTestRequest(model_id="custom-provider:model-1"),
        service=service,  # type: ignore[arg-type]
    )
    assert success.success is True

    missing_provider = await models_router.test_model_connection(
        ModelTestRequest(model_id="missing:model-1"),
        service=service,  # type: ignore[arg-type]
    )
    assert missing_provider.success is False

    service.get_models = AsyncMock(return_value=[])
    missing_model = await models_router.test_model_connection(
        ModelTestRequest(model_id="custom-provider:model-1"),
        service=service,  # type: ignore[arg-type]
    )
    assert missing_model.success is False

    service.get_models = AsyncMock(return_value=[model])
    no_key = await models_router.test_model_connection(
        ModelTestRequest(model_id="custom-provider:model-1"),
        service=service,  # type: ignore[arg-type]
    )
    assert no_key.success is False

    invalid_format = await models_router.test_model_connection(
        ModelTestRequest(model_id="broken-format"),
        service=service,  # type: ignore[arg-type]
    )
    assert invalid_format.success is False

    defaults = await models_router.get_default_config(service=service)  # type: ignore[arg-type]
    assert defaults.provider == "custom-provider"

    updated_default = await models_router.set_default_config(
        "custom-provider", "model-1", service=service
    )  # type: ignore[arg-type]
    assert updated_default["message"] == "Default model updated successfully"

    with pytest.raises(HTTPException) as exc_info:
        await models_router.set_default_config("custom-provider", "bad-model", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400

    patterns = await models_router.get_reasoning_supported_patterns(service=service)  # type: ignore[arg-type]
    assert patterns == ["gpt-*"]

    capabilities = await models_router.get_model_capabilities("model-1", service=service)  # type: ignore[arg-type]
    assert capabilities.capabilities.reasoning is True

    with pytest.raises(HTTPException) as exc_info:
        await models_router.get_model_capabilities("missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    missing_provider_model = _model(provider_id="missing-provider")
    service.get_model = AsyncMock(return_value=missing_provider_model)
    with pytest.raises(HTTPException) as exc_info:
        await models_router.get_model_capabilities("model-1", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_fetch_provider_models_and_protocol_routes(monkeypatch):
    service = Mock()
    provider = _provider(provider_id="fetchable")
    adapter = Mock()
    adapter.fetch_models = AsyncMock(
        side_effect=[
            [
                {"id": "model-a", "name": "Model A", "tags": "chat, fast"},
                {"id": "model-b", "capabilities": {"reasoning": True}, "tags": ["reasoning"]},
            ],
            [],
            RuntimeError("adapter failed"),
        ]
    )
    service.get_provider = AsyncMock(side_effect=[provider, provider, provider, None])
    service.get_api_key = AsyncMock(side_effect=["stored-key", None, "stored-key"])
    service.get_adapter_for_provider = Mock(return_value=adapter)
    service.provider_requires_api_key = Mock(return_value=True)

    builtin_definition = Mock(supports_model_list=True)
    monkeypatch.setattr(
        models_router,
        "get_builtin_provider",
        lambda provider_id: builtin_definition if provider_id == "fetchable" else None,
    )

    fetched = await models_router.fetch_provider_models("fetchable", service=service)  # type: ignore[arg-type]
    assert [item.id for item in fetched] == ["model-a", "model-b"]
    assert fetched[0].tags == ["chat", "fast"]

    with pytest.raises(HTTPException) as exc_info:
        await models_router.fetch_provider_models("fetchable", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await models_router.fetch_provider_models("fetchable", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 500

    with pytest.raises(HTTPException) as exc_info:
        await models_router.fetch_provider_models("missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    protocols = await models_router.get_available_protocols()
    assert any(item["id"] == ApiProtocol.OPENAI.value for item in protocols)
