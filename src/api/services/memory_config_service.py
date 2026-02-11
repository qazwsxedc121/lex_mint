"""Memory configuration service.

Stores runtime-configurable settings for global/assistant memory built on ChromaDB.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional

import yaml

from ..paths import data_state_dir, legacy_config_dir, ensure_local_file

logger = logging.getLogger(__name__)


@dataclass
class MemoryRetrievalConfig:
    top_k: int = 8
    score_threshold: float = 0.35
    max_injected_items: int = 6
    max_item_length: int = 220


@dataclass
class MemoryExtractionConfig:
    enabled: bool = True
    min_text_length: int = 8
    max_items_per_turn: int = 3


@dataclass
class MemoryScopeConfig:
    global_enabled: bool = True
    assistant_enabled: bool = True


@dataclass
class MemoryConfig:
    enabled: bool = False
    profile_id: str = "local-default"
    collection_name: str = "memory_main"
    enabled_layers: List[str] = field(default_factory=lambda: ["fact", "instruction"])
    retrieval: MemoryRetrievalConfig = field(default_factory=MemoryRetrievalConfig)
    extraction: MemoryExtractionConfig = field(default_factory=MemoryExtractionConfig)
    scopes: MemoryScopeConfig = field(default_factory=MemoryScopeConfig)


class MemoryConfigService:
    """Service for loading and updating memory settings."""

    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            path = data_state_dir() / "memory_config.yaml"
        else:
            path = Path(config_path)

        self.config_path = path
        self._ensure_config_exists()
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        if self.config_path.exists():
            return

        default_data = {
            "memory": {
                "enabled": False,
                "profile_id": "local-default",
                "collection_name": "memory_main",
                "enabled_layers": ["fact", "instruction"],
                "retrieval": {
                    "top_k": 8,
                    "score_threshold": 0.35,
                    "max_injected_items": 6,
                    "max_item_length": 220,
                },
                "extraction": {
                    "enabled": True,
                    "min_text_length": 8,
                    "max_items_per_turn": 3,
                },
                "scopes": {
                    "global_enabled": True,
                    "assistant_enabled": True,
                },
            }
        }
        initial_text = yaml.safe_dump(default_data, allow_unicode=True, sort_keys=False)
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=None,
            legacy_paths=[legacy_config_dir() / "memory_config.yaml"],
            initial_text=initial_text,
        )
        logger.info("Created default memory config at %s", self.config_path)

    def _load_config(self) -> MemoryConfig:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            memory_data = data.get("memory", {}) or {}
            retrieval = memory_data.get("retrieval", {}) or {}
            extraction = memory_data.get("extraction", {}) or {}
            scopes = memory_data.get("scopes", {}) or {}

            return MemoryConfig(
                enabled=bool(memory_data.get("enabled", False)),
                profile_id=memory_data.get("profile_id", "local-default"),
                collection_name=memory_data.get("collection_name", "memory_main"),
                enabled_layers=list(memory_data.get("enabled_layers", ["fact", "instruction"])),
                retrieval=MemoryRetrievalConfig(
                    top_k=int(retrieval.get("top_k", 8)),
                    score_threshold=float(retrieval.get("score_threshold", 0.35)),
                    max_injected_items=int(retrieval.get("max_injected_items", 6)),
                    max_item_length=int(retrieval.get("max_item_length", 220)),
                ),
                extraction=MemoryExtractionConfig(
                    enabled=bool(extraction.get("enabled", True)),
                    min_text_length=int(extraction.get("min_text_length", 8)),
                    max_items_per_turn=int(extraction.get("max_items_per_turn", 3)),
                ),
                scopes=MemoryScopeConfig(
                    global_enabled=bool(scopes.get("global_enabled", True)),
                    assistant_enabled=bool(scopes.get("assistant_enabled", True)),
                ),
            )
        except Exception as e:
            logger.error("Failed to load memory config: %s", e)
            return MemoryConfig()

    def reload_config(self) -> None:
        self.config = self._load_config()

    def save_config(self, updates: Dict) -> None:
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}

            if "memory" not in data:
                data["memory"] = {}

            for key, value in updates.items():
                if value is None:
                    continue

                if key in ("retrieval", "extraction", "scopes") and isinstance(value, dict):
                    if key not in data["memory"] or not isinstance(data["memory"].get(key), dict):
                        data["memory"][key] = {}
                    for sub_key, sub_value in value.items():
                        if sub_value is not None:
                            data["memory"][key][sub_key] = sub_value
                else:
                    data["memory"][key] = value

            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

            self.reload_config()
            logger.info("Memory config updated successfully")
        except Exception as e:
            logger.error("Failed to save memory config: %s", e)
            raise

    def get_flat_config(self) -> Dict:
        cfg = self.config
        return {
            "enabled": cfg.enabled,
            "profile_id": cfg.profile_id,
            "collection_name": cfg.collection_name,
            "enabled_layers": cfg.enabled_layers,
            "top_k": cfg.retrieval.top_k,
            "score_threshold": cfg.retrieval.score_threshold,
            "max_injected_items": cfg.retrieval.max_injected_items,
            "max_item_length": cfg.retrieval.max_item_length,
            "auto_extract_enabled": cfg.extraction.enabled,
            "min_text_length": cfg.extraction.min_text_length,
            "max_items_per_turn": cfg.extraction.max_items_per_turn,
            "global_enabled": cfg.scopes.global_enabled,
            "assistant_enabled": cfg.scopes.assistant_enabled,
        }

    def save_flat_config(self, flat_updates: Dict) -> None:
        nested: Dict[str, Dict] = {}
        mapping = {
            "enabled": (None, "enabled"),
            "profile_id": (None, "profile_id"),
            "collection_name": (None, "collection_name"),
            "enabled_layers": (None, "enabled_layers"),
            "top_k": ("retrieval", "top_k"),
            "score_threshold": ("retrieval", "score_threshold"),
            "max_injected_items": ("retrieval", "max_injected_items"),
            "max_item_length": ("retrieval", "max_item_length"),
            "auto_extract_enabled": ("extraction", "enabled"),
            "min_text_length": ("extraction", "min_text_length"),
            "max_items_per_turn": ("extraction", "max_items_per_turn"),
            "global_enabled": ("scopes", "global_enabled"),
            "assistant_enabled": ("scopes", "assistant_enabled"),
        }

        for key, value in flat_updates.items():
            if key not in mapping or value is None:
                continue

            section, section_key = mapping[key]
            if section is None:
                nested[section_key] = value
                continue

            if section not in nested:
                nested[section] = {}
            nested[section][section_key] = value

        if nested:
            self.save_config(nested)
