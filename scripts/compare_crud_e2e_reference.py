#!/usr/bin/env python3
"""Compare local CRUD E2E results against fixed public reference baselines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean
from typing import Dict, Tuple

import yaml


def _load_reference(path: Path, model_key: str) -> Dict[str, float]:
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    models = (((data.get("reference") or {}).get("models")) or {})
    if model_key not in models:
        raise KeyError(f"Unknown baseline model '{model_key}'. Available: {', '.join(sorted(models))}")
    task_scores = (models[model_key].get("task_ragquesteval_recall")) or {}
    if not task_scores:
        raise ValueError(f"No task_ragquesteval_recall found for '{model_key}'.")
    return {str(k): float(v) for k, v in task_scores.items()}


def _extract_task_scores(payload: Dict[str, object]) -> Dict[str, float]:
    scores: Dict[str, float] = {}
    task_metrics = payload.get("task_metrics")
    if isinstance(task_metrics, dict):
        for task, metrics in task_metrics.items():
            if isinstance(metrics, dict) and "ragquesteval_recall" in metrics:
                scores[str(task)] = float(metrics["ragquesteval_recall"])

    if not scores:
        # Backward-compatible shape:
        # {"ragquesteval_recall": {"task_a": 12.3, "task_b": 45.6}}
        maybe_nested = payload.get("ragquesteval_recall")
        if isinstance(maybe_nested, dict):
            for task, value in maybe_nested.items():
                scores[str(task)] = float(value)

    if not scores:
        raise ValueError(
            "Cannot find task scores. Expected one of: "
            "task_metrics.<task>.ragquesteval_recall or ragquesteval_recall.<task>."
        )

    # Auto-normalize [0,1] to percentage scale when needed.
    max_value = max(scores.values())
    if max_value <= 1.5:
        scores = {k: (v * 100.0) for k, v in scores.items()}
    return scores


def _compute(candidate: Dict[str, float], reference: Dict[str, float]) -> Tuple[Dict[str, object], Dict[str, object]]:
    common_tasks = sorted(set(candidate).intersection(reference))
    if not common_tasks:
        raise ValueError("No overlapping tasks between candidate result and reference baseline.")

    rows = []
    for task in common_tasks:
        cand = candidate[task]
        ref = reference[task]
        gap = cand - ref
        ratio = (cand / ref) if ref else 0.0
        rows.append(
            {
                "task": task,
                "candidate": round(cand, 4),
                "reference": round(ref, 4),
                "gap": round(gap, 4),
                "ratio": round(ratio, 4),
            }
        )

    cand_macro = mean(candidate[t] for t in common_tasks)
    ref_macro = mean(reference[t] for t in common_tasks)
    summary = {
        "task_count": len(common_tasks),
        "candidate_macro": round(cand_macro, 4),
        "reference_macro": round(ref_macro, 4),
        "macro_gap": round(cand_macro - ref_macro, 4),
        "macro_ratio": round((cand_macro / ref_macro) if ref_macro else 0.0, 4),
    }
    return {"tasks": common_tasks, "rows": rows}, summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare CRUD E2E result against reference baselines.")
    parser.add_argument("--result", type=Path, required=True, help="Path to local E2E result JSON.")
    parser.add_argument(
        "--reference",
        type=Path,
        default=Path("config/benchmarks/crud_e2e_reference_v1.yaml"),
        help="Path to reference baseline YAML.",
    )
    parser.add_argument(
        "--baseline-model",
        type=str,
        default="gpt4o",
        help="Reference model key in YAML (for example: gpt4o, qwen2_7b).",
    )
    parser.add_argument("--output", type=Path, default=None, help="Optional output JSON path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    result_payload = json.loads(args.result.read_text(encoding="utf-8"))
    candidate_scores = _extract_task_scores(result_payload)
    reference_scores = _load_reference(args.reference, args.baseline_model)

    detail, summary = _compute(candidate_scores, reference_scores)
    report = {
        "baseline_model": args.baseline_model,
        "result_file": str(args.result),
        "reference_file": str(args.reference),
        "summary": summary,
        "rows": detail["rows"],
    }

    print(
        "baseline={baseline} tasks={task_count} candidate_macro={candidate_macro:.4f} "
        "reference_macro={reference_macro:.4f} macro_gap={macro_gap:.4f} macro_ratio={macro_ratio:.4f}".format(
            baseline=args.baseline_model,
            **summary,
        )
    )
    for row in report["rows"]:
        print(
            "{task}: cand={candidate:.4f} ref={reference:.4f} gap={gap:.4f} ratio={ratio:.4f}".format(
                **row
            )
        )

    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"saved={args.output}")


if __name__ == "__main__":
    main()
