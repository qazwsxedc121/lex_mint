"""
Provider Types and Data Models

Defines enums and Pydantic models for the LLM provider abstraction layer.
"""
from enum import Enum
from typing import List, Optional, Any
from pydantic import BaseModel, Field


class ApiProtocol(str, Enum):
    """Supported API protocol types"""
    OPENAI = "openai"           # OpenAI and compatible APIs
    ANTHROPIC = "anthropic"     # Anthropic Claude API
    GEMINI = "gemini"           # Google Gemini API
    OLLAMA = "ollama"           # Ollama local models


class ProviderType(str, Enum):
    """Provider source type"""
    BUILTIN = "builtin"    # Built-in provider (e.g., deepseek, openai)
    CUSTOM = "custom"      # User-defined custom provider


class TokenUsage(BaseModel):
    """Token usage information from LLM response."""
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    reasoning_tokens: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Optional[dict]) -> Optional["TokenUsage"]:
        """Create TokenUsage from provider-specific dict format."""
        if not data:
            return None
        return cls(
            prompt_tokens=data.get("prompt_tokens", data.get("input_tokens", 0)),
            completion_tokens=data.get("completion_tokens", data.get("output_tokens", 0)),
            total_tokens=data.get("total_tokens", 0) or (
                data.get("prompt_tokens", data.get("input_tokens", 0)) +
                data.get("completion_tokens", data.get("output_tokens", 0))
            ),
            reasoning_tokens=data.get("reasoning_tokens"),
        )

    @classmethod
    def extract_from_chunk(cls, chunk) -> Optional["TokenUsage"]:
        """Extract TokenUsage from a LangChain streaming chunk.

        Checks usage_metadata (dict or object) and response_metadata.
        Returns None if no valid usage data found.
        """
        # Check usage_metadata first (LangChain's unified format)
        if hasattr(chunk, 'usage_metadata') and chunk.usage_metadata:
            um = chunk.usage_metadata
            if isinstance(um, dict):
                input_t = um.get('input_tokens', 0) or 0
                output_t = um.get('output_tokens', 0) or 0
                total_t = um.get('total_tokens', 0) or 0
            else:
                input_t = getattr(um, 'input_tokens', 0) or 0
                output_t = getattr(um, 'output_tokens', 0) or 0
                total_t = getattr(um, 'total_tokens', 0) or 0
            if input_t > 0 or output_t > 0 or total_t > 0:
                return cls(
                    prompt_tokens=input_t,
                    completion_tokens=output_t,
                    total_tokens=total_t or (input_t + output_t),
                )

        # Fallback to response_metadata
        if hasattr(chunk, 'response_metadata') and chunk.response_metadata:
            raw_usage = chunk.response_metadata.get('usage')
            if raw_usage:
                return cls.from_dict(raw_usage)

        return None


class CostInfo(BaseModel):
    """Cost information for LLM usage."""
    input_cost: float = 0.0
    output_cost: float = 0.0
    total_cost: float = 0.0
    currency: str = "USD"


class ModelCapabilities(BaseModel):
    """Model capability declaration"""
    context_length: int = Field(default=4096, description="Context window size in tokens")
    vision: bool = Field(default=False, description="Supports image input")
    function_calling: bool = Field(default=False, description="Supports function/tool calling")
    reasoning: bool = Field(default=False, description="Supports thinking/reasoning mode")
    streaming: bool = Field(default=True, description="Supports streaming output")
    file_upload: bool = Field(default=False, description="Supports file upload")
    image_output: bool = Field(default=False, description="Supports image generation")

    def merge_with(self, override: Optional["ModelCapabilities"]) -> "ModelCapabilities":
        """
        Merge with another capabilities object, override takes precedence.

        Args:
            override: Capabilities to override with (model-level capabilities)

        Returns:
            New merged ModelCapabilities instance
        """
        if override is None:
            return self.model_copy()

        # Create a merged dict where override values take precedence
        base_dict = self.model_dump()
        override_dict = override.model_dump(exclude_unset=True)

        for key, value in override_dict.items():
            if value is not None:
                base_dict[key] = value

        return ModelCapabilities(**base_dict)


class ModelDefinition(BaseModel):
    """Built-in model definition (minimal info for builtin providers)"""
    id: str = Field(..., description="Model ID (e.g., deepseek-chat)")
    name: str = Field(..., description="Display name")
    capabilities: Optional[ModelCapabilities] = Field(
        default=None,
        description="Model-specific capabilities (overrides provider defaults)"
    )


