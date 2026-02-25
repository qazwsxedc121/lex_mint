"""
Built-in Provider Definitions

Pre-configured providers with default settings and capabilities.
"""
from .types import (
    ProviderDefinition,
    ModelCapabilities,
    ApiProtocol,
)


# Built-in provider definitions
BUILTIN_PROVIDERS: dict[str, ProviderDefinition] = {
    "deepseek": ProviderDefinition(
        id="deepseek",
        name="DeepSeek",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.deepseek.com",
        sdk_class="deepseek",  # Use dedicated DeepSeek SDK for reasoning_content support
        default_capabilities=ModelCapabilities(
            context_length=64000,
            reasoning=True,
            requires_interleaved_thinking=False,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "kimi": ProviderDefinition(
        id="kimi",
        name="Moonshot (Kimi)",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.moonshot.cn/v1",
        sdk_class="kimi",
        default_capabilities=ModelCapabilities(
            context_length=262144,
            vision=True,
            reasoning=True,
            requires_interleaved_thinking=False,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "zhipu": ProviderDefinition(
        id="zhipu",
        name="Zhipu (GLM)",
        protocol=ApiProtocol.OPENAI,
        base_url="https://open.bigmodel.cn/api/paas/v4",
        sdk_class="zhipu",
        default_capabilities=ModelCapabilities(
            context_length=128000,
            vision=False,
            reasoning=True,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "gemini": ProviderDefinition(
        id="gemini",
        name="Google Gemini",
        protocol=ApiProtocol.GEMINI,
        base_url="https://generativelanguage.googleapis.com/v1beta",
        sdk_class="gemini",
        url_suffix="",
        auto_append_path=False,
        supports_model_list=True,
        default_capabilities=ModelCapabilities(
            context_length=1048576,
            vision=True,
            reasoning=True,
            function_calling=True,
            streaming=True,
        ),
    ),

    "volcengine": ProviderDefinition(
        id="volcengine",
        name="Volcano Engine (Doubao)",
        protocol=ApiProtocol.OPENAI,
        base_url="https://ark.cn-beijing.volces.com/api/v3",
        sdk_class="volcengine",
        url_suffix="",
        auto_append_path=False,
        default_capabilities=ModelCapabilities(
            context_length=128000,
            vision=True,
            reasoning=True,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "openai": ProviderDefinition(
        id="openai",
        name="OpenAI",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.openai.com/v1",
        sdk_class="openai",
        default_capabilities=ModelCapabilities(
            context_length=128000,
            vision=True,
            function_calling=True,
            reasoning=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "openrouter": ProviderDefinition(
        id="openrouter",
        name="OpenRouter",
        protocol=ApiProtocol.OPENAI,
        base_url="https://openrouter.ai/api/v1",
        sdk_class="openai",  # Uses standard OpenAI SDK
        default_capabilities=ModelCapabilities(
            context_length=128000,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "anthropic": ProviderDefinition(
        id="anthropic",
        name="Anthropic",
        protocol=ApiProtocol.ANTHROPIC,
        base_url="https://api.anthropic.com",
        sdk_class="anthropic",
        default_capabilities=ModelCapabilities(
            context_length=200000,
            vision=True,
            reasoning=True,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "ollama": ProviderDefinition(
        id="ollama",
        name="Ollama",
        protocol=ApiProtocol.OLLAMA,
        base_url="http://localhost:11434",
        sdk_class="ollama",
        default_capabilities=ModelCapabilities(
            context_length=4096,
            streaming=True,
        ),
        supports_model_list=True,
        auto_append_path=False,  # Ollama uses different path structure
    ),

    "xai": ProviderDefinition(
        id="xai",
        name="xAI (Grok)",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.x.ai/v1",
        sdk_class="xai",
        default_capabilities=ModelCapabilities(
            context_length=128000,
            reasoning=True,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "together": ProviderDefinition(
        id="together",
        name="Together AI",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.together.xyz/v1",
        sdk_class="openai",
        default_capabilities=ModelCapabilities(
            context_length=32000,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "siliconflow": ProviderDefinition(
        id="siliconflow",
        name="SiliconFlow",
        protocol=ApiProtocol.OPENAI,
        base_url="https://api.siliconflow.cn/v1",
        sdk_class="siliconflow",
        default_capabilities=ModelCapabilities(
            context_length=128000,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),

    "bailian": ProviderDefinition(
        id="bailian",
        name="Alibaba Cloud (Qwen)",
        protocol=ApiProtocol.OPENAI,
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        sdk_class="bailian",
        url_suffix="",
        auto_append_path=False,
        default_capabilities=ModelCapabilities(
            context_length=131072,
            vision=False,
            reasoning=True,
            function_calling=True,
            streaming=True,
        ),
        supports_model_list=True,
    ),
}


def get_builtin_provider(provider_id: str) -> ProviderDefinition | None:
    """
    Get a built-in provider definition by ID.

    Args:
        provider_id: The provider identifier

    Returns:
        ProviderDefinition if found, None otherwise
    """
    return BUILTIN_PROVIDERS.get(provider_id)


def get_all_builtin_providers() -> dict[str, ProviderDefinition]:
    """
    Get all built-in provider definitions.

    Returns:
        Dictionary of provider_id -> ProviderDefinition
    """
    return BUILTIN_PROVIDERS.copy()


def is_builtin_provider(provider_id: str) -> bool:
    """
    Check if a provider ID is a built-in provider.

    Args:
        provider_id: The provider identifier

    Returns:
        True if it's a built-in provider
    """
    return provider_id in BUILTIN_PROVIDERS
