"""
RAG Service

Handles retrieval-augmented generation: query embedding, similarity search,
result merging, and context formatting.
"""
import asyncio
import logging
import hashlib
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple
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
    rerank_score: Optional[float] = None
    final_score: Optional[float] = None

    def to_dict(self):
        data = {
            "content": self.content,
            "score": self.score,
            "kb_id": self.kb_id,
            "doc_id": self.doc_id,
            "filename": self.filename,
            "chunk_index": self.chunk_index,
            "type": "rag",
        }
        if self.rerank_score is not None:
            data["rerank_score"] = self.rerank_score
        if self.final_score is not None:
            data["final_score"] = self.final_score
        return data


class RagService:
    """Service for RAG retrieval operations"""

    def __init__(self):
        from .rag_config_service import RagConfigService
        from .embedding_service import EmbeddingService
        from .rerank_service import RerankService
        from .bm25_service import Bm25Service
        from .query_transform_service import QueryTransformService
        self.rag_config_service = RagConfigService()
        self.embedding_service = EmbeddingService()
        self.rerank_service = RerankService()
        self.bm25_service = Bm25Service()
        self.query_transform_service = QueryTransformService()

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
    def _compute_query_quality_score(diagnostics: Dict[str, Any]) -> float:
        """Heuristic retrieval quality score for CRAG-style query routing."""
        top_k = max(1, int(diagnostics.get("top_k", 1) or 1))
        selected_count = max(0, int(diagnostics.get("selected_count", 0) or 0))
        raw_count = max(0, int(diagnostics.get("raw_count", 0) or 0))

        selected_ratio = min(1.0, selected_count / top_k)
        raw_bonus = min(0.2, 0.2 * (raw_count / max(top_k * 5, 1)))
        return max(0.0, min(1.0, selected_ratio + raw_bonus))

    @staticmethod
    def _select_better_branch(
        rewritten: Tuple[List[RagResult], Dict[str, Any]],
        original: Tuple[List[RagResult], Dict[str, Any]],
    ) -> str:
        """Choose branch by retrieval quality; ties prefer original for safety."""
        _, rew_diag = rewritten
        _, orig_diag = original

        rew_key = (
            int(rew_diag.get("selected_count", 0) or 0),
            int(rew_diag.get("raw_count", 0) or 0),
            float(rew_diag.get("best_score", 0.0) or 0.0),
        )
        orig_key = (
            int(orig_diag.get("selected_count", 0) or 0),
            int(orig_diag.get("raw_count", 0) or 0),
            float(orig_diag.get("best_score", 0.0) or 0.0),
        )
        if rew_key > orig_key:
            return "rewrite"
        return "original"

    @staticmethod
    def _fuse_results_rrf(
        *,
        vector_results: List[RagResult],
        bm25_results: List[RagResult],
        vector_weight: float,
        bm25_weight: float,
        rrf_k: int,
        fusion_top_k: int,
    ) -> List[RagResult]:
        rrf_k = max(1, int(rrf_k))
        fusion_top_k = max(1, int(fusion_top_k))
        vector_weight = max(0.0, float(vector_weight))
        bm25_weight = max(0.0, float(bm25_weight))
        if vector_weight <= 0 and bm25_weight <= 0:
            vector_weight, bm25_weight = 1.0, 1.0

        fused: Dict[Tuple[str, str, int, str], Dict[str, Any]] = {}

        def _merge_channel(items: List[RagResult], weight: float) -> None:
            if weight <= 0:
                return
            for rank, item in enumerate(items, start=1):
                key = RagService._result_identity(item)
                entry = fused.get(key)
                if entry is None:
                    fused[key] = {
                        "item": item,
                        "score": weight * (1.0 / (rrf_k + rank)),
                    }
                else:
                    entry["score"] += weight * (1.0 / (rrf_k + rank))

        _merge_channel(vector_results, vector_weight)
        _merge_channel(bm25_results, bm25_weight)

        merged: List[RagResult] = []
        for row in fused.values():
            base: RagResult = row["item"]
            merged.append(
                RagResult(
                    content=base.content,
                    score=float(row["score"]),
                    kb_id=base.kb_id,
                    doc_id=base.doc_id,
                    filename=base.filename,
                    chunk_index=base.chunk_index,
                )
            )

        merged.sort(key=lambda item: item.score, reverse=True)
        return merged[:fusion_top_k]

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
        requested_kb_count = int(diagnostics.get("requested_kb_count", kb_count) or kb_count)
        best_score = float(diagnostics.get("best_score", 0.0) or 0.0)
        vector_raw_count = int(diagnostics.get("vector_raw_count", 0) or 0)
        bm25_raw_count = int(diagnostics.get("bm25_raw_count", 0) or 0)
        retrieval_mode = str(diagnostics.get("retrieval_mode", "vector") or "vector")
        vector_recall_k = int(diagnostics.get("vector_recall_k", recall_k) or recall_k)
        bm25_recall_k = int(diagnostics.get("bm25_recall_k", recall_k) or recall_k)
        bm25_min_term_coverage = float(diagnostics.get("bm25_min_term_coverage", 0.0) or 0.0)
        fusion_top_k = int(diagnostics.get("fusion_top_k", top_k) or top_k)
        fusion_strategy = str(diagnostics.get("fusion_strategy", "rrf") or "rrf")
        rrf_k = int(diagnostics.get("rrf_k", 60) or 60)
        vector_weight = float(diagnostics.get("vector_weight", 1.0) or 0.0)
        bm25_weight = float(diagnostics.get("bm25_weight", 1.0) or 0.0)
        rerank_enabled = bool(diagnostics.get("rerank_enabled", False))
        rerank_applied = bool(diagnostics.get("rerank_applied", False))
        rerank_weight = float(diagnostics.get("rerank_weight", 0.0) or 0.0)
        rerank_model = str(diagnostics.get("rerank_model", "") or "")
        query_transform_enabled = bool(diagnostics.get("query_transform_enabled", False))
        query_transform_mode = str(diagnostics.get("query_transform_mode", "none") or "none")
        query_transform_applied = bool(diagnostics.get("query_transform_applied", False))
        query_transform_model_id = str(diagnostics.get("query_transform_model_id", "") or "")
        query_original = str(diagnostics.get("query_original", "") or "")
        query_effective = str(diagnostics.get("query_effective", "") or "")
        query_transform_guard_blocked = bool(diagnostics.get("query_transform_guard_blocked", False))
        query_transform_guard_reason = str(diagnostics.get("query_transform_guard_reason", "") or "")
        query_transform_crag_enabled = bool(diagnostics.get("query_transform_crag_enabled", False))
        query_transform_crag_quality_score = float(
            diagnostics.get("query_transform_crag_quality_score", 0.0) or 0.0
        )
        query_transform_crag_quality_label = str(
            diagnostics.get("query_transform_crag_quality_label", "") or ""
        )
        query_transform_crag_decision = str(diagnostics.get("query_transform_crag_decision", "") or "")

        def _trim_query(text: str, max_len: int = 180) -> str:
            normalized = " ".join(text.split())
            if len(normalized) <= max_len:
                return normalized
            return f"{normalized[:max_len]}..."

        return {
            "type": "rag_diagnostics",
            "title": "RAG Diagnostics",
            "snippet": (
                f"raw {raw_count} -> dedup {deduped_count} -> "
                f"diversified {diversified_count} -> selected {selected_count} | "
                f"qt {query_transform_mode}:{query_transform_applied} "
                f"{query_transform_crag_decision or 'direct'}"
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
            "requested_kb_count": requested_kb_count,
            "best_score": best_score,
            "vector_raw_count": vector_raw_count,
            "bm25_raw_count": bm25_raw_count,
            "retrieval_mode": retrieval_mode,
            "vector_recall_k": vector_recall_k,
            "bm25_recall_k": bm25_recall_k,
            "bm25_min_term_coverage": bm25_min_term_coverage,
            "fusion_top_k": fusion_top_k,
            "fusion_strategy": fusion_strategy,
            "rrf_k": rrf_k,
            "vector_weight": vector_weight,
            "bm25_weight": bm25_weight,
            "query_transform_enabled": query_transform_enabled,
            "query_transform_mode": query_transform_mode,
            "query_transform_applied": query_transform_applied,
            "query_transform_model_id": query_transform_model_id,
            "query_transform_guard_blocked": query_transform_guard_blocked,
            "query_transform_guard_reason": query_transform_guard_reason,
            "query_transform_crag_enabled": query_transform_crag_enabled,
            "query_transform_crag_quality_score": query_transform_crag_quality_score,
            "query_transform_crag_quality_label": query_transform_crag_quality_label,
            "query_transform_crag_decision": query_transform_crag_decision,
            "query_original": _trim_query(query_original),
            "query_effective": _trim_query(query_effective),
            "rerank_enabled": rerank_enabled,
            "rerank_applied": rerank_applied,
            "rerank_weight": rerank_weight,
            "rerank_model": rerank_model,
        }

    async def _rank_candidates(
        self,
        *,
        query: str,
        candidates: List[RagResult],
        rerank_enabled: bool,
        rerank_model: str,
        rerank_base_url: str,
        rerank_api_key: str,
        rerank_timeout_seconds: int,
        rerank_weight: float,
    ) -> Tuple[List[RagResult], bool]:
        ranked = list(candidates)
        for item in ranked:
            item.final_score = item.score
            item.rerank_score = None

        ranked.sort(key=lambda x: x.score, reverse=True)
        if not rerank_enabled or len(ranked) <= 1:
            return ranked, False

        rerank_weight = max(0.0, min(1.0, float(rerank_weight)))
        docs = [item.content for item in ranked]
        try:
            rerank_scores = await self.rerank_service.rerank(
                query=query,
                documents=docs,
                model=rerank_model,
                base_url=rerank_base_url,
                api_key=rerank_api_key,
                timeout_seconds=rerank_timeout_seconds,
            )
        except Exception as e:
            logger.warning(f"Rerank request failed, fallback to vector scores: {e}")
            return ranked, False

        if not rerank_scores:
            logger.info("Rerank returned empty scores, fallback to vector scores")
            return ranked, False

        for index, item in enumerate(ranked):
            rerank_score = rerank_scores.get(index)
            if rerank_score is None:
                continue
            item.rerank_score = rerank_score
            item.final_score = rerank_weight * rerank_score + (1.0 - rerank_weight) * item.score

        ranked.sort(
            key=lambda x: x.final_score if x.final_score is not None else x.score,
            reverse=True,
        )
        return ranked, True

    async def retrieve(
        self,
        query: str,
        kb_ids: List[str],
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        runtime_model_id: Optional[str] = None,
    ) -> List[RagResult]:
        results, _ = await self.retrieve_with_diagnostics(
            query=query,
            kb_ids=kb_ids,
            top_k=top_k,
            score_threshold=score_threshold,
            runtime_model_id=runtime_model_id,
        )
        return results

    async def retrieve_with_diagnostics(
        self,
        query: str,
        kb_ids: List[str],
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
        runtime_model_id: Optional[str] = None,
        _skip_query_transform: bool = False,
        _skip_crag_gate: bool = False,
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
        retrieval_mode = str(getattr(config.retrieval, "retrieval_mode", "vector") or "vector").lower()
        if retrieval_mode not in {"vector", "bm25", "hybrid"}:
            retrieval_mode = "vector"
        vector_recall_k = int(
            getattr(config.retrieval, "vector_recall_k", configured_recall_k) or configured_recall_k
        )
        bm25_recall_k = int(
            getattr(config.retrieval, "bm25_recall_k", configured_recall_k) or configured_recall_k
        )
        bm25_min_term_coverage = float(
            getattr(config.retrieval, "bm25_min_term_coverage", 0.35) or 0.0
        )
        bm25_min_term_coverage = max(0.0, min(1.0, bm25_min_term_coverage))
        vector_recall_k = max(effective_top_k, vector_recall_k)
        bm25_recall_k = max(effective_top_k, bm25_recall_k)
        fusion_top_k = int(
            getattr(config.retrieval, "fusion_top_k", max(vector_recall_k, bm25_recall_k))
            or max(vector_recall_k, bm25_recall_k)
        )
        fusion_top_k = max(effective_top_k, fusion_top_k)
        fusion_strategy = str(getattr(config.retrieval, "fusion_strategy", "rrf") or "rrf").lower()
        if fusion_strategy not in {"rrf"}:
            fusion_strategy = "rrf"
        rrf_k = int(getattr(config.retrieval, "rrf_k", 60) or 60)
        vector_weight = float(getattr(config.retrieval, "vector_weight", 1.0) or 0.0)
        bm25_weight = float(getattr(config.retrieval, "bm25_weight", 1.0) or 0.0)
        configured_max_per_doc = int(getattr(config.retrieval, "max_per_doc", 0) or 0)
        reorder_strategy = str(getattr(config.retrieval, "reorder_strategy", "long_context") or "long_context").lower()
        if reorder_strategy not in {"none", "long_context"}:
            reorder_strategy = "long_context"
        query_transform_enabled = bool(getattr(config.retrieval, "query_transform_enabled", False))
        query_transform_mode = str(getattr(config.retrieval, "query_transform_mode", "none") or "none").lower()
        if query_transform_mode not in {"none", "rewrite"}:
            query_transform_mode = "none"
        query_transform_model_id = str(getattr(config.retrieval, "query_transform_model_id", "auto") or "auto")
        query_transform_timeout_seconds = int(
            getattr(config.retrieval, "query_transform_timeout_seconds", 4) or 4
        )
        query_transform_guard_enabled = bool(
            getattr(config.retrieval, "query_transform_guard_enabled", True)
        )
        query_transform_guard_max_new_terms = int(
            getattr(config.retrieval, "query_transform_guard_max_new_terms", 2) or 2
        )
        query_transform_guard_max_new_terms = max(0, min(20, query_transform_guard_max_new_terms))
        query_transform_crag_enabled = bool(
            getattr(config.retrieval, "query_transform_crag_enabled", True)
        )
        query_transform_crag_lower_threshold = float(
            getattr(config.retrieval, "query_transform_crag_lower_threshold", 0.35) or 0.35
        )
        query_transform_crag_upper_threshold = float(
            getattr(config.retrieval, "query_transform_crag_upper_threshold", 0.75) or 0.75
        )
        query_transform_crag_lower_threshold = max(0.0, min(1.0, query_transform_crag_lower_threshold))
        query_transform_crag_upper_threshold = max(0.0, min(1.0, query_transform_crag_upper_threshold))
        if query_transform_crag_lower_threshold >= query_transform_crag_upper_threshold:
            query_transform_crag_lower_threshold = 0.35
            query_transform_crag_upper_threshold = 0.75
        if _skip_query_transform:
            query_transform_enabled = False
            query_transform_mode = "none"
        if _skip_crag_gate:
            query_transform_crag_enabled = False
        rerank_enabled = bool(getattr(config.retrieval, "rerank_enabled", False))
        rerank_model = str(
            getattr(config.retrieval, "rerank_api_model", "jina-reranker-v2-base-multilingual")
            or "jina-reranker-v2-base-multilingual"
        )
        rerank_base_url = str(
            getattr(config.retrieval, "rerank_api_base_url", "https://api.jina.ai/v1/rerank")
            or "https://api.jina.ai/v1/rerank"
        )
        rerank_api_key = str(getattr(config.retrieval, "rerank_api_key", "") or "")
        rerank_timeout_seconds = int(getattr(config.retrieval, "rerank_timeout_seconds", 20) or 20)
        rerank_weight = float(getattr(config.retrieval, "rerank_weight", 0.7) or 0.0)
        vector_backend = str(getattr(config.storage, "vector_store_backend", "chroma") or "chroma").lower()
        if vector_backend not in {"chroma", "sqlite_vec"}:
            vector_backend = "chroma"
        original_query = (query or "").strip()
        effective_query = original_query
        query_transform_applied = False
        query_transform_resolved_model = query_transform_model_id
        query_transform_guard_blocked = False
        query_transform_guard_reason = ""
        if query_transform_enabled and query_transform_mode != "none" and original_query:
            query_transform_service = getattr(self, "query_transform_service", None)
            if query_transform_service is None:
                from .query_transform_service import QueryTransformService

                query_transform_service = QueryTransformService()
                self.query_transform_service = query_transform_service
            try:
                transform_result = await query_transform_service.transform_query(
                    query=original_query,
                    enabled=query_transform_enabled,
                    mode=query_transform_mode,
                    configured_model_id=query_transform_model_id,
                    runtime_model_id=runtime_model_id,
                    timeout_seconds=query_transform_timeout_seconds,
                    guard_enabled=query_transform_guard_enabled,
                    guard_max_new_terms=query_transform_guard_max_new_terms,
                )
                effective_query = transform_result.effective_query or original_query
                query_transform_applied = bool(transform_result.applied)
                query_transform_mode = transform_result.mode
                query_transform_resolved_model = transform_result.resolved_model_id
                query_transform_guard_blocked = bool(getattr(transform_result, "guard_blocked", False))
                query_transform_guard_reason = str(getattr(transform_result, "guard_reason", "") or "")
            except Exception as e:
                logger.warning("Query transform failed in RagService; fallback to original query: %s", e)

        short_query = effective_query.replace("\n", " ")
        if len(short_query) > 120:
            short_query = f"{short_query[:120]}..."
        short_original_query = original_query.replace("\n", " ")
        if len(short_original_query) > 120:
            short_original_query = f"{short_original_query[:120]}..."
        embedding_cfg = config.embedding
        base_url = (embedding_cfg.api_base_url or "").split("?", 1)[0]
        logger.info(
            "[RAG] retrieve start: query='%s', original_query='%s', query_transform=%s/%s applied=%s model=%s, kb_ids=%s, mode=%s, top_k=%s, vector_recall_k=%s, bm25_recall_k=%s, bm25_min_term_coverage=%.2f, fusion_top_k=%s, threshold=%s, max_per_doc=%s, reorder=%s, rerank_enabled=%s, rerank_model=%s, rerank_weight=%.2f, vector_backend=%s, provider=%s, model=%s, base_url=%s",
            short_query,
            short_original_query,
            query_transform_enabled,
            query_transform_mode,
            query_transform_applied,
            query_transform_resolved_model,
            kb_ids,
            retrieval_mode,
            effective_top_k,
            vector_recall_k,
            bm25_recall_k,
            bm25_min_term_coverage,
            fusion_top_k,
            effective_threshold,
            configured_max_per_doc,
            reorder_strategy,
            rerank_enabled,
            rerank_model,
            rerank_weight,
            vector_backend,
            embedding_cfg.provider,
            embedding_cfg.api_model,
            base_url or "default",
        )
        logger.info(
            "[RAG] storage backend=%s sqlite_path=%s persist_directory=%s",
            vector_backend,
            getattr(config.storage, "vector_sqlite_path", "data/state/rag_vec.sqlite3"),
            config.storage.persist_directory,
        )

        kb_service = KnowledgeBaseService()
        vector_results: List[RagResult] = []
        bm25_results: List[RagResult] = []
        searched_kb_count = 0
        kb_lookup_tasks = [kb_service.get_knowledge_base(kb_id) for kb_id in kb_ids]
        kb_lookup_results = await asyncio.gather(*kb_lookup_tasks, return_exceptions=True)

        enabled_kbs: List[Tuple[str, Any]] = []
        for kb_id, kb_lookup in zip(kb_ids, kb_lookup_results):
            if isinstance(kb_lookup, Exception):
                logger.warning(f"RAG lookup failed for KB {kb_id}: {kb_lookup}")
                continue
            kb = kb_lookup
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
            enabled_kbs.append((kb_id, kb))

        query_embedding_cache: Dict[str, Sequence[float]] = {}
        if enabled_kbs and retrieval_mode in {"vector", "hybrid"} and vector_backend == "sqlite_vec":
            model_cache_targets: Dict[str, Optional[str]] = {}
            for _, kb in enabled_kbs:
                override_model = getattr(kb, "embedding_model", None)
                cache_key = (str(override_model).strip() if override_model else "") or "__default__"
                if cache_key not in model_cache_targets:
                    model_cache_targets[cache_key] = override_model

            for cache_key, override_model in model_cache_targets.items():
                try:
                    embedding_fn = self.embedding_service.get_embedding_function(override_model)
                    if not hasattr(embedding_fn, "embed_query"):
                        logger.warning(
                            "sqlite_vec cache skipped for model=%s: embed_query() unavailable",
                            override_model or "default",
                        )
                        continue
                    query_embedding_cache[cache_key] = embedding_fn.embed_query(effective_query)
                except Exception as e:
                    logger.warning(
                        "sqlite_vec cache embed failed for model=%s: %s",
                        override_model or "default",
                        e,
                    )

        async def _retrieve_single_kb(kb_id: str, kb: Any) -> Tuple[List[RagResult], List[RagResult]]:
            local_vector_results: List[RagResult] = []
            local_bm25_results: List[RagResult] = []
            channel_jobs: List[Tuple[str, Any]] = []

            if retrieval_mode in {"vector", "hybrid"}:
                vector_kwargs: Dict[str, Any] = {
                    "kb_id": kb_id,
                    "query": effective_query,
                    "top_k": vector_recall_k,
                    "score_threshold": effective_threshold,
                    "override_model": kb.embedding_model,
                }
                if vector_backend == "sqlite_vec":
                    cache_key = (str(kb.embedding_model).strip() if kb.embedding_model else "") or "__default__"
                    cached_embedding = query_embedding_cache.get(cache_key)
                    if cached_embedding is not None:
                        vector_kwargs["query_embedding"] = cached_embedding
                channel_jobs.append(("vector", asyncio.to_thread(self._search_collection, **vector_kwargs)))

            if retrieval_mode in {"bm25", "hybrid"}:
                channel_jobs.append(
                    (
                        "bm25",
                        asyncio.to_thread(
                            self._search_bm25_collection,
                            kb_id=kb_id,
                            query=effective_query,
                            top_k=bm25_recall_k,
                            min_term_coverage=bm25_min_term_coverage,
                        ),
                    )
                )

            if not channel_jobs:
                return local_vector_results, local_bm25_results

            channel_results = await asyncio.gather(
                *(job for _, job in channel_jobs),
                return_exceptions=True,
            )
            for (channel, _), payload in zip(channel_jobs, channel_results):
                if isinstance(payload, Exception):
                    logger.warning(f"RAG {channel} search failed for KB {kb_id}: {payload}")
                    continue

                if channel == "vector":
                    local_vector_results = list(payload or [])
                    if local_vector_results:
                        best_score = max(r.score for r in local_vector_results)
                        logger.info(
                            "[RAG] kb=%s vector_results=%d best_score=%.4f",
                            kb_id,
                            len(local_vector_results),
                            best_score,
                        )
                    else:
                        logger.info("[RAG] kb=%s vector_results=0", kb_id)
                    continue

                local_bm25_results = list(payload or [])
                if local_bm25_results:
                    best_score = max(r.score for r in local_bm25_results)
                    logger.info(
                        "[RAG] kb=%s bm25_results=%d best_score=%.4f",
                        kb_id,
                        len(local_bm25_results),
                        best_score,
                    )
                else:
                    logger.info("[RAG] kb=%s bm25_results=0", kb_id)

            return local_vector_results, local_bm25_results

        kb_retrieval_tasks = [_retrieve_single_kb(kb_id, kb) for kb_id, kb in enabled_kbs]
        kb_retrieval_results = await asyncio.gather(*kb_retrieval_tasks, return_exceptions=True)
        for (kb_id, _), result in zip(enabled_kbs, kb_retrieval_results):
            if isinstance(result, Exception):
                logger.warning(f"RAG search failed for KB {kb_id}: {result}")
                continue
            kb_vector_results, kb_bm25_results = result
            vector_results.extend(kb_vector_results)
            bm25_results.extend(kb_bm25_results)

        vector_results.sort(key=lambda r: r.score, reverse=True)
        bm25_results.sort(key=lambda r: r.score, reverse=True)
        deduped_vector_results = self._deduplicate_results(vector_results)
        deduped_bm25_results = self._deduplicate_results(bm25_results)

        if retrieval_mode == "vector":
            candidate_results = deduped_vector_results
        elif retrieval_mode == "bm25":
            candidate_results = deduped_bm25_results
        else:
            candidate_results = self._fuse_results_rrf(
                vector_results=deduped_vector_results,
                bm25_results=deduped_bm25_results,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
                rrf_k=rrf_k,
                fusion_top_k=fusion_top_k,
            )

        candidate_results.sort(key=lambda r: r.score, reverse=True)
        deduped_results = self._deduplicate_results(candidate_results)
        ranked_results, rerank_applied = await self._rank_candidates(
            query=effective_query,
            candidates=deduped_results,
            rerank_enabled=rerank_enabled,
            rerank_model=rerank_model,
            rerank_base_url=rerank_base_url,
            rerank_api_key=rerank_api_key,
            rerank_timeout_seconds=rerank_timeout_seconds,
            rerank_weight=rerank_weight,
        )
        diversified_results = self._apply_doc_diversity(ranked_results, configured_max_per_doc)
        selected_results = diversified_results[:effective_top_k]
        reordered_results = self._reorder_results(selected_results, reorder_strategy)
        best_score = max(
            (
                item.final_score if item.final_score is not None else item.score
                for item in selected_results
            ),
            default=0.0,
        )
        diagnostics: Dict[str, Any] = {
            "raw_count": len(vector_results) + len(bm25_results),
            "vector_raw_count": len(vector_results),
            "bm25_raw_count": len(bm25_results),
            "deduped_count": len(deduped_results),
            "diversified_count": len(diversified_results),
            "selected_count": len(selected_results),
            "top_k": effective_top_k,
            "recall_k": configured_recall_k,
            "vector_recall_k": vector_recall_k,
            "bm25_recall_k": bm25_recall_k,
            "bm25_min_term_coverage": bm25_min_term_coverage,
            "fusion_top_k": fusion_top_k,
            "fusion_strategy": fusion_strategy,
            "rrf_k": rrf_k,
            "vector_weight": vector_weight,
            "bm25_weight": bm25_weight,
            "retrieval_mode": retrieval_mode,
            "score_threshold": float(effective_threshold),
            "max_per_doc": configured_max_per_doc,
            "reorder_strategy": reorder_strategy,
            "query_original": original_query,
            "query_effective": effective_query,
            "query_transform_enabled": query_transform_enabled,
            "query_transform_mode": query_transform_mode,
            "query_transform_applied": query_transform_applied,
            "query_transform_model_id": query_transform_resolved_model,
            "query_transform_guard_blocked": query_transform_guard_blocked,
            "query_transform_guard_reason": query_transform_guard_reason,
            "query_transform_crag_enabled": query_transform_crag_enabled,
            "query_transform_crag_quality_score": 0.0,
            "query_transform_crag_quality_label": "skipped",
            "query_transform_crag_decision": "direct",
            "query_transform_crag_lower_threshold": query_transform_crag_lower_threshold,
            "query_transform_crag_upper_threshold": query_transform_crag_upper_threshold,
            "searched_kb_count": searched_kb_count,
            "requested_kb_count": len(kb_ids),
            "best_score": best_score,
            "rerank_enabled": rerank_enabled,
            "rerank_applied": rerank_applied,
            "rerank_model": rerank_model,
            "rerank_weight": rerank_weight,
        }

        final_results = reordered_results
        final_diagnostics = diagnostics

        # CRAG-style quality gate for transformed queries:
        # 1) evaluate retrieval quality score
        # 2) fallback to original query when quality is low
        # 3) for ambiguous quality, compare rewritten vs original branches
        if (
            query_transform_enabled
            and query_transform_applied
            and query_transform_crag_enabled
            and not _skip_crag_gate
            and original_query
            and effective_query
            and original_query != effective_query
        ):
            quality_score = self._compute_query_quality_score(diagnostics)
            if quality_score < query_transform_crag_lower_threshold:
                quality_label = "incorrect"
            elif quality_score < query_transform_crag_upper_threshold:
                quality_label = "ambiguous"
            else:
                quality_label = "correct"

            final_diagnostics["query_transform_crag_quality_score"] = quality_score
            final_diagnostics["query_transform_crag_quality_label"] = quality_label

            if quality_label in {"incorrect", "ambiguous"}:
                original_branch = await self.retrieve_with_diagnostics(
                    query=original_query,
                    kb_ids=kb_ids,
                    top_k=effective_top_k,
                    score_threshold=float(effective_threshold),
                    runtime_model_id=runtime_model_id,
                    _skip_query_transform=True,
                    _skip_crag_gate=True,
                )
                rewritten_branch = (reordered_results, diagnostics)
                winner = self._select_better_branch(rewritten_branch, original_branch)
                if quality_label == "incorrect" and winner == "rewrite":
                    # Low-confidence rewrite can still win by retrieval signals.
                    final_diagnostics["query_transform_crag_decision"] = "keep_rewrite_low_confidence"
                elif winner == "original":
                    final_results, original_diag = original_branch
                    final_diagnostics = dict(original_diag)
                    final_diagnostics.update(
                        {
                            "query_original": original_query,
                            "query_effective": original_query,
                            "query_transform_enabled": query_transform_enabled,
                            "query_transform_mode": query_transform_mode,
                            "query_transform_applied": query_transform_applied,
                            "query_transform_model_id": query_transform_resolved_model,
                            "query_transform_guard_blocked": query_transform_guard_blocked,
                            "query_transform_guard_reason": query_transform_guard_reason,
                            "query_transform_crag_enabled": query_transform_crag_enabled,
                            "query_transform_crag_quality_score": quality_score,
                            "query_transform_crag_quality_label": quality_label,
                            "query_transform_crag_decision": "fallback_original",
                        }
                    )
                else:
                    final_diagnostics["query_transform_crag_decision"] = (
                        "keep_rewrite_after_compare"
                        if quality_label == "ambiguous"
                        else "keep_rewrite_low_confidence"
                    )
            else:
                final_diagnostics["query_transform_crag_decision"] = "keep_rewrite_high_confidence"
        else:
            final_diagnostics["query_transform_crag_quality_score"] = (
                final_diagnostics.get("query_transform_crag_quality_score", 0.0) or 0.0
            )
            final_diagnostics["query_transform_crag_quality_label"] = (
                "skipped"
                if not query_transform_applied
                else str(final_diagnostics.get("query_transform_crag_quality_label", "skipped"))
            )
            final_diagnostics["query_transform_crag_decision"] = (
                "skipped"
                if not query_transform_applied
                else str(final_diagnostics.get("query_transform_crag_decision", "direct"))
            )

        if final_results:
            logger.info(
                "[RAG] retrieve done: raw=%d deduped=%d diversified=%d selected=%d best_score=%.4f",
                int(final_diagnostics.get("raw_count", 0) or 0),
                int(final_diagnostics.get("deduped_count", 0) or 0),
                int(final_diagnostics.get("diversified_count", 0) or 0),
                len(final_results),
                float(final_diagnostics.get("best_score", 0.0) or 0.0),
            )
        else:
            logger.info("[RAG] retrieve done: total=0")
        logger.info(
            "[RAG][DIAG] mode=%s raw=%d(v=%d,b=%d) deduped=%d diversified=%d selected=%d top_k=%d vector_recall_k=%d bm25_recall_k=%d bm25_min_term_coverage=%.2f fusion_top_k=%d threshold=%.3f max_per_doc=%d reorder=%s query_transform=%s/%s applied=%s model=%s guard_blocked=%s crag=%s/%s/%s rerank=%s/%s(%.2f) kb=%d/%d",
            final_diagnostics["retrieval_mode"],
            final_diagnostics["raw_count"],
            final_diagnostics["vector_raw_count"],
            final_diagnostics["bm25_raw_count"],
            final_diagnostics["deduped_count"],
            final_diagnostics["diversified_count"],
            final_diagnostics["selected_count"],
            final_diagnostics["top_k"],
            final_diagnostics["vector_recall_k"],
            final_diagnostics["bm25_recall_k"],
            final_diagnostics["bm25_min_term_coverage"],
            final_diagnostics["fusion_top_k"],
            final_diagnostics["score_threshold"],
            final_diagnostics["max_per_doc"],
            final_diagnostics["reorder_strategy"],
            final_diagnostics["query_transform_enabled"],
            final_diagnostics["query_transform_mode"],
            final_diagnostics["query_transform_applied"],
            final_diagnostics["query_transform_model_id"],
            final_diagnostics.get("query_transform_guard_blocked", False),
            final_diagnostics.get("query_transform_crag_enabled", False),
            final_diagnostics.get("query_transform_crag_quality_label", "skipped"),
            final_diagnostics.get("query_transform_crag_decision", "skipped"),
            final_diagnostics["rerank_enabled"],
            final_diagnostics["rerank_applied"],
            final_diagnostics["rerank_weight"],
            final_diagnostics["searched_kb_count"],
            final_diagnostics["requested_kb_count"],
        )
        return final_results, final_diagnostics

    def _search_collection(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        score_threshold: float,
        override_model: Optional[str] = None,
        query_embedding: Optional[Sequence[float]] = None,
    ) -> List[RagResult]:
        """Search a single collection in the configured vector backend."""
        backend = str(
            getattr(self.rag_config_service.config.storage, "vector_store_backend", "chroma")
            or "chroma"
        ).lower()
        if backend == "sqlite_vec":
            sqlite_kwargs: Dict[str, Any] = {
                "kb_id": kb_id,
                "query": query,
                "top_k": top_k,
                "score_threshold": score_threshold,
                "override_model": override_model,
            }
            if query_embedding is not None:
                sqlite_kwargs["query_embedding"] = query_embedding
            return self._search_collection_sqlite_vec(
                **sqlite_kwargs,
            )
        return self._search_collection_chroma(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            override_model=override_model,
        )

    def _search_collection_chroma(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        score_threshold: float,
        override_model: Optional[str] = None,
    ) -> List[RagResult]:
        """Search a single ChromaDB collection."""
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

    def _search_collection_sqlite_vec(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        score_threshold: float,
        override_model: Optional[str] = None,
        query_embedding: Optional[Sequence[float]] = None,
    ) -> List[RagResult]:
        """Search a single SQLite vector collection."""
        from .sqlite_vec_service import SqliteVecService

        try:
            if query_embedding is None:
                embedding_fn = self.embedding_service.get_embedding_function(override_model)
                if not hasattr(embedding_fn, "embed_query"):
                    logger.warning("sqlite_vec search failed for kb=%s: embedding function lacks embed_query()", kb_id)
                    return []
                query_embedding = embedding_fn.embed_query(query)
            sqlite_vec = SqliteVecService()
            rows = sqlite_vec.search(
                kb_id=kb_id,
                query_embedding=query_embedding,
                top_k=top_k,
            )
        except Exception as e:
            logger.warning(f"SQLite vector search failed for kb {kb_id}: {e}")
            return []

        if not rows:
            logger.info("[RAG] sqlite_vec kb=%s raw_results=0", kb_id)
        else:
            scores = [float(item.get("score", 0.0) or 0.0) for item in rows]
            logger.info(
                "[RAG] sqlite_vec kb=%s raw_results=%d best_raw=%.4f top_scores=%s",
                kb_id,
                len(rows),
                max(scores),
                [round(s, 4) for s in scores[:5]],
            )

        rag_results: List[RagResult] = []
        for item in rows:
            score = float(item.get("score", 0.0) or 0.0)
            if score < score_threshold:
                continue
            rag_results.append(
                RagResult(
                    content=str(item.get("content") or ""),
                    score=score,
                    kb_id=str(item.get("kb_id") or kb_id),
                    doc_id=str(item.get("doc_id") or ""),
                    filename=str(item.get("filename") or ""),
                    chunk_index=int(item.get("chunk_index", 0) or 0),
                )
            )
        return rag_results

    def _search_bm25_collection(
        self,
        *,
        kb_id: str,
        query: str,
        top_k: int,
        min_term_coverage: float,
    ) -> List[RagResult]:
        try:
            rows = self.bm25_service.search(
                kb_id=kb_id,
                query=query,
                top_k=top_k,
                min_term_coverage=min_term_coverage,
            )
        except Exception as e:
            logger.warning(f"BM25 search failed for kb {kb_id}: {e}")
            return []

        results: List[RagResult] = []
        for item in rows:
            results.append(
                RagResult(
                    content=str(item.get("content") or ""),
                    score=float(item.get("score", 0.0) or 0.0),
                    kb_id=str(item.get("kb_id") or kb_id),
                    doc_id=str(item.get("doc_id") or ""),
                    filename=str(item.get("filename") or ""),
                    chunk_index=int(item.get("chunk_index", 0) or 0),
                )
            )
        return results

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
