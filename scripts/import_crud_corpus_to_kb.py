#!/usr/bin/env python3
"""Specialized CRUD corpus importer using the standard KB upload pipeline."""

from __future__ import annotations

import argparse
import asyncio
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.models.knowledge_base import KnowledgeBaseDocument
from src.api.services.document_processing_service import DocumentProcessingService
from src.api.services.knowledge_base_service import KnowledgeBaseService
from src.api.services.rag_config_service import RagConfigService


@dataclass
class ImportStats:
    planned: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0

    @property
    def processed(self) -> int:
        return self.imported + self.skipped + self.failed


@dataclass
class ImportOutcome:
    doc_id: str
    bundle: str
    line_no: int
    ok: bool
    error: str = ""
    doc: Optional[KnowledgeBaseDocument] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import CRUD-RAG 80000_docs with the normal KB upload processing flow."
    )
    parser.add_argument("--kb-id", required=True, help="Target KB id.")
    parser.add_argument(
        "--source-dir",
        type=Path,
        default=Path("learn_proj/CRUD_RAG/data/80000_docs"),
        help="CRUD source folder containing documents_* bundle files.",
    )
    parser.add_argument(
        "--file-glob",
        default="documents*",
        help="File glob pattern under source-dir.",
    )
    parser.add_argument(
        "--start-offset",
        type=int,
        default=0,
        help="Skip first N corpus records in sorted order.",
    )
    parser.add_argument(
        "--max-docs",
        type=int,
        default=None,
        help="Optional cap for this run.",
    )
    parser.add_argument(
        "--lines-per-doc",
        type=int,
        default=1,
        help="Merge N corpus lines into one imported document (default: 1).",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Concurrent processing workers (default: 1).",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip documents already present in KB config.",
    )
    parser.add_argument(
        "--allow-api-embedding",
        action="store_true",
        help="Allow imports when embedding provider is API-based.",
    )
    parser.add_argument(
        "--allow-cpu-embedding",
        action="store_true",
        help="Allow local embedding without GPU offload.",
    )
    parser.add_argument(
        "--continue-on-error",
        action="store_true",
        help="Continue importing after failures.",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=100,
        help="Progress log interval.",
    )
    parser.add_argument(
        "--metadata-flush-size",
        type=int,
        default=50,
        help="Flush ready document metadata every N successful imports.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Plan only; do not write files or index.",
    )
    return parser.parse_args()


