"""Architecture guardrails for retired legacy module paths."""

from __future__ import annotations

import ast
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
SEARCH_DIRS = ("src", "tests", "scripts")
BANNED_MODULE_PREFIXES = (
    "src.agents",
    "src.api.services",
    "src.api.models",
    "src.api.config",
    "src.api.paths",
)


def _iter_python_files():
    for relative_dir in SEARCH_DIRS:
        base_dir = REPO_ROOT / relative_dir
        if not base_dir.exists():
            continue
        for file_path in base_dir.rglob("*.py"):
            if "__pycache__" in file_path.parts:
                continue
            yield file_path


def _is_banned(module_name: str) -> bool:
    return any(
        module_name == banned or module_name.startswith(f"{banned}.")
        for banned in BANNED_MODULE_PREFIXES
    )


def test_no_source_or_tests_import_retired_legacy_modules():
    offenders: list[str] = []

    for file_path in _iter_python_files():
        tree = ast.parse(file_path.read_text(encoding="utf-8-sig"), filename=str(file_path))

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if _is_banned(alias.name):
                        offenders.append(
                            f"{file_path.relative_to(REPO_ROOT)}:{node.lineno} -> {alias.name}"
                        )
            elif isinstance(node, ast.ImportFrom):
                if node.level != 0 or not node.module:
                    continue
                if _is_banned(node.module):
                    offenders.append(
                        f"{file_path.relative_to(REPO_ROOT)}:{node.lineno} -> {node.module}"
                    )

    assert not offenders, "Legacy imports found:\n" + "\n".join(sorted(offenders))


def test_retired_agents_package_is_removed():
    assert not (REPO_ROOT / "src" / "agents").exists()
