"""
Remove stale disabled builtin-seeded models from models_config.yaml.

Policy:
- Keep default model.
- Keep enabled models.
- Remove disabled models only when they match builtin curated model IDs.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

# Ensure "src" imports resolve when running as a script from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.paths import config_local_dir


LEGACY_BUILTIN_MODEL_IDS: dict[str, set[str]] = {
    "deepseek": {"deepseek-chat", "deepseek-reasoner"},
    "zhipu": {
        "glm-5",
        "glm-4.7",
        "glm-4.6",
        "glm-4.6-flash",
        "glm-4.6v",
        "glm-4.5",
        "glm-4.5-air",
        "glm-4.5-flash",
        "glm-z1-air",
        "glm-z1-airx",
    },
    "gemini": {
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.0-flash",
        "gemini-1.5-pro",
        "gemini-1.5-flash",
    },
    "volcengine": {
        "doubao-seed-2-0-pro-260215",
        "doubao-seed-2-0-lite-260215",
        "doubao-seed-2-0-mini-260215",
        "doubao-seed-2-0-code-preview-260215",
        "doubao-1-5-pro-256k-250115",
        "doubao-1-5-pro-32k-250115",
    },
    "openai": {"gpt-4-turbo", "gpt-4o", "gpt-4o-mini", "o1", "o1-mini"},
    "anthropic": {
        "claude-sonnet-4-5-20250929",
        "claude-opus-4-5-20251101",
        "claude-sonnet-4-20250514",
        "claude-haiku-4-5-20250630",
        "claude-3-5-sonnet-20241022",
    },
    "xai": {"grok-4", "grok-4-fast", "grok-3", "grok-3-mini"},
    "bailian": {
        "qwen3-max",
        "qwen-max",
        "qwen3-coder-plus",
        "qvq-plus",
        "qwen-plus",
        "qwen-turbo",
        "qwen-long",
        "qwen3-vl-plus",
        "qwen3-vl-flash",
    },
}


def _load_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError("Invalid config format: root must be a mapping")
    return data


def _build_seeded_ids() -> dict[str, set[str]]:
    return {
        provider_id: set(model_ids)
        for provider_id, model_ids in LEGACY_BUILTIN_MODEL_IDS.items()
    }


def cleanup_models(data: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    providers = data.get("providers") or []
    models = data.get("models") or []
    default_cfg = data.get("default") or {}
    default_key = (default_cfg.get("provider"), default_cfg.get("model"))

    if not isinstance(providers, list) or not isinstance(models, list):
        raise ValueError("Invalid config format: providers/models must be lists")

    provider_type_map = {}
    for item in providers:
        if isinstance(item, dict) and item.get("id"):
            provider_type_map[str(item["id"])] = str(item.get("type", "")).lower()

    seeded_ids = _build_seeded_ids()
    removed_by_provider: dict[str, int] = defaultdict(int)
    kept: list[dict[str, Any]] = []

    for item in models:
        if not isinstance(item, dict):
            kept.append(item)
            continue

        provider_id = str(item.get("provider_id", ""))
        model_id = str(item.get("id", ""))
        enabled = bool(item.get("enabled", False))
        key = (provider_id, model_id)

        is_builtin_provider = provider_type_map.get(provider_id) == "builtin"
        is_seeded = model_id in seeded_ids.get(provider_id, set())

        if key == default_key or enabled or not (is_builtin_provider and is_seeded):
            kept.append(item)
            continue

        removed_by_provider[provider_id] += 1

    cleaned = dict(data)
    cleaned["models"] = kept
    return cleaned, dict(removed_by_provider)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Clean disabled builtin-seeded models from models config."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=config_local_dir() / "models_config.yaml",
        help="Path to models_config.yaml",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show changes without writing file",
    )
    args = parser.parse_args()

    config_path: Path = args.config
    data = _load_yaml(config_path)
    before_count = len(data.get("models") or [])
    cleaned, removed_by_provider = cleanup_models(data)
    after_count = len(cleaned.get("models") or [])
    removed_total = before_count - after_count

    if removed_total <= 0:
        print("No stale builtin-seeded disabled models to remove.")
        return 0

    print(f"Will remove {removed_total} model entries.")
    for provider_id in sorted(removed_by_provider):
        print(f"- {provider_id}: {removed_by_provider[provider_id]}")

    if args.dry_run:
        print("Dry run only. No files were changed.")
        return 0

    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    backup_path = config_path.with_suffix(f".yaml.bak.{timestamp}")
    shutil.copy2(config_path, backup_path)

    with config_path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(cleaned, f, allow_unicode=True, sort_keys=False)

    print(f"Backup created: {backup_path}")
    print(f"Updated: {config_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
