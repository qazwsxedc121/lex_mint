"""One-time migration: move project conversations to .lex_mint in project directories.

Migrates conversation files from the old layout:
    conversations/projects/{project_id}/*.md

To the new layout:
    {project_root_path}/.lex_mint/conversations/*.md
"""

import logging
import shutil
from pathlib import Path
from typing import Dict

import yaml

from ..config import settings

logger = logging.getLogger(__name__)


def migrate_project_conversations(conversations_dir: Path) -> Dict[str, int]:
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

    # Build project_id -> root_path map from config
    config_path = settings.projects_config_path
    project_map: Dict[str, str] = {}
    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)
            if data:
                for proj in data.get('projects', []):
                    pid = proj.get('id')
                    root = proj.get('root_path')
                    if pid and root:
                        project_map[pid] = root
        except Exception as e:
            logger.warning("Failed to read projects config for migration: %s", e)
            return result

    logger.info("Migration: found %d project dir(s) to check, %d project(s) in config",
                len(project_subdirs), len(project_map))

    for proj_dir in project_subdirs:
        project_id = proj_dir.name
        root_path = project_map.get(project_id)

        if not root_path:
            logger.warning("Migration: project '%s' not found in config, skipping", project_id)
            result["skipped"] += 1
            continue

        # Verify root_path exists
        root = Path(root_path)
        if not root.exists() or not root.is_dir():
            logger.warning("Migration: root_path '%s' for project '%s' does not exist, skipping",
                           root_path, project_id)
            result["skipped"] += 1
            continue

        target_dir = root / ".lex_mint" / "conversations"

        # Collect files to migrate
        files_to_move = list(proj_dir.glob("*.md")) + list(proj_dir.glob("*.compare.json"))
        if not files_to_move:
            # Empty directory, clean it up
            try:
                proj_dir.rmdir()
            except OSError:
                pass
            continue

        # Create target directory
        try:
            target_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            logger.error("Migration: failed to create target dir '%s': %s", target_dir, e)
            result["errors"] += 1
            continue

        # Move files
        dir_migrated = 0
        for src_file in files_to_move:
            dst_file = target_dir / src_file.name
            try:
                if dst_file.exists():
                    logger.warning("Migration: target file already exists, skipping: %s", dst_file)
                    result["skipped"] += 1
                    continue
                shutil.move(str(src_file), str(dst_file))
                dir_migrated += 1
            except Exception as e:
                logger.error("Migration: failed to move '%s' -> '%s': %s",
                             src_file, dst_file, e)
                result["errors"] += 1

        if dir_migrated:
            logger.info("Migration: moved %d file(s) for project '%s' -> %s",
                        dir_migrated, project_id, target_dir)
            result["migrated"] += dir_migrated

        # Remove empty source directory
        try:
            if not any(proj_dir.iterdir()):
                proj_dir.rmdir()
        except OSError:
            pass

    # Remove conversations/projects/ if empty
    try:
        if projects_dir.exists() and not any(projects_dir.iterdir()):
            projects_dir.rmdir()
            logger.info("Migration: removed empty conversations/projects/ directory")
    except OSError:
        pass

    logger.info("Migration complete: migrated=%d, skipped=%d, errors=%d",
                result["migrated"], result["skipped"], result["errors"])
    return result
