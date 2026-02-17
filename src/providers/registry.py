"""
Adapter Registry

Maps providers to their SDK adapters without text matching.
"""
import logging
from typing import Type, Dict, Optional

from .base import BaseLLMAdapter
from .types import ProviderConfig, ProviderType, ApiProtocol
from .builtin import BUILTIN_PROVIDERS, get_builtin_provider
from .adapters import (
    OpenAIAdapter,
    DeepSeekAdapter,
    AnthropicAdapter,
    OllamaAdapter,
    XAIAdapter,
    ZhipuAdapter,
)

logger = logging.getLogger(__name__)


class AdapterRegistry:
    """
    SDK adapter registry.

    Maps provider configurations to appropriate adapter instances.
    Uses lookup tables instead of text matching for reliability.
    """

    # Mapping of sdk_class names to adapter classes
    _adapters: Dict[str, Type[BaseLLMAdapter]] = {
        "openai": OpenAIAdapter,
        "deepseek": DeepSeekAdapter,
        "anthropic": AnthropicAdapter,
        "ollama": OllamaAdapter,
        "xai": XAIAdapter,
        "zhipu": ZhipuAdapter,
    }

    # Mapping of API protocols to default adapter classes
    _protocol_adapters: Dict[ApiProtocol, str] = {
        ApiProtocol.OPENAI: "openai",
        ApiProtocol.ANTHROPIC: "anthropic",
        ApiProtocol.GEMINI: "gemini",
        ApiProtocol.OLLAMA: "ollama",
    }

    @classmethod
    def get(cls, sdk_type: str) -> BaseLLMAdapter:
        """
        Get an adapter instance by SDK type.

        Args:
            sdk_type: SDK type name (e.g., "openai", "deepseek")

        Returns:
            Adapter instance (defaults to OpenAIAdapter if not found)
        """
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
        # 1. Check if provider has explicit sdk_class override
        if provider.sdk_class:
            logger.debug(f"Using explicit sdk_class: {provider.sdk_class}")
            return cls.get(provider.sdk_class)

        # 2. For builtin providers, use the predefined sdk_class
        if provider.type == ProviderType.BUILTIN:
            builtin = get_builtin_provider(provider.id)
            if builtin:
                logger.debug(f"Using builtin sdk_class for {provider.id}: {builtin.sdk_class}")
                return cls.get(builtin.sdk_class)

        # 3. For custom providers, determine adapter from protocol
        sdk_type = cls._protocol_adapters.get(provider.protocol, "openai")
        logger.debug(f"Using protocol-based sdk for {provider.id}: {sdk_type}")
        return cls.get(sdk_type)

    @classmethod
    def get_for_provider_id(
        cls,
        provider_id: str,
        provider_type: ProviderType = ProviderType.BUILTIN,
        protocol: ApiProtocol = ApiProtocol.OPENAI,
        sdk_class: Optional[str] = None,
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
    def register(cls, name: str, adapter_class: Type[BaseLLMAdapter]):
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
