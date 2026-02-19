"""Unit tests for provider call mode auto-resolution helpers."""

from src.api.models.model_config import Provider
from src.api.services.model_config_service import ModelConfigService
from src.providers.types import ApiProtocol, CallMode, ProviderType


def _service() -> ModelConfigService:
    """Create a service instance without running filesystem initialization."""
    return ModelConfigService.__new__(ModelConfigService)


def _provider(
    *,
    provider_id: str,
    protocol: ApiProtocol = ApiProtocol.OPENAI,
    base_url: str = "https://example.com/v1",
    provider_type: ProviderType = ProviderType.CUSTOM,
    call_mode: CallMode = CallMode.AUTO,
    sdk_class: str | None = None,
) -> Provider:
    return Provider(
        id=provider_id,
        name=provider_id,
        type=provider_type,
        protocol=protocol,
        call_mode=call_mode,
        base_url=base_url,
        enabled=True,
        sdk_class=sdk_class,
    )


def test_resolve_effective_call_mode_respects_explicit_override():
    service = _service()
    provider = _provider(provider_id="my-provider", call_mode=CallMode.CHAT_COMPLETIONS)
    assert service.resolve_effective_call_mode(provider) == CallMode.CHAT_COMPLETIONS


def test_resolve_effective_call_mode_native_for_anthropic():
    service = _service()
    provider = _provider(provider_id="anthropic-custom", protocol=ApiProtocol.ANTHROPIC)
    assert service.resolve_effective_call_mode(provider) == CallMode.NATIVE


def test_resolve_effective_call_mode_native_for_gemini():
    service = _service()
    provider = _provider(provider_id="gemini-custom", protocol=ApiProtocol.GEMINI)
    assert service.resolve_effective_call_mode(provider) == CallMode.NATIVE


def test_resolve_effective_call_mode_native_for_ollama():
    service = _service()
    provider = _provider(provider_id="ollama-custom", protocol=ApiProtocol.OLLAMA)
    assert service.resolve_effective_call_mode(provider) == CallMode.NATIVE


def test_resolve_effective_call_mode_openai_provider_id_defaults_to_responses():
    service = _service()
    provider = _provider(
        provider_id="openai",
        base_url="https://not-openai.example/v1",
        provider_type=ProviderType.BUILTIN,
    )
    assert service.resolve_effective_call_mode(provider) == CallMode.RESPONSES


def test_resolve_effective_call_mode_base_url_openai_host_defaults_to_responses():
    service = _service()
    provider = _provider(
        provider_id="my-openai-proxy",
        base_url="https://api.openai.com/v1",
    )
    assert service.resolve_effective_call_mode(provider) == CallMode.RESPONSES


def test_resolve_effective_call_mode_scheme_less_openai_host_defaults_to_responses():
    service = _service()
    provider = _provider(
        provider_id="my-openai-proxy",
        base_url="api.openai.com/v1",
    )
    assert service.resolve_effective_call_mode(provider) == CallMode.RESPONSES


def test_resolve_effective_call_mode_other_openai_compatible_defaults_to_chat():
    service = _service()
    provider = _provider(
        provider_id="deepseek-like",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.deepseek.com",
    )
    assert service.resolve_effective_call_mode(provider) == CallMode.CHAT_COMPLETIONS


def test_resolve_effective_call_mode_uses_adapter_family_from_sdk_override():
    service = _service()
    provider = _provider(
        provider_id="custom-anthropic-via-openai-protocol",
        protocol=ApiProtocol.OPENAI,
        sdk_class="anthropic",
        base_url="https://example.com/v1",
    )
    assert service.resolve_effective_call_mode(provider) == CallMode.NATIVE


def test_provider_requires_api_key_for_openai_compatible():
    service = _service()
    provider = _provider(provider_id="deepseek-like", protocol=ApiProtocol.OPENAI)
    assert service.provider_requires_api_key(provider) is True


def test_provider_does_not_require_api_key_for_ollama():
    service = _service()
    provider = _provider(provider_id="local-ollama", protocol=ApiProtocol.OLLAMA)
    assert service.provider_requires_api_key(provider) is False


def test_provider_does_not_require_api_key_for_ollama_sdk_override():
    service = _service()
    provider = _provider(
        provider_id="local-with-override",
        protocol=ApiProtocol.OPENAI,
        sdk_class="ollama",
    )
    assert service.provider_requires_api_key(provider) is False
