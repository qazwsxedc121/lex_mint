#!/usr/bin/env python3
"""Profile import pipeline hotspots (YAML metadata IO vs processing)."""

from __future__ import annotations

import argparse
import asyncio
import cProfile
import pstats
import sys
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Callable, Dict, List

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.models.knowledge_base import KnowledgeBase, KnowledgeBaseDocument, KnowledgeBasesConfig
from src.api.services.document_processing_service import DocumentProcessingService
from src.api.services.knowledge_base_service import KnowledgeBaseService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Profile metadata IO and processing costs.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("learn_proj/CRUD_RAG/data/80000_docs"),
        help="CRUD corpus directory.",
    )
    parser.add_argument(
        "--file-glob",
        default="documents*",
        help="Source file glob under source-dir.",
    )
    parser.add_argument(
        "--samples",
        type=int,
        default=20,
        help="Number of documents to profile.",
    )
    parser.add_argument(
        "--profile-out",
        type=Path,
        default=Path("logs/profile_import_pipeline.pstats"),
        help="cProfile output path.",
    )
    return parser.parse_args()


def _iter_samples(source_dir: Path, file_glob: str, limit: int) -> List[Dict[str, object]]:
    rows: List[Dict[str, object]] = []
    for bundle in sorted(p for p in source_dir.glob(file_glob) if p.is_file()):
        with bundle.open("r", encoding="utf-8", errors="ignore") as handle:
            for line_no, raw in enumerate(handle, start=1):
                text = str(raw or "").strip()
                if not text:
                    continue
                rows.append(
                    {
                        "bundle": bundle.name,
                        "line_no": line_no,
                        "content": text,
                    }
                )
                if len(rows) >= limit:
                    return rows
    return rows


class Metrics:
    def __init__(self) -> None:
        self._values: Dict[str, List[float]] = defaultdict(list)

    def add(self, key: str, seconds: float) -> None:
        self._values[key].append(float(seconds))

    def summary_lines(self) -> List[str]:
        lines: List[str] = []
        for key in sorted(self._values):
            vals = sorted(self._values[key])
            if not vals:
                continue
            count = len(vals)
            avg = sum(vals) / count
            p50 = vals[count // 2]
            p95 = vals[min(count - 1, int(count * 0.95))]
            p99 = vals[min(count - 1, int(count * 0.99))]
            lines.append(
                f"{key}: count={count} avg_ms={avg*1000:.2f} p50_ms={p50*1000:.2f} "
                f"p95_ms={p95*1000:.2f} p99_ms={p99*1000:.2f}"
            )
        return lines


async def _run_profile(args: argparse.Namespace) -> None:
    samples = _iter_samples(args.source_dir, args.file_glob, max(1, int(args.samples)))
    if not samples:
        raise RuntimeError("No samples found to profile.")

    metrics = Metrics()
    kb_service = KnowledgeBaseService()
    processor = DocumentProcessingService()
    kb_id = f"kb_profile_{uuid.uuid4().hex[:8]}"
    kb = KnowledgeBase(id=kb_id, name="tmp profile kb")

    # monkeypatches for deep timings
    orig_load_config = KnowledgeBaseService.load_config
    orig_save_config = KnowledgeBaseService.save_config
    orig_get_kb = KnowledgeBaseService.get_knowledge_base
    orig_yaml_load = yaml.safe_load
    orig_yaml_dump = yaml.safe_dump
    orig_model_dump = KnowledgeBasesConfig.model_dump

    async def wrap_load_config(self):
        t0 = time.perf_counter()
        out = await orig_load_config(self)
        metrics.add("kb.load_config.total", time.perf_counter() - t0)
        return out

    async def wrap_save_config(self, config):
        t0 = time.perf_counter()
        out = await orig_save_config(self, config)
        metrics.add("kb.save_config.total", time.perf_counter() - t0)
        return out

    async def wrap_get_kb(self, *a, **kw):
        t0 = time.perf_counter()
        out = await orig_get_kb(self, *a, **kw)
        metrics.add("kb.get_knowledge_base.total", time.perf_counter() - t0)
        return out

    def wrap_yaml_load(*a, **kw):
        t0 = time.perf_counter()
        out = orig_yaml_load(*a, **kw)
        metrics.add("yaml.safe_load.total", time.perf_counter() - t0)
        return out

    def wrap_yaml_dump(*a, **kw):
        t0 = time.perf_counter()
        out = orig_yaml_dump(*a, **kw)
        metrics.add("yaml.safe_dump.total", time.perf_counter() - t0)
        return out

    def wrap_model_dump(self, *a, **kw):
        t0 = time.perf_counter()
        out = orig_model_dump(self, *a, **kw)
        metrics.add("pydantic.model_dump.total", time.perf_counter() - t0)
        return out

    KnowledgeBaseService.load_config = wrap_load_config
    KnowledgeBaseService.save_config = wrap_save_config
    KnowledgeBaseService.get_knowledge_base = wrap_get_kb
    yaml.safe_load = wrap_yaml_load
    yaml.safe_dump = wrap_yaml_dump
    KnowledgeBasesConfig.model_dump = wrap_model_dump

    profiler = cProfile.Profile()
    await kb_service.add_knowledge_base(kb)

    try:
        profiler.enable()
        for index, sample in enumerate(samples):
            doc_id = f"prof_{index:04d}_{int(sample['line_no']):06d}"
            filename = f"{doc_id}.txt"
            content = str(sample["content"])
            path = kb_service.get_document_storage_path(kb_id, doc_id, filename)

            t0 = time.perf_counter()
            path.write_text(content + "\n", encoding="utf-8")
            size = int(path.stat().st_size)
            metrics.add("io.write_file.total", time.perf_counter() - t0)

            doc = KnowledgeBaseDocument(
                id=doc_id,
                kb_id=kb_id,
                filename=filename,
                file_type=".txt",
                file_size=size,
                status="pending",
            )

            t1 = time.perf_counter()
            await kb_service.add_document(doc)
            metrics.add("kb.add_document.total", time.perf_counter() - t1)

            t2 = time.perf_counter()
            chunk_count = await processor.process_document(
                kb_id,
                doc_id,
                filename,
                ".txt",
                str(path),
                track_status=False,
            )
            metrics.add("rag.process_document.total", time.perf_counter() - t2)

            t3 = time.perf_counter()
            await kb_service.update_document_status(
                kb_id,
                doc_id,
                "ready",
                chunk_count=int(chunk_count or 0),
            )
            metrics.add("kb.update_document_status.total", time.perf_counter() - t3)
        profiler.disable()
    finally:
        try:
            await kb_service.delete_knowledge_base(kb_id)
        finally:
            # restore monkeypatches
            KnowledgeBaseService.load_config = orig_load_config
            KnowledgeBaseService.save_config = orig_save_config
            KnowledgeBaseService.get_knowledge_base = orig_get_kb
            yaml.safe_load = orig_yaml_load
            yaml.safe_dump = orig_yaml_dump
            KnowledgeBasesConfig.model_dump = orig_model_dump

    args.profile_out.parent.mkdir(parents=True, exist_ok=True)
    profiler.dump_stats(str(args.profile_out))

    print(f"samples={len(samples)} profile_out={args.profile_out}")
    for line in metrics.summary_lines():
        print(line)

    print("top_cumulative:")
    stats = pstats.Stats(profiler)
    stats.sort_stats("cumulative")
    stats.print_stats(20)


def main() -> None:
    args = parse_args()
    asyncio.run(_run_profile(args))


if __name__ == "__main__":
    main()
