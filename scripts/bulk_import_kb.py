#!/usr/bin/env python3
"""Bulk import local files and URLs into a knowledge base."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import re
import shutil
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence
from urllib.parse import urlparse

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.models.knowledge_base import KnowledgeBaseDocument
from src.api.services.document_processing_service import DocumentProcessingService
from src.api.services.knowledge_base_service import KnowledgeBaseService
from src.api.services.rag_config_service import RagConfigService
from src.api.services.webpage_service import WebpageService

ALLOWED_EXTENSIONS = {".txt", ".md", ".pdf", ".docx", ".html", ".htm"}


@dataclass
class ImportStats:
    planned: int = 0
    imported: int = 0
    skipped: int = 0
    failed: int = 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bulk import files/URLs into a KB.")
    parser.add_argument("--kb-id", required=True, help="Target knowledge base id.")
    parser.add_argument(
        "--source-dir",
        action="append",
        default=[],
        help="Source directory for local files (repeatable).",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="Recursively scan source directories.",
    )
    parser.add_argument(
        "--max-files",
        type=int,
        default=None,
        help="Optional cap for discovered local files.",
    )
    parser.add_argument(
        "--urls-file",
        type=Path,
        default=None,
        help="Optional text file containing one URL per line.",
    )
    parser.add_argument(
        "--allow-extensionless-txt",
        action="store_true",
        help="Treat extensionless files as .txt.",
    )
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        default=True,
        help="Skip if a document with the same filename already exists in KB.",
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
        help="Continue importing remaining items after an error.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print planned import items.",
    )
    return parser.parse_args()


def _sanitize_filename(value: str, default_name: str = "doc.md") -> str:
    text = str(value or "").strip()
    if not text:
        return default_name
    text = re.sub(r"[\\/:*?\"<>|]+", "_", text)
    text = re.sub(r"\s+", "_", text).strip("._")
    if not text:
        return default_name
    return text[:160]


def _load_urls(urls_file: Path) -> List[str]:
    urls: List[str] = []
    for raw in urls_file.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("http://") or line.startswith("https://"):
            urls.append(line)
    return urls


def _iter_candidate_files(source_dirs: Sequence[str], recursive: bool) -> Iterable[Path]:
    for root_raw in source_dirs:
        root = Path(root_raw).expanduser()
        if not root.exists():
            continue
        if root.is_file():
            yield root
            continue
        if recursive:
            yield from (p for p in root.rglob("*") if p.is_file())
        else:
            yield from (p for p in root.glob("*") if p.is_file())


def _extension_for_path(path: Path, allow_extensionless_txt: bool) -> str:
    ext = path.suffix.lower()
    if ext:
        return ext
    if allow_extensionless_txt:
        return ".txt"
    return ""


def _build_url_filename(url: str) -> str:
    parsed = urlparse(url)
    base = f"{parsed.netloc}{parsed.path}".strip("/") or parsed.netloc or "url"
    base = _sanitize_filename(base, default_name="url")
    short_hash = hashlib.sha1(url.encode("utf-8")).hexdigest()[:10]
    return f"url_{base}_{short_hash}.md"


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
                "Local embedding is not using CUDA. Refusing import without --allow-cpu-embedding."
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
                "Local GGUF embedding does not look GPU-offloaded. "
                "Refusing import without --allow-cpu-embedding."
            )
        return

    raise RuntimeError(f"Unsupported embedding provider: {provider}")


async def _import_file_item(
    *,
    kb_service: KnowledgeBaseService,
    processor: DocumentProcessingService,
    kb_id: str,
    source_path: Path,
    ext: str,
    filename: str,
    dry_run: bool,
) -> None:
    doc_id = str(uuid.uuid4())[:8]
    storage_path = kb_service.get_document_storage_path(kb_id, doc_id, filename)
    file_size = int(source_path.stat().st_size)

    if dry_run:
        print(f"[dry-run] file -> {filename} ({file_size} bytes)")
        return

    shutil.copy2(source_path, storage_path)
    doc = KnowledgeBaseDocument(
        id=doc_id,
        kb_id=kb_id,
        filename=filename,
        file_type=ext,
        file_size=file_size,
        status="pending",
    )
    await kb_service.add_document(doc)
    await processor.process_document(kb_id, doc_id, filename, ext, str(storage_path))
    print(f"[ok] file imported: {filename}")


async def _import_url_item(
    *,
    kb_service: KnowledgeBaseService,
    processor: DocumentProcessingService,
    webpage_service: WebpageService,
    kb_id: str,
    url: str,
    filename: str,
    dry_run: bool,
) -> None:
    if dry_run:
        print(f"[dry-run] url -> {filename} ({url})")
        return

    result = await webpage_service.fetch_and_parse(url)
    if result.error:
        raise RuntimeError(f"URL fetch failed for {url}: {result.error}")
    if not result.text.strip():
        raise RuntimeError(f"URL fetch returned empty content: {url}")

    doc_id = str(uuid.uuid4())[:8]
    storage_path = kb_service.get_document_storage_path(kb_id, doc_id, filename)
    markdown = (
        f"# {result.title or 'Webpage'}\n\n"
        f"Source URL: {result.final_url}\n\n"
        f"{result.text.strip()}\n"
    )
    storage_path.write_text(markdown, encoding="utf-8")

    doc = KnowledgeBaseDocument(
        id=doc_id,
        kb_id=kb_id,
        filename=filename,
        file_type=".md",
        file_size=int(storage_path.stat().st_size),
        status="pending",
    )
    await kb_service.add_document(doc)
    await processor.process_document(kb_id, doc_id, filename, ".md", str(storage_path))
    print(f"[ok] url imported: {url}")


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

    processor = DocumentProcessingService()
    webpage_service = WebpageService()

    existing_docs = await kb_service.get_documents(args.kb_id)
    existing_names = {str(doc.filename or "").strip() for doc in existing_docs}

    file_candidates: List[tuple[Path, str, str]] = []
    seen_paths = set()
    for path in _iter_candidate_files(args.source_dir, args.recursive):
        real = str(path.resolve()).lower()
        if real in seen_paths:
            continue
        seen_paths.add(real)

        ext = _extension_for_path(path, bool(args.allow_extensionless_txt))
        if ext not in ALLOWED_EXTENSIONS:
            continue

        filename = path.name if path.suffix else f"{path.name}.txt"
        filename = _sanitize_filename(filename, default_name="file.txt")
        file_candidates.append((path, ext, filename))
        if args.max_files is not None and len(file_candidates) >= max(1, int(args.max_files)):
            break

    urls: List[str] = []
    if args.urls_file is not None:
        if not args.urls_file.exists():
            raise RuntimeError(f"urls file not found: {args.urls_file}")
        urls = _load_urls(args.urls_file)

    stats = ImportStats()
    stats.planned = len(file_candidates) + len(urls)
    print(f"[plan] kb_id={args.kb_id} file_items={len(file_candidates)} url_items={len(urls)}")
    if stats.planned == 0:
        print("[plan] nothing to import")
        return

    for source_path, ext, filename in file_candidates:
        if args.skip_existing and filename in existing_names:
            stats.skipped += 1
            print(f"[skip] existing filename: {filename}")
            continue
        try:
            await _import_file_item(
                kb_service=kb_service,
                processor=processor,
                kb_id=args.kb_id,
                source_path=source_path,
                ext=ext,
                filename=filename,
                dry_run=bool(args.dry_run),
            )
            if not args.dry_run:
                stats.imported += 1
            existing_names.add(filename)
        except Exception as exc:
            stats.failed += 1
            print(f"[error] file import failed: {source_path} -> {exc}")
            if not args.continue_on_error:
                raise

    for url in urls:
        filename = _build_url_filename(url)
        if args.skip_existing and filename in existing_names:
            stats.skipped += 1
            print(f"[skip] existing url filename: {filename}")
            continue
        try:
            await _import_url_item(
                kb_service=kb_service,
                processor=processor,
                webpage_service=webpage_service,
                kb_id=args.kb_id,
                url=url,
                filename=filename,
                dry_run=bool(args.dry_run),
            )
            if not args.dry_run:
                stats.imported += 1
            existing_names.add(filename)
        except Exception as exc:
            stats.failed += 1
            print(f"[error] url import failed: {url} -> {exc}")
            if not args.continue_on_error:
                raise

    if args.dry_run:
        print("[done] dry-run only, no files were ingested")
        return

    print(
        "[done] planned={planned} imported={imported} skipped={skipped} failed={failed}".format(
            planned=stats.planned,
            imported=stats.imported,
            skipped=stats.skipped,
            failed=stats.failed,
        )
    )


if __name__ == "__main__":
    asyncio.run(_main())
