"""Unit tests for provider endpoint probing service."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.api.models.model_config import (
    Provider,
    ProviderEndpointProbeRequest,
)
from src.api.services.provider_probe_service import ProviderProbeService
from src.providers.types import ApiProtocol, CallMode, ProviderType, EndpointProfile


def _provider() -> Provider:
    return Provider(
        id="stepfun",
        name="StepFun",
        type=ProviderType.BUILTIN,
        protocol=ApiProtocol.OPENAI,
        call_mode=CallMode.AUTO,
        base_url="https://api.stepfun.com/v1",
        endpoint_profile_id="stepfun-cn",
        endpoint_profiles=[
            EndpointProfile(
                id="stepfun-cn",
                label="CN",
                base_url="https://api.stepfun.com/v1",
                region_tags=["cn"],
                priority=10,
                probe_method="openai_models",
            ),
            EndpointProfile(
                id="stepfun-global",
                label="Global",
                base_url="https://api.stepfun.ai/v1",
                region_tags=["global"],
                priority=20,
                probe_method="openai_models",
            ),
        ],
        enabled=True,
    )


@pytest.mark.asyncio
async def test_probe_auto_recommends_region_matched_profile():
    model_service = Mock()
    model_service.get_endpoint_profiles_for_provider = Mock(return_value=_provider().endpoint_profiles)
    probe_service = ProviderProbeService(model_service)
    probe_service._probe_openai_models = AsyncMock(  # type: ignore[method-assign]
        return_value={
            "success": True,
            "classification": "ok",
            "http_status": 200,
            "message": "Connection successful",
            "detected_model_count": 3,
        }
    )

    response = await probe_service.probe(
        _provider(),
        request=ProviderEndpointProbeRequest(mode="auto", strict=True, client_region_hint="cn"),
        api_key="test-key",
    )

    assert response.recommended_endpoint_profile_id == "stepfun-cn"
    assert response.recommended_base_url == "https://api.stepfun.com/v1"
    assert len(response.results) == 2


@pytest.mark.asyncio
async def test_probe_manual_unknown_profile_raises_value_error():
    model_service = Mock()
    model_service.get_endpoint_profiles_for_provider = Mock(return_value=_provider().endpoint_profiles)
    probe_service = ProviderProbeService(model_service)

    with pytest.raises(ValueError, match="Unknown endpoint profile"):
        await probe_service.probe(
            _provider(),
            request=ProviderEndpointProbeRequest(
                mode="manual",
                endpoint_profile_id="missing-profile",
                strict=True,
            ),
            api_key="test-key",
        )

