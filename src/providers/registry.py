"""
Adapter Registry

Maps providers to their SDK adapters without text matching.
"""

import logging
from collections.abc import AsyncIterator
from typing import Any, cast

from langchain_core.messages import BaseMessage

from .adapters import (
    LMSTUDIO_IMPORT_ERROR,
    AnthropicAdapter,
    BailianAdapter,
    DeepSeekAdapter,
    GeminiAdapter,
    KimiAdapter,
    LmStudioAdapter,
    LocalGgufAdapter,
    OllamaAdapter,
    OpenAIAdapter,
    OpenRouterAdapter,
    SiliconFlowAdapter,
    VolcEngineAdapter,
    XAIAdapter,
    ZhipuAdapter,
)
from .base import BaseLLMAdapter
from .builtin import get_builtin_provider
from .types import ApiProtocol, ProviderConfig, ProviderType

logger = logging.getLogger(__name__)


class MissingDependencyAdapter(BaseLLMAdapter):
    """Adapter placeholder used when an optional provider SDK is not installed."""

    def __init__(
        self, *, sdk_type: str, dependency_name: str, import_error: Exception | None = None
    ):
        self._sdk_type = sdk_type
        self._dependency_name = dependency_name
        self._import_error = import_error

    def _message(self) -> str:
        detail = f": {self._import_error}" if self._import_error else ""
        return (
            f"Optional dependency '{self._dependency_name}' is required for provider '{self._sdk_type}'"
            f" but is not installed{detail}."
        )

    def _raise(self) -> None:
        raise RuntimeError(self._message())

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs,
    ) -> Any:
        self._raise()

    async def invoke(
        self,
        llm: Any,
        messages: list[BaseMessage],
        **kwargs,
    ):
        self._raise()

    def stream(
        self,
        llm: Any,
        messages: list[BaseMessage],
        **kwargs,
    ) -> AsyncIterator:
        async def _missing_dependency_stream():
            self._raise()
            yield None

        return cast(AsyncIterator[Any], _missing_dependency_stream())

    async def fetch_models(self, base_url: str, api_key: str):
        self._raise()

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: str | None = None,
    ) -> tuple[bool, str]:
        return False, self._message()


class AdapterRegistry:
    """
    SDK adapter registry.

    Maps provider configurations to appropriate adapter instances.
    Uses lookup tables instead of text matching for reliability.
    """

    # Mapping of sdk_class names to adapter classes
    _adapters: dict[str, type[BaseLLMAdapter]] = {
        "openai": OpenAIAdapter,
        "openrouter": OpenRouterAdapter,
        "deepseek": DeepSeekAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter,
        "xai": XAIAdapter,
        "zhipu": ZhipuAdapter,
        "volcengine": VolcEngineAdapter,
        "gemini": GeminiAdapter,
        "bailian": BailianAdapter,
        "siliconflow": SiliconFlowAdapter,
        "kimi": KimiAdapter,
        "local_gguf": LocalGgufAdapter,
    }
    if LmStudioAdapter is not None:
        _adapters["lmstudio"] = LmStudioAdapter

    # Mapping of API protocols to default adapter classes
    _protocol_adapters: dict[ApiProtocol, str] = {
        ApiProtocol.OPENAI: "openai",
        ApiProtocol.ANTHROPIC: "anthropic",
        ApiProtocol.GEMINI: "gemini",
        ApiProtocol.OLLAMA: "ollama",
        ApiProtocol.LMSTUDIO: "lmstudio",
        ApiProtocol.LOCAL_GGUF: "local_gguf",
    }

    @classmethod
    def resolve_sdk_type_for_provider(cls, provider: ProviderConfig) -> str:
        """
        Resolve the adapter key for a provider without instantiating the adapter.

        Priority:
        1) explicit provider.sdk_class
        2) builtin provider definition sdk_class
        3) protocol-based fallback
        """
        if provider.sdk_class:
            return provider.sdk_class

        if provider.type == ProviderType.BUILTIN:
            builtin = get_builtin_provider(provider.id)
            if builtin:
                return builtin.sdk_class

        return cls._protocol_adapters.get(provider.protocol, "openai")

    @classmethod
    def get(cls, sdk_type: str) -> BaseLLMAdapter:
        """
        Get an adapter instance by SDK type.

        Args:
            sdk_type: SDK type name (e.g., "openai", "deepseek")

        Returns:
            Adapter instance (defaults to OpenAIAdapter if not found)
        """
        if sdk_type == "lmstudio" and LmStudioAdapter is None:
            logger.warning(
                "LM Studio adapter requested but optional dependency 'lmstudio' is not installed"
            )
            return MissingDependencyAdapter(
                sdk_type="lmstudio",
                dependency_name="lmstudio",
                import_error=LMSTUDIO_IMPORT_ERROR,
            )

        adapter_class = cls._adapters.get(sdk_type, OpenAIAdapter)
        return adapter_class()

    @classmethod
    def get_for_provider(cls, provider: ProviderConfig) -> BaseLLMAdapter:
        """
        Get the appropriate adapter for a provider configuration.

        This is the main entry point for getting adapters.
        No text matching - uses structured configuration instead.

        Args:
            provider: Provider configuration

        Returns:
            Appropriate adapter instance for the provider
        """
        sdk_type = cls.resolve_sdk_type_for_provider(provider)
        logger.debug(f"Resolved sdk for {provider.id}: {sdk_type}")
        return cls.get(sdk_type)

    @classmethod
    def get_for_provider_id(
        cls,
        provider_id: str,
        provider_type: ProviderType = ProviderType.BUILTIN,
        protocol: ApiProtocol = ApiProtocol.OPENAI,
        sdk_class: str | None = None,
    ) -> BaseLLMAdapter:
        """
        Get adapter by provider ID with optional overrides.

        Convenience method when you don't have a full ProviderConfig.

        Args:
            provider_id: Provider identifier
            provider_type: Provider type (builtin or custom)
            protocol: API protocol type
            sdk_class: Explicit SDK class override

        Returns:
            Appropriate adapter instance
        """
        # If explicit sdk_class provided, use it
        if sdk_class:
            return cls.get(sdk_class)

        # For builtin providers, look up the sdk_class
        if provider_type == ProviderType.BUILTIN:
            builtin = get_builtin_provider(provider_id)
            if builtin:
                return cls.get(builtin.sdk_class)

        # Fall back to protocol-based selection
        sdk_type = cls._protocol_adapters.get(protocol, "openai")
        return cls.get(sdk_type)

    @classmethod
    def register(cls, name: str, adapter_class: type[BaseLLMAdapter]):
        """
        Register a new adapter class.

        Args:
            name: Name to register under
            adapter_class: Adapter class to register
        """
        cls._adapters[name] = adapter_class
        logger.info(f"Registered adapter: {name}")

    @classmethod
    def get_available_adapters(cls) -> list[str]:
        """
        Get list of available adapter names.

        Returns:
            List of registered adapter names
        """
        return list(cls._adapters.keys())


# Convenience function for easy import
def get_adapter(provider: ProviderConfig) -> BaseLLMAdapter:
    """
    Get the appropriate adapter for a provider.

    This is the main entry point for the adapter system.

    Args:
        provider: Provider configuration

    Returns:
        Adapter instance for the provider
    """
    return AdapterRegistry.get_for_provider(provider)
