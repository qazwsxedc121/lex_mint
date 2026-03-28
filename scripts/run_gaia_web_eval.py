"""Run a small GAIA-style public web evaluation against the local app."""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.evals.gaia_web_eval import (
    DEFAULT_CASES_PATH,
    DEFAULT_REPORTS_DIR,
    load_cases,
    run_eval,
    select_cases,
    write_report_files,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run GAIA-style web research eval")
    parser.add_argument("--base-url", default="http://127.0.0.1:8988", help="Backend base URL")
    parser.add_argument(
        "--model-id", default=None, help="Composite model id, for example openai:gpt-4.1"
    )
    parser.add_argument("--context-type", choices=["chat", "project"], default="chat")
    parser.add_argument("--project-id", default=None, help="Required when context-type=project")
    parser.add_argument("--cases-path", type=str, default=str(DEFAULT_CASES_PATH))
    parser.add_argument(
        "--case-id", action="append", default=[], help="Run only the specified case id"
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="Run only the first N selected cases"
    )
    parser.add_argument(
        "--scored-only", action="store_true", help="Run only cases with reference answers"
    )
    parser.add_argument(
        "--keep-sessions", action="store_true", help="Do not delete temporary eval sessions"
    )
    parser.add_argument(
        "--ensure-project-web-tools",
        action="store_true",
        help="When using project context, enable web_search and read_webpage before the run",
    )
    parser.add_argument("--output-dir", type=str, default=str(DEFAULT_REPORTS_DIR))
    return parser


async def _main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.context_type == "project" and not args.project_id:
        parser.error("--project-id is required when --context-type=project")

    cases = load_cases(Path(args.cases_path))
    selected_cases = select_cases(
        cases,
        case_ids=args.case_id,
        limit=args.limit,
        scored_only=args.scored_only,
    )
    if not selected_cases:
        parser.error("No evaluation cases selected")

    report = await run_eval(
        base_url=args.base_url,
        model_id=args.model_id,
        context_type=args.context_type,
        project_id=args.project_id,
        cases=selected_cases,
        cleanup_sessions=not args.keep_sessions,
        ensure_project_web_tools=args.ensure_project_web_tools,
    )

    run_name = f"gaia_web_eval_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    output_paths = write_report_files(
        report,
        output_dir=Path(args.output_dir),
        run_name=run_name,
    )

    print(f"Wrote JSON report: {output_paths['json']}")
    print(f"Wrote markdown report: {output_paths['markdown']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(_main()))
