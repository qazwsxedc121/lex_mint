#!/usr/bin/env python3
"""Import MTRAG passage corpus zip into KB using normal upload pipeline."""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterator, List, Optional, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.adapters.mtrag_adapter import sanitize_doc_id, to_mtrag_filename
from src.api.models.knowledge_base import KnowledgeBase, KnowledgeBaseDocument
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
    ok: bool
    error: str = ""
    doc: Optional[KnowledgeBaseDocument] = None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import MTRAG corpus zip into KB.")
    parser.add_argument("--kb-id", required=True, help="Target KB id.")
    parser.add_argument("--domain", default="fiqa", help="MTRAG domain: fiqa/cloud/govt/clapnq.")
    parser.add_argument(
        "--corpus-zip",
        type=Path,
        default=None,
        help="Path to corpus zip (default: learn_proj/mt-rag-benchmark/corpora/passage_level/<domain>.jsonl.zip).",
    )
    parser.add_argument(
        "--ids-file",
        type=Path,
        default=None,
        help="Optional text file with one corpus _id per line to import.",
    )
    parser.add_argument("--create-kb-if-missing", action="store_true", help="Create KB if missing.")
    parser.add_argument("--max-docs", type=int, default=None, help="Optional cap for this run.")
    parser.add_argument("--workers", type=int, default=1, help="Concurrent processing workers.")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip already imported docs.")
    parser.add_argument("--allow-api-embedding", action="store_true", help="Allow API embeddings.")
    parser.add_argument("--allow-cpu-embedding", action="store_true", help="Allow non-GPU local embedding.")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue after errors.")
    parser.add_argument("--progress-every", type=int, default=100, help="Progress log interval.")
    parser.add_argument("--metadata-flush-size", type=int, default=50, help="Flush metadata every N docs.")
    parser.add_argument("--dry-run", action="store_true", help="Plan only.")
    return parser.parse_args()


def _check_embedding_runtime(*, allow_api_embedding: bool, allow_cpu_embedding: bool) -> None:
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
                "GGUF embedding does not look GPU-offloaded. Refusing import without --allow-cpu-embedding."
            )
        return

    raise RuntimeError(f"Unsupported embedding provider: {provider}")


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _iter_corpus_records(
    corpus_zip: Path,
    *,
    domain: str,
    max_docs: Optional[int],
    allowed_ids: Optional[Set[str]] = None,
) -> Iterator[Dict[str, str]]:
    emitted = 0
    safe_limit = None if max_docs is None else max(1, int(max_docs))
    with zipfile.ZipFile(corpus_zip, "r") as zf:
        names = [name for name in zf.namelist() if name.endswith(".jsonl")]
        if not names:
            raise RuntimeError(f"No .jsonl file found in zip: {corpus_zip}")
        with zf.open(names[0], "r") as handle:
            for raw in handle:
                row = json.loads(raw)
                corpus_id = str(row.get("_id") or row.get("id") or "").strip()
                text = _clean_text(row.get("text") or "")
                if not corpus_id or not text:
                    continue
                if allowed_ids is not None and corpus_id not in allowed_ids:
                    continue
                title = _clean_text(row.get("title") or "")
                filename = to_mtrag_filename(domain=domain, corpus_id=corpus_id)
                safe_domain = sanitize_doc_id(domain)
                doc_id = f"mtrag_{safe_domain}_{sanitize_doc_id(corpus_id)}"
                content = f"{title}\n\n{text}".strip() if title else text
                yield {
                    "doc_id": doc_id,
                    "filename": filename,
                    "content": content,
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
        f"skipped={stats.skipped} failed={stats.failed} elapsed_s={elapsed:.1f} import_per_s={speed:.2f}"
    )


async def _import_record(
    *,
    kb_service: KnowledgeBaseService,
    processor: DocumentProcessingService,
    kb_id: str,
    kb_snapshot: KnowledgeBase,
    record: Dict[str, str],
) -> ImportOutcome:
    doc_id = record["doc_id"]
    filename = record["filename"]
    content = record["content"]

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
        return ImportOutcome(doc_id=doc_id, ok=True, doc=doc)
    except Exception as exc:
        return ImportOutcome(doc_id=doc_id, ok=False, error=str(exc))


