"""
Model configuration management service.

Handles loading, saving, and managing LLM provider and model settings.
"""

import logging
from pathlib import Path
from typing import Any

from src.core.paths import (
    config_defaults_dir,
    config_local_dir,
    local_keys_config_path,
    shared_keys_config_path,
)
from src.domain.models.model_config import (
    DefaultConfig,
    Model,
    ModelsConfig,
    Provider,
)
from src.providers import (
    AdapterRegistry,
    CallMode,
    EndpointProfile,
    ModelCapabilities,
    ReasoningControls,
    get_all_builtin_providers,
    get_builtin_provider,
)
from src.providers.model_capability_rules import infer_capability_overrides
from src.providers.types import ProviderConfig
from src.providers.types import ProviderDefinition

from .model_config_repository import ModelConfigRepository
from .model_runtime_service import ModelRuntimeService

logger = logging.getLogger(__name__)


class ModelConfigService:
    """Model configuration management service."""

    _BUILTIN_BASE_URL_MIGRATIONS = {
        "siliconflow": {
            "https://api.siliconflow.com/v1": "https://api.siliconflow.cn/v1",
        },
    }
    _MODEL_LEVEL_INTERLEAVED_PROVIDERS = {"deepseek", "kimi"}

    def __init__(self, config_path: Path | None = None, keys_path: Path | None = None):
        """
        Initialize the configuration service.

        Args:
            config_path: Path to ``config/local/models_config.yaml`` by default.
            keys_path: Path to ``config/local/keys_config.yaml`` by default.
        """
        defaults_dir = config_defaults_dir()
        self.defaults_provider_path: Path = defaults_dir / "provider_config.yaml"
        self.defaults_catalog_path: Path = defaults_dir / "models_catalog.yaml"
        self.defaults_app_path: Path = defaults_dir / "app_defaults.yaml"
        self._defaults_config_cache: dict[str, Any] | None = None
        self._layered_models = config_path is None
        self._layered_keys = keys_path is None

        if config_path is None:
            config_path = config_local_dir() / "models_config.yaml"
        if keys_path is None:
            # Runtime key writes are local-only; shared home keys are bootstrap source.
            keys_path = local_keys_config_path()
        self.config_path = config_path
        self.config_dir = self.config_path.parent
        self.provider_config_path = self.config_dir / "provider_config.yaml"
        self.models_catalog_path = self.config_dir / "models_catalog.yaml"
        self.app_defaults_path = self.config_dir / "app_defaults.yaml"
        self.keys_path = keys_path
        self.logger = logger
        self.repository = ModelConfigRepository(self)
        self.runtime = ModelRuntimeService(self)
        self._ensure_config_exists()
        self._sync_builtin_entries()
        self._ensure_keys_config_exists()

    def _get_repository(self) -> ModelConfigRepository:
        repository = getattr(self, "repository", None)
        if repository is None:
            self.logger = getattr(self, "logger", logger)
            repository = ModelConfigRepository(self)
            self.repository = repository
        return repository

    def _get_runtime(self) -> ModelRuntimeService:
        runtime = getattr(self, "runtime", None)
        if runtime is None:
            runtime = ModelRuntimeService(self)
            self.runtime = runtime
        return runtime

    @staticmethod
    def _empty_default_payload() -> dict[str, str]:
        return {"provider": "", "model": ""}

    @classmethod
    def _normalize_default_payload(cls, value: Any) -> dict[str, str]:
        if not isinstance(value, dict):
            return cls._empty_default_payload()
        return {
            "provider": str(value.get("provider") or "").strip(),
            "model": str(value.get("model") or "").strip(),
        }

    @classmethod
    def _require_default_model_lookup_id(cls, config: ModelsConfig) -> str:
        default_payload = cls._normalize_default_payload(
            {
                "provider": config.default.provider,
                "model": config.default.model,
            }
        )
        if not default_payload["provider"] or not default_payload["model"]:
            raise ValueError("No default model configured. Add a provider and model first.")
        return f"{default_payload['provider']}:{default_payload['model']}"

    @staticmethod
    def _load_yaml_dict(path: Path) -> dict[str, Any]:
        return ModelConfigRepository.load_yaml_dict(path)

    @staticmethod
    def _write_yaml_dict(path: Path, data: dict[str, Any]) -> None:
        ModelConfigRepository.write_yaml_dict(path, data)

    def _split_config_paths_exist(self) -> bool:
        return self._get_repository().split_config_paths_exist()

    @staticmethod
    def _assemble_aggregate_config(
        provider_data: dict[str, Any],
        catalog_data: dict[str, Any],
        app_data: dict[str, Any],
    ) -> dict[str, Any]:
        return ModelConfigRepository.assemble_aggregate_config(
            ModelConfigRepository.__new__(ModelConfigRepository),
            provider_data,
            catalog_data,
            app_data,
        )

    def _load_split_config(self) -> dict[str, Any]:
        return self._get_repository().load_split_config()

    def _split_aggregate_config(
        self,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        return self._get_repository().split_aggregate_config(data)

    def _ensure_config_exists(self):
        """Ensure split config files exist."""
        self._get_repository().ensure_config_exists()

    def _get_default_config(self) -> dict:
        """Get default configuration."""
        return self._get_repository().default_config()

    def _load_defaults_config(self) -> dict[str, Any]:
        """Load the repo default split config once for bootstrap decisions."""
        return self._get_repository().load_defaults_config()

    def _get_default_enabled_builtin_provider_ids(self) -> set[str]:
        """Derive enabled builtin providers from defaults YAML."""
        defaults = self._load_defaults_config()
        providers = defaults.get("providers")
        if isinstance(providers, list):
            enabled_ids = {
                str(provider.get("id"))
                for provider in providers
                if isinstance(provider, dict)
                and str(provider.get("id") or "").strip()
                and provider.get("type", "builtin") == "builtin"
                and bool(provider.get("enabled"))
            }
            if enabled_ids:
                return enabled_ids
        return set()

    def _get_default_reasoning_supported_patterns(self) -> list[str]:
        """Derive reasoning hint patterns from defaults YAML."""
        defaults = self._load_defaults_config()
        patterns = defaults.get("reasoning_supported_patterns")
        if isinstance(patterns, list):
            return [str(pattern) for pattern in patterns if str(pattern or "").strip()]
        return []

    def _provider_from_definition(self, definition, enabled: bool) -> dict[str, Any]:
        return {
            "id": definition.id,
            "name": definition.name,
            "type": "builtin",
            "protocol": definition.protocol.value,
            "call_mode": "auto",
            "base_url": definition.base_url,
            "endpoint_profile_id": definition.default_endpoint_profile_id,
            "api_keys": [],
            "enabled": enabled,
            "default_capabilities": definition.default_capabilities.model_dump(mode="json"),
            "url_suffix": definition.url_suffix,
            "auto_append_path": definition.auto_append_path,
            "supports_model_list": definition.supports_model_list,
            "sdk_class": definition.sdk_class,
            "endpoint_profiles": [
                profile.model_dump(mode="json") for profile in definition.endpoint_profiles
            ],
        }

    def _model_from_definition(
        self,
        *,
        provider_id: str,
        model_id: str,
        model_name: str,
        capabilities: ModelCapabilities | None,
        enabled: bool,
    ) -> dict[str, Any]:
        tags = self._derive_tags_for_model(model_id=model_id, capabilities=capabilities)
        return {
            "id": model_id,
            "name": model_name,
            "provider_id": provider_id,
            "tags": tags,
            "enabled": enabled,
            "capabilities": capabilities.model_dump(mode="json") if capabilities else None,
        }

    @staticmethod
    def _normalize_tag_list(raw_tags: Any) -> list[str]:
        """Normalize tags from string/list into lower-case unique list."""
        if isinstance(raw_tags, str):
            candidates = [part.strip() for part in raw_tags.split(",")]
        elif isinstance(raw_tags, list):
            candidates = [str(part).strip() for part in raw_tags]
        elif raw_tags is None:
            candidates = []
        else:
            candidates = [str(raw_tags).strip()]

        normalized: list[str] = []
        seen = set()
        for tag in candidates:
            clean_tag = tag.lower()
            if not clean_tag or clean_tag in seen:
                continue
            normalized.append(clean_tag)
            seen.add(clean_tag)
        return normalized

    def _derive_tags_for_model(
        self,
        *,
        model_id: str,
        capabilities: ModelCapabilities | None,
        fallback_group: str | None = None,
    ) -> list[str]:
        """Infer useful tags for built-in and migrated models."""
        tags: list[str] = []
        if fallback_group:
            tags.extend(self._normalize_tag_list(fallback_group))

        if "reason" in model_id.lower():
            tags.append("reasoning")
        elif not tags:
            tags.append("chat")

        if capabilities:
            if capabilities.reasoning:
                tags.append("reasoning")
            if capabilities.vision:
                tags.append("vision")
            if capabilities.function_calling:
                tags.append("function-calling")
            if capabilities.file_upload:
                tags.append("file-upload")
            if capabilities.image_output:
                tags.append("image-output")

        return self._normalize_tag_list(tags)

    def _ensure_split_config_lists(self, data: dict[str, Any]) -> tuple[list[Any], list[Any]]:
        providers = data.get("providers")
        if not isinstance(providers, list):
            providers = []
            data["providers"] = providers

        models = data.get("models")
        if not isinstance(models, list):
            models = []
            data["models"] = models

        return providers, models

    def _sync_model_tags_and_groups(self, models: list[Any]) -> bool:
        changed = False
        for model in models:
            if not isinstance(model, dict):
                continue
            model_capabilities = None
            if isinstance(model.get("capabilities"), dict):
                try:
                    model_capabilities = ModelCapabilities(**model["capabilities"])
                except Exception:
                    model_capabilities = None
            existing_tags = self._normalize_tag_list(model.get("tags"))
            inferred_tags = self._derive_tags_for_model(
                model_id=str(model.get("id", "")),
                capabilities=model_capabilities,
                fallback_group=model.get("group"),
            )
            merged_tags = existing_tags or inferred_tags
            if model.get("tags") != merged_tags:
                model["tags"] = merged_tags
                changed = True
            if "group" in model:
                model.pop("group", None)
                changed = True
        return changed

    def _sync_builtin_provider_metadata(self, providers: list[Any]) -> bool:
        changed = False
        existing_providers = {
            provider.get("id"): provider
            for provider in providers
            if isinstance(provider, dict) and provider.get("id")
        }

        for definition in get_all_builtin_providers().values():
            provider_entry = existing_providers.get(definition.id)
            if not (isinstance(provider_entry, dict) and provider_entry.get("type") == "builtin"):
                continue
            changed |= self._sync_single_builtin_provider_entry(provider_entry, definition)

        return changed

    def _sync_single_builtin_provider_entry(
        self, provider_entry: dict[str, Any], definition: ProviderDefinition
    ) -> bool:
        changed = False
        current_base_url = self._normalize_url(provider_entry.get("base_url"))

        for legacy_url, target_url in self._BUILTIN_BASE_URL_MIGRATIONS.get(definition.id, {}).items():
            if current_base_url == self._normalize_url(legacy_url) and self._normalize_url(
                definition.base_url
            ) == self._normalize_url(target_url):
                provider_entry["base_url"] = target_url
                current_base_url = self._normalize_url(target_url)
                changed = True

        if provider_entry.get("supports_model_list") != definition.supports_model_list:
            provider_entry["supports_model_list"] = definition.supports_model_list
            changed = True
        if provider_entry.get("sdk_class") != definition.sdk_class:
            provider_entry["sdk_class"] = definition.sdk_class
            changed = True

        profile_payload = [profile.model_dump(mode="json") for profile in definition.endpoint_profiles]
        if provider_entry.get("endpoint_profiles") != profile_payload:
            provider_entry["endpoint_profiles"] = profile_payload
            changed = True

        if not provider_entry.get("endpoint_profile_id"):
            resolved_profile = (
                self._resolve_endpoint_profile_id_by_url(
                    definition.endpoint_profiles,
                    str(provider_entry.get("base_url", "")),
                )
                or definition.default_endpoint_profile_id
            )
            if resolved_profile:
                provider_entry["endpoint_profile_id"] = resolved_profile
                changed = True

        provider_caps = provider_entry.get("default_capabilities")
        if isinstance(provider_caps, dict):
            changed |= self._sync_provider_interleaved_thinking_flag(
                provider_caps=provider_caps,
                provider_id=definition.id,
                default_value=definition.default_capabilities.requires_interleaved_thinking,
            )

        return changed

    def _sync_provider_interleaved_thinking_flag(
        self,
        *,
        provider_caps: dict[str, Any],
        provider_id: str,
        default_value: bool,
    ) -> bool:
        if provider_id in self._MODEL_LEVEL_INTERLEAVED_PROVIDERS:
            if provider_caps.get("requires_interleaved_thinking") is not False:
                provider_caps["requires_interleaved_thinking"] = False
                return True
            return False

        if "requires_interleaved_thinking" not in provider_caps:
            provider_caps["requires_interleaved_thinking"] = default_value
            return True
        return False

    def _sync_default_selection(self, data: dict[str, Any], providers: list[Any], models: list[Any]) -> bool:
        changed = False
        normalized_default = self._normalize_default_payload(data.get("default"))
        default_provider = normalized_default["provider"]
        default_model = normalized_default["model"]

        existing_providers = {
            provider.get("id"): provider
            for provider in providers
            if isinstance(provider, dict) and provider.get("id")
        }
        default_provider_entry = existing_providers.get(default_provider)
        default_model_entry = next(
            (
                model_entry
                for model_entry in models
                if isinstance(model_entry, dict)
                and model_entry.get("provider_id") == default_provider
                and model_entry.get("id") == default_model
            ),
            None,
        )

        default_is_configured = bool(default_provider and default_model)
        default_is_valid = (
            default_is_configured
            and isinstance(default_provider_entry, dict)
            and isinstance(default_model_entry, dict)
            and bool(default_provider_entry.get("enabled"))
            and bool(default_model_entry.get("enabled"))
        )
        if data.get("default") != normalized_default:
            data["default"] = normalized_default
            changed = True
        if default_is_configured and not default_is_valid:
            data["default"] = self._empty_default_payload()
            changed = True
        return changed

    def _ensure_reasoning_supported_patterns(self, data: dict[str, Any]) -> bool:
        reasoning_patterns = data.get("reasoning_supported_patterns")
        if isinstance(reasoning_patterns, list):
            return False
        data["reasoning_supported_patterns"] = self._get_default_reasoning_supported_patterns()
        return True

    def _backfill_local_gguf_capabilities(self, models: list[Any]) -> bool:
        changed = False
        for model_entry in models:
            if not isinstance(model_entry, dict):
                continue
            model_id_value = model_entry.get("id")
            if not isinstance(model_id_value, str):
                continue

            provider_id_value = model_entry.get("provider_id")
            if provider_id_value != "local_gguf":
                continue
            inferred = infer_capability_overrides(
                model_id_value,
                provider_id=provider_id_value if isinstance(provider_id_value, str) else None,
            )
            if not inferred:
                continue

            model_caps = model_entry.get("capabilities")
            if not isinstance(model_caps, dict):
                continue

            if inferred.get("function_calling") is True and model_caps.get("function_calling") is False:
                model_caps["function_calling"] = True
                changed = True
            if inferred.get("reasoning") is True and model_caps.get("reasoning") is False:
                model_caps["reasoning"] = True
                changed = True
            if (
                inferred.get("requires_interleaved_thinking") is True
                and model_caps.get("requires_interleaved_thinking") is False
            ):
                model_caps["requires_interleaved_thinking"] = True
                changed = True
            if inferred.get("reasoning_controls") and not isinstance(
                model_caps.get("reasoning_controls"), dict
            ):
                model_caps["reasoning_controls"] = inferred["reasoning_controls"]
                changed = True

        return changed

    def _sync_builtin_entries(self) -> None:
        """
        Refresh non-user-editable builtin metadata for providers already present in local config.
        """
        data = self._load_split_config()
        if not isinstance(data, dict):
            return

        providers, models = self._ensure_split_config_lists(data)
        changed = False
        changed |= self._sync_model_tags_and_groups(models)
        changed |= self._sync_builtin_provider_metadata(providers)
        changed |= self._sync_default_selection(data, providers, models)
        changed |= self._ensure_reasoning_supported_patterns(data)
        changed |= self._backfill_local_gguf_capabilities(models)

        if changed:
            provider_data, catalog_data, app_data = self._split_aggregate_config(data)
            self._write_yaml_dict(self.provider_config_path, provider_data)
            self._write_yaml_dict(self.models_catalog_path, catalog_data)
            self._write_yaml_dict(self.app_defaults_path, app_data)

    async def load_config(self) -> ModelsConfig:
        """Load config."""
        data = self._load_split_config()
        return ModelsConfig(**data)

    async def save_config(self, config: ModelsConfig):
        """Persist aggregated model/provider/default config into split local files."""
        data = config.model_dump(mode="json")
        provider_data, catalog_data, app_data = self._split_aggregate_config(data)
        self._write_yaml_dict(self.provider_config_path, provider_data)
        self._write_yaml_dict(self.models_catalog_path, catalog_data)
        self._write_yaml_dict(self.app_defaults_path, app_data)

    def _ensure_keys_config_exists(self):
        self._get_repository().ensure_keys_config_exists()

    async def load_keys_config(self) -> dict:
        return await self._get_repository().load_keys_config()

    async def save_keys_config(self, keys_data: dict):
        await self._get_repository().save_keys_config(keys_data)

    @staticmethod
    def _normalize_url(value: Any) -> str:
        return str(value or "").strip().rstrip("/")

    @classmethod
    def _resolve_endpoint_profile_id_by_url(
        cls,
        endpoint_profiles: list[EndpointProfile],
        base_url: str,
    ) -> str | None:
        normalized_base = cls._normalize_url(base_url)
        for profile in endpoint_profiles:
            if cls._normalize_url(profile.base_url) == normalized_base:
                return profile.id
        return None

    @staticmethod
    def _same_path(path_a: Path, path_b: Path) -> bool:
        return ModelConfigRepository.same_path(path_a, path_b)

    def _is_shared_keys_path(self, path: Path) -> bool:
        return self._get_repository().is_shared_keys_path(path)

    @staticmethod
    def _shared_keys_config_path() -> Path:
        return shared_keys_config_path()

    def _assert_keys_path_writable(self) -> None:
        self._get_repository().assert_keys_path_writable()

    async def get_api_key(self, provider_id: str) -> str | None:
        """
        Get the API key for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            The API key, or ``None`` if it is not configured.
        """
        keys_data = await self.load_keys_config()
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

    async def set_api_key(self, provider_id: str, api_key: str):
        """
        Set or update the API key for a provider.

        Args:
            provider_id: Provider ID.
            api_key: API key value.
        """
        keys_data = await self.load_keys_config()
        if "providers" not in keys_data:
            keys_data["providers"] = {}
        if provider_id not in keys_data["providers"]:
            keys_data["providers"][provider_id] = {}
        keys_data["providers"][provider_id]["api_key"] = api_key
        await self.save_keys_config(keys_data)

    async def delete_api_key(self, provider_id: str):
        """
        Delete the stored API key for a provider.

        Args:
            provider_id: Provider ID.
        """
        keys_data = await self.load_keys_config()
        if "providers" in keys_data and provider_id in keys_data["providers"]:
            del keys_data["providers"][provider_id]
            await self.save_keys_config(keys_data)

    async def has_api_key(self, provider_id: str) -> bool:
        """
        Check whether a provider has a non-empty API key.

        Args:
            provider_id: Provider ID.

        Returns:
            ``True`` when an API key exists, otherwise ``False``.
        """
        api_key = await self.get_api_key(provider_id)
        return api_key is not None and api_key.strip() != ""

    # ==================== Provider Management ====================

    @staticmethod
    def _is_provider_enabled(provider: Provider) -> bool:
        return bool(getattr(provider, "enabled", False))

    @classmethod
    def _is_model_effectively_enabled(cls, model: Model, provider: Provider | None) -> bool:
        return (
            provider is not None
            and bool(getattr(model, "enabled", False))
            and cls._is_provider_enabled(provider)
        )

    @classmethod
    def _resolve_model_and_provider_from_config(
        cls,
        config: ModelsConfig,
        model_id: str | None = None,
    ) -> tuple[Model, Provider, str, bool]:
        requested_model_id = model_id
        using_default_model = requested_model_id is None
        if requested_model_id is None:
            requested_model_id = cls._require_default_model_lookup_id(config)

        model = cls._find_model_in_config(config, requested_model_id)
        if not model:
            raise ValueError(f"Model with id '{requested_model_id}' not found")

        provider = next((p for p in config.providers if p.id == model.provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        return model, provider, requested_model_id, using_default_model

    @classmethod
    def _ensure_model_is_enabled(
        cls,
        *,
        model: Model,
        provider: Provider,
        requested_model_id: str,
        using_default_model: bool,
    ) -> None:
        if cls._is_model_effectively_enabled(model, provider):
            return

        if using_default_model:
            raise ValueError(
                f"Default model '{requested_model_id}' is disabled. Configure another default model first."
            )

        if not bool(model.enabled):
            raise ValueError(f"Model '{requested_model_id}' is disabled")

        raise ValueError(
            f"Provider '{provider.id}' is disabled, so model '{requested_model_id}' is unavailable"
        )

    async def require_enabled_model(self, model_id: str | None = None) -> tuple[Model, Provider]:
        """Resolve a model/provider pair and ensure both are enabled."""
        config = await self.load_config()
        model, provider, requested_model_id, using_default_model = (
            self._resolve_model_and_provider_from_config(
                config,
                model_id,
            )
        )
        self._ensure_model_is_enabled(
            model=model,
            provider=provider,
            requested_model_id=requested_model_id,
            using_default_model=using_default_model,
        )
        return model, provider

    async def get_providers(self, enabled_only: bool = False) -> list[Provider]:
        """Get all providers, including has_api_key metadata."""
        config = await self.load_config()
        providers_with_keys = []
        for provider in config.providers:
            # Check whether the provider has an API key configured.
            has_key = await self.has_api_key(provider.id)
            requires_key = self.provider_requires_api_key(provider)
            # Attach runtime-only key metadata to the returned provider object.
            provider_dict = provider.model_dump()
            provider_dict["has_api_key"] = has_key
            provider_dict["requires_api_key"] = requires_key
            provider_obj = Provider(**provider_dict)
            if enabled_only and not self._is_provider_enabled(provider_obj):
                continue
            providers_with_keys.append(provider_obj)
        return providers_with_keys

    async def get_provider(
        self, provider_id: str, include_masked_key: bool = False
    ) -> Provider | None:
        """
        Get a provider by ID.

        Args:
            provider_id: Provider ID.
            include_masked_key: Whether to include a masked API key preview.
        """
        config = await self.load_config()
        for provider in config.providers:
            if provider.id == provider_id:
                provider_dict = provider.model_dump()

                # Attach runtime-only key metadata.
                has_key = await self.has_api_key(provider_id)
                requires_key = self.provider_requires_api_key(provider)
                provider_dict["has_api_key"] = has_key
                provider_dict["requires_api_key"] = requires_key

                # Add a masked key preview when requested.
                if include_masked_key and has_key:
                    api_key = await self.get_api_key(provider_id)
                    if api_key:
                        provider_dict["api_key"] = self._mask_api_key(api_key)

                return Provider(**provider_dict)
        return None

    def get_endpoint_profiles_for_provider(self, provider: Provider) -> list[EndpointProfile]:
        """Resolve endpoint profiles from builtin definitions first, then provider config."""
        builtin = get_builtin_provider(provider.id)
        if builtin and builtin.endpoint_profiles:
            return list(builtin.endpoint_profiles)
        if provider.endpoint_profiles:
            return list(provider.endpoint_profiles)
        return []

    def resolve_endpoint_profile_base_url(
        self, provider: Provider, endpoint_profile_id: str
    ) -> str | None:
        """Resolve the base URL for a given endpoint profile id."""
        for profile in self.get_endpoint_profiles_for_provider(provider):
            if profile.id == endpoint_profile_id:
                return profile.base_url
        return None

    def resolve_endpoint_profile_id_for_base_url(
        self, provider: Provider, base_url: str
    ) -> str | None:
        """Resolve endpoint profile id by matching base URL."""
        return self._resolve_endpoint_profile_id_by_url(
            self.get_endpoint_profiles_for_provider(provider),
            base_url,
        )

    def recommend_endpoint_profile_id(
        self,
        provider: Provider,
        client_region_hint: str = "unknown",
    ) -> str | None:
        """Recommend endpoint profile by region hint + profile priority."""
        profiles = self.get_endpoint_profiles_for_provider(provider)
        if not profiles:
            return None

        hint = (client_region_hint or "unknown").strip().lower()
        best = sorted(
            profiles,
            key=lambda p: (
                0 if hint != "unknown" and hint in [tag.lower() for tag in p.region_tags] else 1,
                p.priority,
            ),
        )[0]
        return best.id

    def _mask_api_key(self, api_key: str) -> str:
        """
        Mask an API key while preserving a small prefix and suffix.

        Example: ``sk-xxxx1234`` -> ``sk-****...1234``
        """
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:3]}****...{api_key[-4:]}"

    async def add_provider(self, provider: Provider):
        """
        Add a provider.

        Raises:
            ValueError: If the provider ID already exists.
        """
        config = await self.load_config()

        # Ensure the provider ID is unique.
        if any(p.id == provider.id for p in config.providers):
            raise ValueError(f"Provider with id '{provider.id}' already exists")

        # Remove transient fields so they are not persisted to config.
        provider_dict = provider.model_dump(exclude={"api_key", "has_api_key", "requires_api_key"})
        config.providers.append(Provider(**provider_dict))
        await self.save_config(config)

    async def update_provider(self, provider_id: str, updated: Provider):
        """
        Update provider.

        Raises:
            ValueError: If the provider does not exist.
        """
        config = await self.load_config()

        for i, provider in enumerate(config.providers):
            if provider.id == provider_id:
                updated_dict = updated.model_dump(
                    exclude={"api_key", "has_api_key", "requires_api_key"}
                )
                config.providers[i] = Provider(**updated_dict)
                if config.default.provider == provider_id and (
                    config.providers[i].id != provider_id or not bool(config.providers[i].enabled)
                ):
                    config.default = DefaultConfig(**self._empty_default_payload())
                await self.save_config(config)
                return

        raise ValueError(f"Provider with id '{provider_id}' not found")

    async def delete_provider(self, provider_id: str):
        """
        Delete a provider and all models under it.

        Raises:
            ValueError: If the provider does not exist or is built in.
        """
        config = await self.load_config()

        if config.default.provider == provider_id:
            config.default = DefaultConfig(**self._empty_default_payload())
        if get_builtin_provider(provider_id):
            raise ValueError(f"Cannot delete built-in provider '{provider_id}', disable it instead")

        original_count = len(config.providers)
        config.providers = [p for p in config.providers if p.id != provider_id]
        config.models = [m for m in config.models if m.provider_id != provider_id]

        if len(config.providers) == original_count:
            raise ValueError(f"Provider with id '{provider_id}' not found")

        await self.save_config(config)

    # ==================== Model Management ====================

    async def get_models(
        self, provider_id: str | None = None, enabled_only: bool = False
    ) -> list[Model]:
        """
        Get models, optionally filtered by provider.

        Args:
            provider_id: Provider ID to filter by.
        """
        config = await self.load_config()
        providers_by_id = {provider.id: provider for provider in config.providers}
        models = config.models
        if provider_id:
            models = [m for m in models if m.provider_id == provider_id]
        if enabled_only:
            models = [
                model
                for model in models
                if self._is_model_effectively_enabled(model, providers_by_id.get(model.provider_id))
            ]
        return models

    async def get_model(self, model_id: str) -> Model | None:
        """
        Get a model by ID.

        Args:
            model_id: Model ID, supporting composite IDs like ``provider_id:model_id``.
        """
        config = await self.load_config()

        # Determine whether this is a composite identifier.
        is_composite = False
        provider_id = None
        simple_model_id = None

        if ":" in model_id:
            potential_provider, potential_model = model_id.split(":", 1)
            # Treat the prefix as a provider ID only when it matches a known provider.
            if any(p.id == potential_provider for p in config.providers):
                is_composite = True
                provider_id = potential_provider
                simple_model_id = potential_model

        if is_composite:
            # Composite ID format: provider_id:model_id.
            for model in config.models:
                if model.id == simple_model_id and model.provider_id == provider_id:
                    return model
        else:
            # Simple ID lookup, including model IDs that may contain colons.
            for model in config.models:
                if model.id == model_id:
                    return model

        return None

    async def add_model(self, model: Model):
        """
        Add a model.

        Raises:
            ValueError: If the model already exists or its provider is missing.
        """
        config = await self.load_config()

        # Ensure the composite key (provider_id + model_id) is unique.
        if any(m.id == model.id and m.provider_id == model.provider_id for m in config.models):
            raise ValueError(
                f"Model '{model.id}' already exists for provider '{model.provider_id}'"
            )

        # Ensure the referenced provider exists.
        if not any(p.id == model.provider_id for p in config.providers):
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        config.models.append(model)
        await self.save_config(config)

    async def update_model(self, model_id: str, updated: Model):
        """
        Update a model.

        Args:
            model_id: Model ID, can be simple or composite provider_id:model_id.

        Raises:
            ValueError: If the model does not exist.
        """
        config = await self.load_config()

        is_composite = False
        provider_id = None
        simple_model_id = None

        if ":" in model_id:
            potential_provider, potential_model = model_id.split(":", 1)
            if any(p.id == potential_provider for p in config.providers):
                is_composite = True
                provider_id = potential_provider
                simple_model_id = potential_model

        if is_composite:
            for i, model in enumerate(config.models):
                if model.id == simple_model_id and model.provider_id == provider_id:
                    config.models[i] = updated
                    if (
                        model.provider_id == config.default.provider
                        and model.id == config.default.model
                        and (
                            updated.provider_id != model.provider_id
                            or updated.id != model.id
                            or not bool(updated.enabled)
                        )
                    ):
                        config.default = DefaultConfig(**self._empty_default_payload())
                    await self.save_config(config)
                    return
        else:
            for i, model in enumerate(config.models):
                if model.id == model_id:
                    config.models[i] = updated
                    if (
                        model.provider_id == config.default.provider
                        and model.id == config.default.model
                        and (
                            updated.provider_id != model.provider_id
                            or updated.id != model.id
                            or not bool(updated.enabled)
                        )
                    ):
                        config.default = DefaultConfig(**self._empty_default_payload())
                    await self.save_config(config)
                    return

        raise ValueError(f"Model with id '{model_id}' not found")

    async def delete_model(self, model_id: str):
        """
        Delete a model.

        Args:
            model_id: Model ID, can be simple or composite provider_id:model_id.

        Raises:
            ValueError: If the model does not exist.
        """
        config = await self.load_config()

        is_composite = False
        provider_id = None
        simple_model_id = None

        if ":" in model_id:
            potential_provider, potential_model = model_id.split(":", 1)
            if any(p.id == potential_provider for p in config.providers):
                is_composite = True
                provider_id = potential_provider
                simple_model_id = potential_model

        if is_composite:
            composite_default = f"{config.default.provider}:{config.default.model}"
            deleting_default = model_id == composite_default or (
                simple_model_id == config.default.model and provider_id == config.default.provider
            )
            original_count = len(config.models)
            config.models = [
                m
                for m in config.models
                if not (m.id == simple_model_id and m.provider_id == provider_id)
            ]
        else:
            deleting_default = config.default.model == model_id and any(
                m.id == model_id and m.provider_id == config.default.provider for m in config.models
            )
            original_count = len(config.models)
            config.models = [m for m in config.models if m.id != model_id]

        if len(config.models) == original_count:
            raise ValueError(f"Model with id '{model_id}' not found")

        if deleting_default:
            config.default = DefaultConfig(**self._empty_default_payload())

        await self.save_config(config)

    # ==================== Default Configuration ====================

    async def get_default_config(self) -> DefaultConfig:
        """Get the default provider/model configuration."""
        config = await self.load_config()
        return config.default

    async def set_default_model(self, provider_id: str, model_id: str):
        """
        Set the default provider/model pair.

        Raises:
            ValueError: If the provider or model does not exist, does not match,
                or is disabled.
        """
        config = await self.load_config()

        # Validate that the provider exists.
        if not any(p.id == provider_id for p in config.providers):
            raise ValueError(f"Provider with id '{provider_id}' not found")

        # Validate that the model exists and belongs to the provider.
        model = next((m for m in config.models if m.id == model_id), None)
        if not model:
            raise ValueError(f"Model with id '{model_id}' not found")
        if model.provider_id != provider_id:
            raise ValueError(f"Model '{model_id}' does not belong to provider '{provider_id}'")
        provider = next((p for p in config.providers if p.id == provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{provider_id}' not found")
        self._ensure_model_is_enabled(
            model=model,
            provider=provider,
            requested_model_id=f"{provider_id}:{model_id}",
            using_default_model=False,
        )

        config.default.provider = provider_id
        config.default.model = model_id
        await self.save_config(config)

    async def get_reasoning_supported_patterns(self) -> list[str]:
        """Get reasoning effort model-name patterns."""
        config = await self.load_config()
        return config.reasoning_supported_patterns

    # ==================== Connection Testing ====================

    async def test_provider_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: str | None = None,
        provider: Provider | None = None,
    ) -> tuple[bool, str]:
        """
        Test connectivity for a provider endpoint.

        Args:
            base_url: Provider API base URL.
            api_key: API key used for the test request.
            model_id: Optional model ID to test against.
            provider: Optional provider definition used to resolve the adapter.

        Returns:
            A tuple of ``(success, message)``.
        """
        # Resolve the correct adapter for this provider
        if provider:
            provider_cfg = ProviderConfig(
                id=provider.id,
                name=provider.name,
                type=provider.type,
                protocol=provider.protocol,
                call_mode=provider.call_mode
                if hasattr(provider, "call_mode") and provider.call_mode
                else CallMode.AUTO,
                base_url=base_url,
                endpoint_profile_id=provider.endpoint_profile_id,
                endpoint_profiles=provider.endpoint_profiles,
                sdk_class=provider.sdk_class,
            )
            adapter = AdapterRegistry.get_for_provider(provider_cfg)
        else:
            adapter = AdapterRegistry.get("openai")

        try:
            success, message = await adapter.test_connection(
                base_url=base_url,
                api_key=api_key,
                model_id=model_id,
            )
        except Exception:
            logger.exception(
                "Provider connection test crashed: provider=%s base_url=%s model_id=%s",
                getattr(provider, "id", None),
                base_url,
                model_id,
            )
            raise

        log_fn = logger.info if success else logger.error
        log_fn(
            "Provider connection test result: provider=%s base_url=%s model_id=%s success=%s message=%s",
            getattr(provider, "id", None),
            base_url,
            model_id,
            success,
            message,
        )
        return success, message

    # ==================== Provider Abstraction Support ====================

    def get_model_and_provider_sync(self, model_id: str | None = None) -> tuple[Model, Provider]:
        """
        Synchronously load a model and provider pair.
        """
        config = ModelsConfig(**self._load_split_config())

        model, provider, requested_model_id, using_default_model = (
            self._resolve_model_and_provider_from_config(
                config,
                model_id,
            )
        )
        self._ensure_model_is_enabled(
            model=model,
            provider=provider,
            requested_model_id=requested_model_id,
            using_default_model=using_default_model,
        )

        return model, provider

    @staticmethod
    def _find_model_in_config(config: ModelsConfig, model_id: str) -> Model | None:
        if ":" in model_id:
            provider_id, simple_model_id = model_id.split(":", 1)
            return next(
                (
                    m
                    for m in config.models
                    if m.id == simple_model_id and m.provider_id == provider_id
                ),
                None,
            )
        return next((m for m in config.models if m.id == model_id), None)

    @staticmethod
    def _find_single_enabled_model_and_provider(
        config: ModelsConfig,
    ) -> tuple[Model, Provider] | None:
        providers_by_id = {p.id: p for p in config.providers}
        candidates: list[tuple[Model, Provider]] = []
        for model in config.models:
            provider = providers_by_id.get(model.provider_id)
            if provider is None:
                continue
            if bool(model.enabled) and bool(provider.enabled):
                candidates.append((model, provider))
        if len(candidates) == 1:
            return candidates[0]
        return None

    def get_merged_capabilities(self, model: Model, provider: Provider) -> ModelCapabilities:
        """
        Get the merged capability configuration for a model.

        Precedence: ``model.capabilities`` > ``provider.default_capabilities`` >
        built-in defaults.

        Args:
            model: Model configuration.
            provider: Provider configuration.

        Returns:
            The merged ``ModelCapabilities`` value.
        """
        # Start with default capabilities
        base_caps = ModelCapabilities()

        # Try to get builtin provider defaults
        builtin = get_builtin_provider(provider.id)
        if builtin:
            base_caps = builtin.default_capabilities

        # Override with provider config defaults
        if provider.default_capabilities:
            base_caps = base_caps.merge_with(provider.default_capabilities)

        # Override with model-specific capabilities
        if model.capabilities:
            base_caps = base_caps.merge_with(model.capabilities)

        inferred_overrides = infer_capability_overrides(
            model.id,
            provider_id=provider.id,
        )
        if inferred_overrides:
            explicit_capability_fields: set[str] = set()
            if provider.default_capabilities:
                explicit_capability_fields.update(
                    provider.default_capabilities.model_dump(exclude_unset=True).keys()
                )
            if model.capabilities:
                explicit_capability_fields.update(
                    model.capabilities.model_dump(exclude_unset=True).keys()
                )

            filtered_inferred_overrides: dict[str, Any] = {
                key: value
                for key, value in inferred_overrides.items()
                if key not in explicit_capability_fields
            }
            inferred_reasoning_controls = filtered_inferred_overrides.get("reasoning_controls")
            if isinstance(inferred_reasoning_controls, dict):
                filtered_inferred_overrides["reasoning_controls"] = ReasoningControls(
                    **inferred_reasoning_controls
                )
            if filtered_inferred_overrides:
                base_caps = base_caps.model_copy(update=filtered_inferred_overrides)

        if not base_caps.reasoning and base_caps.reasoning_controls is not None:
            base_caps = base_caps.model_copy(update={"reasoning_controls": None})

        return base_caps

    def get_api_key_sync(self, provider_id: str) -> str | None:
        return self._get_runtime().get_api_key_sync(provider_id)

    def provider_requires_api_key(self, provider: Provider | ProviderConfig) -> bool:
        return self._get_runtime().provider_requires_api_key(provider)

    @staticmethod
    def _normalize_base_host(base_url: str) -> str:
        return ModelRuntimeService.normalize_base_host(base_url)

    def is_openai_official_provider(self, provider: Provider | ProviderConfig) -> bool:
        return self._get_runtime().is_openai_official_provider(provider)

    def resolve_effective_call_mode(self, provider: Provider | ProviderConfig) -> CallMode:
        return self._get_runtime().resolve_effective_call_mode(provider)

    def resolve_provider_api_key_sync(self, provider: Provider) -> str:
        return self._get_runtime().resolve_provider_api_key_sync(provider)

    def to_provider_config(self, provider: Provider) -> ProviderConfig:
        return self._get_runtime().to_provider_config(provider)

    def get_adapter_for_provider(self, provider: Provider):
        return self._get_runtime().get_adapter_for_provider(provider)

    # ==================== LLM Instantiation ====================

    def get_llm_instance(
        self,
        model_id: str | None = None,
        *,
        temperature: float | None = None,
        max_tokens: int | None = None,
        top_p: float | None = None,
        top_k: int | None = None,
        frequency_penalty: float | None = None,
        presence_penalty: float | None = None,
        disable_thinking: bool = False,
    ) -> Any:
        return self._get_runtime().get_llm_instance(
            model_id,
            temperature=temperature,
            max_tokens=max_tokens,
            top_p=top_p,
            top_k=top_k,
            frequency_penalty=frequency_penalty,
            presence_penalty=presence_penalty,
            disable_thinking=disable_thinking,
        )
