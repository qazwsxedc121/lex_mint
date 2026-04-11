"""Static checker for plugin isolation (self-contained degree)."""

from __future__ import annotations

import argparse
import ast
import json
from dataclasses import dataclass
from pathlib import Path

import yaml


DEFAULT_ALLOWED_SRC_PREFIXES = (
    "src.tools.plugins.models",
    "src.providers.plugins.models",
    "src.tools.definitions",
    "src.providers.types",
    "src.providers.base",
)


@dataclass
class PluginIsolationReport:
    plugin_id: str
    path: Path
    py_files: int
    total_imports: int
    relative_imports: int
    plugin_namespace_imports: int
    allowed_src_imports: int
    core_src_imports: int
    external_imports: int
    entrypoint_imports_src: int
    entrypoint_local_defs: int
    thin_wrapper: bool
    score: int
    issues: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "plugin_id": self.plugin_id,
            "path": str(self.path),
            "py_files": self.py_files,
            "total_imports": self.total_imports,
            "relative_imports": self.relative_imports,
            "plugin_namespace_imports": self.plugin_namespace_imports,
            "allowed_src_imports": self.allowed_src_imports,
            "core_src_imports": self.core_src_imports,
            "external_imports": self.external_imports,
            "entrypoint_imports_src": self.entrypoint_imports_src,
            "entrypoint_local_defs": self.entrypoint_local_defs,
            "thin_wrapper": self.thin_wrapper,
            "score": self.score,
            "issues": list(self.issues),
        }


def _iter_python_files(plugin_dir: Path) -> list[Path]:
    return sorted(
        [p for p in plugin_dir.rglob("*.py") if p.is_file() and "__pycache__" not in p.parts],
        key=lambda p: str(p),
    )


def _parse_imports(path: Path) -> tuple[list[tuple[str, int]], int]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    imports: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((str(alias.name), 0))
        elif isinstance(node, ast.ImportFrom):
            module_name = str(node.module or "")
            imports.append((module_name, int(node.level or 0)))
    return imports, _count_local_defs(tree)


def _count_local_defs(tree: ast.AST) -> int:
    count = 0
    for node in tree.body if isinstance(tree, ast.Module) else []:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            count += 1
    return count


def _is_allowed_src_module(module_name: str, allowed_prefixes: tuple[str, ...]) -> bool:
    return any(
        module_name == prefix or module_name.startswith(f"{prefix}.") for prefix in allowed_prefixes
    )


def _load_manifest_plugin_id(manifest_path: Path) -> str | None:
    try:
        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
    except Exception:
        return None
    if not isinstance(raw, dict):
        return None
    plugin_id = str(raw.get("id") or "").strip()
    return plugin_id or None


