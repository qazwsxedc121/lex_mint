#!/usr/bin/env python3
"""Run CRUD-RAG benchmark by converting CRUD split data into run_rag_eval format."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Sequence

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.crud_rag_adapter import (  # noqa: E402
    DEFAULT_TASKS,
    build_rag_eval_dataset_from_crud,
    load_crud_split_dataset,
)


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _load_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Benchmark config must be a YAML object.")
    benchmark = raw.get("benchmark", raw)
    if not isinstance(benchmark, dict):
        raise ValueError("`benchmark` section must be an object.")
    return benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run CRUD-RAG benchmark for lex_mint_rag.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/benchmarks/crud_rag_v1.yaml"),
        help="Benchmark config YAML path.",
    )
    parser.add_argument(
        "--crud-dataset",
        type=Path,
        default=None,
        help="Override CRUD split dataset path.",
    )
    parser.add_argument(
        "--kb-ids",
        type=str,
        default=None,
        help="Comma-separated KB IDs to evaluate against (overrides config).",
    )
    parser.add_argument(
        "--tasks",
        type=str,
        default=None,
        help="Comma-separated CRUD task names (overrides config).",
    )
    parser.add_argument(
        "--per-task-max",
        type=int,
        default=None,
        help="Max number of samples per task (overrides config).",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Override top_k used in converted cases.",
    )
    parser.add_argument(
        "--modes",
        type=str,
        default=None,
        help="Comma-separated retrieval modes for run_rag_eval (default from config).",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="Override score threshold passed to run_rag_eval.",
    )
    parser.add_argument(
        "--bm25-min-term-coverage",
        type=float,
        default=None,
        help="Override BM25 lexical coverage threshold passed to run_rag_eval.",
    )
    parser.add_argument(
        "--runtime-model-id",
        type=str,
        default=None,
        help="Optional runtime model id passed to run_rag_eval.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Benchmark output directory (default: data/benchmarks/crud_rag_v1_<timestamp>).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only generate converted dataset and manifest without running run_rag_eval.",
    )
    return parser.parse_args()


def _resolve_list(cli_value: str | None, config_value: Any, default: Sequence[str]) -> List[str]:
    if cli_value is not None:
        return _split_csv(cli_value)
    if isinstance(config_value, list):
        return [str(item).strip() for item in config_value if str(item).strip()]
    if isinstance(config_value, str) and config_value.strip():
        return _split_csv(config_value)
    return list(default)


def _resolve_int(cli_value: int | None, config_value: Any, default: int) -> int:
    if cli_value is not None:
        return int(cli_value)
    if config_value is not None:
        return int(config_value)
    return int(default)


def _resolve_float(cli_value: float | None, config_value: Any) -> float | None:
    if cli_value is not None:
        return float(cli_value)
    if config_value is None:
        return None
    return float(config_value)


def _resolve_path(cli_value: Path | None, config_value: Any, default: Path) -> Path:
    if cli_value is not None:
        return cli_value
    if config_value:
        return Path(str(config_value))
    return default


def main() -> None:
    args = parse_args()
    config = _load_config(args.config)

    benchmark_name = str(config.get("name", "crud_rag_v1")).strip() or "crud_rag_v1"
    crud_dataset_path = _resolve_path(
        args.crud_dataset,
        config.get("crud_dataset_path"),
        Path("learn_proj/CRUD_RAG/data/crud_split/split_merged.json"),
    )
    kb_ids = _resolve_list(args.kb_ids, config.get("kb_ids"), default=[])
    if not kb_ids:
        raise ValueError(
            "No KB IDs configured. Set `benchmark.kb_ids` in config or pass --kb-ids kb_a,kb_b."
        )
    tasks = _resolve_list(args.tasks, config.get("tasks"), DEFAULT_TASKS)
    per_task_max = _resolve_int(args.per_task_max, config.get("per_task_max"), 200)
    top_k = _resolve_int(args.top_k, config.get("top_k"), 5)
    modes = ",".join(_resolve_list(args.modes, config.get("modes"), ["hybrid"]))
    score_threshold = _resolve_float(args.score_threshold, config.get("score_threshold"))
    bm25_min_term_coverage = _resolve_float(
        args.bm25_min_term_coverage,
        config.get("bm25_min_term_coverage"),
    )
    runtime_model_id = args.runtime_model_id or str(config.get("runtime_model_id") or "").strip() or None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or Path("data/benchmarks") / f"{benchmark_name}_{timestamp}"
    output_dir.mkdir(parents=True, exist_ok=True)

    crud_data = load_crud_split_dataset(crud_dataset_path)
    converted_dataset = build_rag_eval_dataset_from_crud(
        crud_data=crud_data,
        kb_ids=kb_ids,
        tasks=tasks,
        per_task_max=per_task_max,
        top_k=top_k,
        dataset_name=benchmark_name,
    )

    converted_dataset_path = output_dir / "dataset_converted.json"
    converted_dataset_path.write_text(
        json.dumps(converted_dataset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    rag_eval_output_dir = output_dir / "rag_eval"
    run_command: List[str] = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_rag_eval.py"),
        "--dataset",
        str(converted_dataset_path),
        "--modes",
        modes,
        "--output-dir",
        str(rag_eval_output_dir),
    ]
    if score_threshold is not None:
        run_command.extend(["--score-threshold", str(score_threshold)])
    if bm25_min_term_coverage is not None:
        run_command.extend(["--bm25-min-term-coverage", str(bm25_min_term_coverage)])
    if runtime_model_id:
        run_command.extend(["--runtime-model-id", runtime_model_id])

    manifest = {
        "benchmark_name": benchmark_name,
        "crud_dataset_path": str(crud_dataset_path),
        "tasks": tasks,
        "per_task_max": per_task_max,
        "top_k": top_k,
        "kb_ids": kb_ids,
        "modes": modes,
        "score_threshold": score_threshold,
        "bm25_min_term_coverage": bm25_min_term_coverage,
        "runtime_model_id": runtime_model_id,
        "converted_dataset_path": str(converted_dataset_path),
        "rag_eval_output_dir": str(rag_eval_output_dir),
        "command": run_command,
    }
    (output_dir / "benchmark_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Converted dataset saved to: {converted_dataset_path}")
    print(f"Cases: {len(converted_dataset.get('cases', []))}")

    if args.dry_run:
        print("Dry-run enabled; skipped run_rag_eval.")
        return

    process = subprocess.run(run_command, cwd=str(REPO_ROOT), check=False)
    if process.returncode != 0:
        raise SystemExit(process.returncode)

    print(f"CRUD-RAG benchmark artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()