async def _main() -> None:
    args = parse_args()
    _check_embedding_runtime(
        allow_api_embedding=bool(args.allow_api_embedding),
        allow_cpu_embedding=bool(args.allow_cpu_embedding),
    )

    domain = str(args.domain or "").strip().lower()
    if not domain:
        raise RuntimeError("domain cannot be empty")
    corpus_zip = args.corpus_zip or Path(
        f"learn_proj/mt-rag-benchmark/corpora/passage_level/{domain}.jsonl.zip"
    )
    if not corpus_zip.exists():
        raise RuntimeError(f"Corpus zip not found: {corpus_zip}")
    allowed_ids: Optional[Set[str]] = None
    if args.ids_file is not None:
        if not args.ids_file.exists():
            raise RuntimeError(f"ids file not found: {args.ids_file}")
        allowed_ids = {
            str(line).strip()
            for line in args.ids_file.read_text(encoding="utf-8").splitlines()
            if str(line).strip() and not str(line).strip().startswith("#")
        }
        print(f"[plan] ids_file={args.ids_file} ids={len(allowed_ids)}")
        if not allowed_ids:
            raise RuntimeError("ids file is empty")

    kb_service = KnowledgeBaseService()
    kb = await kb_service.get_knowledge_base(args.kb_id)
    if kb is None:
        if not args.create_kb_if_missing:
            raise RuntimeError(
                f"Knowledge base not found: {args.kb_id}. Use --create-kb-if-missing to create it."
            )
        await kb_service.add_knowledge_base(KnowledgeBase(id=args.kb_id, name=args.kb_id))
        kb = await kb_service.get_knowledge_base(args.kb_id)
        if kb is None:
            raise RuntimeError(f"Failed to create knowledge base: {args.kb_id}")
        print(f"[kb] created {args.kb_id}")

    workers = max(1, int(args.workers))
    metadata_flush_size = max(1, int(args.metadata_flush_size))
    progress_every = max(1, int(args.progress_every))
    print(f"[run] domain={domain} workers={workers} metadata_flush_size={metadata_flush_size}")

    processor_pool = [DocumentProcessingService() for _ in range(workers)]
    existing_doc_ids: Set[str] = set()
    if args.skip_existing:
        existing = await kb_service.get_documents(args.kb_id)
        existing_doc_ids = {str(item.id) for item in existing}
        print(f"[resume] existing docs in KB={len(existing_doc_ids)}")

    stats = ImportStats()
    pending: set[asyncio.Task[ImportOutcome]] = set()
    worker_cursor = 0
    ready_doc_buffer: List[KnowledgeBaseDocument] = []
    started_at = time.perf_counter()

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
        done, remaining = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
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
                print(f"[error] {outcome.doc_id} -> {outcome.error}")
                if not args.continue_on_error:
                    await _flush_ready_docs(force=True)
                    for future in pending:
                        future.cancel()
                    if pending:
                        await asyncio.gather(*pending, return_exceptions=True)
                    raise RuntimeError(f"Import failed at {outcome.doc_id}")
            _print_progress(stats, progress_every=progress_every, started_at=started_at)

    for record in _iter_corpus_records(
        corpus_zip,
        domain=domain,
        max_docs=args.max_docs,
        allowed_ids=allowed_ids,
    ):
        stats.planned += 1
        doc_id = record["doc_id"]

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
        worker_cursor = (worker_cursor + 1) % workers
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
        if len(pending) >= workers:
            await _drain_one()

    while pending:
        await _drain_one()
    await _flush_ready_docs(force=True)

    elapsed = max(0.001, time.perf_counter() - started_at)
    speed = stats.imported / elapsed
    print(
        f"[done] planned={stats.planned} imported={stats.imported} skipped={stats.skipped} failed={stats.failed} "
        f"dry_run={bool(args.dry_run)} elapsed_s={elapsed:.1f} import_per_s={speed:.2f}"
    )


if __name__ == "__main__":
    asyncio.run(_main())
