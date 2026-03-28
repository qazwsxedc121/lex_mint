"""Runtime provider resolution and LLM instantiation helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, Optional
from urllib.parse import urlparse

import yaml

from src.providers import AdapterRegistry, CallMode, ApiProtocol, ProviderType
from src.providers.types import ProviderConfig

from src.domain.models.model_config import ModelsConfig, Provider

if TYPE_CHECKING:
    from .model_config_service import ModelConfigService


class ModelRuntimeService:
    """Owns provider runtime policy and LLM adapter construction."""

    def __init__(self, owner: "ModelConfigService"):
        self.owner = owner

    def get_api_key_sync(self, provider_id: str) -> Optional[str]:
        if not self.owner.keys_path.exists():
            return None
        try:
            with open(self.owner.keys_path, 'r', encoding='utf-8') as f:
                keys_data = yaml.safe_load(f)
        except Exception:
            return None
        if not isinstance(keys_data, dict):
            return None
        providers = keys_data.get("providers")
        if not isinstance(providers, dict):
            return None
        provider_data = providers.get(provider_id)
        if not isinstance(provider_data, dict):
            return None
        api_key = provider_data.get("api_key")
        if isinstance(api_key, str):
            return api_key
        return None

    def provider_requires_api_key(self, provider: Provider | ProviderConfig) -> bool:
        provider_cfg = provider if isinstance(provider, ProviderConfig) else self.to_provider_config(provider)
        sdk_type = AdapterRegistry.resolve_sdk_type_for_provider(provider_cfg)
        return sdk_type not in {"ollama", "lmstudio", "local_gguf"}

    @staticmethod
    def normalize_base_host(base_url: str) -> str:
        if not base_url:
            return ""
        candidate = base_url.strip()
        if not candidate:
            return ""
        if "://" not in candidate:
            candidate = f"https://{candidate}"
        try:
            parsed = urlparse(candidate)
            return (parsed.hostname or "").strip().lower().rstrip(".")
        except Exception:
            return ""

    def is_openai_official_provider(self, provider: Provider | ProviderConfig) -> bool:
        provider_id = (getattr(provider, "id", "") or "").strip().lower()
        if provider_id == "openai":
            return True
        base_url = getattr(provider, "base_url", "") or ""
        return self.normalize_base_host(base_url) == "api.openai.com"

    def resolve_effective_call_mode(self, provider: Provider | ProviderConfig) -> CallMode:
        raw_mode = getattr(provider, "call_mode", CallMode.AUTO)
        if isinstance(raw_mode, CallMode):
            configured_mode = raw_mode
        else:
            try:
                configured_mode = CallMode(raw_mode)
            except Exception:
                configured_mode = CallMode.AUTO

        if configured_mode != CallMode.AUTO:
            return configured_mode

        provider_cfg = provider if isinstance(provider, ProviderConfig) else self.to_provider_config(provider)
        sdk_type = AdapterRegistry.resolve_sdk_type_for_provider(provider_cfg)
        if sdk_type in {"anthropic", "gemini", "ollama", "lmstudio", "local_gguf"}:
            return CallMode.NATIVE
        if self.is_openai_official_provider(provider_cfg):
            return CallMode.RESPONSES
        return CallMode.CHAT_COMPLETIONS

    def resolve_provider_api_key_sync(self, provider: Provider) -> str:
        api_key = self.get_api_key_sync(provider.id)
        if api_key:
            return api_key
        if self.provider_requires_api_key(provider):
            raise RuntimeError(
                f"API key not found for provider '{provider.id}'. "
                "Please set it via the UI (stored in config/local/keys_config.yaml)."
            )
        return ""

    def to_provider_config(self, provider: Provider) -> ProviderConfig:
        return ProviderConfig(
            id=provider.id,
            name=provider.name,
            type=provider.type if hasattr(provider, 'type') and provider.type else ProviderType.BUILTIN,
            protocol=provider.protocol if hasattr(provider, 'protocol') and provider.protocol else ApiProtocol.OPENAI,
            call_mode=provider.call_mode if hasattr(provider, 'call_mode') and provider.call_mode else CallMode.AUTO,
            base_url=provider.base_url,
            endpoint_profile_id=provider.endpoint_profile_id,
            enabled=provider.enabled,
            default_capabilities=provider.default_capabilities,
            sdk_class=provider.sdk_class if hasattr(provider, 'sdk_class') else None,
            endpoint_profiles=provider.endpoint_profiles if hasattr(provider, 'endpoint_profiles') else [],
        )

    def get_adapter_for_provider(self, provider: Provider):
        return AdapterRegistry.get_for_provider(self.to_provider_config(provider))

    def get_llm_instance(
        self,
        model_id: Optional[str] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None,
        disable_thinking: bool = False,
    ) -> Any:
        config = ModelsConfig(**self.owner._load_split_config())
        model, provider, requested_model_id, using_default_model = self.owner._resolve_model_and_provider_from_config(
            config,
            model_id,
        )
        self.owner._ensure_model_is_enabled(
            model=model,
            provider=provider,
            requested_model_id=requested_model_id,
            using_default_model=using_default_model,
        )

        adapter = self.get_adapter_for_provider(provider)
        resolved_call_mode = self.resolve_effective_call_mode(provider)
        effective_call_mode = resolved_call_mode.value if isinstance(resolved_call_mode, CallMode) else str(resolved_call_mode)
        capabilities = self.owner.get_merged_capabilities(model, provider)

        create_kwargs: Dict[str, Any] = {
            "model": model.id,
            "base_url": provider.base_url,
            "api_key": self.resolve_provider_api_key_sync(provider),
            "temperature": 0.7 if temperature is None else temperature,
            "streaming": False,
            "call_mode": effective_call_mode,
            "requires_interleaved_thinking": bool(capabilities.requires_interleaved_thinking),
        }
        if max_tokens is not None:
            create_kwargs["max_tokens"] = max_tokens
        if top_p is not None:
            create_kwargs["top_p"] = top_p
        if top_k is not None:
            create_kwargs["top_k"] = top_k
        if frequency_penalty is not None:
            create_kwargs["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            create_kwargs["presence_penalty"] = presence_penalty
        if disable_thinking:
            create_kwargs["disable_thinking"] = True

        return adapter.create_llm(**create_kwargs)
