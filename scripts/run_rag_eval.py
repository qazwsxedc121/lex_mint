#!/usr/bin/env python3
"""Run labeled RAG retrieval evaluation and export benchmark artifacts.

Dataset schema (JSON):
{
  "name": "dataset-name",
  "description": "optional",
  "cases": [
    {
      "id": "case-id",
      "query": "user query",
      "kb_ids": ["kb_a"],
      "top_k": 5,
      "score_threshold": 0.3,
      "expected": {
        "doc_ids": ["doc_1"],
        "filenames": ["manual.md"],
        "keywords": ["optional phrase"]
      }
    }
  ]
}
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.services.rag_service import RagResult, RagService


@dataclass
class EvalCase:
    case_id: str
    query: str
    kb_ids: List[str]
    top_k: Optional[int]
    score_threshold: Optional[float]
    doc_ids: Set[str]
    filenames: Set[str]
    keywords: Set[str]
    expect_none: bool

    @property
    def has_targets(self) -> bool:
        return self.expect_none or bool(self.doc_ids or self.filenames or self.keywords)

    @property
    def uses_keyword_targets_only(self) -> bool:
        return not (self.doc_ids or self.filenames)

    def target_count(self) -> int:
        if self.expect_none:
            return 0
        if not self.uses_keyword_targets_only:
            return len(self.doc_ids) + len(self.filenames)
        return len(self.keywords)


def _as_lower_set(values: Optional[Iterable[Any]]) -> Set[str]:
    if not values:
        return set()
    items: Set[str] = set()
    for item in values:
        text = str(item or "").strip().lower()
        if text:
            items.add(text)
    return items


def _load_cases(dataset_path: Path) -> Tuple[Dict[str, Any], List[EvalCase]]:
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    raw_cases = raw.get("cases", [])
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Dataset must include a non-empty 'cases' array.")

    normalized: List[EvalCase] = []
    default_kb_ids = raw.get("default_kb_ids", [])
    for index, item in enumerate(raw_cases, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Case #{index} must be an object.")

        case_id = str(item.get("id") or f"case_{index:03d}").strip()
        query = str(item.get("query") or "").strip()
        if not query:
            raise ValueError(f"Case '{case_id}' is missing query.")

        kb_ids = item.get("kb_ids", default_kb_ids)
        if not isinstance(kb_ids, list):
            raise ValueError(f"Case '{case_id}' has invalid kb_ids; expected list.")
        kb_ids = [str(v).strip() for v in kb_ids if str(v).strip()]
        if not kb_ids:
            raise ValueError(f"Case '{case_id}' has empty kb_ids.")

        expected = item.get("expected", {})
        if not isinstance(expected, dict):
            raise ValueError(f"Case '{case_id}' has invalid expected object.")

        doc_ids = _as_lower_set(expected.get("doc_ids") or item.get("expected_doc_ids"))
        filenames = _as_lower_set(expected.get("filenames") or item.get("expected_filenames"))
        keywords = _as_lower_set(expected.get("keywords") or item.get("expected_keywords"))
        expect_none = bool(item.get("expect_none") or expected.get("none"))
        if expect_none and (doc_ids or filenames or keywords):
            raise ValueError(
                f"Case '{case_id}' cannot set expect_none together with expected targets."
            )

        case = EvalCase(
            case_id=case_id,
            query=query,
            kb_ids=kb_ids,
            top_k=item.get("top_k"),
            score_threshold=item.get("score_threshold"),
            doc_ids=doc_ids,
            filenames=filenames,
            keywords=keywords,
            expect_none=expect_none,
        )
        if not case.has_targets:
            raise ValueError(
                f"Case '{case_id}' has no expected targets. "
                "Provide doc_ids, filenames, or keywords."
            )
        normalized.append(case)

    return raw, normalized


def _match_targets(case: EvalCase, result: RagResult) -> Set[str]:
    matched: Set[str] = set()
    doc_id = (result.doc_id or "").strip().lower()
    filename = (result.filename or "").strip().lower()
    content = (result.content or "").strip().lower()

    # Strict mode:
    # - If doc_id/filename labels exist, recall is measured only on those labels.
    # - Keywords act as fallback labels only when no doc/file labels are provided.
    if not case.uses_keyword_targets_only:
        if doc_id and doc_id in case.doc_ids:
            matched.add(f"doc:{doc_id}")
        if filename and filename in case.filenames:
            matched.add(f"file:{filename}")
    else:
        for keyword in case.keywords:
            if keyword and keyword in content:
                matched.add(f"kw:{keyword}")
    return matched


def _evaluate_case(case: EvalCase, results: Sequence[RagResult], top_k: int) -> Dict[str, Any]:
    capped = list(results[: max(1, int(top_k))])
    if case.expect_none:
        no_answer_success = 1.0 if len(capped) == 0 else 0.0
        return {
            "case_id": case.case_id,
            "top_k": top_k,
            "expect_none": True,
            "target_type": "none",
            "target_count": 0,
            "matched_target_count": 0,
            "hit_at_k": no_answer_success,
            "citation_hit": no_answer_success,
            "mrr": no_answer_success,
            "precision_at_k": 0.0,
            "recall_at_k": 0.0,
            "first_relevant_rank": None,
            "relevant_ranks": [],
            "no_answer_success": no_answer_success,
        }

    total_targets = case.target_count()
    seen_targets: Set[str] = set()
    relevant_ranks: List[int] = []

    for rank, item in enumerate(capped, start=1):
        matched = _match_targets(case, item)
        if matched:
            relevant_ranks.append(rank)
            seen_targets.update(matched)

    hit = 1.0 if relevant_ranks else 0.0
    first_rank = relevant_ranks[0] if relevant_ranks else None
    mrr = (1.0 / first_rank) if first_rank else 0.0
    precision_at_k = (len(relevant_ranks) / max(1, top_k))
    recall_at_k = (len(seen_targets) / max(1, total_targets))

    return {
        "case_id": case.case_id,
        "top_k": top_k,
        "expect_none": False,
        "target_type": "keyword" if case.uses_keyword_targets_only else "doc_file",
        "target_count": total_targets,
        "matched_target_count": len(seen_targets),
        "hit_at_k": hit,
        "citation_hit": hit,
        "mrr": mrr,
        "precision_at_k": precision_at_k,
        "recall_at_k": recall_at_k,
        "first_relevant_rank": first_rank,
        "relevant_ranks": relevant_ranks,
        "no_answer_success": None,
    }


def _summarize_mode(mode: str, case_rows: Sequence[Dict[str, Any]]) -> Dict[str, Any]:
    if not case_rows:
        return {
            "mode": mode,
            "case_count": 0,
            "hit_rate": 0.0,
            "citation_hit_rate": 0.0,
            "mean_mrr": 0.0,
            "mean_precision_at_k": 0.0,
            "mean_recall_at_k": 0.0,
            "answerable_case_count": 0,
            "no_answer_case_count": 0,
            "no_answer_success_rate": 0.0,
            "overall_pass_rate": 0.0,
        }

    answerable_rows = [row for row in case_rows if not bool(row.get("expect_none", False))]
    no_answer_rows = [row for row in case_rows if bool(row.get("expect_none", False))]

    if answerable_rows:
        hit_rate = mean(row["hit_at_k"] for row in answerable_rows)
        citation_hit_rate = mean(row["citation_hit"] for row in answerable_rows)
        mean_mrr = mean(row["mrr"] for row in answerable_rows)
        mean_precision = mean(row["precision_at_k"] for row in answerable_rows)
        mean_recall = mean(row["recall_at_k"] for row in answerable_rows)
    else:
        hit_rate = 0.0
        citation_hit_rate = 0.0
        mean_mrr = 0.0
        mean_precision = 0.0
        mean_recall = 0.0

    no_answer_success_rate = (
        mean(float(row.get("no_answer_success", 0.0) or 0.0) for row in no_answer_rows)
        if no_answer_rows
        else 0.0
    )
    pass_sum = sum(float(row.get("hit_at_k", 0.0) or 0.0) for row in answerable_rows) + sum(
        float(row.get("no_answer_success", 0.0) or 0.0) for row in no_answer_rows
    )

    return {
        "mode": mode,
        "case_count": len(case_rows),
        "hit_rate": hit_rate,
        "citation_hit_rate": citation_hit_rate,
        "mean_mrr": mean_mrr,
        "mean_precision_at_k": mean_precision,
        "mean_recall_at_k": mean_recall,
        "answerable_case_count": len(answerable_rows),
        "no_answer_case_count": len(no_answer_rows),
        "no_answer_success_rate": no_answer_success_rate,
        "overall_pass_rate": pass_sum / max(1, len(case_rows)),
    }


def _build_report(
    *,
    dataset_name: str,
    dataset_path: Path,
    summaries: Sequence[Dict[str, Any]],
    output_dir: Path,
) -> str:
    lines = [
        "# RAG Retrieval Evaluation Report",
        "",
        f"- Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- Dataset: `{dataset_name}`",
        f"- Dataset file: `{dataset_path}`",
        f"- Output dir: `{output_dir}`",
        "",
        "## Mode Summary",
        "",
        "| Mode | Cases | Hit Rate | Citation Hit | Mean MRR | Mean P@K | Mean Recall@K |",
        "|------|------:|---------:|-------------:|---------:|---------:|--------------:|",
    ]
    for item in summaries:
        lines.append(
            "| {mode} | {case_count} | {hit_rate:.3f} | {citation_hit_rate:.3f} | "
            "{mean_mrr:.3f} | {mean_precision_at_k:.3f} | {mean_recall_at_k:.3f} |".format(**item)
        )

    lines.extend(
        [
            "",
            "## Extra Metrics",
            "",
            "| Mode | Answerable Cases | No-Answer Cases | No-Answer Success | Overall Pass |",
            "|------|-----------------:|----------------:|------------------:|-------------:|",
        ]
    )
    for item in summaries:
        lines.append(
            "| {mode} | {answerable_case_count} | {no_answer_case_count} | "
            "{no_answer_success_rate:.3f} | {overall_pass_rate:.3f} |".format(**item)
        )

    if summaries:
        best_mode = max(summaries, key=lambda row: (row["mean_mrr"], row["mean_recall_at_k"]))
        lines.extend(
            [
                "",
                "## Recommendation",
                "",
                f"- Best mode by MRR/Recall: `{best_mode['mode']}`",
                "- Use this as the default candidate for the current dataset.",
            ]
        )

    return "\n".join(lines) + "\n"


async def _evaluate_mode(
    *,
    mode: str,
    cases: Sequence[EvalCase],
    top_k_override: Optional[int],
    score_threshold_override: Optional[float],
    bm25_min_term_coverage_override: Optional[float],
) -> Dict[str, Any]:
    service = RagService()
    retrieval_cfg = service.rag_config_service.config.retrieval
    retrieval_cfg.retrieval_mode = mode

    if top_k_override is not None:
        retrieval_cfg.top_k = max(1, int(top_k_override))
    if score_threshold_override is not None:
        retrieval_cfg.score_threshold = float(score_threshold_override)
    if bm25_min_term_coverage_override is not None:
        retrieval_cfg.bm25_min_term_coverage = max(
            0.0,
            min(1.0, float(bm25_min_term_coverage_override)),
        )

    case_outputs: List[Dict[str, Any]] = []
    for case in cases:
        local_top_k = (
            max(1, int(top_k_override))
            if top_k_override is not None
            else max(1, int(case.top_k or retrieval_cfg.top_k))
        )
        local_threshold = (
            float(score_threshold_override)
            if score_threshold_override is not None
            else (
                float(case.score_threshold)
                if case.score_threshold is not None
                else float(retrieval_cfg.score_threshold)
            )
        )

        try:
            results, diagnostics = await service.retrieve_with_diagnostics(
                query=case.query,
                kb_ids=case.kb_ids,
                top_k=local_top_k,
                score_threshold=local_threshold,
            )
            row = _evaluate_case(case, results, local_top_k)
            row.update(
                {
                    "query": case.query,
                    "kb_ids": case.kb_ids,
                    "score_threshold": local_threshold,
                    "result_count": len(results),
                    "results": [item.to_dict() for item in results],
                    "diagnostics": diagnostics,
                }
            )
            case_outputs.append(row)
        except Exception as exc:
            case_outputs.append(
                {
                    "case_id": case.case_id,
                    "query": case.query,
                    "kb_ids": case.kb_ids,
                    "error": str(exc),
                }
            )

    metric_rows = [row for row in case_outputs if "error" not in row]
    summary = _summarize_mode(mode, metric_rows)
    return {
        "mode": mode,
        "summary": summary,
        "cases": case_outputs,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run RAG retrieval evaluation on labeled dataset.")
    parser.add_argument(
        "--dataset",
        type=Path,
        default=Path("docs/rag_eval_dataset.example.json"),
        help="Path to JSON dataset file.",
    )
    parser.add_argument(
        "--modes",
        type=str,
        default="vector,bm25,hybrid",
        help="Comma-separated retrieval modes to evaluate.",
    )
    parser.add_argument(
        "--top-k",
        type=int,
        default=None,
        help="Optional top_k override for all cases.",
    )
    parser.add_argument(
        "--score-threshold",
        type=float,
        default=None,
        help="Optional score_threshold override for all cases.",
    )
    parser.add_argument(
        "--bm25-min-term-coverage",
        type=float,
        default=None,
        help="Optional BM25 lexical coverage threshold override (0-1).",
    )
    parser.add_argument(
        "--max-cases",
        type=int,
        default=None,
        help="Optional cap of evaluated cases from the dataset.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional output directory (default: data/benchmarks/rag_eval_<timestamp>).",
    )
    return parser.parse_args()


async def _main() -> None:
    args = parse_args()
    dataset_path = args.dataset
    if not dataset_path.exists():
        raise FileNotFoundError(f"Dataset not found: {dataset_path}")

    raw_dataset, cases = _load_cases(dataset_path)
    if args.max_cases is not None:
        cases = cases[: max(1, int(args.max_cases))]

    modes = [item.strip().lower() for item in args.modes.split(",") if item.strip()]
    supported_modes = {"vector", "bm25", "hybrid"}
    for mode in modes:
        if mode not in supported_modes:
            raise ValueError(f"Unsupported mode '{mode}', expected one of {sorted(supported_modes)}.")

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = args.output_dir or (Path("data") / "benchmarks" / f"rag_eval_{timestamp}")
    output_dir.mkdir(parents=True, exist_ok=True)

    mode_outputs: List[Dict[str, Any]] = []
    for mode in modes:
        mode_result = await _evaluate_mode(
            mode=mode,
            cases=cases,
            top_k_override=args.top_k,
            score_threshold_override=args.score_threshold,
            bm25_min_term_coverage_override=args.bm25_min_term_coverage,
        )
        mode_outputs.append(mode_result)
        (output_dir / f"mode_{mode}_cases.json").write_text(
            json.dumps(mode_result["cases"], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    summaries = [item["summary"] for item in mode_outputs]
    report = _build_report(
        dataset_name=str(raw_dataset.get("name", "unnamed-dataset")),
        dataset_path=dataset_path,
        summaries=summaries,
        output_dir=output_dir,
    )

    summary_payload = {
        "dataset": {
            "name": raw_dataset.get("name", "unnamed-dataset"),
            "description": raw_dataset.get("description", ""),
            "path": str(dataset_path),
            "case_count": len(cases),
        },
        "summaries": summaries,
    }
    (output_dir / "summary.json").write_text(
        json.dumps(summary_payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_dir / "report.md").write_text(report, encoding="utf-8")
    (output_dir / "dataset_snapshot.json").write_text(
        json.dumps(raw_dataset, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Saved RAG eval artifacts to: {output_dir}")
    for summary in summaries:
        print(
            "mode={mode} cases={case_count} hit={hit_rate:.3f} "
            "mrr={mean_mrr:.3f} recall={mean_recall_at_k:.3f}".format(**summary)
        )


if __name__ == "__main__":
    asyncio.run(_main())
