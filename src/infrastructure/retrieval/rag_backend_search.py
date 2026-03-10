"""Vector and lexical backend search helpers for RAG retrieval."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Sequence, cast

from src.api.paths import resolve_user_data_path

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from .rag_service import RagService


class RagBackendSearch:
    """Owns backend-specific retrieval implementations."""

    def __init__(self, owner: "RagService"):
        self.owner = owner

    def search_collection(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        score_threshold: float,
        override_model: Optional[str] = None,
        query_embedding: Optional[Sequence[float]] = None,
    ) -> List[Any]:
        backend = str(
            getattr(self.owner.rag_config_service.config.storage, "vector_store_backend", "chroma")
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
            return self.search_collection_sqlite_vec(**sqlite_kwargs)
        return self.search_collection_chroma(
            kb_id=kb_id,
            query=query,
            top_k=top_k,
            score_threshold=score_threshold,
            override_model=override_model,
        )

    def search_collection_chroma(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        score_threshold: float,
        override_model: Optional[str] = None,
    ) -> List[Any]:
        from langchain_chroma import Chroma

        persist_dir = Path(self.owner.rag_config_service.config.storage.persist_directory)
        if not persist_dir.is_absolute():
            persist_dir = resolve_user_data_path(persist_dir)

        collection_name = f"kb_{kb_id}"
        embedding_fn = cast(Any, self.owner.embedding_service.get_embedding_function(override_model))

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
            results_with_scores = vectorstore.similarity_search_with_relevance_scores(query, k=top_k)
        except Exception as e:
            logger.warning("ChromaDB search failed for collection %s: %s", collection_name, e)
            return []

        if not results_with_scores:
            logger.info("[RAG] collection=%s raw_results=0", collection_name)
        else:
            scores = [score for _, score in results_with_scores]
            logger.info(
                "[RAG] collection=%s raw_results=%d best_raw=%.4f top_scores=%s",
                collection_name,
                len(results_with_scores),
                max(scores),
                [round(s, 4) for s in sorted(scores, reverse=True)[:5]],
            )

        rag_results = []
        for doc, score in results_with_scores:
            if score < score_threshold:
                continue
            metadata = doc.metadata or {}
            rag_results.append(
                self.owner.result_cls(
                    content=doc.page_content,
                    score=score,
                    kb_id=metadata.get("kb_id", kb_id),
                    doc_id=metadata.get("doc_id", ""),
                    filename=metadata.get("filename", ""),
                    chunk_index=metadata.get("chunk_index", 0),
                )
            )
        return rag_results

    def search_collection_sqlite_vec(
        self,
        kb_id: str,
        query: str,
        top_k: int,
        score_threshold: float,
        override_model: Optional[str] = None,
        query_embedding: Optional[Sequence[float]] = None,
    ) -> List[Any]:
        from src.infrastructure.retrieval.sqlite_vec_service import SqliteVecService

        try:
            if query_embedding is None:
                embedding_fn = self.owner.embedding_service.get_embedding_function(override_model)
                if not hasattr(embedding_fn, "embed_query"):
                    logger.warning("sqlite_vec search failed for kb=%s: embedding function lacks embed_query()", kb_id)
                    return []
                query_embedding = embedding_fn.embed_query(query)
            if query_embedding is None:
                return []
            sqlite_vec = SqliteVecService()
            rows = cast(
                List[Dict[str, Any]],
                sqlite_vec.search(
                    kb_id=kb_id,
                    query_embedding=query_embedding,
                    top_k=top_k,
                ),
            )
        except Exception as e:
            logger.warning("SQLite vector search failed for kb %s: %s", kb_id, e)
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

        rag_results = []
        for item in rows:
            score = float(item.get("score", 0.0) or 0.0)
            if score < score_threshold:
                continue
            rag_results.append(
                self.owner.result_cls(
                    content=str(item.get("content") or ""),
                    score=score,
                    kb_id=str(item.get("kb_id") or kb_id),
                    doc_id=str(item.get("doc_id") or ""),
                    filename=str(item.get("filename") or ""),
                    chunk_index=int(item.get("chunk_index", 0) or 0),
                )
            )
        return rag_results

    def search_bm25_collection(
        self,
        *,
        kb_id: str,
        query: str,
        top_k: int,
        min_term_coverage: float,
    ) -> List[Any]:
        try:
            rows = cast(
                List[Dict[str, Any]],
                self.owner.bm25_service.search(
                    kb_id=kb_id,
                    query=query,
                    top_k=top_k,
                    min_term_coverage=min_term_coverage,
                ),
            )
        except Exception as e:
            logger.warning("BM25 search failed for kb %s: %s", kb_id, e)
            return []

        results = []
        for item in rows:
            results.append(
                self.owner.result_cls(
                    content=str(item.get("content") or ""),
                    score=float(item.get("score", 0.0) or 0.0),
                    kb_id=str(item.get("kb_id") or kb_id),
                    doc_id=str(item.get("doc_id") or ""),
                    filename=str(item.get("filename") or ""),
                    chunk_index=int(item.get("chunk_index", 0) or 0),
                )
            )
        return results

