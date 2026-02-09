"""
RAG Service

Handles retrieval-augmented generation: query embedding, similarity search,
result merging, and context formatting.
"""
import logging
from pathlib import Path
from typing import List, Optional
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

    async def retrieve(
        self,
        query: str,
        kb_ids: List[str],
        top_k: Optional[int] = None,
        score_threshold: Optional[float] = None,
    ) -> List[RagResult]:
        """
        Retrieve relevant chunks from knowledge bases.

        Args:
            query: User query string
            kb_ids: List of knowledge base IDs to search
            top_k: Override number of results to return
            score_threshold: Override minimum similarity score

        Returns:
            List of RagResult sorted by relevance score (descending)
        """
        from .knowledge_base_service import KnowledgeBaseService

        config = self.rag_config_service.config
        effective_top_k = top_k or config.retrieval.top_k
        effective_threshold = score_threshold if score_threshold is not None else config.retrieval.score_threshold
        short_query = (query or "").strip().replace("\n", " ")
        if len(short_query) > 120:
            short_query = f"{short_query[:120]}..."
        embedding_cfg = config.embedding
        base_url = (embedding_cfg.api_base_url or "").split("?", 1)[0]
        logger.info(
            "[RAG] retrieve start: query='%s', kb_ids=%s, top_k=%s, threshold=%s, provider=%s, model=%s, base_url=%s",
            short_query,
            kb_ids,
            effective_top_k,
            effective_threshold,
            embedding_cfg.provider,
            embedding_cfg.api_model,
            base_url or "default",
        )
        logger.info("[RAG] storage persist_directory=%s", config.storage.persist_directory)

        kb_service = KnowledgeBaseService()
        all_results: List[RagResult] = []

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

                results = self._search_collection(
                    kb_id=kb_id,
                    query=query,
                    top_k=effective_top_k,
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

        # Sort by score (descending) and take top_k
        all_results.sort(key=lambda r: r.score, reverse=True)
        if all_results:
            logger.info(
                "[RAG] retrieve done: total=%d best_score=%.4f",
                len(all_results),
                all_results[0].score,
            )
        else:
            logger.info("[RAG] retrieve done: total=0")
        return all_results[:effective_top_k]

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
