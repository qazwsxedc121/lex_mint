"""
Assistant configuration management service

Handles loading, saving, and managing AI assistant configurations
"""
import yaml
import aiofiles
from pathlib import Path
from typing import List, Optional
from langchain_openai import ChatOpenAI

from ..models.assistant_config import Assistant, AssistantsConfig
from .model_config_service import ModelConfigService


class AssistantConfigService:
    """Assistant configuration management service"""

    def __init__(self, config_path: Path = None, model_service: ModelConfigService = None):
        """
        Initialize assistant configuration service

        Args:
            config_path: Configuration file path, defaults to project root assistants_config.yaml
            model_service: Model configuration service instance for validation
        """
        if config_path is None:
            # Default config file in project root
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "assistants_config.yaml"
        self.config_path = config_path
        self.model_service = model_service or ModelConfigService()
        self._ensure_config_exists()

    def _ensure_config_exists(self):
        """Ensure configuration file exists, create default if not"""
        if not self.config_path.exists():
            default_config = self._get_default_config()
            # Synchronous write for initial config
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

    def _get_default_config(self) -> dict:
        """Get default configuration"""
        return {
            "default": "general-assistant",
            "assistants": [
                {
                    "id": "general-assistant",
                    "name": "General Assistant",
                    "description": "General purpose conversational AI",
                    "model_id": "deepseek:deepseek-chat",
                    "system_prompt": "You are a helpful AI assistant. Provide clear, accurate, and friendly responses.",
                    "temperature": 0.7,
                    "max_tokens": 4000,
                    "enabled": True
                },
                {
                    "id": "code-assistant",
                    "name": "Code Assistant",
                    "description": "Specialized in programming and code analysis",
                    "model_id": "deepseek:deepseek-coder",
                    "system_prompt": "You are an expert programming assistant. Help users with code, debugging, and technical questions. Provide clear explanations and working code examples.",
                    "temperature": 0.3,
                    "max_tokens": 8000,
                    "enabled": True
                },
                {
                    "id": "creative-writer",
                    "name": "Creative Writer",
                    "description": "Creative writing and storytelling",
                    "model_id": "deepseek:deepseek-chat",
                    "system_prompt": "You are a creative writing assistant. Help users with storytelling, creative writing, and imaginative content. Be creative and engaging.",
                    "temperature": 0.9,
                    "max_tokens": 4000,
                    "enabled": True
                }
            ]
        }

    async def load_config(self) -> AssistantsConfig:
        """Load configuration file"""
        async with aiofiles.open(self.config_path, 'r', encoding='utf-8') as f:
            content = await f.read()
            data = yaml.safe_load(content)
            return AssistantsConfig(**data)

    async def save_config(self, config: AssistantsConfig):
        """
        Save configuration file (atomic write)

        Uses temporary file + replace for atomicity
        """
        # Write to temporary file first
        temp_path = self.config_path.with_suffix('.yaml.tmp')
        async with aiofiles.open(temp_path, 'w', encoding='utf-8') as f:
            content = yaml.safe_dump(
                config.model_dump(),
                allow_unicode=True,
                sort_keys=False
            )
            await f.write(content)

        # Atomic replace
        temp_path.replace(self.config_path)

    # ==================== Assistant Management ====================

    async def get_assistants(self) -> List[Assistant]:
        """Get all assistants"""
        config = await self.load_config()
        return config.assistants

    async def get_assistant(self, assistant_id: str) -> Optional[Assistant]:
        """
        Get specified assistant

        Args:
            assistant_id: Assistant ID

        Returns:
            Assistant object or None if not found
        """
        config = await self.load_config()
        for assistant in config.assistants:
            if assistant.id == assistant_id:
                return assistant
        return None

    async def add_assistant(self, assistant: Assistant):
        """
        Add assistant

        Raises:
            ValueError: If assistant ID already exists or model_id is invalid
        """
        config = await self.load_config()

        # Check if ID already exists
        if any(a.id == assistant.id for a in config.assistants):
            raise ValueError(f"Assistant with id '{assistant.id}' already exists")

        # Validate model_id exists
        model = await self.model_service.get_model(assistant.model_id)
        if not model:
            raise ValueError(f"Model with id '{assistant.model_id}' not found")

        config.assistants.append(assistant)
        await self.save_config(config)

    async def update_assistant(self, assistant_id: str, updated: Assistant):
        """
        Update assistant

        Raises:
            ValueError: If assistant not found or model_id is invalid
        """
        config = await self.load_config()

        # Validate model_id if provided
        if updated.model_id:
            model = await self.model_service.get_model(updated.model_id)
            if not model:
                raise ValueError(f"Model with id '{updated.model_id}' not found")

        for i, assistant in enumerate(config.assistants):
            if assistant.id == assistant_id:
                config.assistants[i] = updated
                await self.save_config(config)
                return

        raise ValueError(f"Assistant with id '{assistant_id}' not found")

    async def delete_assistant(self, assistant_id: str):
        """
        Delete assistant

        Raises:
            ValueError: If assistant not found or is default assistant
        """
        config = await self.load_config()

        # Check if it's the default assistant
        if config.default == assistant_id:
            raise ValueError(f"Cannot delete default assistant '{assistant_id}'")

        original_count = len(config.assistants)
        config.assistants = [a for a in config.assistants if a.id != assistant_id]

        if len(config.assistants) == original_count:
            raise ValueError(f"Assistant with id '{assistant_id}' not found")

        await self.save_config(config)

    # ==================== Default Assistant ====================

    async def get_default_assistant_id(self) -> str:
        """Get default assistant ID"""
        config = await self.load_config()
        return config.default

    async def get_default_assistant(self) -> Assistant:
        """
        Get default assistant

        Raises:
            ValueError: If default assistant not found
        """
        config = await self.load_config()
        assistant = await self.get_assistant(config.default)
        if not assistant:
            raise ValueError(f"Default assistant '{config.default}' not found")
        return assistant

    async def set_default_assistant(self, assistant_id: str):
        """
        Set default assistant

        Raises:
            ValueError: If assistant not found
        """
        config = await self.load_config()

        # Verify assistant exists
        if not any(a.id == assistant_id for a in config.assistants):
            raise ValueError(f"Assistant with id '{assistant_id}' not found")

        config.default = assistant_id
        await self.save_config(config)

    # ==================== LLM Creation ====================

    async def get_effective_temperature(self, assistant: Assistant) -> float:
        """
        Get effective temperature for assistant

        Returns assistant's temperature if set, otherwise model's default temperature

        Args:
            assistant: Assistant object

        Returns:
            Effective temperature value
        """
        if assistant.temperature is not None:
            return assistant.temperature

        # Fallback to model's default temperature
        model = await self.model_service.get_model(assistant.model_id)
        if model:
            return model.temperature

        # Last resort default
        return 0.7

    async def create_llm_from_assistant(self, assistant_id: str) -> tuple[ChatOpenAI, Optional[str], Optional[int]]:
        """
        Create LLM instance from assistant configuration

        Args:
            assistant_id: Assistant ID

        Returns:
            Tuple of (ChatOpenAI instance, system_prompt, max_tokens)

        Raises:
            ValueError: If assistant not found or configuration invalid
        """
        assistant = await self.get_assistant(assistant_id)
        if not assistant:
            raise ValueError(f"Assistant with id '{assistant_id}' not found")

        # Get effective temperature
        temperature = await self.get_effective_temperature(assistant)

        # Create LLM instance using model service (with overridden temperature)
        # First get the base LLM instance
        llm = self.model_service.get_llm_instance(assistant.model_id)

        # Override temperature
        llm.temperature = temperature

        return llm, assistant.system_prompt, assistant.max_tokens

    async def create_ephemeral_assistant_from_model(self, model_id: str) -> Assistant:
        """
        Create ephemeral assistant from model ID (for backward compatibility)

        Args:
            model_id: Model ID (composite format)

        Returns:
            Ephemeral Assistant object (not persisted)

        Raises:
            ValueError: If model not found
        """
        model = await self.model_service.get_model(model_id)
        if not model:
            raise ValueError(f"Model with id '{model_id}' not found")

        return Assistant(
            id=f"ephemeral-{model_id.replace(':', '-')}",
            name=f"Legacy: {model.name}",
            description="Temporary assistant for backward compatibility",
            model_id=model_id,
            system_prompt=None,
            temperature=model.temperature,
            max_tokens=None,
            enabled=True
        )
