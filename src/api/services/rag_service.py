"""
RAG Service

Handles retrieval-augmented generation: query embedding, similarity search,
result merging, and context formatting.
"""
import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class RagResult:
    """A single RAG retrieval result"""
    content: str
    score: float
    kb_id: str
    doc_id: str
    filename: str
    chunk_index: int

    def to_dict(self):
        return {
            "content": self.content,
            "score": self.score,
            "kb_id": self.kb_id,
            "doc_id": self.doc_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "type": "rag",
        }


class RagService:
    """Service for RAG retrieval operations"""

    def __init__(self):
        from .rag_config_service import RagConfigService
        from .embedding_service import EmbeddingService
        self.rag_config_service = RagConfigService()
        self.embedding_service = EmbeddingService()

    @staticmethod
    def _result_identity(result: RagResult) -> Tuple[str, str, int, str]:
        """Stable identity key for deduplicating retrieved chunks."""
        doc_key = result.doc_id or result.filename or ""
        if not doc_key:
            digest = hashlib.sha1(result.content.encode("utf-8", errors="ignore")).hexdigest()
            doc_key = f"content:{digest}"
        return (result.kb_id, doc_key, int(result.chunk_index), result.filename or "")

    @staticmethod
    def _doc_identity(result: RagResult) -> str:
        """Document-level identity key for diversity capping."""
        return f"{result.kb_id}:{result.doc_id or result.filename or RagService._result_identity(result)[1]}"

    @staticmethod
    def _deduplicate_results(results: List[RagResult]) -> List[RagResult]:
        seen = set()
        deduped: List[RagResult] = []
        for item in results:
            key = RagService._result_identity(item)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(item)
        return deduped

    @staticmethod
    def _apply_doc_diversity(results: List[RagResult], max_per_doc: int) -> List[RagResult]:
        if max_per_doc <= 0:
            return results

        per_doc: Dict[str, int] = {}
        diversified: List[RagResult] = []
        for item in results:
            doc_key = RagService._doc_identity(item)
            count = per_doc.get(doc_key, 0)
            if count >= max_per_doc:
                continue
            per_doc[doc_key] = count + 1
            diversified.append(item)
        return diversified

    @staticmethod
    def _long_context_reorder(results: List[RagResult]) -> List[RagResult]:
        """
        Reorder so top-ranked chunks appear near both prompt edges:
        [1,2,3,4,5,6] -> [1,3,5,6,4,2].
        """
        if len(results) <= 2:
            return results
        front = results[::2]
        back = results[1::2]
        return front + list(reversed(back))

    @staticmethod
    def _reorder_results(results: List[RagResult], strategy: str) -> List[RagResult]:
        if strategy == "none":
            return results
        if strategy == "long_context":
            return RagService._long_context_reorder(results)
        return results

    @staticmethod
    def build_rag_diagnostics_source(diagnostics: Dict[str, Any]) -> Dict[str, Any]:
        """Convert diagnostics into a source payload that can be stored and rendered."""
        raw_count = int(diagnostics.get("raw_count", 0) or 0)
        deduped_count = int(diagnostics.get("deduped_count", 0) or 0)
        diversified_count = int(diagnostics.get("diversified_count", 0) or 0)
        selected_count = int(diagnostics.get("selected_count", 0) or 0)
        top_k = int(diagnostics.get("top_k", selected_count) or selected_count)
        recall_k = int(diagnostics.get("recall_k", top_k) or top_k)
        reorder_strategy = str(diagnostics.get("reorder_strategy", "long_context") or "long_context")
        max_per_doc = int(diagnostics.get("max_per_doc", 0) or 0)
        score_threshold = float(diagnostics.get("score_threshold", 0.0) or 0.0)
        kb_count = int(diagnostics.get("searched_kb_count", 0) or 0)

        return {
            "type": "rag_diagnostics",
            "title": "RAG Diagnostics",
            "snippet": (
                f"raw {raw_count} -> dedup {deduped_count} -> "
                f"diversified {diversified_count} -> selected {selected_count}"
            ),
            "raw_count": raw_count,
            "deduped_count": deduped_count,
            "diversified_count": diversified_count,
            "selected_count": selected_count,
            "top_k": top_k,
            "recall_k": recall_k,
            "score_threshold": score_threshold,
            "max_per_doc": max_per_doc,
            "reorder_strategy": reorder_strategy,
            "searched_kb_count": kb_count,
        }

    async def retrieve(
        self,
        query: str,
        kb_ids: List[str],
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> List[RagResult]:
        results, _ = await self.retrieve_with_diagnostics(
            query=query,
            kb_ids=kb_ids,
            top_k=top_k,
            score_threshold=score_threshold,
        )
        return results

    async def retrieve_with_diagnostics(
        self,
        query: str,
        kb_ids: List[str],
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> Tuple[List[RagResult], Dict[str, Any]]:
        """
        Retrieve relevant chunks from knowledge bases.

        Args:
            query: User query string
            kb_ids: List of knowledge base IDs to search
            top_k: Override number of results to return
            score_threshold: Override minimum similarity score

        Returns:
            Tuple of (results, diagnostics)
        """
        from .knowledge_base_service import KnowledgeBaseService

        config = self.rag_config_service.config
        effective_top_k = max(1, int(top_k or config.retrieval.top_k))
        effective_threshold = score_threshold if score_threshold is not None else config.retrieval.score_threshold
        configured_recall_k = int(getattr(config.retrieval, "recall_k", effective_top_k) or effective_top_k)
        effective_recall_k = max(effective_top_k, configured_recall_k)
        configured_max_per_doc = int(getattr(config.retrieval, "max_per_doc", 0) or 0)
        reorder_strategy = str(getattr(config.retrieval, "reorder_strategy", "long_context") or "long_context").lower()
        if reorder_strategy not in {"none", "long_context"}:
            reorder_strategy = "long_context"
        short_query = (query or "").strip().replace("\n", " ")
        if len(short_query) > 120:
            short_query = f"{short_query[:120]}..."
        embedding_cfg = config.embedding
        base_url = (embedding_cfg.api_base_url or "").split("?", 1)[0]
        logger.info(
            "[RAG] retrieve start: query='%s', kb_ids=%s, top_k=%s, recall_k=%s, threshold=%s, max_per_doc=%s, reorder=%s, provider=%s, model=%s, base_url=%s",
            short_query,
            kb_ids,
            effective_top_k,
            effective_recall_k,
            effective_threshold,
            configured_max_per_doc,
            reorder_strategy,
            embedding_cfg.provider,
            embedding_cfg.api_model,
            base_url or "default",
        )
        logger.info("[RAG] storage persist_directory=%s", config.storage.persist_directory)

        kb_service = KnowledgeBaseService()
        all_results: List[RagResult] = []
        searched_kb_count = 0

        for kb_id in kb_ids:
            try:
                # Check if KB exists and is enabled
                kb = await kb_service.get_knowledge_base(kb_id)
                if not kb or not kb.enabled:
                    logger.info("[RAG] kb=%s skipped (missing or disabled)", kb_id)
                    continue
                logger.info(
                    "[RAG] kb=%s enabled=%s embedding_model=%s doc_count=%s",
                    kb_id,
                    kb.enabled,
                    kb.embedding_model,
                    kb.document_count,
                )
                searched_kb_count += 1

                results = self._search_collection(
                    kb_id=kb_id,
                    query=query,
                    top_k=effective_recall_k,
                    score_threshold=effective_threshold,
                    override_model=kb.embedding_model,
                )
                if results:
                    best_score = max(r.score for r in results)
                    logger.info("[RAG] kb=%s results=%d best_score=%.4f", kb_id, len(results), best_score)
                else:
                    logger.info("[RAG] kb=%s results=0 (after threshold)", kb_id)
                all_results.extend(results)
            except Exception as e:
                logger.warning(f"RAG search failed for KB {kb_id}: {e}")
                continue

        # Score ranking baseline
        all_results.sort(key=lambda r: r.score, reverse=True)
        deduped_results = self._deduplicate_results(all_results)
        diversified_results = self._apply_doc_diversity(deduped_results, configured_max_per_doc)
        selected_results = diversified_results[:effective_top_k]
        reordered_results = self._reorder_results(selected_results, reorder_strategy)
        best_score = max((item.score for item in selected_results), default=0.0)
        diagnostics: Dict[str, Any] = {
            "raw_count": len(all_results),
            "deduped_count": len(deduped_results),
            "diversified_count": len(diversified_results),
            "selected_count": len(selected_results),
            "top_k": effective_top_k,
            "recall_k": effective_recall_k,
            "score_threshold": float(effective_threshold),
            "max_per_doc": configured_max_per_doc,
            "reorder_strategy": reorder_strategy,
            "searched_kb_count": searched_kb_count,
            "requested_kb_count": len(kb_ids),
            "best_score": best_score,
        }

        if reordered_results:
            logger.info(
                "[RAG] retrieve done: raw=%d deduped=%d diversified=%d selected=%d best_score=%.4f",
                len(all_results),
                len(deduped_results),
                len(diversified_results),
                len(reordered_results),
                best_score,
            )
        else:
            logger.info("[RAG] retrieve done: total=0")
        logger.info(
            "[RAG][DIAG] raw=%d deduped=%d diversified=%d selected=%d top_k=%d recall_k=%d threshold=%.3f max_per_doc=%d reorder=%s kb=%d/%d",
            diagnostics["raw_count"],
            diagnostics["deduped_count"],
            diagnostics["diversified_count"],
            diagnostics["selected_count"],
            diagnostics["top_k"],
            diagnostics["recall_k"],
            diagnostics["score_threshold"],
            diagnostics["max_per_doc"],
            diagnostics["reorder_strategy"],
            diagnostics["searched_kb_count"],
            diagnostics["requested_kb_count"],
        )
        return reordered_results, diagnostics

    def _search_collection(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        score_threshold: float,
        override_model: Optional[str] = None,
    ) -> List[RagResult]:
        """Search a single ChromaDB collection"""
        from langchain_chroma import Chroma

        persist_dir = Path(self.rag_config_service.config.storage.persist_directory)
        if not persist_dir.is_absolute():
            persist_dir = Path(__file__).parent.parent.parent.parent / persist_dir

        collection_name = f"kb_{kb_id}"

        embedding_fn = self.embedding_service.get_embedding_function(override_model)

        try:
            vectorstore = Chroma(
                collection_name=collection_name,
                embedding_function=embedding_fn,
                persist_directory=str(persist_dir),
                collection_metadata={"hnsw:space": "cosine"},
            )
            try:
                collection_count = vectorstore._collection.count()
                logger.info(
                    "[RAG] collection=%s count=%s persist_dir=%s override_model=%s",
                    collection_name,
                    collection_count,
                    str(persist_dir),
                    override_model,
                )
            except Exception:
                logger.info(
                    "[RAG] collection=%s persist_dir=%s override_model=%s",
                    collection_name,
                    str(persist_dir),
                    override_model,
                )

            # Search with scores
            results_with_scores = vectorstore.similarity_search_with_relevance_scores(
                query, k=top_k
            )
        except Exception as e:
            logger.warning(f"ChromaDB search failed for collection {collection_name}: {e}")
            return []

        if not results_with_scores:
            logger.info("[RAG] collection=%s raw_results=0", collection_name)
        else:
            scores = [score for _, score in results_with_scores]
            best_raw = max(scores)
            top_scores = sorted(scores, reverse=True)[:5]
            logger.info(
                "[RAG] collection=%s raw_results=%d best_raw=%.4f top_scores=%s",
                collection_name,
                len(results_with_scores),
                best_raw,
                [round(s, 4) for s in top_scores],
            )

        rag_results = []
        for doc, score in results_with_scores:
            if score >= score_threshold:
                metadata = doc.metadata or {}
                rag_results.append(RagResult(
                    content=doc.page_content,
                    score=score,
                    kb_id=metadata.get("kb_id", kb_id),
                    doc_id=metadata.get("doc_id", ""),
                    filename=metadata.get("filename", ""),
                    chunk_index=metadata.get("chunk_index", 0),
                ))

        return rag_results

    @staticmethod
    def build_rag_context(query: str, results: List[RagResult]) -> str:
        """
        Format RAG results as context string for injection into system prompt.

        Pattern reference: SearchService.build_search_context()
        """
        if not results:
            return ""

        lines = [
            "Knowledge base context (use this information to answer the user's question):",
            f"Query: {query}",
        ]

        seen_filenames = set()
        for index, result in enumerate(results, start=1):
            content = result.content.strip()
            if len(content) > 800:
                content = content[:800] + "..."

            source_label = result.filename
            if source_label not in seen_filenames:
                seen_filenames.add(source_label)

            lines.append(f"[{index}] From: {source_label}")
            lines.append(f"Content: {content}")

        return "\n".join(lines)
