"""
Path helpers for repository layout.

Layout (desired):
- config/defaults/: tracked default configs
- config/local/: instance-specific writable configs (gitignored)
- data/state/: instance/user state files (gitignored)
"""

from __future__ import annotations

import os
import re
import sys
from collections.abc import Iterable
from functools import lru_cache
from pathlib import Path

_WINDOWS_DRIVE_PATH_RE = re.compile(r"^[A-Za-z]:[\\/]")


@lru_cache(maxsize=1)
def source_repo_root() -> Path:
    """Return the source checkout root regardless of runtime overrides."""
    return Path(__file__).resolve().parents[2]


@lru_cache(maxsize=1)
def repo_root() -> Path:
    runtime_root = os.getenv("LEX_MINT_RUNTIME_ROOT", "").strip()
    if runtime_root:
        return Path(runtime_root).expanduser().resolve()

    if getattr(sys, "frozen", False):
        # PyInstaller/Nuitka runtime: place writable/runtime files next to the exe.
        return Path(sys.executable).resolve().parent

    return source_repo_root()


def is_packaged_runtime() -> bool:
    if os.getenv("LEX_MINT_PACKAGED", "").strip().lower() in {"1", "true", "yes", "on"}:
        return True
    return bool(getattr(sys, "frozen", False))


def lex_mint_home_dir() -> Path:
    return Path.home() / ".lex_mint"


def default_user_data_root() -> Path:
    local_appdata = os.getenv("LOCALAPPDATA", "").strip()
    if local_appdata:
        base_path = Path(local_appdata).expanduser()
        if os.name != "nt" and _WINDOWS_DRIVE_PATH_RE.match(local_appdata):
            return base_path / "LexMint"
        return base_path.resolve() / "LexMint"
    return lex_mint_home_dir() / "app"


@lru_cache(maxsize=1)
def user_data_root() -> Path:
    configured_root = os.getenv("LEX_MINT_USER_DATA_ROOT", "").strip()
    if configured_root:
        return Path(configured_root).expanduser().resolve()
    if is_packaged_runtime():
        return default_user_data_root()
    return repo_root()


def resolve_user_data_path(path: Path | str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate.expanduser().resolve()
    return user_data_root() / candidate


def configured_models_root() -> Path | None:
    configured_root = os.getenv("LEX_MINT_MODELS_ROOT", "").strip()
    if not configured_root:
        return None
    return Path(configured_root).expanduser().resolve()


def appdata_models_root() -> Path:
    return default_user_data_root() / "models"


def install_models_root() -> Path:
    return repo_root() / "models"


def _normalize_model_relative_path(path: Path | str) -> Path:
    candidate = Path(path)
    parts = candidate.parts
    if parts and parts[0].lower() == "models":
        trimmed = Path(*parts[1:]) if len(parts) > 1 else Path()
        return trimmed
    return candidate


def resolve_model_path(path: Path | str) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate.resolve()

    relative_candidate = _normalize_model_relative_path(candidate)
    search_roots: list[Path] = []
    configured_root = configured_models_root()
    if configured_root is not None:
        search_roots.append(configured_root)
    search_roots.append(appdata_models_root())
    search_roots.append(install_models_root())

    resolved_candidates = [root / relative_candidate for root in search_roots]
    existing = first_existing(resolved_candidates)
    if existing is not None:
        return existing
    return resolved_candidates[0]


def config_defaults_dir() -> Path:
    runtime_defaults_dir = repo_root() / "config" / "defaults"
    if runtime_defaults_dir.exists():
        return runtime_defaults_dir
    return source_repo_root() / "config" / "defaults"


def config_local_dir() -> Path:
    return user_data_root() / "config" / "local"


def local_keys_config_path() -> Path:
    return config_local_dir() / "keys_config.yaml"


def data_state_dir() -> Path:
    return user_data_root() / "data" / "state"


def knowledge_bases_dir() -> Path:
    return user_data_root() / "data" / "knowledge_bases"


def conversations_dir() -> Path:
    return user_data_root() / "conversations"


def attachments_dir() -> Path:
    return user_data_root() / "attachments"


def logs_dir() -> Path:
    return user_data_root() / "logs"


def shared_keys_config_path() -> Path:
    return lex_mint_home_dir() / "keys_config.yaml"


def first_existing(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        try:
            if path.exists():
                return path
        except OSError:
            continue
    return None


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def ensure_local_file(
    *,
    local_path: Path,
    defaults_path: Path | None = None,
    initial_text: str | None = None,
) -> None:
    """
    Ensure a writable local file exists.

    Preference order for bootstrapping:
    1) defaults_path
    2) initial_text
    """
    if local_path.exists():
        return

    ensure_dir(local_path.parent)

    bootstrap_sources: list[Path] = []
    if defaults_path is not None:
        bootstrap_sources.append(defaults_path)

    src = first_existing(bootstrap_sources)
    if src is not None:
        local_path.write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
        return

    if initial_text is None:
        initial_text = ""
    local_path.write_text(initial_text, encoding="utf-8")


def resolve_layered_read_path(
    *,
    local_path: Path,
    defaults_path: Path | None = None,
) -> Path:
    """
    Pick an existing file to read, preferring local overrides.
    Falls back to defaults.
    """
    candidates: list[Path] = [local_path]
    if defaults_path is not None:
        candidates.append(defaults_path)

    existing = first_existing(candidates)
    return existing or local_path
