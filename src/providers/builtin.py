"""
Built-in Provider Definitions

Pre-configured providers with default settings and models.
"""
from .types import (
    ProviderDefinition,
    ModelDefinition,
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
            function_calling=True,
            streaming=True,
        ),
        builtin_models=[
            ModelDefinition(
                id="deepseek-chat",
                name="DeepSeek Chat",
                capabilities=ModelCapabilities(
                    context_length=64000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="deepseek-reasoner",
                name="DeepSeek Reasoner",
                capabilities=ModelCapabilities(
                    context_length=64000,
                    reasoning=True,
                    function_calling=False,
                )
            ),
        ],
        supports_model_list=False,
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
        builtin_models=[
            ModelDefinition(
                id="glm-5",
                name="GLM-5",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-4.7",
                name="GLM-4.7",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-4.6",
                name="GLM-4.6",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-4.6-flash",
                name="GLM-4.6 Flash",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-4.6v",
                name="GLM-4.6V",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-4.5",
                name="GLM-4.5",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-4.5-air",
                name="GLM-4.5 Air",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-4.5-flash",
                name="GLM-4.5 Flash",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-z1-air",
                name="GLM-Z1 Air",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="glm-z1-airx",
                name="GLM-Z1 AirX",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
        ],
        supports_model_list=False,
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
        builtin_models=[
            ModelDefinition(
                id="doubao-seed-2-0-pro-260215",
                name="Doubao Seed 2.0 Pro",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="doubao-seed-2-0-lite-260215",
                name="Doubao Seed 2.0 Lite",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="doubao-seed-2-0-mini-260215",
                name="Doubao Seed 2.0 Mini",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="doubao-seed-2-0-code-preview-260215",
                name="Doubao Seed 2.0 Code",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="doubao-1-5-pro-256k-250115",
                name="Doubao 1.5 Pro 256K",
                capabilities=ModelCapabilities(
                    context_length=256000,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="doubao-1-5-pro-32k-250115",
                name="Doubao 1.5 Pro 32K",
                capabilities=ModelCapabilities(
                    context_length=32000,
                    function_calling=True,
                )
            ),
        ],
        supports_model_list=False,
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
        builtin_models=[
            ModelDefinition(
                id="gpt-4-turbo",
                name="GPT-4 Turbo",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="gpt-4o",
                name="GPT-4o",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="gpt-4o-mini",
                name="GPT-4o Mini",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    vision=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="o1",
                name="OpenAI o1",
                capabilities=ModelCapabilities(
                    context_length=200000,
                    reasoning=True,
                    function_calling=False,
                )
            ),
            ModelDefinition(
                id="o1-mini",
                name="OpenAI o1 Mini",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=False,
                )
            ),
        ],
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
        builtin_models=[],  # Models fetched dynamically
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
        builtin_models=[
            # Claude 4.x Family (Current)
            ModelDefinition(
                id="claude-sonnet-4-5-20250929",
                name="Claude Sonnet 4.5",
                capabilities=ModelCapabilities(
                    context_length=200000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="claude-opus-4-5-20251101",
                name="Claude Opus 4.5",
                capabilities=ModelCapabilities(
                    context_length=200000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="claude-sonnet-4-20250514",
                name="Claude Sonnet 4",
                capabilities=ModelCapabilities(
                    context_length=200000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="claude-haiku-4-5-20250630",
                name="Claude Haiku 4.5",
                capabilities=ModelCapabilities(
                    context_length=200000,
                    vision=True,
                    function_calling=True,
                )
            ),
            # Claude 3.5 (Legacy - still supported)
            ModelDefinition(
                id="claude-3-5-sonnet-20241022",
                name="Claude 3.5 Sonnet (Legacy)",
                capabilities=ModelCapabilities(
                    context_length=200000,
                    vision=True,
                    reasoning=True,
                    function_calling=True,
                )
            ),
        ],
        supports_model_list=False,
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
        builtin_models=[],  # Models fetched dynamically from local Ollama
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
        builtin_models=[
            ModelDefinition(
                id="grok-4",
                name="Grok 4",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="grok-4-fast",
                name="Grok 4.1 Fast",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    reasoning=True,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="grok-3",
                name="Grok 3",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    function_calling=True,
                )
            ),
            ModelDefinition(
                id="grok-3-mini",
                name="Grok 3 Mini",
                capabilities=ModelCapabilities(
                    context_length=128000,
                    function_calling=True,
                )
            ),
        ],
        supports_model_list=False,
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
        builtin_models=[],  # Models fetched dynamically
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
