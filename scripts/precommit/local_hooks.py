"""Local pre-commit hooks that avoid remote hook repositories."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import yaml

EXCLUDE_PATTERN = re.compile(r"^frontend/public/pyodide/")


def _normalize(path: str) -> str:
    return path.replace("\\", "/")


def _should_skip(path: str) -> bool:
    return bool(EXCLUDE_PATTERN.match(_normalize(path)))


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return None


def _write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8", newline="\n")


def trailing_whitespace(paths: list[str]) -> int:
    changed = 0
    for raw in paths:
        if _should_skip(raw):
            continue
        path = Path(raw)
        if not path.is_file():
            continue
        content = _read_text(path)
        if content is None:
            continue
        lines = content.splitlines(keepends=True)
        fixed_lines = [re.sub(r"[ \t]+(\r?\n)$", r"\1", line) for line in lines]
        fixed = "".join(fixed_lines)
        if fixed != content:
            _write_text(path, fixed)
            changed += 1

    if changed:
        print(f"fixed trailing whitespace in {changed} file(s)")
        return 1
    return 0


def end_of_file_fixer(paths: list[str]) -> int:
    changed = 0
    for raw in paths:
        if _should_skip(raw):
            continue
        path = Path(raw)
        if not path.is_file():
            continue
        content = _read_text(path)
        if content is None:
            continue
        stripped = content.rstrip("\r\n")
        fixed = f"{stripped}\n" if stripped else "\n"
        if fixed != content:
            _write_text(path, fixed)
            changed += 1

    if changed:
        print(f"fixed end-of-file newlines in {changed} file(s)")
        return 1
    return 0


def check_yaml(paths: list[str]) -> int:
    failed = 0
    for raw in paths:
        if _should_skip(raw):
            continue
        path = Path(raw)
        if not path.is_file():
            continue
        try:
            yaml.safe_load(path.read_text(encoding="utf-8"))
        except Exception as exc:
            failed += 1
            print(f"{raw}: invalid yaml: {exc}")

    return 1 if failed else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Run local pre-commit hook helpers.")
    parser.add_argument("hook", choices=["trailing-whitespace", "end-of-file-fixer", "check-yaml"])
    parser.add_argument("paths", nargs="*")
    args = parser.parse_args(argv)

    if args.hook == "trailing-whitespace":
        return trailing_whitespace(args.paths)
    if args.hook == "end-of-file-fixer":
        return end_of_file_fixer(args.paths)
    return check_yaml(args.paths)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
