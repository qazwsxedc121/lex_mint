"""
Follow-up Questions Service

Generates follow-up question suggestions after each chat response.
"""

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.core.paths import (
    config_defaults_dir,
    config_local_dir,
    ensure_local_file,
)
from src.infrastructure.config.model_config_service import ModelConfigService
from src.infrastructure.config.yaml_config_utils import (
    load_default_yaml_section,
    load_layered_yaml_section,
    save_yaml_section_updates,
)

logger = logging.getLogger(__name__)


def _response_content_to_text(content: object) -> str:
    """Normalize LangChain response content into plain text."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            elif isinstance(item, dict):
                text_value = item.get("text")
                if isinstance(text_value, str):
                    parts.append(text_value)
        return "".join(parts)
    return str(content or "")


@dataclass
class FollowupConfig:
    """Configuration for follow-up question generation"""

    enabled: bool
    count: int
    model_id: str
    max_context_rounds: int
    timeout_seconds: int
    prompt_template: str


class FollowupService:
    """Service for generating follow-up question suggestions"""

    def __init__(self, config_path: str | None = None):
        self.defaults_path: Path | None = config_defaults_dir() / "followup_config.yaml"

        if config_path is None:
            self.config_path = config_local_dir() / "followup_config.yaml"
        else:
            self.config_path = Path(config_path)

        ensure_local_file(
            local_path=self.config_path,
            defaults_path=self.defaults_path,
            initial_text=yaml.safe_dump({"followup": {}}, allow_unicode=True, sort_keys=False),
        )
        self.config = self._load_config()

    def _load_default_section(self) -> dict:
        """Load fallback defaults from the repo default config file."""
        return load_default_yaml_section(self.defaults_path, "followup")

    def _load_config(self) -> FollowupConfig:
        """Load configuration from YAML file"""
        default_config, config_data = load_layered_yaml_section(
            config_path=self.config_path,
            defaults_path=self.defaults_path,
            section_name="followup",
            logger=logger,
            error_label="followup config",
        )

        return FollowupConfig(
            enabled=config_data.get("enabled", default_config.get("enabled", True)),
            count=config_data.get("count", default_config.get("count", 3)),
            model_id=config_data.get("model_id", default_config.get("model_id", "")),
            max_context_rounds=config_data.get(
                "max_context_rounds",
                default_config.get("max_context_rounds", 3),
            ),
            timeout_seconds=config_data.get(
                "timeout_seconds",
                default_config.get("timeout_seconds", 15),
            ),
            prompt_template=config_data.get(
                "prompt_template",
                default_config.get("prompt_template", ""),
            ),
        )

    def reload_config(self):
        """Reload configuration from file"""
        self.config = self._load_config()

    def save_config(self, updates: dict):
        """Save updated configuration to file"""
        try:
            save_yaml_section_updates(
                config_path=self.config_path,
                section_name="followup",
                updates=updates,
            )
            self.reload_config()
            logger.info("Followup config updated successfully")
        except Exception as e:
            logger.error(f"Failed to save followup config: {e}")
            raise

    async def generate_followups_async(self, messages: list[dict]) -> list[str]:
        """
        Generate follow-up question suggestions asynchronously

        Args:
            messages: List of conversation messages

        Returns:
            List of follow-up questions
        """
        try:
            if not self.config.enabled or self.config.count <= 0:
                return []

            if not messages:
                logger.warning("[Followup] No messages provided")
                return []

            logger.info(f"[Followup] Starting follow-up generation with {len(messages)} messages")

            # Extract recent conversation rounds
            max_messages = self.config.max_context_rounds * 2  # user + assistant
            recent_messages = messages[-max_messages:]

            # Build conversation text
            conversation_lines = []
            for msg in recent_messages:
                role = msg.get("type", msg.get("role", "unknown"))
                content = msg.get("content", "")
                if role == "human":
                    conversation_lines.append(f"User: {content}")
                elif role in ("assistant", "ai"):
                    conversation_lines.append(f"Assistant: {content}")

            conversation_text = "\n".join(conversation_lines)

            # Build prompt
            prompt = self.config.prompt_template.format(
                count=self.config.count, conversation_text=conversation_text
            )

            # Initialize model
            model_config_service = ModelConfigService()
            model_instance = model_config_service.get_llm_instance(self.config.model_id)

            # Call model with timeout
            logger.info(f"[Followup] Calling model {self.config.model_id}")
            response = await asyncio.wait_for(
                model_instance.ainvoke(prompt), timeout=self.config.timeout_seconds
            )

            # Parse response into questions
            raw_text = _response_content_to_text(response.content).strip()
            questions = []

            for line in raw_text.split("\n"):
                line = line.strip()
                if not line:
                    continue
                # Remove common numbering patterns like "1.", "1)", "- ", "* "
                import re

                line = re.sub(r"^[\d]+[.\)]\s*", "", line)
                line = re.sub(r"^[-*]\s*", "", line)
                line = line.strip()
                if line:
                    questions.append(line)

            # Limit to configured count
            questions = questions[: self.config.count]

            logger.info(f"[Followup] Generated {len(questions)} follow-up questions")
            return questions

        except asyncio.TimeoutError:
            logger.error("[Followup] Timeout generating follow-up questions")
            return []
        except Exception as e:
            logger.error(f"[Followup] Failed to generate follow-up questions: {e}")
            return []
