"""Unit tests for ModelConfigService."""

import pytest
import yaml
from pathlib import Path
from unittest.mock import patch, Mock

from src.api.services.model_config_service import ModelConfigService
from src.api.models.model_config import Provider, Model, ModelsConfig


class TestModelConfigService:
    """Test cases for ModelConfigService class."""

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
            type="builtin",
            protocol="openai",
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
            "id": "openai",
            "name": "OpenAI",
            "type": "builtin",
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
        await service.delete_provider("openai")

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
            group="chat",
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
            "group": "chat",
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
