"""
Path helpers for repository layout.

Layout (desired):
- config/defaults/: tracked default configs
- config/local/: instance-specific writable configs (gitignored)
- data/state/: instance/user state files (gitignored)
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Iterable, Optional


@lru_cache(maxsize=1)
def repo_root() -> Path:
    # This file lives at src/api/paths.py -> parents: api/ -> src/ -> repo root
    return Path(__file__).resolve().parents[2]


def config_defaults_dir() -> Path:
    return repo_root() / "config" / "defaults"


def config_local_dir() -> Path:
    return repo_root() / "config" / "local"


def local_keys_config_path() -> Path:
    return config_local_dir() / "keys_config.yaml"


def data_state_dir() -> Path:
    return repo_root() / "data" / "state"


def lex_mint_home_dir() -> Path:
    return Path.home() / ".lex_mint"


def shared_keys_config_path() -> Path:
    return lex_mint_home_dir() / "keys_config.yaml"


def legacy_config_dir() -> Path:
    # Backward compatible read-only location for older installs.
    return repo_root() / "config"


def first_existing(paths: Iterable[Path]) -> Optional[Path]:
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
    defaults_path: Optional[Path] = None,
    legacy_paths: Optional[list[Path]] = None,
    initial_text: Optional[str] = None,
) -> None:
    """
    Ensure a writable local file exists.

    Preference order for bootstrapping:
    1) First existing legacy path
    2) defaults_path
    3) initial_text
    """
    if local_path.exists():
        return

    ensure_dir(local_path.parent)

    bootstrap_sources: list[Path] = []
    if legacy_paths:
        bootstrap_sources.extend(legacy_paths)
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
    defaults_path: Optional[Path] = None,
    legacy_paths: Optional[list[Path]] = None,
) -> Path:
    """
    Pick an existing file to read, preferring local overrides.
    Falls back to legacy paths, then defaults.
    """
    candidates: list[Path] = [local_path]
    if legacy_paths:
        candidates.extend(legacy_paths)
    if defaults_path is not None:
        candidates.append(defaults_path)

    existing = first_existing(candidates)
    return existing or local_path
