"""Unit tests for AssistantConfigService empty-config behavior."""

from unittest.mock import AsyncMock, Mock

import pytest

from src.domain.models.assistant_config import Assistant
from src.infrastructure.config.assistant_config_service import AssistantConfigService


class TestAssistantConfigService:
    @pytest.mark.asyncio
    async def test_bootstraps_empty_config(self, temp_config_dir):
        config_path = temp_config_dir / "assistants_config.yaml"
        service = AssistantConfigService(config_path=config_path)

        config = await service.load_config()

        assert config.default == ""
        assert config.assistants == []

    @pytest.mark.asyncio
    async def test_get_default_assistant_without_configured_default_raises_clear_error(
        self, temp_config_dir
    ):
        config_path = temp_config_dir / "assistants_config.yaml"
        service = AssistantConfigService(config_path=config_path)

        with pytest.raises(ValueError, match="No default assistant configured"):
            await service.get_default_assistant()

    @pytest.mark.asyncio
    async def test_delete_default_assistant_clears_default(self, temp_config_dir):
        config_path = temp_config_dir / "assistants_config.yaml"
        service = AssistantConfigService(config_path=config_path)
        config = await service.load_config()
        config.default = "writer"
        config.assistants = [
            Assistant(
                id="writer",
                name="Writer",
                model_id="deepseek:deepseek-chat",
                enabled=True,
            )
        ]
        await service.save_config(config)

        await service.delete_assistant("writer")

        updated = await service.load_config()
        assert updated.default == ""
        assert updated.assistants == []

    @pytest.mark.asyncio
    async def test_get_assistants_enabled_only_filters_disabled_and_unavailable_bindings(
        self, temp_config_dir
    ):
        config_path = temp_config_dir / "assistants_config.yaml"
        model_service = Mock()

        async def _require_enabled_model(model_id=None):
            if model_id == "deepseek:deepseek-chat":
                return Mock(id="deepseek-chat", provider_id="deepseek"), Mock(
                    id="deepseek", enabled=True
                )
            raise ValueError(f"Model '{model_id}' is disabled")

        model_service.require_enabled_model = AsyncMock(side_effect=_require_enabled_model)
        service = AssistantConfigService(config_path=config_path, model_service=model_service)
        config = await service.load_config()
        config.assistants = [
            Assistant(id="ready", name="Ready", model_id="deepseek:deepseek-chat", enabled=True),
            Assistant(
                id="disabled", name="Disabled", model_id="deepseek:deepseek-chat", enabled=False
            ),
            Assistant(id="broken", name="Broken", model_id="openai:gpt-4", enabled=True),
        ]
        await service.save_config(config)

        enabled_assistants = await service.get_assistants(enabled_only=True)

        assert [assistant.id for assistant in enabled_assistants] == ["ready"]

    @pytest.mark.asyncio
    async def test_set_default_assistant_rejects_disabled_assistant(self, temp_config_dir):
        config_path = temp_config_dir / "assistants_config.yaml"
        model_service = Mock()
        model_service.require_enabled_model = AsyncMock()
        service = AssistantConfigService(config_path=config_path, model_service=model_service)
        config = await service.load_config()
        config.assistants = [
            Assistant(id="writer", name="Writer", model_id="deepseek:deepseek-chat", enabled=False),
        ]
        await service.save_config(config)

        with pytest.raises(ValueError, match="Assistant 'writer' is disabled"):
            await service.set_default_assistant("writer")

    @pytest.mark.asyncio
    async def test_get_default_assistant_rejects_unavailable_model_binding(self, temp_config_dir):
        config_path = temp_config_dir / "assistants_config.yaml"
        model_service = Mock()
        model_service.require_enabled_model = AsyncMock(
            side_effect=ValueError("Model 'openai:gpt-4' is disabled")
        )
        service = AssistantConfigService(config_path=config_path, model_service=model_service)
        config = await service.load_config()
        config.default = "writer"
        config.assistants = [
            Assistant(id="writer", name="Writer", model_id="openai:gpt-4", enabled=True),
        ]
        await service.save_config(config)

        with pytest.raises(ValueError, match="Default assistant 'writer' is unavailable"):
            await service.get_default_assistant()
