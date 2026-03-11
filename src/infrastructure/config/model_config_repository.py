"""Persistence helpers for model configuration data."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

import aiofiles
import yaml

from src.core.paths import ensure_local_file

if TYPE_CHECKING:
    from .model_config_service import ModelConfigService


class ModelConfigRepository:
    """Owns YAML I/O, split-config assembly, and key-file persistence."""

    def __init__(self, owner: "ModelConfigService"):
        self.owner = owner

    @staticmethod
    def load_yaml_dict(path: Path) -> dict[str, Any]:
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def write_yaml_dict(path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

    def split_config_paths_exist(self) -> bool:
        return (
            self.owner.provider_config_path.exists()
            and self.owner.models_catalog_path.exists()
            and self.owner.app_defaults_path.exists()
        )

    def assemble_aggregate_config(
        self,
        provider_data: dict[str, Any],
        catalog_data: dict[str, Any],
        app_data: dict[str, Any],
    ) -> dict[str, Any]:
        providers = provider_data.get("providers")
        models = catalog_data.get("models")
        default_config = app_data.get("default")
        reasoning_patterns = app_data.get("reasoning_supported_patterns")
        return {
            "providers": providers if isinstance(providers, list) else [],
            "models": models if isinstance(models, list) else [],
            "default": (
                {
                    "provider": str(default_config.get("provider") or "").strip(),
                    "model": str(default_config.get("model") or "").strip(),
                }
                if isinstance(default_config, dict)
                else {"provider": "", "model": ""}
            ),
            "reasoning_supported_patterns": reasoning_patterns if isinstance(reasoning_patterns, list) else [],
        }

    def load_split_config(self) -> dict[str, Any]:
        provider_data = self.load_yaml_dict(self.owner.provider_config_path)
        catalog_data = self.load_yaml_dict(self.owner.models_catalog_path)
        app_data = self.load_yaml_dict(self.owner.app_defaults_path)
        return self.assemble_aggregate_config(provider_data, catalog_data, app_data)

    def split_aggregate_config(
        self,
        data: dict[str, Any],
    ) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        providers = data.get("providers")
        models = data.get("models")
        default_config = data.get("default")
        reasoning_patterns = data.get("reasoning_supported_patterns")

        app_payload = {
            "default": (
                {
                    "provider": str(default_config.get("provider") or "").strip(),
                    "model": str(default_config.get("model") or "").strip(),
                }
                if isinstance(default_config, dict)
                else {"provider": "", "model": ""}
            ),
            "reasoning_supported_patterns": (
                reasoning_patterns
                if isinstance(reasoning_patterns, list)
                else self.owner._get_default_reasoning_supported_patterns()
            ),
        }
        return (
            {"providers": providers if isinstance(providers, list) else []},
            {"models": models if isinstance(models, list) else []},
            app_payload,
        )

    def ensure_config_exists(self) -> None:
        if self.split_config_paths_exist():
            return

        provider_defaults, catalog_defaults, app_defaults = self.split_aggregate_config(
            self.default_config()
        )

        if self.owner._layered_models:
            ensure_local_file(
                local_path=self.owner.provider_config_path,
                initial_text=yaml.safe_dump(provider_defaults, allow_unicode=True, sort_keys=False),
            )
            ensure_local_file(
                local_path=self.owner.models_catalog_path,
                initial_text=yaml.safe_dump(catalog_defaults, allow_unicode=True, sort_keys=False),
            )
            ensure_local_file(
                local_path=self.owner.app_defaults_path,
                initial_text=yaml.safe_dump(app_defaults, allow_unicode=True, sort_keys=False),
            )
            return

        self.write_yaml_dict(self.owner.provider_config_path, provider_defaults)
        self.write_yaml_dict(self.owner.models_catalog_path, catalog_defaults)
        self.write_yaml_dict(self.owner.app_defaults_path, app_defaults)

    def default_config(self) -> dict[str, Any]:
        return {
            "default": self.owner._empty_default_payload(),
            "providers": [],
            "models": [],
            "reasoning_supported_patterns": self.owner._get_default_reasoning_supported_patterns(),
        }

    def load_defaults_config(self) -> dict[str, Any]:
        if self.owner._defaults_config_cache is not None:
            return self.owner._defaults_config_cache

        if (
            self.owner.defaults_provider_path.exists()
            and self.owner.defaults_catalog_path.exists()
            and self.owner.defaults_app_path.exists()
        ):
            self.owner._defaults_config_cache = self.assemble_aggregate_config(
                self.load_yaml_dict(self.owner.defaults_provider_path),
                self.load_yaml_dict(self.owner.defaults_catalog_path),
                self.load_yaml_dict(self.owner.defaults_app_path),
            )
            return self.owner._defaults_config_cache

        self.owner._defaults_config_cache = {}
        return self.owner._defaults_config_cache

    def ensure_keys_config_exists(self) -> None:
        if self.owner.keys_path.exists():
            return
        default_keys = {"providers": {}}
        initial_text = yaml.safe_dump(default_keys, allow_unicode=True, sort_keys=False)

        if self.owner._layered_keys:
            shared_keys_path = self.owner._shared_keys_config_path()
            bootstrap_path = shared_keys_path if shared_keys_path.exists() else None
            ensure_local_file(
                local_path=self.owner.keys_path,
                defaults_path=bootstrap_path,
                initial_text=initial_text,
            )
            return

        if self.is_shared_keys_path(self.owner.keys_path):
            self.owner.logger.warning(
                "Refusing to create shared key file at %s; runtime writes must use config/local/keys_config.yaml",
                self.owner.keys_path,
            )
            return

        with open(self.owner.keys_path, "w", encoding="utf-8") as f:
            f.write(initial_text)

    async def load_keys_config(self) -> dict[str, Any]:
        if not self.owner.keys_path.exists():
            return {"providers": {}}
        async with aiofiles.open(self.owner.keys_path, "r", encoding="utf-8") as f:
            content = await f.read()
        data = yaml.safe_load(content)
        return data if data else {"providers": {}}

    async def save_keys_config(self, keys_data: dict[str, Any]) -> None:
        self.assert_keys_path_writable()

        temp_path = self.owner.keys_path.with_suffix(".yaml.tmp")
        async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
            content = yaml.safe_dump(keys_data, allow_unicode=True, sort_keys=False)
            await f.write(content)
        temp_path.replace(self.owner.keys_path)

    @staticmethod
    def same_path(path_a: Path, path_b: Path) -> bool:
        try:
            return path_a.expanduser().resolve() == path_b.expanduser().resolve()
        except Exception:
            return str(path_a.expanduser()) == str(path_b.expanduser())

    def is_shared_keys_path(self, path: Path) -> bool:
        return self.same_path(path, self.owner._shared_keys_config_path())

    def assert_keys_path_writable(self) -> None:
        if self.is_shared_keys_path(self.owner.keys_path):
            raise PermissionError(
                "Shared key file (~/.lex_mint/keys_config.yaml) is bootstrap-only. "
                "Runtime writes are allowed only in config/local/keys_config.yaml."
            )
