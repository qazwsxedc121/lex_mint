"""
LLM Provider Abstraction Layer

This package provides a unified interface for interacting with different LLM providers.

Key components:
- types: Data models and enums
- builtin: Pre-configured provider definitions
- registry: Adapter lookup without text matching
- adapters: SDK-specific implementations

Usage:
    from src.providers import AdapterRegistry, ProviderConfig, ModelCapabilities

    # Get adapter for a provider
    adapter = AdapterRegistry.get_for_provider(provider_config)

    # Create LLM instance
    llm = adapter.create_llm(
        model="deepseek-chat",
        base_url="https://api.deepseek.com",
        api_key="your-key",
        thinking_enabled=True,
    )

    # Stream responses
    async for chunk in adapter.stream(llm, messages):
        if chunk.thinking:
            print(f"<think>{chunk.thinking}</think>")
        if chunk.content:
            print(chunk.content, end="")
"""
from .types import (
    ApiProtocol,
    CallMode,
    ProviderType,
    ReasoningControlMode,
    ReasoningControls,
    TokenUsage,
    CostInfo,
    ModelCapabilities,
    ProviderDefinition,
    ProviderConfig,
    ModelConfig,
    StreamChunk,
    LLMResponse,
)
from .builtin import (
    BUILTIN_PROVIDERS,
    get_builtin_provider,
    get_all_builtin_providers,
    is_builtin_provider,
)
from .registry import (
    AdapterRegistry,
    get_adapter,
)
from .base import BaseLLMAdapter

__all__ = [
    # Types
    "ApiProtocol",
    "CallMode",
    "ProviderType",
    "ReasoningControlMode",
    "ReasoningControls",
    "TokenUsage",
    "CostInfo",
    "ModelCapabilities",
    "ProviderDefinition",
    "ProviderConfig",
    "ModelConfig",
    "StreamChunk",
    "LLMResponse",
    # Builtin
    "BUILTIN_PROVIDERS",
    "get_builtin_provider",
    "get_all_builtin_providers",
    "is_builtin_provider",
    # Registry
    "AdapterRegistry",
    "get_adapter",
    # Base
    "BaseLLMAdapter",
]
