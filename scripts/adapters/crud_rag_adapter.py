#!/usr/bin/env python3
"""Adapters for converting CRUD-RAG into this repo's rag_eval dataset schema."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Sequence

DEFAULT_TASKS: tuple[str, ...] = (
    "questanswer_1doc",
    "questanswer_2docs",
    "questanswer_3docs",
)

_MIN_ANCHOR_CHARS = 10
_TARGET_ANCHOR_CHARS = 24


def _clean_text(value: Any) -> str:
    return " ".join(str(value or "").split()).strip()


def _compact_text(value: Any) -> str:
    return re.sub(r"\s+", "", str(value or "")).strip()


def _extract_anchor(text: Any) -> str:
    compact = _compact_text(text)
    if not compact:
        return ""
    if "正文：" in compact:
        compact = compact.split("正文：", 1)[1]
    if len(compact) < _MIN_ANCHOR_CHARS:
        return ""

    start = min(12, max(0, len(compact) // 6))
    end = min(len(compact), start + _TARGET_ANCHOR_CHARS)
    anchor = compact[start:end]
    if len(anchor) < _MIN_ANCHOR_CHARS:
        anchor = compact[: min(len(compact), _TARGET_ANCHOR_CHARS)]
    return anchor.lower()


def load_crud_split_dataset(dataset_path: Path) -> Dict[str, List[Dict[str, Any]]]:
    raw = json.loads(dataset_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise ValueError("CRUD split dataset must be a JSON object keyed by task name.")

    normalized: Dict[str, List[Dict[str, Any]]] = {}
    for task_name, rows in raw.items():
        if not isinstance(rows, list):
            continue
        normalized[str(task_name)] = [item for item in rows if isinstance(item, dict)]
    return normalized


def build_rag_eval_dataset_from_crud(
    *,
    crud_data: Dict[str, List[Dict[str, Any]]],
    kb_ids: Sequence[str],
    tasks: Sequence[str],
    per_task_max: int,
    top_k: int,
    dataset_name: str,
) -> Dict[str, Any]:
    if not kb_ids:
        raise ValueError("kb_ids cannot be empty.")

    normalized_kb_ids = [str(item).strip() for item in kb_ids if str(item).strip()]
    if not normalized_kb_ids:
        raise ValueError("kb_ids cannot be empty after normalization.")

    cases: List[Dict[str, Any]] = []
    safe_top_k = max(1, int(top_k))
    safe_per_task_max = max(1, int(per_task_max))

    for task_name in tasks:
        rows = list(crud_data.get(task_name) or [])
        if not rows:
            continue

        for index, row in enumerate(rows[:safe_per_task_max], start=1):
            query = _clean_text(row.get("questions") or row.get("question") or row.get("event"))
            if not query:
                continue

            source_id = _clean_text(row.get("ID") or f"{task_name}_{index:05d}")
            keywords: List[str] = []

            event_anchor = _extract_anchor(row.get("event"))
            if event_anchor:
                keywords.append(event_anchor)

            for field in ("news1", "news2", "news3", "text", "beginning"):
                anchor = _extract_anchor(row.get(field))
                if anchor and anchor not in keywords:
                    keywords.append(anchor)
                if len(keywords) >= 3:
                    break

            if not keywords:
                continue

            case_id = f"{task_name}_{index:05d}_{source_id}"
            cases.append(
                {
                    "id": case_id,
                    "query": query,
                    "kb_ids": normalized_kb_ids,
                    "top_k": safe_top_k,
                    "expected": {
                        "keywords": keywords,
                    },
                    "meta": {
                        "task": task_name,
                        "source_id": source_id,
                    },
                }
            )

    return {
        "name": dataset_name,
        "description": (
            "Converted from CRUD-RAG split_merged quest-answer tasks. "
            "Expected targets use source-text anchors as keyword labels."
        ),
        "default_kb_ids": normalized_kb_ids,
        "cases": cases,
    }

