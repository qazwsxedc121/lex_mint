#!/usr/bin/env python3
"""Adapters for converting MTRAG retrieval tasks into run_rag_eval schema."""

from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Sequence


def sanitize_doc_id(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    return re.sub(r"[^A-Za-z0-9._-]+", "_", text)


def to_mtrag_filename(*, domain: str, corpus_id: str) -> str:
    safe_domain = sanitize_doc_id(domain)
    safe_id = sanitize_doc_id(corpus_id)
    return f"mtrag_{safe_domain}_{safe_id}.txt"


def clean_query_text(text: Any) -> str:
    query = str(text or "").strip()
    if not query:
        return ""
    # remove optional "|user|:" prefixes in MTRAG query files
    query = re.sub(r"\|user\|\s*:\s*", "", query, flags=re.IGNORECASE).strip()
    return query


def load_queries(path: Path) -> Dict[str, str]:
    queries: Dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        raw = str(line or "").strip()
        if not raw:
            continue
        row = json.loads(raw)
        qid = str(row.get("_id") or row.get("id") or "").strip()
        query = clean_query_text(row.get("text") or row.get("query"))
        if not qid or not query:
            continue
        queries[qid] = query
    return queries


def load_qrels(path: Path) -> Dict[str, Dict[str, float]]:
    qrels: Dict[str, Dict[str, float]] = {}
    with path.open("r", encoding="utf-8") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            qid = str(row.get("query-id") or row.get("query_id") or "").strip()
            doc_id = str(row.get("corpus-id") or row.get("doc-id") or "").strip()
            score_raw = row.get("score", 1)
            if not qid or not doc_id:
                continue
            try:
                score = float(score_raw)
            except Exception:
                score = 1.0
            qrels.setdefault(qid, {})[doc_id] = score
    return qrels


def build_rag_eval_dataset_from_mtrag(
    *,
    queries: Mapping[str, str],
    qrels: Mapping[str, Mapping[str, float]],
    kb_ids: Sequence[str],
    domain: str,
    dataset_name: str,
    top_k: int,
    max_cases: int | None = None,
) -> Dict[str, Any]:
    if not kb_ids:
        raise ValueError("kb_ids cannot be empty.")

    normalized_kb_ids = [str(item).strip() for item in kb_ids if str(item).strip()]
    if not normalized_kb_ids:
        raise ValueError("kb_ids cannot be empty after normalization.")

    safe_top_k = max(1, int(top_k))
    safe_max_cases = None if max_cases is None else max(1, int(max_cases))

    cases: List[Dict[str, Any]] = []
    count = 0
    for qid in sorted(queries.keys()):
        if qid not in qrels:
            continue
        query = str(queries[qid]).strip()
        if not query:
            continue
        rel_docs = qrels[qid]
        filenames = [
            to_mtrag_filename(domain=domain, corpus_id=doc_id)
            for doc_id, score in rel_docs.items()
            if float(score) > 0
        ]
        if not filenames:
            continue

        case = {
            "id": qid,
            "query": query,
            "kb_ids": normalized_kb_ids,
            "top_k": safe_top_k,
            "expected": {
                "filenames": sorted(set(filenames)),
            },
            "meta": {
                "domain": domain,
                "qid": qid,
                "relevant_doc_count": len(filenames),
            },
        }
        cases.append(case)
        count += 1
        if safe_max_cases is not None and count >= safe_max_cases:
            break

    return {
        "name": dataset_name,
        "description": (
            "Converted from MTRAG retrieval tasks (BEIR format). "
            "Expected targets are relevant corpus filenames from qrels."
        ),
        "default_kb_ids": normalized_kb_ids,
        "cases": cases,
    }

