"""Generate shared workflow JSON schema from backend Pydantic models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from pydantic import TypeAdapter


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_PATH = REPO_ROOT / "shared" / "schemas" / "workflow.schema.json"

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.models.workflow import (  # noqa: E402
    Workflow,
    WorkflowCreate,
    WorkflowInputDef,
    WorkflowNode,
    WorkflowUpdate,
)


def build_schema_bundle() -> dict[str, Any]:
    """Build a deterministic schema bundle used by both backend and frontend."""
    return {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$id": "https://lex-mint.local/schemas/workflow.schema.json",
        "title": "Lex Mint Workflow Schema Bundle",
        "description": "Generated from src.api.models.workflow. Do not edit manually.",
        "schemas": {
            "Workflow": Workflow.model_json_schema(),
            "WorkflowCreate": WorkflowCreate.model_json_schema(),
            "WorkflowUpdate": WorkflowUpdate.model_json_schema(),
            "WorkflowInputDef": WorkflowInputDef.model_json_schema(),
            "WorkflowNode": TypeAdapter(WorkflowNode).json_schema(),
        },
    }


def serialize_schema_bundle(bundle: dict[str, Any]) -> str:
    """Serialize schema bundle with stable formatting for drift checks."""
    return json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=str(DEFAULT_OUTPUT_PATH),
        help=f"Output path for generated schema (default: {DEFAULT_OUTPUT_PATH})",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify output file is up-to-date without writing changes.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    output_path = Path(args.output).expanduser().resolve()
    expected_content = serialize_schema_bundle(build_schema_bundle())

    if args.check:
        if not output_path.exists():
            print(f"[schema] Missing file: {output_path}")
            return 1

        existing_content = output_path.read_text(encoding="utf-8")
        if existing_content != expected_content:
            print(f"[schema] Out of date: {output_path}")
            print("[schema] Run: npm run generate:workflow-schema")
            return 1

        print(f"[schema] Up to date: {output_path}")
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    previous_content = output_path.read_text(encoding="utf-8") if output_path.exists() else None
    output_path.write_text(expected_content, encoding="utf-8")

    if previous_content == expected_content:
        print(f"[schema] Unchanged: {output_path}")
    else:
        print(f"[schema] Wrote: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
