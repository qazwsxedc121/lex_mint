"""One-time migration: move project conversations to .lex_mint in project directories.

Migrates conversation files from the old layout:
    conversations/projects/{project_id}/*.md

To the new layout:
    {project_root_path}/.lex_mint/conversations/*.md
"""

import logging
import shutil
from pathlib import Path

import yaml

from src.core.config import settings

logger = logging.getLogger(__name__)


def _load_project_root_map() -> dict[str, str]:
    config_path = settings.projects_config_path
    if not config_path.exists():
        return {}

    try:
        with open(config_path, encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except Exception as e:
        logger.warning("Failed to read projects config for migration: %s", e)
        return {}

    project_map: dict[str, str] = {}
    for proj in (data or {}).get("projects", []):
        pid = proj.get("id")
        root = proj.get("root_path")
        if pid and root:
            project_map[pid] = root
    return project_map


def _cleanup_empty_dir(path: Path) -> None:
    try:
        if path.exists() and not any(path.iterdir()):
            path.rmdir()
    except OSError:
        pass


def _iter_project_files(project_dir: Path) -> list[Path]:
    return list(project_dir.glob("*.md")) + list(project_dir.glob("*.compare.json"))


def _resolve_target_dir(
    project_id: str, project_map: dict[str, str], result: dict[str, int]
) -> Path | None:
    root_path = project_map.get(project_id)
    if not root_path:
        logger.warning("Migration: project '%s' not found in config, skipping", project_id)
        result["skipped"] += 1
        return None

    root = Path(root_path)
    if not root.exists() or not root.is_dir():
        logger.warning(
            "Migration: root_path '%s' for project '%s' does not exist, skipping",
            root_path,
            project_id,
        )
        result["skipped"] += 1
        return None

    return root / ".lex_mint" / "conversations"


def _ensure_target_dir(target_dir: Path, result: dict[str, int]) -> bool:
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
        return True
    except Exception as e:
        logger.error("Migration: failed to create target dir '%s': %s", target_dir, e)
        result["errors"] += 1
        return False


def _move_project_files(
    project_id: str,
    source_dir: Path,
    target_dir: Path,
    files_to_move: list[Path],
    result: dict[str, int],
) -> int:
    migrated_count = 0
    for src_file in files_to_move:
        dst_file = target_dir / src_file.name
        try:
            if dst_file.exists():
                logger.warning("Migration: target file already exists, skipping: %s", dst_file)
                result["skipped"] += 1
                continue
            shutil.move(str(src_file), str(dst_file))
            migrated_count += 1
        except Exception as e:
            logger.error("Migration: failed to move '%s' -> '%s': %s", src_file, dst_file, e)
            result["errors"] += 1

    if migrated_count:
        logger.info(
            "Migration: moved %d file(s) for project '%s' -> %s",
            migrated_count,
            project_id,
            target_dir,
        )

    _cleanup_empty_dir(source_dir)
    return migrated_count


def _migrate_project_dir(
    proj_dir: Path, project_map: dict[str, str], result: dict[str, int]
) -> None:
    target_dir = _resolve_target_dir(proj_dir.name, project_map, result)
    if target_dir is None:
        return

    files_to_move = _iter_project_files(proj_dir)
    if not files_to_move:
        _cleanup_empty_dir(proj_dir)
        return

    if not _ensure_target_dir(target_dir, result):
        return

    result["migrated"] += _move_project_files(
        proj_dir.name, proj_dir, target_dir, files_to_move, result
    )


def migrate_project_conversations(conversations_dir: Path) -> dict[str, int]:
    """Migrate project conversations from central storage to project directories.

    Reads projects_config.yaml to build project_id -> root_path map, then moves
    all .md and .compare.json files from conversations/projects/{project_id}/
    to {root_path}/.lex_mint/conversations/.

    Args:
        conversations_dir: Base conversations directory (e.g. "conversations")

    Returns:
        Dict with counts: {"migrated": N, "skipped": N, "errors": N}
    """
    result = {"migrated": 0, "skipped": 0, "errors": 0}

    projects_dir = Path(conversations_dir) / "projects"
    if not projects_dir.exists():
        return result

    # Check if there are any project subdirectories to migrate
    project_subdirs = [d for d in projects_dir.iterdir() if d.is_dir()]
    if not project_subdirs:
        return result

    project_map = _load_project_root_map()

    logger.info(
        "Migration: found %d project dir(s) to check, %d project(s) in config",
        len(project_subdirs),
        len(project_map),
    )

    for proj_dir in project_subdirs:
        _migrate_project_dir(proj_dir, project_map, result)

    # Remove conversations/projects/ if empty
    if projects_dir.exists() and not any(projects_dir.iterdir()):
        _cleanup_empty_dir(projects_dir)
        logger.info("Migration: removed empty conversations/projects/ directory")

    logger.info(
        "Migration complete: migrated=%d, skipped=%d, errors=%d",
        result["migrated"],
        result["skipped"],
        result["errors"],
    )
    return result
