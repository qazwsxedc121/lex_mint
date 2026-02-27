#!/usr/bin/env python3
"""Run MTRAG retrieval benchmark via run_rag_eval."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.mtrag_adapter import (  # noqa: E402
    build_rag_eval_dataset_from_mtrag,
    load_qrels,
    load_queries,
)


def _split_csv(value: str) -> List[str]:
    return [item.strip() for item in str(value or "").split(",") if item.strip()]


def _load_config(path: Path) -> Dict[str, Any]:
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError("Benchmark config must be a YAML object.")
    section = raw.get("benchmark", raw)
    if not isinstance(section, dict):
        raise ValueError("`benchmark` section must be an object.")
    return section


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run MTRAG retrieval benchmark.")
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("config/benchmarks/mtrag_fiqa_retrieval_v1.yaml"),
        help="Benchmark config YAML path.",
    )
    parser.add_argument("--kb-ids", type=str, default=None, help="Comma-separated KB IDs override.")
    parser.add_argument("--modes", type=str, default=None, help="Comma-separated retrieval modes override.")
    parser.add_argument("--max-cases", type=int, default=None, help="Optional max cases.")
    parser.add_argument("--output-dir", type=Path, default=None, help="Benchmark output directory.")
    parser.add_argument("--runtime-model-id", type=str, default=None, help="Optional runtime model id.")
    parser.add_argument("--dry-run", action="store_true", help="Only convert dataset and write manifest.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = _load_config(args.config)

    name = str(cfg.get("name") or "mtrag_retrieval_v1")
    domain = str(cfg.get("domain") or "fiqa")
    query_path = Path(str(cfg.get("queries_path") or f"learn_proj/mt-rag-benchmark/human/retrieval_tasks/{domain}/{domain}_rewrite.jsonl"))
    qrels_path = Path(str(cfg.get("qrels_path") or f"learn_proj/mt-rag-benchmark/human/retrieval_tasks/{domain}/qrels/dev.tsv"))
    kb_ids = _split_csv(args.kb_ids) if args.kb_ids else [str(v).strip() for v in (cfg.get("kb_ids") or []) if str(v).strip()]
    if not kb_ids:
        raise ValueError("No KB IDs configured. Set benchmark.kb_ids or pass --kb-ids.")

    modes = args.modes or ",".join([str(v).strip() for v in (cfg.get("modes") or ["bm25", "vector", "hybrid"]) if str(v).strip()])
    top_k = int(cfg.get("top_k") or 10)
    score_threshold = float(cfg.get("score_threshold") or 0.0)
    bm25_min_term_coverage = float(cfg.get("bm25_min_term_coverage") or 0.0)
    max_cases = args.max_cases if args.max_cases is not None else cfg.get("max_cases")
    runtime_model_id = args.runtime_model_id or str(cfg.get("runtime_model_id") or "").strip() or None

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (Path("data/benchmarks") / f"{name}_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    queries = load_queries(query_path)
    qrels = load_qrels(qrels_path)
    converted = build_rag_eval_dataset_from_mtrag(
        queries=queries,
        qrels=qrels,
        kb_ids=kb_ids,
        domain=domain,
        dataset_name=name,
        top_k=top_k,
        max_cases=(None if max_cases is None else int(max_cases)),
    )

    dataset_path = output_dir / "dataset_converted.json"
    dataset_path.write_text(json.dumps(converted, ensure_ascii=False, indent=2), encoding="utf-8")

    rag_eval_output = output_dir / "rag_eval"
    cmd: List[str] = [
        sys.executable,
        str(REPO_ROOT / "scripts" / "run_rag_eval.py"),
        "--dataset",
        str(dataset_path),
        "--modes",
        modes,
        "--output-dir",
        str(rag_eval_output),
        "--score-threshold",
        str(score_threshold),
        "--bm25-min-term-coverage",
        str(bm25_min_term_coverage),
        "--top-k",
        str(top_k),
    ]
    if runtime_model_id:
        cmd.extend(["--runtime-model-id", runtime_model_id])

    manifest = {
        "benchmark_name": name,
        "domain": domain,
        "queries_path": str(query_path),
        "qrels_path": str(qrels_path),
        "kb_ids": kb_ids,
        "modes": modes,
        "top_k": top_k,
        "score_threshold": score_threshold,
        "bm25_min_term_coverage": bm25_min_term_coverage,
        "max_cases": max_cases,
        "runtime_model_id": runtime_model_id,
        "converted_dataset_path": str(dataset_path),
        "rag_eval_output_dir": str(rag_eval_output),
        "command": cmd,
    }
    (output_dir / "benchmark_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Converted dataset saved to: {dataset_path}")
    print(f"Cases: {len(converted.get('cases', []))}")

    if args.dry_run:
        print("Dry-run enabled; skipped run_rag_eval.")
        return

    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), check=False)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)

    print(f"MTRAG retrieval benchmark artifacts saved to: {output_dir}")


if __name__ == "__main__":
    main()
