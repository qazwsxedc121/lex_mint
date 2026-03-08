"""Unit tests for AssistantConfigService empty-config behavior."""

import pytest

from src.api.models.assistant_config import Assistant
from src.api.services.assistant_config_service import AssistantConfigService


class TestAssistantConfigService:
    @pytest.mark.asyncio
    async def test_bootstraps_empty_config(self, temp_config_dir):
        config_path = temp_config_dir / "assistants_config.yaml"
        service = AssistantConfigService(config_path=config_path)

        config = await service.load_config()

        assert config.default == ""
        assert config.assistants == []

    @pytest.mark.asyncio
    async def test_get_default_assistant_without_configured_default_raises_clear_error(self, temp_config_dir):
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
