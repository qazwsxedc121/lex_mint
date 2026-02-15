"""Unit tests for prompt template schema and service behavior."""

from pathlib import Path

import pytest
import yaml
from pydantic import ValidationError

from src.api.models.prompt_template import PromptTemplate, PromptTemplateVariable
from src.api.services.prompt_template_service import PromptTemplateConfigService


def test_prompt_template_variable_rejects_reserved_key():
    with pytest.raises(ValidationError, match="reserved"):
        PromptTemplateVariable(key="cursor", type="text")


def test_prompt_template_rejects_duplicate_variable_keys():
    with pytest.raises(ValidationError, match="Duplicate variable key"):
        PromptTemplate(
            id="dup-var",
            name="dup-var",
            content="hello {{topic}}",
            enabled=True,
            variables=[
                PromptTemplateVariable(key="topic", type="text"),
                PromptTemplateVariable(key="topic", type="text"),
            ],
        )


def test_prompt_template_rejects_invalid_select_default():
    with pytest.raises(ValidationError, match="must be one of the options"):
        PromptTemplateVariable(
            key="tone",
            type="select",
            options=["formal", "casual"],
            default="friendly",
        )


@pytest.mark.asyncio
async def test_prompt_template_service_loads_legacy_templates_without_variables(temp_config_dir):
    config_path = Path(temp_config_dir) / "prompt_templates_config.yaml"
    legacy_data = {
        "templates": [
            {
                "id": "legacy-1",
                "name": "legacy",
                "description": None,
                "content": "legacy content",
                "enabled": True,
            }
        ]
    }
    config_path.write_text(yaml.safe_dump(legacy_data), encoding="utf-8")

    service = PromptTemplateConfigService(config_path=config_path)
    templates = await service.get_templates()

    assert len(templates) == 1
    assert templates[0].id == "legacy-1"
    assert templates[0].variables == []


@pytest.mark.asyncio
async def test_prompt_template_service_persists_variable_schema(temp_config_dir):
    config_path = Path(temp_config_dir) / "prompt_templates_config.yaml"
    service = PromptTemplateConfigService(config_path=config_path)

    template = PromptTemplate(
        id="typed-vars",
        name="typed-vars",
        description="template with schema",
        content="Write about {{topic}} in {{language}}.",
        enabled=True,
        variables=[
            PromptTemplateVariable(
                key="topic",
                label="Topic",
                type="text",
                required=True,
            ),
            PromptTemplateVariable(
                key="language",
                type="select",
                options=["English", "Chinese"],
                default="English",
            ),
        ],
    )

    await service.add_template(template)
    loaded = await service.get_template("typed-vars")

    assert loaded is not None
    assert len(loaded.variables) == 2
    assert loaded.variables[0].key == "topic"
    assert loaded.variables[1].type == "select"
    assert loaded.variables[1].options == ["English", "Chinese"]
    assert loaded.variables[1].default == "English"
