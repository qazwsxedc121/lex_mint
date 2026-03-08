"""
Model configuration management service.

Handles loading, saving, and managing LLM provider and model settings.
"""
import yaml
import aiofiles
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Optional, Tuple, Any, Dict
from urllib.parse import urlparse
from langchain_openai import ChatOpenAI

from ..models.model_config import (
    Provider,
    Model,
    DefaultConfig,
    ModelsConfig,
)
from src.providers import (
    AdapterRegistry,
    ModelCapabilities,
    EndpointProfile,
    ReasoningControls,
    CallMode,
    ProviderType,
    ApiProtocol,
    get_builtin_provider,
    get_all_builtin_providers,
)
from src.providers.types import ProviderConfig
from src.providers.model_capability_rules import infer_capability_overrides

from ..paths import (
    config_defaults_dir,
    config_local_dir,
    local_keys_config_path,
    shared_keys_config_path,
    legacy_config_dir,
    ensure_local_file,
)

logger = logging.getLogger(__name__)


class ModelConfigService:
    """Model configuration management service."""

    _BUILTIN_BASE_URL_MIGRATIONS = {
        "siliconflow": {
            "https://api.siliconflow.com/v1": "https://api.siliconflow.cn/v1",
        },
    }
    _MODEL_LEVEL_INTERLEAVED_PROVIDERS = {"deepseek", "kimi"}

    def __init__(self, config_path: Optional[Path] = None, keys_path: Optional[Path] = None):
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
        self.defaults_legacy_path: Path = defaults_dir / "models_config.yaml"
        self.legacy_models_paths: list[Path] = []
        self.legacy_keys_paths: list[Path] = []
        self._defaults_config_cache: Optional[dict[str, Any]] = None
        self._layered_models = config_path is None
        self._layered_keys = keys_path is None

        if config_path is None:
            self.legacy_models_paths = [legacy_config_dir() / "models_config.yaml"]
            config_path = config_local_dir() / "models_config.yaml"
        if keys_path is None:
            # Runtime key writes are local-only; shared home keys are bootstrap source.
            self.legacy_keys_paths = [
                shared_keys_config_path(),
                legacy_config_dir() / "keys_config.yaml",
            ]
            keys_path = local_keys_config_path()
        self.config_path = config_path
        self.config_dir = self.config_path.parent
        self.provider_config_path = self.config_dir / "provider_config.yaml"
        self.models_catalog_path = self.config_dir / "models_catalog.yaml"
        self.app_defaults_path = self.config_dir / "app_defaults.yaml"
        self.keys_path = keys_path
        self._ensure_config_exists()
        self._sync_builtin_entries()
        self._ensure_keys_config_exists()

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
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _write_yaml_dict(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def _split_config_paths_exist(self) -> bool:
        return (
            self.provider_config_path.exists()
            and self.models_catalog_path.exists()
            and self.app_defaults_path.exists()
        )

    @staticmethod
    def _assemble_aggregate_config(
        provider_data: dict[str, Any],
        catalog_data: dict[str, Any],
        app_data: dict[str, Any],
    ) -> dict[str, Any]:
        providers = provider_data.get("providers")
        models = catalog_data.get("models")
        default_config = app_data.get("default")
        reasoning_patterns = app_data.get("reasoning_supported_patterns")
        return {
            "providers": providers if isinstance(providers, list) else [],
            "models": models if isinstance(models, list) else [],
            "default": (
                {
                    "provider": str(default_config.get("provider") or "").strip(),
                    "model": str(default_config.get("model") or "").strip(),
                }
                if isinstance(default_config, dict)
                else {"provider": "", "model": ""}
            ),
            "reasoning_supported_patterns": reasoning_patterns if isinstance(reasoning_patterns, list) else [],
        }

    def _load_split_config(self) -> dict[str, Any]:
        provider_data = self._load_yaml_dict(self.provider_config_path)
        catalog_data = self._load_yaml_dict(self.models_catalog_path)
        app_data = self._load_yaml_dict(self.app_defaults_path)
        return self._assemble_aggregate_config(provider_data, catalog_data, app_data)

    def _split_aggregate_config(
        self,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        providers = data.get("providers")
        models = data.get("models")
        default_config = data.get("default")
        reasoning_patterns = data.get("reasoning_supported_patterns")

        app_payload = {
            "default": (
                {
                    "provider": str(default_config.get("provider") or "").strip(),
                    "model": str(default_config.get("model") or "").strip(),
                }
                if isinstance(default_config, dict)
                else {"provider": "", "model": ""}
            ),
            "reasoning_supported_patterns": (
                reasoning_patterns
                if isinstance(reasoning_patterns, list)
                else self._get_default_reasoning_supported_patterns()
            ),
        }
        return (
            {"providers": providers if isinstance(providers, list) else []},
            {"models": models if isinstance(models, list) else []},
            app_payload,
        )
    def _backup_legacy_models_config(self) -> None:
        if not self.config_path.exists():
            return
        suffix = datetime.now().strftime("%Y%m%d%H%M%S")
        backup_path = self.config_path.with_name(f"{self.config_path.name}.bak.{suffix}")
        if backup_path.exists():
            return
        backup_path.write_text(self.config_path.read_text(encoding="utf-8"), encoding="utf-8")

    def _migrate_legacy_config_if_needed(self) -> None:
        if self._split_config_paths_exist() or not self.config_path.exists():
            return

        legacy_data = self._load_yaml_dict(self.config_path)
        if not legacy_data or not any(key in legacy_data for key in ("providers", "models", "default")):
            return

        provider_data, catalog_data, app_data = self._split_aggregate_config(legacy_data)
        self._write_yaml_dict(self.provider_config_path, provider_data)
        self._write_yaml_dict(self.models_catalog_path, catalog_data)
        self._write_yaml_dict(self.app_defaults_path, app_data)
        self._backup_legacy_models_config()

    def _ensure_config_exists(self):
        """Ensure split config files exist, migrating legacy aggregate config when needed."""
        self._migrate_legacy_config_if_needed()
        if self._split_config_paths_exist():
            return

        provider_defaults, catalog_defaults, app_defaults = self._split_aggregate_config(
            self._get_default_config()
        )

        if self._layered_models:
            ensure_local_file(
                local_path=self.provider_config_path,
                initial_text=yaml.safe_dump(provider_defaults, allow_unicode=True, sort_keys=False),
            )
            ensure_local_file(
                local_path=self.models_catalog_path,
                initial_text=yaml.safe_dump(catalog_defaults, allow_unicode=True, sort_keys=False),
            )
            ensure_local_file(
                local_path=self.app_defaults_path,
                initial_text=yaml.safe_dump(app_defaults, allow_unicode=True, sort_keys=False),
            )
            return

        self._write_yaml_dict(self.provider_config_path, provider_defaults)
        self._write_yaml_dict(self.models_catalog_path, catalog_defaults)
        self._write_yaml_dict(self.app_defaults_path, app_defaults)

    def _get_default_config(self) -> dict:
        """Get default configuration."""
        return {
            "default": self._empty_default_payload(),
            "providers": [],
            "models": [],
            "reasoning_supported_patterns": self._get_default_reasoning_supported_patterns(),
        }

    def _load_defaults_config(self) -> dict[str, Any]:
        """Load the repo default split config once for bootstrap decisions."""
        if self._defaults_config_cache is not None:
            return self._defaults_config_cache

        if (
            self.defaults_provider_path.exists()
            and self.defaults_catalog_path.exists()
            and self.defaults_app_path.exists()
        ):
            self._defaults_config_cache = self._assemble_aggregate_config(
                self._load_yaml_dict(self.defaults_provider_path),
                self._load_yaml_dict(self.defaults_catalog_path),
                self._load_yaml_dict(self.defaults_app_path),
            )
            return self._defaults_config_cache

        if not self.defaults_legacy_path.exists():
            self._defaults_config_cache = {}
            return self._defaults_config_cache

        try:
            with open(self.defaults_legacy_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to read legacy defaults models config: %s", e)
            data = {}

        self._defaults_config_cache = data if isinstance(data, dict) else {}
        return self._defaults_config_cache

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
                profile.model_dump(mode="json")
                for profile in definition.endpoint_profiles
            ],
        }

    def _model_from_definition(
        self,
        *,
        provider_id: str,
        model_id: str,
        model_name: str,
        capabilities: Optional[ModelCapabilities],
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
        capabilities: Optional[ModelCapabilities],
        fallback_group: Optional[str] = None,
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

    def _sync_builtin_entries(self) -> None:
        """
        Refresh non-user-editable builtin metadata for providers already present in local config.
        """
        data = self._load_split_config()
        if not isinstance(data, dict):
            return

        providers = data.get("providers")
        if not isinstance(providers, list):
            providers = []
            data["providers"] = providers

        models = data.get("models")
        if not isinstance(models, list):
            models = []
            data["models"] = models

        changed = False

        def _normalize_url(value: Any) -> str:
            return str(value or "").strip().rstrip("/")

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

        normalized_default = self._normalize_default_payload(data.get("default"))
        default_provider = normalized_default["provider"]
        default_model = normalized_default["model"]

        existing_providers = {
            p.get("id"): p
            for p in providers
            if isinstance(p, dict) and p.get("id")
        }

        for definition in get_all_builtin_providers().values():
            provider_entry = existing_providers.get(definition.id)
            if not (
                isinstance(provider_entry, dict)
                and provider_entry.get("type") == "builtin"
            ):
                continue

            current_base_url = _normalize_url(provider_entry.get("base_url"))
            for legacy_url, target_url in self._BUILTIN_BASE_URL_MIGRATIONS.get(definition.id, {}).items():
                if (
                    current_base_url == _normalize_url(legacy_url)
                    and _normalize_url(definition.base_url) == _normalize_url(target_url)
                ):
                    provider_entry["base_url"] = target_url
                    current_base_url = _normalize_url(target_url)
                    changed = True

            if provider_entry.get("supports_model_list") != definition.supports_model_list:
                provider_entry["supports_model_list"] = definition.supports_model_list
                changed = True
            if provider_entry.get("sdk_class") != definition.sdk_class:
                provider_entry["sdk_class"] = definition.sdk_class
                changed = True
            profile_payload = [
                profile.model_dump(mode="json")
                for profile in definition.endpoint_profiles
            ]
            if provider_entry.get("endpoint_profiles") != profile_payload:
                provider_entry["endpoint_profiles"] = profile_payload
                changed = True
            if not provider_entry.get("endpoint_profile_id"):
                resolved_profile = self._resolve_endpoint_profile_id_by_url(
                    definition.endpoint_profiles,
                    str(provider_entry.get("base_url", "")),
                ) or definition.default_endpoint_profile_id
                if resolved_profile:
                    provider_entry["endpoint_profile_id"] = resolved_profile
                    changed = True

            provider_caps = provider_entry.get("default_capabilities")
            if isinstance(provider_caps, dict):
                if definition.id in self._MODEL_LEVEL_INTERLEAVED_PROVIDERS:
                    if provider_caps.get("requires_interleaved_thinking") is not False:
                        provider_caps["requires_interleaved_thinking"] = False
                        changed = True
                elif "requires_interleaved_thinking" not in provider_caps:
                    provider_caps["requires_interleaved_thinking"] = (
                        definition.default_capabilities.requires_interleaved_thinking
                    )
                    changed = True

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

        reasoning_patterns = data.get("reasoning_supported_patterns")
        if not isinstance(reasoning_patterns, list):
            reasoning_patterns = self._get_default_reasoning_supported_patterns()
            data["reasoning_supported_patterns"] = reasoning_patterns
            changed = True

        # Backfill stale dynamic local GGUF capability flags when explicit metadata is absent.
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
            if inferred.get("requires_interleaved_thinking") is True and model_caps.get("requires_interleaved_thinking") is False:
                model_caps["requires_interleaved_thinking"] = True
                changed = True
            if inferred.get("reasoning_controls") and not isinstance(model_caps.get("reasoning_controls"), dict):
                model_caps["reasoning_controls"] = inferred["reasoning_controls"]
                changed = True

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
        data = config.model_dump(mode='json')
        provider_data, catalog_data, app_data = self._split_aggregate_config(data)
        self._write_yaml_dict(self.provider_config_path, provider_data)
        self._write_yaml_dict(self.models_catalog_path, catalog_data)
        self._write_yaml_dict(self.app_defaults_path, app_data)

    def _ensure_keys_config_exists(self):
        """Ensure the key config file exists, creating an empty file if needed."""
        if not self.keys_path.exists():
            default_keys = {"providers": {}}
            initial_text = yaml.safe_dump(default_keys, allow_unicode=True, sort_keys=False)

            if self._layered_keys:
                ensure_local_file(
                    local_path=self.keys_path,
                    defaults_path=None,
                    legacy_paths=self.legacy_keys_paths,
                    initial_text=initial_text,
                )
                return

            if self._is_shared_keys_path(self.keys_path):
                logger.warning(
                    "Refusing to create shared key file at %s; "
                    "runtime writes must use config/local/keys_config.yaml",
                    self.keys_path,
                )
                return

            with open(self.keys_path, 'w', encoding='utf-8') as f:
                f.write(initial_text)

    async def load_keys_config(self) -> dict:
        """Load the key configuration file."""
        if not self.keys_path.exists():
            return {"providers": {}}

        async with aiofiles.open(self.keys_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content)
            return data if data else {"providers": {}}

    async def save_keys_config(self, keys_data: dict):
        """
        Save the key configuration file atomically.

        Uses a temporary file followed by replace to avoid partial writes.
        """
        self._assert_keys_path_writable()

        # Write the temporary file first.
        temp_path = self.keys_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            content = yaml.safe_dump(
                keys_data,
                allow_unicode=True,
                sort_keys=False
            )
            await f.write(content)

        # Replace atomically.
        temp_path.replace(self.keys_path)

    @staticmethod
    def _normalize_url(value: str) -> str:
        return str(value or "").strip().rstrip("/")

    @classmethod
    def _resolve_endpoint_profile_id_by_url(
        cls,
        endpoint_profiles: list[EndpointProfile],
        base_url: str,
    ) -> Optional[str]:
        normalized_base = cls._normalize_url(base_url)
        for profile in endpoint_profiles:
            if cls._normalize_url(profile.base_url) == normalized_base:
                return profile.id
        return None

    @staticmethod
    def _same_path(path_a: Path, path_b: Path) -> bool:
        try:
            return path_a.expanduser().resolve() == path_b.expanduser().resolve()
        except Exception:
            return str(path_a.expanduser()) == str(path_b.expanduser())

    def _is_shared_keys_path(self, path: Path) -> bool:
        return self._same_path(path, shared_keys_config_path())

    def _assert_keys_path_writable(self) -> None:
        if self._is_shared_keys_path(self.keys_path):
            raise PermissionError(
                "Shared key file (~/.lex_mint/keys_config.yaml) is bootstrap-only. "
                "Runtime writes are allowed only in config/local/keys_config.yaml."
            )

    async def get_api_key(self, provider_id: str) -> Optional[str]:
        """
        Get the API key for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            The API key, or ``None`` if it is not configured.
        """
        keys_data = await self.load_keys_config()
        return keys_data.get("providers", {}).get(provider_id, {}).get("api_key")

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

    async def get_providers(self) -> List[Provider]:
        """Get all providers, including has_api_key metadata."""
        config = await self.load_config()
        providers_with_keys = []
        for provider in config.providers:
            # Check whether the provider has an API key configured.
            has_key = await self.has_api_key(provider.id)
            requires_key = self.provider_requires_api_key(provider)
            # Attach runtime-only key metadata to the returned provider object.
            provider_dict = provider.model_dump()
            provider_dict['has_api_key'] = has_key
            provider_dict['requires_api_key'] = requires_key
            providers_with_keys.append(Provider(**provider_dict))
        return providers_with_keys

    async def get_provider(self, provider_id: str, include_masked_key: bool = False) -> Optional[Provider]:
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
                provider_dict['has_api_key'] = has_key
                provider_dict['requires_api_key'] = requires_key

                # Add a masked key preview when requested.
                if include_masked_key and has_key:
                    api_key = await self.get_api_key(provider_id)
                    if api_key:
                        provider_dict['api_key'] = self._mask_api_key(api_key)

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

    def resolve_endpoint_profile_base_url(self, provider: Provider, endpoint_profile_id: str) -> Optional[str]:
        """Resolve the base URL for a given endpoint profile id."""
        for profile in self.get_endpoint_profiles_for_provider(provider):
            if profile.id == endpoint_profile_id:
                return profile.base_url
        return None

    def resolve_endpoint_profile_id_for_base_url(self, provider: Provider, base_url: str) -> Optional[str]:
        """Resolve endpoint profile id by matching base URL."""
        return self._resolve_endpoint_profile_id_by_url(
            self.get_endpoint_profiles_for_provider(provider),
            base_url,
        )

    def recommend_endpoint_profile_id(
        self,
        provider: Provider,
        client_region_hint: str = "unknown",
    ) -> Optional[str]:
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
        provider_dict = provider.model_dump(exclude={'api_key', 'has_api_key', 'requires_api_key'})
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
                updated_dict = updated.model_dump(exclude={'api_key', 'has_api_key', 'requires_api_key'})
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

    async def get_models(self, provider_id: Optional[str] = None) -> List[Model]:
        """
        Get models, optionally filtered by provider.

        Args:
            provider_id: Provider ID to filter by.
        """
        config = await self.load_config()
        if provider_id:
            return [m for m in config.models if m.provider_id == provider_id]
        return config.models

    async def get_model(self, model_id: str) -> Optional[Model]:
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

        if ':' in model_id:
            potential_provider, potential_model = model_id.split(':', 1)
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
        if any(m.id == model.id and m.provider_id == model.provider_id
               for m in config.models):
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

        if ':' in model_id:
            potential_provider, potential_model = model_id.split(':', 1)
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

        if ':' in model_id:
            potential_provider, potential_model = model_id.split(':', 1)
            if any(p.id == potential_provider for p in config.providers):
                is_composite = True
                provider_id = potential_provider
                simple_model_id = potential_model

        if is_composite:
            composite_default = f"{config.default.provider}:{config.default.model}"
            deleting_default = model_id == composite_default or (
                simple_model_id == config.default.model
                and provider_id == config.default.provider
            )
            original_count = len(config.models)
            config.models = [
                m for m in config.models
                if not (m.id == simple_model_id and m.provider_id == provider_id)
            ]
        else:
            deleting_default = (
                config.default.model == model_id
                and any(
                    m.id == model_id and m.provider_id == config.default.provider
                    for m in config.models
                )
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
        if not bool(model.enabled):
            raise ValueError(f"Model '{model_id}' is disabled and cannot be set as default")

        provider = next((p for p in config.providers if p.id == provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{provider_id}' not found")
        if not bool(provider.enabled):
            raise ValueError(f"Provider '{provider_id}' is disabled and cannot be set as default")

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
        model_id: Optional[str] = None,
        provider: Optional[Provider] = None
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
                call_mode=provider.call_mode if hasattr(provider, 'call_mode') and provider.call_mode else CallMode.AUTO,
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

    def get_model_and_provider_sync(
        self,
        model_id: Optional[str] = None
    ) -> Tuple[Model, Provider]:
        """
        Synchronously load a model and provider pair.
        """
        config = ModelsConfig(**self._load_split_config())

        requested_model_id = model_id
        if requested_model_id is None:
            requested_model_id = self._require_default_model_lookup_id(config)

        model = self._find_model_in_config(config, requested_model_id)
        if not model:
            raise ValueError(f"Model with id '{requested_model_id}' not found")

        provider = next((p for p in config.providers if p.id == model.provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        if model_id is None and (not bool(model.enabled) or not bool(provider.enabled)):
            raise ValueError(
                f"Default model '{requested_model_id}' is disabled. Configure another default model first."
            )

        return model, provider

    @staticmethod
    def _find_model_in_config(config: ModelsConfig, model_id: str) -> Optional[Model]:
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
    ) -> Optional[Tuple[Model, Provider]]:
        providers_by_id = {p.id: p for p in config.providers}
        candidates: List[Tuple[Model, Provider]] = []
        for model in config.models:
            provider = providers_by_id.get(model.provider_id)
            if provider is None:
                continue
            if bool(model.enabled) and bool(provider.enabled):
                candidates.append((model, provider))
        if len(candidates) == 1:
            return candidates[0]
        return None

    def get_merged_capabilities(
        self,
        model: Model,
        provider: Provider
    ) -> ModelCapabilities:
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

            filtered_inferred_overrides: Dict[str, Any] = {
                key: value
                for key, value in inferred_overrides.items()
                if key not in explicit_capability_fields
            }
            inferred_reasoning_controls = filtered_inferred_overrides.get("reasoning_controls")
            if isinstance(inferred_reasoning_controls, dict):
                filtered_inferred_overrides["reasoning_controls"] = ReasoningControls(**inferred_reasoning_controls)
            if filtered_inferred_overrides:
                base_caps = base_caps.model_copy(update=filtered_inferred_overrides)

        if not base_caps.reasoning and base_caps.reasoning_controls is not None:
            base_caps = base_caps.model_copy(update={"reasoning_controls": None})

        return base_caps

    def get_api_key_sync(self, provider_id: str) -> Optional[str]:
        """
        Get the API key for a provider synchronously.

        Args:
            provider_id: Provider ID.

        Returns:
            The API key, or ``None`` if it is not configured.
        """
        if not self.keys_path.exists():
            return None

        try:
            with open(self.keys_path, 'r', encoding='utf-8') as f:
                keys_data = yaml.safe_load(f)
                if keys_data and "providers" in keys_data:
                    return keys_data["providers"].get(provider_id, {}).get("api_key")
        except Exception:
            pass
        return None

    def provider_requires_api_key(self, provider: Provider | ProviderConfig) -> bool:
        """
        Return whether this provider requires a non-empty API key.

        Uses resolved adapter family instead of protocol-only checks so custom
        sdk overrides (for example sdk_class=ollama) behave correctly.
        """
        provider_cfg = provider if isinstance(provider, ProviderConfig) else self.to_provider_config(provider)
        sdk_type = AdapterRegistry.resolve_sdk_type_for_provider(provider_cfg)
        return sdk_type not in {"ollama", "lmstudio", "local_gguf"}

    @staticmethod
    def _normalize_base_host(base_url: str) -> str:
        """Extract normalized host from base URL (supports URLs without scheme)."""
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
        """
        Determine whether a provider should be treated as OpenAI official.

        Primary rule:
        - provider id is "openai"

        Fallback rule:
        - base_url host is api.openai.com
        """
        provider_id = (getattr(provider, "id", "") or "").strip().lower()
        if provider_id == "openai":
            return True

        base_url = getattr(provider, "base_url", "") or ""
        host = self._normalize_base_host(base_url)
        return host == "api.openai.com"

    def resolve_effective_call_mode(self, provider: Provider | ProviderConfig) -> CallMode:
        """
        Resolve effective call mode with auto policy.

        Auto policy:
        - Anthropic/Gemini/Ollama adapter families -> native
        - OpenAI official -> responses
        - Others -> chat_completions
        """
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
        """
        Resolve API key for a provider, allowing empty key for local providers.

        Raises:
            RuntimeError: when provider requires API key but none is configured.
        """
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
        """
        Convert a ``Provider`` into a ``ProviderConfig`` for ``AdapterRegistry``.

        Args:
            provider: Provider instance.

        Returns:
            The normalized ``ProviderConfig`` instance.
        """
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
        """
        Get the adapter implementation for a provider.

        Args:
            provider: Provider instance.

        Returns:
            The resolved ``BaseLLMAdapter`` implementation.
        """
        provider_config = self.to_provider_config(provider)
        return AdapterRegistry.get_for_provider(provider_config)

    # ==================== LLM Instantiation ====================

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
        """
        Create an LLM instance synchronously.
        """
        config = ModelsConfig(**self._load_split_config())

        requested_model_id = model_id
        if requested_model_id is None:
            requested_model_id = self._require_default_model_lookup_id(config)

        model = self._find_model_in_config(config, requested_model_id)
        if not model:
            raise ValueError(f"Model with id '{requested_model_id}' not found")

        provider = next((p for p in config.providers if p.id == model.provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        if model_id is None and (not bool(model.enabled) or not bool(provider.enabled)):
            raise ValueError(
                f"Default model '{requested_model_id}' is disabled. Configure another default model first."
            )

        api_key = self.resolve_provider_api_key_sync(provider)

        adapter = self.get_adapter_for_provider(provider)
        resolved_call_mode = self.resolve_effective_call_mode(provider)
        effective_call_mode = (
            resolved_call_mode.value
            if isinstance(resolved_call_mode, CallMode)
            else str(resolved_call_mode)
        )
        capabilities = self.get_merged_capabilities(model, provider)

        create_kwargs: Dict[str, Any] = {
            "model": model.id,
            "base_url": provider.base_url,
            "api_key": api_key,
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