class ProviderDefinition(BaseModel):
    """
    Built-in provider definition.

    This is used to define the built-in providers with their default configurations.
    """
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name")
    protocol: ApiProtocol = Field(default=ApiProtocol.OPENAI, description="API protocol type")
    base_url: str = Field(..., description="Default API base URL")
    api_key_env: str = Field(..., description="Environment variable name for API key")
    sdk_class: str = Field(default="openai", description="SDK adapter class to use")
    default_capabilities: ModelCapabilities = Field(
        default_factory=ModelCapabilities,
        description="Default capabilities for models under this provider"
    )
    builtin_models: List[ModelDefinition] = Field(
        default_factory=list,
        description="Pre-defined models for this provider"
    )
    url_suffix: str = Field(default="/v1", description="URL suffix for API calls")
    auto_append_path: bool = Field(default=True, description="Auto-append path to base URL")
    supports_model_list: bool = Field(default=False, description="Supports fetching model list via API")


class ProviderConfig(BaseModel):
    """
    Provider configuration (stored in config file).

    This represents the user's configuration for a provider, which may override
    builtin defaults or define custom providers.
    """
    # === Basic info ===
    id: str = Field(..., description="Unique identifier")
    name: str = Field(..., description="Display name")
    type: ProviderType = Field(default=ProviderType.BUILTIN, description="Provider source type")

    # === API configuration ===
    protocol: ApiProtocol = Field(default=ApiProtocol.OPENAI, description="API protocol type")
    base_url: str = Field(..., description="API base URL")
    api_key_env: str = Field(default="", description="Environment variable name for API key")
    api_keys: List[str] = Field(default_factory=list, description="Multiple API keys for rotation")

    # === State ===
    enabled: bool = Field(default=True, description="Whether the provider is enabled")

    # === Capability declaration (provider-level defaults) ===
    default_capabilities: Optional[ModelCapabilities] = Field(
        default=None,
        description="Default capabilities for models under this provider"
    )

    # === Advanced configuration ===
    url_suffix: str = Field(default="/v1", description="URL suffix for API calls")
    auto_append_path: bool = Field(default=True, description="Auto-append path to base URL")
    supports_model_list: bool = Field(default=False, description="Supports fetching model list")
    sdk_class: Optional[str] = Field(default=None, description="Override SDK adapter class")

    # === Runtime fields (not persisted) ===
    has_api_key: Optional[bool] = Field(default=None, exclude=True, description="Whether API key is configured")
    api_key: Optional[str] = Field(default=None, exclude=True, description="API key (for transfer only)")


class ModelConfig(BaseModel):
    """
    Model configuration (stored in config file).

    This represents a specific model configuration under a provider.
    """
    id: str = Field(..., description="Model ID (e.g., gpt-4-turbo)")
    name: str = Field(..., description="Display name")
    provider_id: str = Field(..., description="Parent provider ID")
    group: str = Field(default="General", description="Model group/category")
    temperature: float = Field(default=0.7, ge=0.0, le=2.0, description="Default temperature")
    enabled: bool = Field(default=True, description="Whether the model is enabled")

    # === Model capabilities (overrides provider defaults) ===
    capabilities: Optional[ModelCapabilities] = Field(
        default=None,
        description="Model-specific capabilities (overrides provider defaults)"
    )


class StreamChunk(BaseModel):
    """
    Represents a streaming chunk from LLM response.

    Normalizes output from different providers into a common format.
    """
    content: str = Field(default="", description="Main response content")
    thinking: str = Field(default="", description="Reasoning/thinking content (if supported)")
    tool_calls: List[Any] = Field(default_factory=list, description="Tool call requests")
    finish_reason: Optional[str] = Field(default=None, description="Finish reason if this is the final chunk")
    usage: Optional[TokenUsage] = Field(default=None, description="Token usage (typically in final chunk)")
    raw: Optional[Any] = Field(default=None, exclude=True, description="Raw chunk from provider")


class LLMResponse(BaseModel):
    """
    Represents a complete LLM response.

    Normalizes output from different providers into a common format.
    """
    content: str = Field(default="", description="Main response content")
    thinking: str = Field(default="", description="Reasoning/thinking content (if supported)")
    tool_calls: List[Any] = Field(default_factory=list, description="Tool call requests")
    finish_reason: Optional[str] = Field(default=None, description="Finish reason")
    usage: Optional[TokenUsage] = Field(default=None, description="Token usage information")
    raw: Optional[Any] = Field(default=None, exclude=True, description="Raw response from provider")
