"""Code execution config service for dangerous server-side Python execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml

from src.core.paths import config_defaults_dir, config_local_dir, ensure_local_file
from src.infrastructure.config.yaml_config_utils import (
    load_layered_yaml_section,
    save_yaml_section_updates,
)

logger = logging.getLogger(__name__)


@dataclass
class CodeExecutionConfig:
    """Configuration for code execution behavior."""

    enable_server_side_tool_execution: bool = False


class CodeExecutionConfigService:
    """Load/save code execution config."""

    def __init__(self, config_path: str | None = None) -> None:
        self.defaults_path: Path | None = config_defaults_dir() / "code_execution_config.yaml"
        if config_path is None:
            self.config_path = config_local_dir() / "code_execution_config.yaml"
        else:
            self.config_path = Path(config_path)
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=self.defaults_path,
            initial_text=yaml.safe_dump(
                {"code_execution": {}}, allow_unicode=True, sort_keys=False
            ),
        )

    def _load_config(self) -> CodeExecutionConfig:
        default_config, config_data = load_layered_yaml_section(
            config_path=self.config_path,
            defaults_path=self.defaults_path,
            section_name="code_execution",
            logger=logger,
            error_label="code execution config",
        )
        return CodeExecutionConfig(
            enable_server_side_tool_execution=bool(
                config_data.get(
                    "enable_server_side_tool_execution",
                    default_config.get("enable_server_side_tool_execution", False),
                )
            )
        )

    def save_config(self, updates: dict[str, object]) -> None:
        save_yaml_section_updates(
            config_path=self.config_path,
            section_name="code_execution",
            updates=updates,
        )
        self.config = self._load_config()
