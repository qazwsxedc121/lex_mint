"""Find callable symbols in src/ that appear to be used only by tests.

This is a lightweight static analysis:
- definitions are collected from `src/**/*.py`
- call sites are collected from AST `Call(...)` in both `src/**/*.py` and `tests/**/*.py`

Because Python is dynamic, output is a candidate list and requires manual review.
"""

from __future__ import annotations

import argparse
import ast
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import TypeVar


@dataclass(frozen=True)
class CallableDef:
    name: str
    qualname: str
    path: Path
    lineno: int
    kind: str


@dataclass(frozen=True)
class CallSite:
    name: str
    owner: str | None
    path: Path
    lineno: int


class _DefCollector(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.class_stack: list[str] = []
        self.function_depth = 0
        self.items: list[CallableDef] = []

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802
        if self.function_depth == 0:
            self.class_stack.append(node.name)
            self.generic_visit(node)
            self.class_stack.pop()
            return
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._visit_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._visit_function(node, is_async=True)

    def _visit_function(
        self, node: ast.FunctionDef | ast.AsyncFunctionDef, *, is_async: bool
    ) -> None:
        kind = "async method" if self.class_stack and is_async else "method"
        if not self.class_stack:
            kind = "async function" if is_async else "function"

        if self.function_depth == 0:
            qual_parts = [*self.class_stack, node.name]
            self.items.append(
                CallableDef(
                    name=node.name,
                    qualname=".".join(qual_parts),
                    path=self.path,
                    lineno=node.lineno,
                    kind=kind,
                )
            )

        self.function_depth += 1
        self.generic_visit(node)
        self.function_depth -= 1


class _CallCollector(ast.NodeVisitor):
    def __init__(self, path: Path) -> None:
        self.path = path
        self.items: list[CallSite] = []
        self._scopes: list[dict[str, str]] = [{}]

    @staticmethod
    def _resolve_ctor_name(expr: ast.expr) -> str | None:
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            return expr.attr
        return None

    def _bind_name_if_ctor(self, target: ast.expr, value: ast.expr) -> None:
        if not isinstance(target, ast.Name):
            return
        if not isinstance(value, ast.Call):
            return
        ctor_name = self._resolve_ctor_name(value.func)
        if not ctor_name:
            return
        self._scopes[-1][target.id] = ctor_name

    def visit_Assign(self, node: ast.Assign) -> None:  # noqa: N802
        for target in node.targets:
            self._bind_name_if_ctor(target, node.value)
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:  # noqa: N802
        if node.value is not None:
            self._bind_name_if_ctor(node.target, node.value)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802
        self._scopes.append({})
        self.generic_visit(node)
        self._scopes.pop()

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802
        self._scopes.append({})
        self.generic_visit(node)
        self._scopes.pop()

    def visit_Call(self, node: ast.Call) -> None:  # noqa: N802
        called_name: str | None = None
        owner: str | None = None
        if isinstance(node.func, ast.Name):
            called_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            called_name = node.func.attr
            if isinstance(node.func.value, ast.Name):
                var_name = node.func.value.id
                for scope in reversed(self._scopes):
                    inferred_owner = scope.get(var_name)
                    if inferred_owner:
                        owner = inferred_owner
                        break

        if called_name:
            self.items.append(
                CallSite(name=called_name, owner=owner, path=self.path, lineno=node.lineno)
            )
        self.generic_visit(node)


def _iter_py_files(root: Path) -> Iterable[Path]:
    if not root.exists():
        return []
    return sorted(p for p in root.rglob("*.py") if p.is_file())


def _parse_file(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return None


def collect_definitions(src_root: Path) -> list[CallableDef]:
    definitions: list[CallableDef] = []
    for path in _iter_py_files(src_root):
        tree = _parse_file(path)
        if tree is None:
            continue
        collector = _DefCollector(path)
        collector.visit(tree)
        definitions.extend(collector.items)
    return definitions


def collect_calls(code_root: Path) -> list[CallSite]:
    calls: list[CallSite] = []
    for path in _iter_py_files(code_root):
        tree = _parse_file(path)
        if tree is None:
            continue
        collector = _CallCollector(path)
        collector.visit(tree)
        calls.extend(collector.items)
    return calls


T = TypeVar("T")


def build_index_by_name(items: Iterable[T], key: str = "name") -> dict[str, list[T]]:
    index: dict[str, list[T]] = {}
    for item in items:
        name = getattr(item, key)
        index.setdefault(name, []).append(item)
    return index


def _rel(path: Path, repo_root: Path) -> str:
    try:
        return str(path.relative_to(repo_root))
    except ValueError:
        return str(path)


def _in_scope(path: Path, scope_root: Path | None) -> bool:
    if scope_root is None:
        return True
    try:
        path.relative_to(scope_root)
        return True
    except ValueError:
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find src callables that appear used only in tests."
    )
    parser.add_argument(
        "--repo-root", default=".", help="Repository root path (default: current dir)."
    )
    parser.add_argument(
        "--scope",
        default=None,
        help=(
            "Limit definition candidates to this directory relative to repo root "
            "(e.g. src/application/chat)."
        ),
    )
    parser.add_argument(
        "--include-ambiguous",
        action="store_true",
        help="Include names that are defined multiple times in src.",
    )
    parser.add_argument(
        "--symbol",
        default=None,
        help="Inspect one symbol name and print definitions/call sites.",
    )
    parser.add_argument(
        "--qualname",
        default=None,
        help="Inspect one qualified symbol (e.g. ChatApplicationService.process_message_stream).",
    )
    args = parser.parse_args()

    repo_root = Path(args.repo_root).resolve()
    src_root = repo_root / "src"
    tests_root = repo_root / "tests"

    definitions = collect_definitions(src_root)
    src_calls = collect_calls(src_root)
    test_calls = collect_calls(tests_root)

    scope_root = (repo_root / args.scope).resolve() if args.scope else None

    defs_by_name = build_index_by_name(definitions)
    src_calls_by_name = build_index_by_name(src_calls)
    test_calls_by_name = build_index_by_name(test_calls)
    defs_by_qualname = build_index_by_name(definitions, key="qualname")

    if args.symbol:
        symbol = str(args.symbol)
        print(f"SYMBOL: {symbol}")
        print("DEFINITIONS:")
        for d in defs_by_name.get(symbol, []):
            print(f"  - {_rel(d.path, repo_root)}:{d.lineno} [{d.kind}] {d.qualname}")
        print("SRC CALL SITES:")
        for c in src_calls_by_name.get(symbol, []):
            owner_text = f"{c.owner}." if c.owner else ""
            print(f"  - {_rel(c.path, repo_root)}:{c.lineno} ({owner_text}{c.name})")
        print("TEST CALL SITES:")
        for c in test_calls_by_name.get(symbol, []):
            owner_text = f"{c.owner}." if c.owner else ""
            print(f"  - {_rel(c.path, repo_root)}:{c.lineno} ({owner_text}{c.name})")
        return 0

    if args.qualname:
        qualname = str(args.qualname)
        if "." in qualname:
            owner, name = qualname.rsplit(".", 1)
        else:
            owner, name = None, qualname

        def _match(c: CallSite) -> bool:
            if c.name != name:
                return False
            if owner is None:
                return True
            return c.owner == owner

        src_q = [c for c in src_calls if _match(c)]
        test_q = [c for c in test_calls if _match(c)]
        src_unknown = [c for c in src_calls if c.name == name and c.owner is None]
        test_unknown = [c for c in test_calls if c.name == name and c.owner is None]

        print(f"QUALNAME: {qualname}")
        print("DEFINITIONS:")
        for d in defs_by_qualname.get(qualname, []):
            print(f"  - {_rel(d.path, repo_root)}:{d.lineno} [{d.kind}] {d.qualname}")
        print("SRC CALL SITES:")
        for c in src_q:
            owner_text = f"{c.owner}." if c.owner else ""
            print(f"  - {_rel(c.path, repo_root)}:{c.lineno} ({owner_text}{c.name})")
        if owner is not None and src_unknown:
            print("SRC UNKNOWN-OWNER CALL SITES:")
            for c in src_unknown:
                print(f"  - {_rel(c.path, repo_root)}:{c.lineno} ({c.name})")
        print("TEST CALL SITES:")
        for c in test_q:
            owner_text = f"{c.owner}." if c.owner else ""
            print(f"  - {_rel(c.path, repo_root)}:{c.lineno} ({owner_text}{c.name})")
        if owner is not None and test_unknown:
            print("TEST UNKNOWN-OWNER CALL SITES:")
            for c in test_unknown:
                print(f"  - {_rel(c.path, repo_root)}:{c.lineno} ({c.name})")
        print(
            "SUMMARY: "
            f"src_calls={len(src_q)} test_calls={len(test_q)} "
            f"src_unknown_owner={len(src_unknown)} test_unknown_owner={len(test_unknown)}"
        )
        return 0

    candidates: list[tuple[CallableDef, int, int, int]] = []
    for d in definitions:
        if not _in_scope(d.path.resolve(), scope_root):
            continue
        ambiguous_count = len(defs_by_name.get(d.name, []))
        if ambiguous_count > 1 and not args.include_ambiguous:
            continue
        if "." in d.qualname:
            owner, _ = d.qualname.rsplit(".", 1)
            src_matched = [c for c in src_calls_by_name.get(d.name, []) if c.owner == owner]
            test_matched = [c for c in test_calls_by_name.get(d.name, []) if c.owner == owner]
            src_unknown = [c for c in src_calls_by_name.get(d.name, []) if c.owner is None]
            test_unknown = [c for c in test_calls_by_name.get(d.name, []) if c.owner is None]
            if ambiguous_count == 1:
                src_count = len(src_matched) + len(src_unknown)
                test_count = len(test_matched) + len(test_unknown)
            else:
                src_count = len(src_matched)
                test_count = len(test_matched)
        else:
            src_count = len(src_calls_by_name.get(d.name, []))
            test_count = len(test_calls_by_name.get(d.name, []))
        if src_count == 0 and test_count > 0:
            candidates.append((d, src_count, test_count, ambiguous_count))

    candidates.sort(key=lambda item: (-item[2], _rel(item[0].path, repo_root), item[0].lineno))

    print("path\tline\tkind\tqualname\tname\tsrc_calls\ttest_calls\tdef_name_count")
    for d, src_count, test_count, ambiguous_count in candidates:
        print(
            f"{_rel(d.path, repo_root)}\t{d.lineno}\t{d.kind}\t{d.qualname}\t{d.name}\t"
            f"{src_count}\t{test_count}\t{ambiguous_count}"
        )

    print(f"\nTOTAL_CANDIDATES={len(candidates)}")
    print("NOTE=Static heuristic only; dynamic calls/reflection may not be captured.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
