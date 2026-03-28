"""Post-processing helpers for RAG retrieval results."""

from __future__ import annotations

import hashlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .rag_service import RagResult


class RagPostProcessor:
    """Owns deterministic result ordering and deduplication rules."""

    @staticmethod
    def result_identity(result: RagResult) -> tuple[str, str, int, str]:
        doc_key = result.doc_id or result.filename or ""
        if not doc_key:
            digest = hashlib.sha1(result.content.encode("utf-8", errors="ignore")).hexdigest()
            doc_key = f"content:{digest}"
        return (result.kb_id, doc_key, int(result.chunk_index), result.filename or "")

    @classmethod
    def doc_identity(cls, result: RagResult) -> str:
        return (
            f"{result.kb_id}:{result.doc_id or result.filename or cls.result_identity(result)[1]}"
        )

    @classmethod
    def deduplicate_results(cls, results: list[RagResult]) -> list[RagResult]:
        seen = set()
        deduped: list[RagResult] = []
        for item in results:
            key = cls.result_identity(item)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @classmethod
    def apply_doc_diversity(cls, results: list[RagResult], max_per_doc: int) -> list[RagResult]:
        if max_per_doc <= 0:
            return results
        per_doc: dict[str, int] = {}
        diversified: list[RagResult] = []
        for item in results:
            doc_key = cls.doc_identity(item)
            count = per_doc.get(doc_key, 0)
            if count >= max_per_doc:
                continue
            per_doc[doc_key] = count + 1
            diversified.append(item)
        return diversified

    @classmethod
    def collapse_to_best_per_doc(cls, results: list[RagResult]) -> list[RagResult]:
        seen_docs = set()
        collapsed: list[RagResult] = []
        for item in results:
            doc_key = cls.doc_identity(item)
            if doc_key in seen_docs:
                continue
            seen_docs.add(doc_key)
            collapsed.append(item)
        return collapsed

    @staticmethod
    def long_context_reorder(results: list[RagResult]) -> list[RagResult]:
        if len(results) <= 2:
            return results
        front = results[::2]
        back = results[1::2]
        return front + list(reversed(back))

    @classmethod
    def reorder_results(cls, results: list[RagResult], strategy: str) -> list[RagResult]:
        if strategy == "none":
            return results
        if strategy == "long_context":
            return cls.long_context_reorder(results)
        return results
