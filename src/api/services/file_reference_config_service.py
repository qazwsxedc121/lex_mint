"""File reference preview/injection configuration service."""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional
import logging

import yaml

from ..paths import (
    config_defaults_dir,
    config_local_dir,
    legacy_config_dir,
    ensure_local_file,
)

logger = logging.getLogger(__name__)


@dataclass
class FileReferenceConfig:
    """Configuration for @file context injection and UI preview."""

    ui_preview_max_chars: int = 1200
    ui_preview_max_lines: int = 28
    injection_preview_max_chars: int = 600
    injection_preview_max_lines: int = 40
    chunk_size: int = 2500
    max_chunks: int = 6
    total_budget_chars: int = 18000


class FileReferenceConfigService:
    """Load/save file reference config from layered config files."""

    def __init__(self, config_path: Optional[Path] = None):
        self.defaults_path: Optional[Path] = None
        self.legacy_paths: list[Path] = []

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "file_reference_config.yaml"
            self.config_path = config_local_dir() / "file_reference_config.yaml"
            self.legacy_paths = [legacy_config_dir() / "file_reference_config.yaml"]
        else:
            self.config_path = Path(config_path)

        self._ensure_config_exists()
        self.config = self._load_config()

    @staticmethod
    def _default_data() -> Dict:
        return {
            "file_reference": {
                "ui_preview_max_chars": 1200,
                "ui_preview_max_lines": 28,
                "injection_preview_max_chars": 600,
                "injection_preview_max_lines": 40,
                "chunk_size": 2500,
                "max_chunks": 6,
                "total_budget_chars": 18000,
            }
        }

    @staticmethod
    def _safe_int(value: object, fallback: int) -> int:
        try:
            parsed = int(value)  # type: ignore[arg-type]
        except Exception:
            return fallback
        return parsed if parsed > 0 else fallback

    def _ensure_config_exists(self) -> None:
        if self.config_path.exists():
            return

        initial_text = yaml.safe_dump(self._default_data(), allow_unicode=True, sort_keys=False)
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=self.defaults_path,
            legacy_paths=self.legacy_paths,
            initial_text=initial_text,
        )
        logger.info("Created file reference config at %s", self.config_path)

    def _load_config(self) -> FileReferenceConfig:
        self._ensure_config_exists()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            cfg = data.get("file_reference", {})
            defaults = FileReferenceConfig()
            return FileReferenceConfig(
                ui_preview_max_chars=self._safe_int(
                    cfg.get("ui_preview_max_chars"), defaults.ui_preview_max_chars
                ),
                ui_preview_max_lines=self._safe_int(
                    cfg.get("ui_preview_max_lines"), defaults.ui_preview_max_lines
                ),
                injection_preview_max_chars=self._safe_int(
                    cfg.get("injection_preview_max_chars"), defaults.injection_preview_max_chars
                ),
                injection_preview_max_lines=self._safe_int(
                    cfg.get("injection_preview_max_lines"), defaults.injection_preview_max_lines
                ),
                chunk_size=self._safe_int(cfg.get("chunk_size"), defaults.chunk_size),
                max_chunks=self._safe_int(cfg.get("max_chunks"), defaults.max_chunks),
                total_budget_chars=self._safe_int(
                    cfg.get("total_budget_chars"), defaults.total_budget_chars
                ),
            )
        except Exception as e:
            logger.warning("Failed to load file reference config: %s", e)
            return FileReferenceConfig()

    def reload_config(self) -> None:
        self.config = self._load_config()

    def save_config(self, updates: Dict) -> None:
        self._ensure_config_exists()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

        if "file_reference" not in data:
            data["file_reference"] = {}

        for key, value in updates.items():
            data["file_reference"][key] = value

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        self.config = self._load_config()