def _open_text_file(path: Path):
    encodings = ("utf-8", "utf-8-sig", "gb18030", "latin-1")
    for enc in encodings:
        try:
            return path.open("r", encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.open("r", encoding="utf-8", errors="replace")


def _natural_sort_key(path: Path):
    # Keep numeric suffixes in human order (part_2 before part_10).
    return [int(token) if token.isdigit() else token.lower() for token in re.split(r"(\d+)", path.name)]


def _check_embedding_runtime(
    *,
    allow_api_embedding: bool,
    allow_cpu_embedding: bool,
) -> None:
    cfg = RagConfigService().config.embedding
    provider = str(cfg.provider or "").strip().lower()
    print(f"[embed] provider={provider}")

    if provider == "api":
        print(f"[embed] api_base_url={cfg.api_base_url}")
        print(f"[embed] api_model={cfg.api_model}")
        if not allow_api_embedding:
            raise RuntimeError(
                "Embedding provider is API-based. Refusing import without --allow-api-embedding."
            )
        return

    if provider == "local":
        device = str(cfg.local_device or "cpu").strip().lower()
        print(f"[embed] local_model={cfg.local_model}")
        print(f"[embed] local_device={device}")
        if "cuda" not in device and not allow_cpu_embedding:
            raise RuntimeError(
                "Local embedding is not CUDA. Refusing import without --allow-cpu-embedding."
            )
        return

    if provider == "local_gguf":
        n_gpu_layers = int(cfg.local_gguf_n_gpu_layers or 0)
        print(f"[embed] local_gguf_model_path={cfg.local_gguf_model_path}")
        print(f"[embed] local_gguf_n_gpu_layers={n_gpu_layers}")
        gpu_offload_supported: Optional[bool] = None
        try:
            import llama_cpp

            support_fn = getattr(llama_cpp, "llama_supports_gpu_offload", None)
            if callable(support_fn):
                gpu_offload_supported = bool(support_fn())
        except Exception:
            gpu_offload_supported = None
        print(f"[embed] gpu_offload_supported={gpu_offload_supported}")

        gpu_expected = n_gpu_layers > 0 and gpu_offload_supported is not False
        if not gpu_expected and not allow_cpu_embedding:
            raise RuntimeError(
                "GGUF embedding does not look GPU-offloaded. "
                "Refusing import without --allow-cpu-embedding."
            )
        return

    raise RuntimeError(f"Unsupported embedding provider: {provider}")


def _iter_corpus_records(
    files: List[Path],
    *,
    start_offset: int,
    max_docs: Optional[int],
    lines_per_doc: int,
) -> Iterator[Dict[str, object]]:
    seen = 0
    emitted = 0
    safe_offset = max(0, int(start_offset))
    safe_limit = None if max_docs is None else max(1, int(max_docs))
    safe_lines_per_doc = max(1, int(lines_per_doc))

    for bundle in files:
        stem = bundle.stem
        group_items: List[tuple[int, str]] = []
        with _open_text_file(bundle) as handle:
            for line_no, raw in enumerate(handle, start=1):
                content = str(raw or "").strip()
                if not content:
                    continue

                seen += 1
                if seen <= safe_offset:
                    continue

                if safe_lines_per_doc == 1:
                    doc_id = f"crud_{stem}_{line_no:06d}"
                    filename = f"{doc_id}.txt"
                    yield {
                        "doc_id": doc_id,
                        "filename": filename,
                        "content": content,
                        "bundle": bundle.name,
                        "line_no": line_no,
                    }
                    emitted += 1
                    if safe_limit is not None and emitted >= safe_limit:
                        return
                    continue

                group_items.append((line_no, content))
                if len(group_items) < safe_lines_per_doc:
                    continue

                start_line = int(group_items[0][0])
                end_line = int(group_items[-1][0])
                merged = "\n\n".join(item[1] for item in group_items)
                doc_id = f"crud_{stem}_{start_line:06d}_{end_line:06d}"
                filename = f"{doc_id}.txt"
                yield {
                    "doc_id": doc_id,
                    "filename": filename,
                    "content": merged,
                    "bundle": bundle.name,
                    "line_no": start_line,
                }
                group_items = []
                emitted += 1
                if safe_limit is not None and emitted >= safe_limit:
                    return

        if safe_lines_per_doc > 1 and group_items:
            start_line = int(group_items[0][0])
            end_line = int(group_items[-1][0])
            merged = "\n\n".join(item[1] for item in group_items)
            doc_id = f"crud_{stem}_{start_line:06d}_{end_line:06d}"
            filename = f"{doc_id}.txt"
            yield {
                "doc_id": doc_id,
                "filename": filename,
                "content": merged,
                "bundle": bundle.name,
                "line_no": start_line,
            }
            emitted += 1
            if safe_limit is not None and emitted >= safe_limit:
                return


def _print_progress(stats: ImportStats, *, progress_every: int, started_at: float) -> None:
    if stats.processed <= 0:
        return
    if stats.processed % progress_every != 0:
        return
    elapsed = max(0.001, time.perf_counter() - started_at)
    speed = stats.imported / elapsed
    print(
        f"[progress] planned={stats.planned} imported={stats.imported} "
        f"skipped={stats.skipped} failed={stats.failed} "
        f"elapsed_s={elapsed:.1f} import_per_s={speed:.2f}"
    )


async def _import_record(
    *,
    kb_service: KnowledgeBaseService,
    processor: DocumentProcessingService,
    kb_id: str,
    kb_snapshot,
    record: Dict[str, object],
) -> ImportOutcome:
    doc_id = str(record["doc_id"])
    filename = str(record["filename"])
    content = str(record["content"])
    bundle = str(record["bundle"])
    line_no = int(record["line_no"])

    storage_path = kb_service.get_document_storage_path(kb_id, doc_id, filename)
    try:
        storage_path.write_text(content + "\n", encoding="utf-8")
        file_size = int(storage_path.stat().st_size)

        chunk_count = await processor.process_document(
            kb_id,
            doc_id,
            filename,
            ".txt",
            str(storage_path),
            track_status=False,
            kb_snapshot=kb_snapshot,
        )
        doc = KnowledgeBaseDocument(
            id=doc_id,
            kb_id=kb_id,
            filename=filename,
            file_type=".txt",
            file_size=file_size,
            status="ready",
            chunk_count=int(chunk_count or 0),
        )
        return ImportOutcome(
            doc_id=doc_id,
            bundle=bundle,
            line_no=line_no,
            ok=True,
            doc=doc,
        )
    except Exception as exc:
        return ImportOutcome(
            doc_id=doc_id,
            bundle=bundle,
            line_no=line_no,
            ok=False,
            error=str(exc),
        )


async def _main() -> None:
    args = parse_args()
    _check_embedding_runtime(
        allow_api_embedding=bool(args.allow_api_embedding),
        allow_cpu_embedding=bool(args.allow_cpu_embedding),
    )

    kb_service = KnowledgeBaseService()
    kb = await kb_service.get_knowledge_base(args.kb_id)
    if kb is None:
        raise RuntimeError(f"Knowledge base not found: {args.kb_id}")

    if not args.source_dir.exists():
        raise RuntimeError(f"Source dir not found: {args.source_dir}")
    bundle_files = sorted(
        (p for p in args.source_dir.glob(args.file_glob) if p.is_file()),
        key=_natural_sort_key,
    )
    if not bundle_files:
        raise RuntimeError(
            f"No files matched in {args.source_dir} with glob '{args.file_glob}'."
        )

    worker_count = max(1, int(args.workers))
    metadata_flush_size = max(1, int(args.metadata_flush_size))
    print(f"[run] workers={worker_count}")
    print(f"[run] lines_per_doc={max(1, int(args.lines_per_doc))}")
    print(f"[run] metadata_flush_size={metadata_flush_size}")

    processor_pool = [DocumentProcessingService() for _ in range(worker_count)]

    existing_doc_ids = set()
    if args.skip_existing:
        existing = await kb_service.get_documents(args.kb_id)
        existing_doc_ids = {str(item.id) for item in existing}
        print(f"[resume] existing docs in KB={len(existing_doc_ids)}")

    stats = ImportStats()
    progress_every = max(1, int(args.progress_every))
    started_at = time.perf_counter()
    pending: set[asyncio.Task[ImportOutcome]] = set()
    worker_cursor = 0
    ready_doc_buffer: List[KnowledgeBaseDocument] = []

    async def _flush_ready_docs(*, force: bool = False) -> None:
        nonlocal ready_doc_buffer
        if not ready_doc_buffer:
            return
        if not force and len(ready_doc_buffer) < metadata_flush_size:
            return
        batch = ready_doc_buffer
        ready_doc_buffer = []
        await kb_service.add_documents_bulk(batch)
        print(f"[meta] flushed_ready_docs={len(batch)}")

    async def _drain_one() -> None:
        nonlocal pending
        done, remaining = await asyncio.wait(
            pending,
            return_when=asyncio.FIRST_COMPLETED,
        )
        pending = set(remaining)
        for task in done:
            outcome = await task
            if outcome.ok:
                stats.imported += 1
                existing_doc_ids.add(outcome.doc_id)
                if outcome.doc is not None:
                    ready_doc_buffer.append(outcome.doc)
                    await _flush_ready_docs()
            else:
                stats.failed += 1
                print(
                    f"[error] {outcome.doc_id} from {outcome.bundle}:{outcome.line_no} "
                    f"-> {outcome.error}"
                )
                if not args.continue_on_error:
                    await _flush_ready_docs(force=True)
                    for future in pending:
                        future.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    raise RuntimeError(
                        f"Import failed at {outcome.doc_id} from {outcome.bundle}:{outcome.line_no}"
                    )
            _print_progress(stats, progress_every=progress_every, started_at=started_at)

    for record in _iter_corpus_records(
        bundle_files,
        start_offset=int(args.start_offset),
        max_docs=args.max_docs,
        lines_per_doc=int(args.lines_per_doc),
    ):
        stats.planned += 1
        doc_id = str(record["doc_id"])

        if args.skip_existing and doc_id in existing_doc_ids:
            stats.skipped += 1
            _print_progress(stats, progress_every=progress_every, started_at=started_at)
            continue

        if args.dry_run:
            stats.imported += 1
            existing_doc_ids.add(doc_id)
            _print_progress(stats, progress_every=progress_every, started_at=started_at)
            continue

        processor = processor_pool[worker_cursor]
        worker_cursor = (worker_cursor + 1) % worker_count
        pending.add(
            asyncio.create_task(
                _import_record(
                    kb_service=kb_service,
                    processor=processor,
                    kb_id=args.kb_id,
                    kb_snapshot=kb,
                    record=record,
                )
            )
        )
        if len(pending) >= worker_count:
            await _drain_one()

    while pending:
        await _drain_one()
    await _flush_ready_docs(force=True)

    elapsed = max(0.001, time.perf_counter() - started_at)
    speed = stats.imported / elapsed
    print(
        f"[done] planned={stats.planned} imported={stats.imported} "
        f"skipped={stats.skipped} failed={stats.failed} dry_run={bool(args.dry_run)} "
        f"elapsed_s={elapsed:.1f} import_per_s={speed:.2f}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