def analyze_plugin(
    plugin_dir: Path,
    *,
    allowed_src_prefixes: tuple[str, ...],
) -> PluginIsolationReport:
    manifest_path = plugin_dir / "manifest.yaml"
    plugin_id = _load_manifest_plugin_id(manifest_path) or plugin_dir.name
    py_files = _iter_python_files(plugin_dir)

    total_imports = 0
    relative_imports = 0
    plugin_namespace_imports = 0
    allowed_src_imports = 0
    core_src_imports = 0
    external_imports = 0

    entrypoint = plugin_dir / "plugin.py"
    entrypoint_imports_src = 0
    entrypoint_local_defs = 0

    for py_file in py_files:
        imports, local_defs = _parse_imports(py_file)
        if py_file == entrypoint:
            entrypoint_local_defs = local_defs
        for module_name, level in imports:
            total_imports += 1
            if level > 0:
                relative_imports += 1
                continue
            if module_name.startswith(f"plugins.{plugin_id}"):
                plugin_namespace_imports += 1
                continue
            if module_name.startswith("src."):
                if _is_allowed_src_module(module_name, allowed_src_prefixes):
                    allowed_src_imports += 1
                else:
                    core_src_imports += 1
                if py_file == entrypoint:
                    entrypoint_imports_src += 1
                continue
            external_imports += 1

    thin_wrapper = (
        entrypoint.exists()
        and entrypoint_imports_src > 0
        and entrypoint_local_defs <= 1
        and len(py_files) <= 2
    )

    score = 100
    score -= core_src_imports * 20
    score -= max(0, entrypoint_imports_src - 1) * 5
    if thin_wrapper:
        score -= 20
    score = max(0, min(100, score))

    issues: list[str] = []
    if core_src_imports > 0:
        issues.append(f"imports core src modules: {core_src_imports}")
    if thin_wrapper:
        issues.append("entrypoint appears to be a thin wrapper")
    if score < 60:
        issues.append(f"low isolation score: {score}")

    return PluginIsolationReport(
        plugin_id=plugin_id,
        path=plugin_dir,
        py_files=len(py_files),
        total_imports=total_imports,
        relative_imports=relative_imports,
        plugin_namespace_imports=plugin_namespace_imports,
        allowed_src_imports=allowed_src_imports,
        core_src_imports=core_src_imports,
        external_imports=external_imports,
        entrypoint_imports_src=entrypoint_imports_src,
        entrypoint_local_defs=entrypoint_local_defs,
        thin_wrapper=thin_wrapper,
        score=score,
        issues=issues,
    )


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check plugin self-contained degree (static).")
    parser.add_argument(
        "--plugins-dir",
        default="plugins",
        help="Plugin root directory (default: plugins).",
    )
    parser.add_argument(
        "--allow-src-prefix",
        action="append",
        default=[],
        help="Additional allowed src module prefix (repeatable).",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Fail (exit 1) when plugin violates thresholds.",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=60,
        help="Strict mode threshold: minimum isolation score (default: 60).",
    )
    parser.add_argument(
        "--max-core-src-imports",
        type=int,
        default=0,
        help="Strict mode threshold: maximum core src imports (default: 0).",
    )
    parser.add_argument(
        "--forbid-thin-wrapper",
        action="store_true",
        help="Strict mode threshold: fail when thin wrapper is detected.",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    plugins_dir = Path(args.plugins_dir)
    if not plugins_dir.exists():
        print(f"plugins dir not found: {plugins_dir}")
        return 1

    allowed_src_prefixes = tuple(
        list(DEFAULT_ALLOWED_SRC_PREFIXES) + [str(item).strip() for item in args.allow_src_prefix]
    )
    plugin_dirs = sorted(
        [
            p
            for p in plugins_dir.iterdir()
            if p.is_dir() and (p / "manifest.yaml").is_file() and p.name != "__pycache__"
        ],
        key=lambda p: p.name,
    )

    reports = [analyze_plugin(p, allowed_src_prefixes=allowed_src_prefixes) for p in plugin_dirs]
    failing: list[PluginIsolationReport] = []
    for report in reports:
        if report.score < int(args.min_score):
            failing.append(report)
            continue
        if report.core_src_imports > int(args.max_core_src_imports):
            failing.append(report)
            continue
        if args.forbid_thin_wrapper and report.thin_wrapper:
            failing.append(report)

    if args.json:
        payload = {
            "plugins_dir": str(plugins_dir),
            "strict": bool(args.strict),
            "min_score": int(args.min_score),
            "max_core_src_imports": int(args.max_core_src_imports),
            "forbid_thin_wrapper": bool(args.forbid_thin_wrapper),
            "reports": [r.to_dict() for r in reports],
            "failing_ids": [r.plugin_id for r in failing],
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"Plugin isolation report ({plugins_dir})")
        for report in reports:
            issue_text = "; ".join(report.issues) if report.issues else "ok"
            print(
                f"- {report.plugin_id}: score={report.score}, core_src={report.core_src_imports}, "
                f"thin_wrapper={str(report.thin_wrapper).lower()}, files={report.py_files} -> {issue_text}"
            )
        if failing and args.strict:
            print("")
            print("Failing plugins:")
            for report in failing:
                print(f"  - {report.plugin_id}")
        elif failing:
            print("")
            print("Plugins below configured thresholds (advisory mode):")
            for report in failing:
                print(f"  - {report.plugin_id}")

    if args.strict and failing:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
