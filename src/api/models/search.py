"""Search-related data models."""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class SearchSource(BaseModel):
    """Single web search source item."""

    type: Optional[Literal["search", "webpage", "rag", "memory", "rag_diagnostics"]] = Field(
        None,
        description="Source type: search, webpage, rag, memory, or rag_diagnostics"
    )
    title: Optional[str] = Field(None, description="Result title")
    url: Optional[str] = Field(None, description="Result URL")
    snippet: Optional[str] = Field(None, description="Short snippet or summary")
    score: Optional[float] = Field(None, description="Relevance score if provided")

    # Memory-specific fields (optional)
    id: Optional[str] = Field(None, description="Memory item ID")
    scope: Optional[Literal["global", "assistant"]] = Field(None, description="Memory scope")
    layer: Optional[Literal["fact", "instruction"]] = Field(None, description="Memory layer")

    # RAG-specific fields (optional)
    content: Optional[str] = Field(None, description="RAG chunk content")
    kb_id: Optional[str] = Field(None, description="Knowledge base ID")
    doc_id: Optional[str] = Field(None, description="Knowledge base document ID")
    filename: Optional[str] = Field(None, description="Document filename")
    chunk_index: Optional[int] = Field(None, description="Chunk index in document")
    rerank_score: Optional[float] = Field(None, description="Reranker score when rerank is enabled")
    final_score: Optional[float] = Field(None, description="Final blended score after rerank")

    # RAG diagnostics fields (optional)
    raw_count: Optional[int] = Field(None, description="Raw retrieved chunks before processing")
    deduped_count: Optional[int] = Field(None, description="Chunk count after deduplication")
    diversified_count: Optional[int] = Field(None, description="Chunk count after doc diversity cap")
    selected_count: Optional[int] = Field(None, description="Final selected chunks")
    top_k: Optional[int] = Field(None, description="Configured top_k")
    recall_k: Optional[int] = Field(None, description="Configured recall_k")
    max_per_doc: Optional[int] = Field(None, description="Per-document cap for selected chunks")
    reorder_strategy: Optional[Literal["none", "long_context"]] = Field(None, description="Reorder strategy")
    searched_kb_count: Optional[int] = Field(None, description="Knowledge base collections searched")
    query_transform_enabled: Optional[bool] = Field(None, description="Whether query transformation is enabled")
    query_transform_mode: Optional[Literal["none", "rewrite"]] = Field(
        None,
        description="Query transformation mode",
    )
    query_transform_applied: Optional[bool] = Field(
        None,
        description="Whether query transformation changed the query",
    )
    query_transform_model_id: Optional[str] = Field(
        None,
        description="Model ID used for query transformation",
    )
    query_transform_guard_blocked: Optional[bool] = Field(
        None,
        description="Whether rewrite was blocked by anti-hallucination guard",
    )
    query_transform_guard_reason: Optional[str] = Field(
        None,
        description="Reason for anti-hallucination guard block",
    )
    query_transform_crag_enabled: Optional[bool] = Field(
        None,
        description="Whether CRAG-style quality gate is enabled for rewritten queries",
    )
    query_transform_crag_quality_score: Optional[float] = Field(
        None,
        description="Heuristic retrieval quality score for rewritten query",
    )
    query_transform_crag_quality_label: Optional[Literal["correct", "ambiguous", "incorrect", "skipped"]] = Field(
        None,
        description="Quality label for rewritten query",
    )
    query_transform_crag_decision: Optional[str] = Field(
        None,
        description="CRAG-style final decision for rewritten query",
    )
    retrieval_queries: Optional[list[str]] = Field(
        None,
        description="Planned retrieval queries list (includes effective query)",
    )
    retrieval_query_count: Optional[int] = Field(
        None,
        description="Total planned retrieval query count",
    )
    retrieval_query_planner_enabled: Optional[bool] = Field(
        None,
        description="Whether retrieval query planner is enabled",
    )
    retrieval_query_planner_applied: Optional[bool] = Field(
        None,
        description="Whether planner produced multi-query retrieval",
    )
    retrieval_query_planner_model_id: Optional[str] = Field(
        None,
        description="Model ID used by retrieval query planner",
    )
    retrieval_query_planner_fallback: Optional[bool] = Field(
        None,
        description="Whether retrieval query planner fell back to original/effective query",
    )
    retrieval_query_planner_reason: Optional[str] = Field(
        None,
        description="Planner result reason: ok/disabled/empty_query/model_unavailable/error",
    )
    query_original: Optional[str] = Field(None, description="Original user query (trimmed)")
    query_effective: Optional[str] = Field(None, description="Effective retrieval query (trimmed)")
    rerank_enabled: Optional[bool] = Field(None, description="Whether rerank is enabled in retrieval config")
    rerank_applied: Optional[bool] = Field(None, description="Whether rerank was successfully applied")
    rerank_weight: Optional[float] = Field(None, description="Blend weight for rerank score")
    rerank_model: Optional[str] = Field(None, description="Configured rerank model")
