"""Unit tests for ModelConfigService."""

import pytest
import yaml
import shutil
from pathlib import Path
from unittest.mock import patch, Mock

from src.api.services.model_config_service import ModelConfigService
from src.api.models.model_config import Provider, Model, ModelsConfig
from src.providers.types import ApiProtocol, ProviderType, ModelCapabilities


class TestModelConfigService:
    """Test cases for ModelConfigService class."""

    @pytest.fixture(autouse=True)
    def _disable_builtin_sync(self, monkeypatch, request):
        """Keep unit tests focused on local file behavior, not builtin auto-sync."""
        if request.node.name.startswith("test_sync_builtin_"):
            return
        monkeypatch.setattr(ModelConfigService, "_sync_builtin_entries", lambda self: None)

    @pytest.mark.asyncio
    async def test_ensure_config_exists(self, temp_config_dir):
        """Test that default config is created if it doesn't exist."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        service = ModelConfigService(config_path, keys_path)

        assert config_path.exists()
        assert keys_path.exists()

        # Verify default config structure
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            assert "default" in data
            assert "providers" in data
            assert "models" in data

    @pytest.mark.asyncio
    async def test_sync_builtin_supports_model_list_flag(self):
        """Builtin providers should refresh non-editable model-list support flags."""
        test_dir = Path(".tmp") / "test_sync_builtin_supports_model_list_flag"
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        config_path = test_dir / "models_config.yaml"
        keys_path = test_dir / "keys_config.yaml"

        stale_config = {
            "default": {"provider": "deepseek", "model": "deepseek-chat"},
            "providers": [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "type": "builtin",
                    "protocol": "openai",
                    "base_url": "https://api.deepseek.com",
                    "enabled": True,
                    "supports_model_list": False,
                    "sdk_class": "deepseek",
                }
            ],
            "models": [
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek Chat",
                    "provider_id": "deepseek",
                    "tags": ["chat"],
                    "enabled": True,
                }
            ],
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(stale_config, f)
            with open(keys_path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"providers": {}}, f)

            service = ModelConfigService(config_path, keys_path)
            provider = await service.get_provider("deepseek")
            stepfun = await service.get_provider("stepfun")

            assert provider is not None
            assert provider.supports_model_list is True
            assert stepfun is not None
            assert stepfun.base_url == "https://api.stepfun.com/v1"
            assert stepfun.sdk_class == "openai"
            assert stepfun.supports_model_list is True
            assert stepfun.enabled is False
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_sync_builtin_migrates_siliconflow_legacy_base_url(self):
        """Builtin sync should migrate legacy SiliconFlow .com base URL to .cn."""
        test_dir = Path(".tmp") / "test_sync_builtin_migrates_siliconflow_legacy_base_url"
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        config_path = test_dir / "models_config.yaml"
        keys_path = test_dir / "keys_config.yaml"

        stale_config = {
            "default": {"provider": "deepseek", "model": "deepseek-chat"},
            "providers": [
                {
                    "id": "siliconflow",
                    "name": "SiliconFlow",
                    "type": "builtin",
                    "protocol": "openai",
                    "base_url": "https://api.siliconflow.com/v1",
                    "enabled": True,
                    "supports_model_list": True,
                    "sdk_class": "siliconflow",
                }
            ],
            "models": [
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek Chat",
                    "provider_id": "deepseek",
                    "tags": ["chat"],
                    "enabled": True,
                }
            ],
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(stale_config, f)
            with open(keys_path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"providers": {}}, f)

            service = ModelConfigService(config_path, keys_path)
            provider = await service.get_provider("siliconflow")

            assert provider is not None
            assert provider.base_url == "https://api.siliconflow.cn/v1"
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_default_config_uses_single_bootstrap_model(self):
        """Fresh config should avoid preloading large builtin model catalogs."""
        test_dir = Path(".tmp") / "test_default_config_uses_single_bootstrap_model"
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        config_path = test_dir / "models_config.yaml"
        keys_path = test_dir / "keys_config.yaml"

        try:
            service = ModelConfigService(config_path, keys_path)
            config = await service.load_config()

            assert config.default.provider == "deepseek"
            assert config.default.model == "deepseek-chat"
            assert len(config.models) == 1
            assert config.models[0].provider_id == "deepseek"
            assert config.models[0].id == "deepseek-chat"
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_sync_builtin_does_not_auto_seed_builtin_model_catalog(self):
        """Builtin sync should not append large curated model lists."""
        test_dir = Path(".tmp") / "test_sync_builtin_does_not_auto_seed_builtin_model_catalog"
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        config_path = test_dir / "models_config.yaml"
        keys_path = test_dir / "keys_config.yaml"

        config_data = {
            "default": {"provider": "deepseek", "model": "deepseek-chat"},
            "providers": [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "type": "builtin",
                    "protocol": "openai",
                    "base_url": "https://api.deepseek.com",
                    "enabled": True,
                    "supports_model_list": True,
                    "sdk_class": "deepseek",
                }
            ],
            "models": [
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek Chat",
                    "provider_id": "deepseek",
                    "tags": ["chat"],
                    "enabled": True,
                }
            ],
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f)
            with open(keys_path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"providers": {}}, f)

            service = ModelConfigService(config_path, keys_path)
            config = await service.load_config()

            assert len(config.models) == 1
            assert config.models[0].id == "deepseek-chat"
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_load_config(self, temp_config_dir, sample_model_config):
        """Test loading configuration from file."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        # Write sample config
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)

        # Create empty keys config
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        config = await service.load_config()

        assert isinstance(config, ModelsConfig)
        assert config.default.provider == "deepseek"
        assert config.default.model == "deepseek-chat"
        assert len(config.providers) == 1
        assert len(config.models) == 1

    @pytest.mark.asyncio
    async def test_save_config(self, temp_config_dir, sample_model_config):
        """Test saving configuration to file."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        service = ModelConfigService(config_path, keys_path)
        config = ModelsConfig(**sample_model_config)

        # Modify and save
        config.default.model = "deepseek-coder"
        await service.save_config(config)

        # Reload and verify
        loaded_config = await service.load_config()
        assert loaded_config.default.model == "deepseek-coder"

    @pytest.mark.asyncio
    async def test_add_provider(self, temp_config_dir, sample_model_config):
        """Test adding a new provider."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)

        # Use dict instead of Provider object to avoid enum issues
        new_provider_dict = {
            "id": "openai",
            "name": "OpenAI",
            "type": "builtin",
            "protocol": "openai",
            "base_url": "https://api.openai.com/v1",
            "enabled": True
        }
        new_provider = Provider(**new_provider_dict)

        await service.add_provider(new_provider)

        # Verify
        providers = await service.get_providers()
        assert len(providers) == 2
        assert any(p.id == "openai" for p in providers)

    @pytest.mark.asyncio
    async def test_add_duplicate_provider(self, temp_config_dir, sample_model_config):
        """Test adding provider with duplicate ID."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)

        duplicate_provider = Provider(
            id="deepseek",  # Already exists
            name="Duplicate",
            type=ProviderType.BUILTIN,
            protocol=ApiProtocol.OPENAI,
            base_url="https://test.com",
            enabled=True
        )

        with pytest.raises(ValueError, match="already exists"):
            await service.add_provider(duplicate_provider)

    @pytest.mark.asyncio
    async def test_delete_provider(self, temp_config_dir, sample_model_config):
        """Test deleting a provider."""
        # Add second provider to config
        sample_model_config["providers"].append({
            "id": "custom-openai",
            "name": "Custom OpenAI",
            "type": "custom",
            "protocol": "openai",
            "base_url": "https://api.openai.com/v1",
            "enabled": True
        })

        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        await service.delete_provider("custom-openai")

        # Verify
        providers = await service.get_providers()
        assert len(providers) == 1
        assert providers[0].id == "deepseek"

    @pytest.mark.asyncio
    async def test_delete_default_provider(self, temp_config_dir, sample_model_config):
        """Test that default provider cannot be deleted."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)

        with pytest.raises(ValueError, match="Cannot delete default provider"):
            await service.delete_provider("deepseek")

    @pytest.mark.asyncio
    async def test_get_models(self, temp_config_dir, sample_model_config):
        """Test getting all models."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        models = await service.get_models()

        assert len(models) == 1
        assert models[0].id == "deepseek-chat"
        assert models[0].provider_id == "deepseek"

    @pytest.mark.asyncio
    async def test_get_model_by_simple_id(self, temp_config_dir, sample_model_config):
        """Test getting model by simple ID."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        model = await service.get_model("deepseek-chat")

        assert model is not None
        assert model.id == "deepseek-chat"
        assert model.provider_id == "deepseek"

    @pytest.mark.asyncio
    async def test_get_model_by_composite_id(self, temp_config_dir, sample_model_config):
        """Test getting model by composite ID (provider_id:model_id)."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        model = await service.get_model("deepseek:deepseek-chat")

        assert model is not None
        assert model.id == "deepseek-chat"
        assert model.provider_id == "deepseek"

    @pytest.mark.asyncio
    async def test_add_model(self, temp_config_dir, sample_model_config):
        """Test adding a new model."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)

        new_model = Model(
            id="deepseek-coder",
            name="DeepSeek Coder",
            provider_id="deepseek",
            tags=["chat"],
            enabled=True
        )

        await service.add_model(new_model)

        # Verify
        models = await service.get_models()
        assert len(models) == 2
        assert any(m.id == "deepseek-coder" for m in models)

    @pytest.mark.asyncio
    async def test_delete_model(self, temp_config_dir, sample_model_config):
        """Test deleting a model."""
        # Add second model
        sample_model_config["models"].append({
            "id": "deepseek-coder",
            "name": "DeepSeek Coder",
            "provider_id": "deepseek",
            "tags": ["chat"],
            "enabled": True
        })

        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        await service.delete_model("deepseek-coder")

        # Verify
        models = await service.get_models()
        assert len(models) == 1
        assert models[0].id == "deepseek-chat"

    @pytest.mark.asyncio
    async def test_delete_default_model(self, temp_config_dir, sample_model_config):
        """Test that default model cannot be deleted."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)

        with pytest.raises(ValueError, match="Cannot delete default model"):
            await service.delete_model("deepseek-chat")

    @pytest.mark.asyncio
    async def test_api_key_operations(self, temp_config_dir, sample_model_config):
        """Test API key get/set/delete operations."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)

        # Initially no API key
        assert await service.has_api_key("deepseek") == False
        assert await service.get_api_key("deepseek") is None

        # Set API key
        await service.set_api_key("deepseek", "test_key_12345")
        assert await service.has_api_key("deepseek") == True
        assert await service.get_api_key("deepseek") == "test_key_12345"

        # Delete API key
        await service.delete_api_key("deepseek")
        assert await service.has_api_key("deepseek") == False

    @pytest.mark.asyncio
    async def test_mask_api_key(self, temp_config_dir):
        """Test API key masking."""
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"

        service = ModelConfigService(config_path, keys_path)

        masked = service._mask_api_key("sk-80081234567890abcdef")
        assert masked == "sk-****...cdef"

        # Short key
        masked_short = service._mask_api_key("short")
        assert masked_short == "****"

    @pytest.mark.asyncio
    async def test_shared_keys_path_is_read_only(self, temp_config_dir, sample_model_config):
        """Shared key file must never be modified by runtime key operations."""
        config_path = temp_config_dir / "models_config.yaml"
        shared_keys_path = temp_config_dir / "shared" / "keys_config.yaml"
        shared_keys_path.parent.mkdir(parents=True, exist_ok=True)

        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(sample_model_config, f)
        with open(shared_keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump({"providers": {"deepseek": {"api_key": "old_value"}}}, f)

        with patch("src.api.services.model_config_service.shared_keys_config_path", return_value=shared_keys_path):
            service = ModelConfigService(config_path, shared_keys_path)

            with pytest.raises(PermissionError, match="bootstrap-only"):
                await service.set_api_key("deepseek", "new_value")

        with open(shared_keys_path, 'r', encoding='utf-8') as f:
            shared_data = yaml.safe_load(f)
        assert shared_data["providers"]["deepseek"]["api_key"] == "old_value"

    @pytest.mark.asyncio
    async def test_default_keys_path_bootstraps_from_shared_once(self, temp_config_dir):
        """Default key path should be local, bootstrapped from shared file."""
        config_local_path = temp_config_dir / "config" / "local"
        config_defaults_path = temp_config_dir / "config" / "defaults"
        legacy_config_path = temp_config_dir / "config"
        shared_keys_path = temp_config_dir / "home" / ".lex_mint" / "keys_config.yaml"

        config_defaults_path.mkdir(parents=True, exist_ok=True)
        shared_keys_path.parent.mkdir(parents=True, exist_ok=True)

        shared_payload = {"providers": {"openai": {"api_key": "shared_key_value"}}}
        with open(shared_keys_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(shared_payload, f)

        with patch("src.api.services.model_config_service.config_local_dir", return_value=config_local_path), \
                patch("src.api.services.model_config_service.config_defaults_dir", return_value=config_defaults_path), \
                patch("src.api.services.model_config_service.legacy_config_dir", return_value=legacy_config_path), \
                patch("src.api.services.model_config_service.local_keys_config_path", return_value=config_local_path / "keys_config.yaml"), \
                patch("src.api.services.model_config_service.shared_keys_config_path", return_value=shared_keys_path):
            service = ModelConfigService()

        expected_local_keys = config_local_path / "keys_config.yaml"
        assert service.keys_path == expected_local_keys
        assert expected_local_keys.exists()

        with open(expected_local_keys, 'r', encoding='utf-8') as f:
            local_data = yaml.safe_load(f)
        assert local_data == shared_payload

    def test_get_merged_capabilities_uses_model_rules_when_model_capability_missing(self, temp_config_dir):
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"
        with open(keys_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        model = Model(id="moonshotai/kimi-k2.5", name="Kimi", provider_id="openrouter", enabled=True)
        provider = Provider(
            id="openrouter",
            name="OpenRouter",
            type=ProviderType.BUILTIN,
            protocol=ApiProtocol.OPENAI,
            base_url="https://openrouter.ai/api/v1",
            enabled=True,
            default_capabilities=ModelCapabilities(requires_interleaved_thinking=False),
        )

        merged = service.get_merged_capabilities(model, provider)
        assert merged.requires_interleaved_thinking is True
        assert merged.reasoning is True
        assert merged.reasoning_controls is not None
        assert merged.reasoning_controls.mode.value == "enum"
        assert merged.reasoning_controls.options == ["minimal", "low", "medium", "high", "xhigh"]

    def test_get_merged_capabilities_hard_interleaved_rule_overrides_model_false(self, temp_config_dir):
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"
        with open(keys_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        model = Model(
            id="deepseek-chat",
            name="DeepSeek Chat",
            provider_id="openrouter",
            enabled=True,
            capabilities=ModelCapabilities(requires_interleaved_thinking=False),
        )
        provider = Provider(
            id="openrouter",
            name="OpenRouter",
            type=ProviderType.BUILTIN,
            protocol=ApiProtocol.OPENAI,
            base_url="https://openrouter.ai/api/v1",
            enabled=True,
            default_capabilities=ModelCapabilities(requires_interleaved_thinking=False),
        )

        merged = service.get_merged_capabilities(model, provider)
        assert merged.requires_interleaved_thinking is True

    def test_get_merged_capabilities_model_reasoning_override_wins_over_rules(self, temp_config_dir):
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"
        with open(keys_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        model = Model(
            id="deepseek-chat",
            name="DeepSeek Chat",
            provider_id="openrouter",
            enabled=True,
            capabilities=ModelCapabilities(reasoning=False),
        )
        provider = Provider(
            id="openrouter",
            name="OpenRouter",
            type=ProviderType.BUILTIN,
            protocol=ApiProtocol.OPENAI,
            base_url="https://openrouter.ai/api/v1",
            enabled=True,
            default_capabilities=ModelCapabilities(reasoning=False),
        )

        merged = service.get_merged_capabilities(model, provider)
        assert merged.reasoning is False

    def test_get_merged_capabilities_uses_provider_reasoning_controls_fallback(self, temp_config_dir):
        config_path = temp_config_dir / "models_config.yaml"
        keys_path = temp_config_dir / "keys_config.yaml"
        with open(keys_path, "w", encoding="utf-8") as f:
            yaml.safe_dump({"providers": {}}, f)

        service = ModelConfigService(config_path, keys_path)
        model = Model(id="gpt-5-mini", name="GPT", provider_id="openai", enabled=True)
        provider = Provider(
            id="openai",
            name="OpenAI",
            type=ProviderType.BUILTIN,
            protocol=ApiProtocol.OPENAI,
            base_url="https://api.openai.com/v1",
            enabled=True,
        )
        merged = service.get_merged_capabilities(model, provider)
        assert merged.reasoning_controls is not None
        assert merged.reasoning_controls.mode.value == "enum"
        assert merged.reasoning_controls.options == ["low", "medium", "high"]

    @pytest.mark.asyncio
    async def test_sync_builtin_sets_provider_interleaved_false_for_model_level_providers(self):
        test_dir = Path(".tmp") / "test_sync_builtin_sets_provider_interleaved_false_for_model_level_providers"
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        config_path = test_dir / "models_config.yaml"
        keys_path = test_dir / "keys_config.yaml"

        config_data = {
            "default": {"provider": "deepseek", "model": "deepseek-chat"},
            "providers": [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "type": "builtin",
                    "protocol": "openai",
                    "base_url": "https://api.deepseek.com",
                    "enabled": True,
                    "supports_model_list": True,
                    "sdk_class": "deepseek",
                    "default_capabilities": {
                        "requires_interleaved_thinking": True,
                    },
                },
                {
                    "id": "kimi",
                    "name": "Moonshot (Kimi)",
                    "type": "builtin",
                    "protocol": "openai",
                    "base_url": "https://api.moonshot.cn/v1",
                    "enabled": True,
                    "supports_model_list": True,
                    "sdk_class": "kimi",
                    "default_capabilities": {
                        "requires_interleaved_thinking": True,
                    },
                },
            ],
            "models": [
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek Chat",
                    "provider_id": "deepseek",
                    "tags": ["chat"],
                    "enabled": True,
                }
            ],
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f)
            with open(keys_path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"providers": {}}, f)

            service = ModelConfigService(config_path, keys_path)
            deepseek_provider = await service.get_provider("deepseek")
            kimi_provider = await service.get_provider("kimi")

            assert deepseek_provider is not None
            assert kimi_provider is not None
            assert deepseek_provider.default_capabilities.requires_interleaved_thinking is False
            assert kimi_provider.default_capabilities.requires_interleaved_thinking is False
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)

    @pytest.mark.asyncio
    async def test_sync_builtin_backfills_stale_model_interleaved_false(self):
        test_dir = Path(".tmp") / "test_sync_builtin_backfills_stale_model_interleaved_false"
        shutil.rmtree(test_dir, ignore_errors=True)
        test_dir.mkdir(parents=True, exist_ok=True)
        config_path = test_dir / "models_config.yaml"
        keys_path = test_dir / "keys_config.yaml"

        config_data = {
            "default": {"provider": "deepseek", "model": "deepseek-chat"},
            "providers": [
                {
                    "id": "deepseek",
                    "name": "DeepSeek",
                    "type": "builtin",
                    "protocol": "openai",
                    "base_url": "https://api.deepseek.com",
                    "enabled": True,
                    "supports_model_list": True,
                    "sdk_class": "deepseek",
                }
            ],
            "models": [
                {
                    "id": "deepseek-chat",
                    "name": "DeepSeek Chat",
                    "provider_id": "deepseek",
                    "tags": ["chat"],
                    "enabled": True,
                    "capabilities": {
                        "reasoning": True,
                        "requires_interleaved_thinking": False,
                    },
                }
            ],
        }

        try:
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(config_data, f)
            with open(keys_path, "w", encoding="utf-8") as f:
                yaml.safe_dump({"providers": {}}, f)

            service = ModelConfigService(config_path, keys_path)
            model = await service.get_model("deepseek-chat")
            assert model is not None
            assert model.capabilities is not None
            assert model.capabilities.requires_interleaved_thinking is True
        finally:
            shutil.rmtree(test_dir, ignore_errors=True)
