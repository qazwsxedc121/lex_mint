"""Code execution config service for dangerous server-side Python execution."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
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

    enable_client_tool_execution: bool = True
    enable_server_jupyter_execution: bool = False
    enable_server_subprocess_execution: bool = False
    execution_priority: list[str] = field(
        default_factory=lambda: ["client", "server_jupyter", "server_subprocess"]
    )
    jupyter_kernel_name: str = "python3"


_ALLOWED_EXECUTION_METHODS = ("client", "server_jupyter", "server_subprocess")


def _normalize_execution_priority(value: object) -> list[str]:
    if not isinstance(value, list):
        value = []
    seen: set[str] = set()
    ordered: list[str] = []
    for item in value:
        method = str(item or "").strip()
        if method in _ALLOWED_EXECUTION_METHODS and method not in seen:
            ordered.append(method)
            seen.add(method)
    for method in _ALLOWED_EXECUTION_METHODS:
        if method not in seen:
            ordered.append(method)
    return ordered


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
        merged_data = {**default_config, **config_data}
        legacy_enable_server = bool(merged_data.get("enable_server_side_tool_execution", False))
        legacy_backend = str(merged_data.get("server_side_execution_backend", "subprocess")).strip()
        legacy_kernel_name = (
            str(merged_data.get("jupyter_kernel_name", "python3")).strip() or "python3"
        )
        enable_client_tool_execution = bool(merged_data.get("enable_client_tool_execution", True))
        enable_server_jupyter_execution = bool(
            merged_data.get(
                "enable_server_jupyter_execution",
                legacy_enable_server and legacy_backend == "jupyter",
            )
        )
        enable_server_subprocess_execution = bool(
            merged_data.get(
                "enable_server_subprocess_execution",
                legacy_enable_server and legacy_backend != "jupyter",
            )
        )
        execution_priority = _normalize_execution_priority(
            merged_data.get("execution_priority", default_config.get("execution_priority", []))
        )
        return CodeExecutionConfig(
            enable_client_tool_execution=enable_client_tool_execution,
            enable_server_jupyter_execution=enable_server_jupyter_execution,
            enable_server_subprocess_execution=enable_server_subprocess_execution,
            execution_priority=execution_priority,
            jupyter_kernel_name=legacy_kernel_name,
        )

    def save_config(self, updates: dict[str, object]) -> None:
        save_yaml_section_updates(
            config_path=self.config_path,
            section_name="code_execution",
            updates=updates,
        )
        self.config = self._load_config()
