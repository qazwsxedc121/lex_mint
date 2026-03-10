"""Unit tests for group runtime support service."""

from types import SimpleNamespace

import pytest

from src.api.services.group_runtime_support_service import GroupRuntimeSupportService


@pytest.mark.asyncio
async def test_build_group_runtime_assistant_returns_none_for_invalid_token():
    service = GroupRuntimeSupportService()

    result = await service.build_group_runtime_assistant("")

    assert result is None


@pytest.mark.asyncio
async def test_build_group_runtime_assistant_resolves_assistant(monkeypatch):
    import src.infrastructure.config.assistant_config_service as assistant_config_service

    class _FakeAssistantService:
        async def require_enabled_assistant(self, assistant_id):
            assert assistant_id == "assistant-1"
            return SimpleNamespace(
                id="assistant-1",
                name="Assistant One",
                model_id="provider:model-a",
                system_prompt=None,
                temperature=0.2,
                max_tokens=100,
                top_p=None,
                top_k=None,
                frequency_penalty=None,
                presence_penalty=None,
                max_rounds=None,
                memory_enabled=True,
                knowledge_base_ids=[],
                enabled=True,
            )

    monkeypatch.setattr(assistant_config_service, "AssistantConfigService", _FakeAssistantService)
    service = GroupRuntimeSupportService()

    participant_id, assistant_obj, assistant_name = await service.build_group_runtime_assistant("assistant-1")

    assert participant_id == "assistant-1"
    assert assistant_name == "Assistant One"
    assert assistant_obj.model_id == "provider:model-a"


@pytest.mark.asyncio
async def test_build_group_runtime_assistant_resolves_model_token(monkeypatch):
    import src.infrastructure.config.model_config_service as model_config_service

    class _FakeModelService:
        async def require_enabled_model(self, model_id):
            assert model_id == "provider:model-a"
            return SimpleNamespace(
                provider_id="provider",
                id="model-a",
                name="Model A",
                chat_template={
                    "temperature": 0.3,
                    "max_tokens": 200,
                },
            ), SimpleNamespace()

    monkeypatch.setattr(model_config_service, "ModelConfigService", _FakeModelService)
    service = GroupRuntimeSupportService()

    participant_id, assistant_obj, assistant_name = await service.build_group_runtime_assistant(
        "model::provider:model-a"
    )

    assert participant_id == "model::provider:model-a"
    assert assistant_name == "Model A"
    assert assistant_obj.model_id == "provider:model-a"
    assert assistant_obj.temperature == 0.3
    assert assistant_obj.max_tokens == 200


def test_resolve_group_settings_defaults_to_round_robin():
    service = GroupRuntimeSupportService()

    settings = service.resolve_group_settings(
        group_mode=None,
        group_assistants=["assistant-1", "assistant-2"],
        group_settings=None,
        assistant_config_map={},
    )

    assert settings.group_mode == "round_robin"
    assert settings.group_assistants == ["assistant-1", "assistant-2"]
