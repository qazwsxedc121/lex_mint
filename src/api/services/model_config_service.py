"""
模型配置管理服务

负责加载、保存和管理 LLM 提供商和模型配置
"""
import yaml
import aiofiles
import logging
from pathlib import Path
from typing import List, Optional, Tuple, Any
from urllib.parse import urlparse
from langchain_openai import ChatOpenAI

from ..models.model_config import Provider, Model, DefaultConfig, ModelsConfig
from src.providers import (
    AdapterRegistry,
    ModelCapabilities,
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
    """模型配置管理服务"""

    _DEFAULT_ENABLED_BUILTIN_PROVIDERS = {"deepseek", "openrouter"}
    _BOOTSTRAP_PROVIDER_ID = "deepseek"
    _BOOTSTRAP_MODEL_ID = "deepseek-chat"
    _BOOTSTRAP_MODEL_NAME = "DeepSeek Chat"
    _BUILTIN_BASE_URL_MIGRATIONS = {
        "siliconflow": {
            "https://api.siliconflow.com/v1": "https://api.siliconflow.cn/v1",
        },
    }
    _MODEL_LEVEL_INTERLEAVED_PROVIDERS = {"deepseek", "kimi"}

    def __init__(self, config_path: Optional[Path] = None, keys_path: Optional[Path] = None):
        """
        初始化配置服务

        Args:
            config_path: 配置文件路径，默认使用项目内 config/local/models_config.yaml
            keys_path: 密钥文件路径，默认使用项目内 config/local/keys_config.yaml
        """
        self.defaults_path: Optional[Path] = None
        self.legacy_models_paths: list[Path] = []
        self.legacy_keys_paths: list[Path] = []
        self._layered_models = config_path is None
        self._layered_keys = keys_path is None

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "models_config.yaml"
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
        self.keys_path = keys_path
        self._ensure_config_exists()
        self._sync_builtin_entries()
        self._ensure_keys_config_exists()

    def _ensure_config_exists(self):
        """确保配置文件存在，如果不存在则创建默认配置"""
        if not self.config_path.exists():
            default_config = self._get_default_config()
            initial_text = yaml.safe_dump(default_config, allow_unicode=True, sort_keys=False)

            if self._layered_models:
                ensure_local_file(
                    local_path=self.config_path,
                    defaults_path=self.defaults_path,
                    legacy_paths=self.legacy_models_paths,
                    initial_text=initial_text,
                )
                return

            with open(self.config_path, 'w', encoding='utf-8') as f:
                f.write(initial_text)

    def _get_default_config(self) -> dict:
        """获取默认配置"""
        providers: list[dict[str, Any]] = []
        models: list[dict[str, Any]] = []

        for definition in get_all_builtin_providers().values():
            providers.append(
                self._provider_from_definition(
                    definition,
                    enabled=definition.id in self._DEFAULT_ENABLED_BUILTIN_PROVIDERS,
                )
            )

        # Keep default config minimal; runtime model discovery should come from provider APIs.
        models.append(self._build_bootstrap_model())

        return {
            "default": {
                "provider": self._BOOTSTRAP_PROVIDER_ID,
                "model": self._BOOTSTRAP_MODEL_ID,
            },
            "providers": providers,
            "models": models,
            "reasoning_supported_patterns": ["deepseek-chat", "glm-"],
        }

    def _build_bootstrap_model(self) -> dict[str, Any]:
        """Build a single default model so a fresh install is immediately usable."""
        deepseek = get_builtin_provider(self._BOOTSTRAP_PROVIDER_ID)
        capabilities = deepseek.default_capabilities if deepseek else None
        return self._model_from_definition(
            provider_id=self._BOOTSTRAP_PROVIDER_ID,
            model_id=self._BOOTSTRAP_MODEL_ID,
            model_name=self._BOOTSTRAP_MODEL_NAME,
            capabilities=capabilities,
            enabled=True,
        )

    def _provider_from_definition(self, definition, enabled: bool) -> dict[str, Any]:
        return {
            "id": definition.id,
            "name": definition.name,
            "type": "builtin",
            "protocol": definition.protocol.value,
            "call_mode": "auto",
            "base_url": definition.base_url,
            "api_keys": [],
            "enabled": enabled,
            "default_capabilities": definition.default_capabilities.model_dump(mode="json"),
            "url_suffix": definition.url_suffix,
            "auto_append_path": definition.auto_append_path,
            "supports_model_list": definition.supports_model_list,
            "sdk_class": definition.sdk_class,
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
        Ensure built-in providers/models always exist in local config.

        Adds missing entries and refreshes non-user-editable builtin flags.
        """
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning(f"Failed to read model config for builtin sync: {e}")
            return

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

        default_config = data.get("default") or {}
        default_provider = default_config.get("provider")
        default_model = default_config.get("model")

        existing_providers = {
            p.get("id"): p
            for p in providers
            if isinstance(p, dict) and p.get("id")
        }
        existing_provider_ids = set(existing_providers.keys())
        existing_model_keys = {
            (m.get("provider_id"), m.get("id"))
            for m in models
            if isinstance(m, dict) and m.get("provider_id") and m.get("id")
        }

        for definition in get_all_builtin_providers().values():
            if definition.id not in existing_provider_ids:
                providers.append(
                    self._provider_from_definition(
                        definition,
                        enabled=definition.id in self._DEFAULT_ENABLED_BUILTIN_PROVIDERS,
                    )
                )
                existing_provider_ids.add(definition.id)
                changed = True
            else:
                # Keep non-user-editable builtin metadata flags in sync.
                provider_entry = existing_providers.get(definition.id)
                if (
                    isinstance(provider_entry, dict)
                    and provider_entry.get("type") == "builtin"
                ):
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

        default_key = (default_provider, default_model)
        bootstrap_key = (self._BOOTSTRAP_PROVIDER_ID, self._BOOTSTRAP_MODEL_ID)
        if default_key not in existing_model_keys:
            if bootstrap_key not in existing_model_keys:
                models.append(self._build_bootstrap_model())
                existing_model_keys.add(bootstrap_key)
            data["default"] = {
                "provider": self._BOOTSTRAP_PROVIDER_ID,
                "model": self._BOOTSTRAP_MODEL_ID,
            }
            changed = True

        reasoning_patterns = data.get("reasoning_supported_patterns")
        if not isinstance(reasoning_patterns, list):
            reasoning_patterns = []
            data["reasoning_supported_patterns"] = reasoning_patterns
            changed = True

        for pattern in ["deepseek-chat", "glm-"]:
            if pattern not in reasoning_patterns:
                reasoning_patterns.append(pattern)
                changed = True

        # Backfill stale model-level interleaved flags from older provider-level defaults.
        for model_entry in models:
            if not isinstance(model_entry, dict):
                continue
            model_id_value = model_entry.get("id")
            if not isinstance(model_id_value, str):
                continue

            inferred = infer_capability_overrides(model_id_value)
            if inferred.get("requires_interleaved_thinking") is not True:
                continue

            model_caps = model_entry.get("capabilities")
            if not isinstance(model_caps, dict):
                continue

            if model_caps.get("requires_interleaved_thinking") is False:
                model_caps["requires_interleaved_thinking"] = True
                changed = True

        if changed:
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    async def load_config(self) -> ModelsConfig:
        """加载配置文件"""
        async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content)
            return ModelsConfig(**data)

    async def save_config(self, config: ModelsConfig):
        """
        保存配置文件（原子性写入）

        使用临时文件 + 替换的方式确保原子性
        """
        # 先写入临时文件
        temp_path = self.config_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            # Use mode='json' to serialize enums as values
            content = yaml.safe_dump(
                config.model_dump(mode='json'),
                allow_unicode=True,
                sort_keys=False
            )
            await f.write(content)

        # 原子性替换
        temp_path.replace(self.config_path)

    def _ensure_keys_config_exists(self):
        """确保密钥配置文件存在，如果不存在则创建空配置"""
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
        """加载密钥配置文件"""
        if not self.keys_path.exists():
            return {"providers": {}}

        async with aiofiles.open(self.keys_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content)
            return data if data else {"providers": {}}

    async def save_keys_config(self, keys_data: dict):
        """
        保存密钥配置文件（原子性写入）

        使用临时文件 + 替换的方式确保原子性
        """
        self._assert_keys_path_writable()

        # 先写入临时文件
        temp_path = self.keys_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            content = yaml.safe_dump(
                keys_data,
                allow_unicode=True,
                sort_keys=False
            )
            await f.write(content)

        # 原子性替换
        temp_path.replace(self.keys_path)

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
        获取指定提供商的 API 密钥

        Args:
            provider_id: 提供商ID

        Returns:
            API 密钥，如果不存在则返回 None
        """
        keys_data = await self.load_keys_config()
        return keys_data.get("providers", {}).get(provider_id, {}).get("api_key")

    async def set_api_key(self, provider_id: str, api_key: str):
        """
        设置/更新指定提供商的 API 密钥

        Args:
            provider_id: 提供商ID
            api_key: API 密钥
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
        删除指定提供商的 API 密钥

        Args:
            provider_id: 提供商ID
        """
        keys_data = await self.load_keys_config()
        if "providers" in keys_data and provider_id in keys_data["providers"]:
            del keys_data["providers"][provider_id]
            await self.save_keys_config(keys_data)

    async def has_api_key(self, provider_id: str) -> bool:
        """
        检查指定提供商是否已配置 API 密钥

        Args:
            provider_id: 提供商ID

        Returns:
            如果已配置密钥返回 True，否则返回 False
        """
        api_key = await self.get_api_key(provider_id)
        return api_key is not None and api_key.strip() != ""

    # ==================== 提供商管理 ====================

    async def get_providers(self) -> List[Provider]:
        """获取所有提供商（包含 has_api_key 标记）"""
        config = await self.load_config()
        providers_with_keys = []
        for provider in config.providers:
            # 检查是否有 API 密钥
            has_key = await self.has_api_key(provider.id)
            requires_key = self.provider_requires_api_key(provider)
            # 创建新的 Provider 对象，添加 has_api_key 字段
            provider_dict = provider.model_dump()
            provider_dict['has_api_key'] = has_key
            provider_dict['requires_api_key'] = requires_key
            providers_with_keys.append(Provider(**provider_dict))
        return providers_with_keys

    async def get_provider(self, provider_id: str, include_masked_key: bool = False) -> Optional[Provider]:
        """
        获取指定提供商

        Args:
            provider_id: 提供商ID
            include_masked_key: 是否包含遮罩后的API密钥（用于编辑界面显示）
        """
        config = await self.load_config()
        for provider in config.providers:
            if provider.id == provider_id:
                provider_dict = provider.model_dump()

                # 添加 has_api_key 标记
                has_key = await self.has_api_key(provider_id)
                requires_key = self.provider_requires_api_key(provider)
                provider_dict['has_api_key'] = has_key
                provider_dict['requires_api_key'] = requires_key

                # 如果需要，添加遮罩后的API密钥
                if include_masked_key and has_key:
                    api_key = await self.get_api_key(provider_id)
                    if api_key:
                        provider_dict['api_key'] = self._mask_api_key(api_key)

                return Provider(**provider_dict)
        return None

    def _mask_api_key(self, api_key: str) -> str:
        """
        遮罩API密钥，只显示前缀和后4位

        例如: sk- -> sk-****
        """
        if len(api_key) <= 8:
            return "****"
        return f"{api_key[:3]}****...{api_key[-4:]}"

    async def add_provider(self, provider: Provider):
        """
        添加提供商

        Raises:
            ValueError: 如果提供商ID已存在
        """
        config = await self.load_config()

        # 检查ID是否已存在
        if any(p.id == provider.id for p in config.providers):
            raise ValueError(f"Provider with id '{provider.id}' already exists")

        # 移除临时字段，避免保存到配置文件
        provider_dict = provider.model_dump(exclude={'api_key', 'has_api_key', 'requires_api_key'})
        config.providers.append(Provider(**provider_dict))
        await self.save_config(config)

    async def update_provider(self, provider_id: str, updated: Provider):
        """
        更新提供商

        Raises:
            ValueError: 如果提供商不存在
        """
        config = await self.load_config()

        for i, provider in enumerate(config.providers):
            if provider.id == provider_id:
                # 移除临时字段，避免保存到配置文件
                updated_dict = updated.model_dump(exclude={'api_key', 'has_api_key', 'requires_api_key'})
                config.providers[i] = Provider(**updated_dict)
                await self.save_config(config)
                return

        raise ValueError(f"Provider with id '{provider_id}' not found")

    async def delete_provider(self, provider_id: str):
        """
        删除提供商（级联删除关联的模型）

        Raises:
            ValueError: 如果提供商不存在或是默认提供商
        """
        config = await self.load_config()

        # 检查是否是默认提供商
        if config.default.provider == provider_id:
            raise ValueError(f"Cannot delete default provider '{provider_id}'")
        if get_builtin_provider(provider_id):
            raise ValueError(f"Cannot delete built-in provider '{provider_id}', disable it instead")

        # 删除提供商
        config.providers = [p for p in config.providers if p.id != provider_id]

        # 级联删除关联的模型
        config.models = [m for m in config.models if m.provider_id != provider_id]

        await self.save_config(config)

    # ==================== 模型管理 ====================

    async def get_models(self, provider_id: Optional[str] = None) -> List[Model]:
        """
        获取模型列表

        Args:
            provider_id: 可选的提供商ID，用于筛选
        """
        config = await self.load_config()
        if provider_id:
            return [m for m in config.models if m.provider_id == provider_id]
        return config.models

    async def get_model(self, model_id: str) -> Optional[Model]:
        """
        获取指定模型

        Args:
            model_id: 模型ID，可以是简单ID或复合ID (provider_id:model_id)
        """
        config = await self.load_config()

        # 判断是否为复合ID：检查第一个冒号前是否为有效的provider_id
        is_composite = False
        provider_id = None
        simple_model_id = None

        if ':' in model_id:
            potential_provider, potential_model = model_id.split(':', 1)
            # 检查是否为有效的provider_id
            if any(p.id == potential_provider for p in config.providers):
                is_composite = True
                provider_id = potential_provider
                simple_model_id = potential_model

        if is_composite:
            # 复合ID格式：provider_id:model_id
            for model in config.models:
                if model.id == simple_model_id and model.provider_id == provider_id:
                    return model
        else:
            # 简单ID（包括可能包含冒号的模型ID）
            for model in config.models:
                if model.id == model_id:
                    return model

        return None

    async def add_model(self, model: Model):
        """
        添加模型

        Raises:
            ValueError: 如果模型在该提供商下已存在，或提供商不存在
        """
        config = await self.load_config()

        # 检查同一个提供商下是否有重复的模型ID（复合主键）
        if any(m.id == model.id and m.provider_id == model.provider_id
               for m in config.models):
            raise ValueError(
                f"Model '{model.id}' already exists for provider '{model.provider_id}'"
            )

        # 检查提供商是否存在
        if not any(p.id == model.provider_id for p in config.providers):
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        config.models.append(model)
        await self.save_config(config)

    async def update_model(self, model_id: str, updated: Model):
        """
        更新模型

        Args:
            model_id: 模型ID，可以是简单ID或复合ID (provider_id:model_id)

        Raises:
            ValueError: 如果模型不存在
        """
        config = await self.load_config()

        # 判断是否为复合ID：检查第一个冒号前是否为有效的provider_id
        is_composite = False
        provider_id = None
        simple_model_id = None

        if ':' in model_id:
            potential_provider, potential_model = model_id.split(':', 1)
            # 检查是否为有效的provider_id
            if any(p.id == potential_provider for p in config.providers):
                is_composite = True
                provider_id = potential_provider
                simple_model_id = potential_model

        if is_composite:
            # 复合ID格式：provider_id:model_id
            for i, model in enumerate(config.models):
                if model.id == simple_model_id and model.provider_id == provider_id:
                    config.models[i] = updated
                    await self.save_config(config)
                    return
        else:
            # 简单ID（包括可能包含冒号的模型ID）
            for i, model in enumerate(config.models):
                if model.id == model_id:
                    config.models[i] = updated
                    await self.save_config(config)
                    return

        raise ValueError(f"Model with id '{model_id}' not found")

    async def delete_model(self, model_id: str):
        """
        删除模型

        Args:
            model_id: 模型ID，可以是简单ID或复合ID (provider_id:model_id)

        Raises:
            ValueError: 如果模型不存在或是默认模型
        """
        config = await self.load_config()

        # 判断是否为复合ID：检查第一个冒号前是否为有效的provider_id
        is_composite = False
        provider_id = None
        simple_model_id = None

        if ':' in model_id:
            potential_provider, potential_model = model_id.split(':', 1)
            # 检查是否为有效的provider_id
            if any(p.id == potential_provider for p in config.providers):
                is_composite = True
                provider_id = potential_provider
                simple_model_id = potential_model

        if is_composite:
            # 复合ID格式：provider_id:model_id
            composite_default = f"{config.default.provider}:{config.default.model}"

            # 检查是否是默认模型
            if model_id == composite_default or (
                simple_model_id == config.default.model and
                provider_id == config.default.provider
            ):
                raise ValueError(f"Cannot delete default model '{model_id}'")

            # 删除模型
            original_count = len(config.models)
            config.models = [
                m for m in config.models
                if not (m.id == simple_model_id and m.provider_id == provider_id)
            ]
        else:
            # 简单ID（包括可能包含冒号的模型ID，如 google/model:free）
            if config.default.model == model_id:
                raise ValueError(f"Cannot delete default model '{model_id}'")

            original_count = len(config.models)
            config.models = [m for m in config.models if m.id != model_id]

        if len(config.models) == original_count:
            raise ValueError(f"Model with id '{model_id}' not found")

        await self.save_config(config)

    # ==================== 默认配置 ====================

    async def get_default_config(self) -> DefaultConfig:
        """获取默认配置"""
        config = await self.load_config()
        return config.default

    async def set_default_model(self, provider_id: str, model_id: str):
        """
        设置默认模型

        Raises:
            ValueError: 如果提供商或模型不存在
        """
        config = await self.load_config()

        # 验证提供商存在
        if not any(p.id == provider_id for p in config.providers):
            raise ValueError(f"Provider with id '{provider_id}' not found")

        # 验证模型存在且属于该提供商
        model = next((m for m in config.models if m.id == model_id), None)
        if not model:
            raise ValueError(f"Model with id '{model_id}' not found")
        if model.provider_id != provider_id:
            raise ValueError(f"Model '{model_id}' does not belong to provider '{provider_id}'")

        config.default.provider = provider_id
        config.default.model = model_id
        await self.save_config(config)

    async def get_reasoning_supported_patterns(self) -> list[str]:
        """获取支持 reasoning effort 参数的模型名称模式列表"""
        config = await self.load_config()
        return config.reasoning_supported_patterns

    # ==================== 测试连接 ====================

    async def test_provider_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: Optional[str] = None,
        provider: Optional[Provider] = None
    ) -> tuple[bool, str]:
        """
        测试提供商连接是否有效

        Args:
            base_url: API基础URL
            api_key: API密钥
            model_id: 用于测试的模型ID（默认使用通用的模型名）
            provider: 提供商配置（用于选择正确的适配器）

        Returns:
            (是否成功, 消息)
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
                sdk_class=provider.sdk_class,
            )
            adapter = AdapterRegistry.get_for_provider(provider_cfg)
        else:
            adapter = AdapterRegistry.get("openai")

        return await adapter.test_connection(
            base_url=base_url,
            api_key=api_key,
            model_id=model_id,
        )

    # ==================== Provider 抽象层支持 ====================

    def get_model_and_provider_sync(
        self,
        model_id: Optional[str] = None
    ) -> Tuple[Model, Provider]:
        """
        同步获取模型和提供商配置

        Args:
            model_id: 模型ID，支持复合ID (provider_id:model_id)

        Returns:
            Tuple of (Model, Provider)

        Raises:
            ValueError: 如果模型或提供商不存在
        """
        # 同步加载配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            config = ModelsConfig(**data)

        # 确定使用哪个模型
        if model_id is None:
            model_id = f"{config.default.provider}:{config.default.model}"

        # 查找模型（支持复合ID）
        model = None
        if ':' in model_id:
            provider_id, simple_model_id = model_id.split(':', 1)
            model = next(
                (m for m in config.models
                 if m.id == simple_model_id and m.provider_id == provider_id),
                None
            )
        else:
            model = next((m for m in config.models if m.id == model_id), None)

        if not model:
            raise ValueError(f"Model with id '{model_id}' not found")

        # 查找提供商
        provider = next((p for p in config.providers if p.id == model.provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        return model, provider

    def get_merged_capabilities(
        self,
        model: Model,
        provider: Provider
    ) -> ModelCapabilities:
        """
        获取合并后的模型能力配置

        优先级：model.capabilities > provider.default_capabilities > 内置默认值

        Args:
            model: Model 配置
            provider: Provider 配置

        Returns:
            合并后的 ModelCapabilities
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

        inferred_overrides = infer_capability_overrides(model.id)
        hard_require_interleaved = (
            inferred_overrides.get("requires_interleaved_thinking") is True
            if inferred_overrides
            else False
        )
        if inferred_overrides:
            base_caps = base_caps.model_copy(update=inferred_overrides)

        # Override with model-specific capabilities
        if model.capabilities:
            base_caps = base_caps.merge_with(model.capabilities)

        # Keep required interleaved passthrough as a hard safety rule.
        if hard_require_interleaved and not base_caps.requires_interleaved_thinking:
            base_caps = base_caps.model_copy(update={"requires_interleaved_thinking": True})

        return base_caps

    def get_api_key_sync(self, provider_id: str) -> Optional[str]:
        """
        同步获取 API 密钥

        Args:
            provider_id: 提供商ID

        Returns:
            API 密钥，如果不存在则返回 None
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
        return sdk_type != "ollama"

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

        if sdk_type in {"anthropic", "gemini", "ollama"}:
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
        将 Provider 转换为 ProviderConfig（用于 AdapterRegistry）

        Args:
            provider: Provider 配置

        Returns:
            ProviderConfig 实例
        """
        return ProviderConfig(
            id=provider.id,
            name=provider.name,
            type=provider.type if hasattr(provider, 'type') and provider.type else ProviderType.BUILTIN,
            protocol=provider.protocol if hasattr(provider, 'protocol') and provider.protocol else ApiProtocol.OPENAI,
            call_mode=provider.call_mode if hasattr(provider, 'call_mode') and provider.call_mode else CallMode.AUTO,
            base_url=provider.base_url,
            enabled=provider.enabled,
            default_capabilities=provider.default_capabilities,
            sdk_class=provider.sdk_class if hasattr(provider, 'sdk_class') else None,
        )

    def get_adapter_for_provider(self, provider: Provider):
        """
        获取提供商对应的 SDK 适配器

        Args:
            provider: Provider 配置

        Returns:
            BaseLLMAdapter 实例
        """
        provider_config = self.to_provider_config(provider)
        return AdapterRegistry.get_for_provider(provider_config)

    # ==================== LLM 实例化 ====================

    def get_llm_instance(
        self,
        model_id: Optional[str] = None,
        *,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
        top_p: Optional[float] = None,
        top_k: Optional[int] = None,
        frequency_penalty: Optional[float] = None,
        presence_penalty: Optional[float] = None
    ) -> ChatOpenAI:
        """
        创建 LLM 实例（同步方法）

        Args:
            model_id: 模型ID，可以是简单ID或复合ID (provider_id:model_id)
                     如果为 None 则使用默认模型

        Returns:
            ChatOpenAI 实例

        Raises:
            ValueError: 如果模型不存在或配置无效
            RuntimeError: 如果 API 密钥未配置
        """
        # 同步加载配置
        with open(self.config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            config = ModelsConfig(**data)

        # 确定使用哪个模型
        if model_id is None:
            # 使用默认模型（复合ID）
            model_id = f"{config.default.provider}:{config.default.model}"

        # 查找模型（支持复合ID）
        model = None
        if ':' in model_id:
            provider_id, simple_model_id = model_id.split(':', 1)
            model = next(
                (m for m in config.models
                 if m.id == simple_model_id and m.provider_id == provider_id),
                None
            )
        else:
            # 简单ID：直接匹配（向后兼容）
            model = next((m for m in config.models if m.id == model_id), None)

        if not model:
            raise ValueError(f"Model with id '{model_id}' not found")

        # 查找提供商
        provider = next((p for p in config.providers if p.id == model.provider_id), None)
        if not provider:
            raise ValueError(f"Provider with id '{model.provider_id}' not found")

        api_key = self.resolve_provider_api_key_sync(provider)

        # 创建 LLM 实例
        model_kwargs = {}
        if top_p is not None:
            model_kwargs["top_p"] = top_p
        if top_k is not None:
            model_kwargs["top_k"] = top_k
        if frequency_penalty is not None:
            model_kwargs["frequency_penalty"] = frequency_penalty
        if presence_penalty is not None:
            model_kwargs["presence_penalty"] = presence_penalty

        build_kwargs = {
            "model": model.id,
            "temperature": 0.7 if temperature is None else temperature,
            "base_url": provider.base_url,
            "api_key": api_key,
        }
        if max_tokens is not None:
            build_kwargs["max_tokens"] = max_tokens
        if model_kwargs:
            build_kwargs["model_kwargs"] = model_kwargs

        return ChatOpenAI(**build_kwargs)
