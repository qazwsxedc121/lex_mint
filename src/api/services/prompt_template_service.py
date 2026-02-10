"""
Prompt template configuration management service
"""
import yaml
import aiofiles
from pathlib import Path
from typing import List, Optional

from ..models.prompt_template import PromptTemplate, PromptTemplatesConfig


class PromptTemplateConfigService:
    """Prompt template configuration management service."""

    def __init__(self, config_path: Path = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "prompt_templates_config.yaml"
        self.config_path = config_path
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Ensure configuration file exists, create default if not."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            default_config = self._get_default_config()
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

    def _get_default_config(self) -> dict:
        return {"templates": []}

    async def load_config(self) -> PromptTemplatesConfig:
        async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content) or {}
            if "templates" not in data:
                data["templates"] = []
            return PromptTemplatesConfig(**data)

    async def save_config(self, config: PromptTemplatesConfig):
        temp_path = self.config_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            content = yaml.safe_dump(
                config.model_dump(mode='json'),
                allow_unicode=True,
                sort_keys=False
            )
            await f.write(content)
        temp_path.replace(self.config_path)

    # ==================== Template Management ====================

    async def get_templates(self) -> List[PromptTemplate]:
        config = await self.load_config()
        return config.templates

    async def get_template(self, template_id: str) -> Optional[PromptTemplate]:
        config = await self.load_config()
        for template in config.templates:
            if template.id == template_id:
                return template
        return None

    async def add_template(self, template: PromptTemplate):
        config = await self.load_config()
        if any(t.id == template.id for t in config.templates):
            raise ValueError(f"Template with id '{template.id}' already exists")
        config.templates.append(template)
        await self.save_config(config)

    async def update_template(self, template_id: str, updated: PromptTemplate):
        config = await self.load_config()
        for i, template in enumerate(config.templates):
            if template.id == template_id:
                config.templates[i] = updated
                await self.save_config(config)
                return
        raise ValueError(f"Template with id '{template_id}' not found")

    async def delete_template(self, template_id: str):
        config = await self.load_config()
        original_count = len(config.templates)
        config.templates = [t for t in config.templates if t.id != template_id]
        if len(config.templates) == original_count:
            raise ValueError(f"Template with id '{template_id}' not found")
        await self.save_config(config)
