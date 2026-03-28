"""Search-related data models."""

from typing import Literal

from pydantic import BaseModel, Field


class SearchSource(BaseModel):
    """Single web search source item."""

    type: Literal["search", "webpage", "rag", "memory", "rag_diagnostics"] | None = Field(
        None, description="Source type: search, webpage, rag, memory, or rag_diagnostics"
    )
    title: str | None = Field(None, description="Result title")
    url: str | None = Field(None, description="Result URL")
    snippet: str | None = Field(None, description="Short snippet or summary")
    score: float | None = Field(None, description="Relevance score if provided")

    # Memory-specific fields (optional)
    id: str | None = Field(None, description="Memory item ID")
    scope: Literal["global", "assistant"] | None = Field(None, description="Memory scope")
    layer: Literal["fact", "instruction"] | None = Field(None, description="Memory layer")

    # RAG-specific fields (optional)
    content: str | None = Field(None, description="RAG chunk content")
    kb_id: str | None = Field(None, description="Knowledge base ID")
    doc_id: str | None = Field(None, description="Knowledge base document ID")
    filename: str | None = Field(None, description="Document filename")
    chunk_index: int | None = Field(None, description="Chunk index in document")
    rerank_score: float | None = Field(None, description="Reranker score when rerank is enabled")
    final_score: float | None = Field(None, description="Final blended score after rerank")

    # RAG diagnostics fields (optional)
    raw_count: int | None = Field(None, description="Raw retrieved chunks before processing")
    deduped_count: int | None = Field(None, description="Chunk count after deduplication")
    diversified_count: int | None = Field(None, description="Chunk count after doc diversity cap")
    selected_count: int | None = Field(None, description="Final selected chunks")
    top_k: int | None = Field(None, description="Configured top_k")
    recall_k: int | None = Field(None, description="Configured recall_k")
    max_per_doc: int | None = Field(None, description="Per-document cap for selected chunks")
    reorder_strategy: Literal["none", "long_context"] | None = Field(
        None, description="Reorder strategy"
    )
    searched_kb_count: int | None = Field(None, description="Knowledge base collections searched")
    query_transform_enabled: bool | None = Field(
        None, description="Whether query transformation is enabled"
    )
    query_transform_mode: Literal["none", "rewrite"] | None = Field(
        None,
        description="Query transformation mode",
    )
    query_transform_applied: bool | None = Field(
        None,
        description="Whether query transformation changed the query",
    )
    query_transform_model_id: str | None = Field(
        None,
        description="Model ID used for query transformation",
    )
    query_transform_guard_blocked: bool | None = Field(
        None,
        description="Whether rewrite was blocked by anti-hallucination guard",
    )
    query_transform_guard_reason: str | None = Field(
        None,
        description="Reason for anti-hallucination guard block",
    )
    query_transform_crag_enabled: bool | None = Field(
        None,
        description="Whether CRAG-style quality gate is enabled for rewritten queries",
    )
    query_transform_crag_quality_score: float | None = Field(
        None,
        description="Heuristic retrieval quality score for rewritten query",
    )
    query_transform_crag_quality_label: (
        Literal["correct", "ambiguous", "incorrect", "skipped"] | None
    ) = Field(
        None,
        description="Quality label for rewritten query",
    )
    query_transform_crag_decision: str | None = Field(
        None,
        description="CRAG-style final decision for rewritten query",
    )
    retrieval_queries: list[str] | None = Field(
        None,
        description="Planned retrieval queries list (includes effective query)",
    )
    retrieval_query_count: int | None = Field(
        None,
        description="Total planned retrieval query count",
    )
    retrieval_query_planner_enabled: bool | None = Field(
        None,
        description="Whether retrieval query planner is enabled",
    )
    retrieval_query_planner_applied: bool | None = Field(
        None,
        description="Whether planner produced multi-query retrieval",
    )
    retrieval_query_planner_model_id: str | None = Field(
        None,
        description="Model ID used by retrieval query planner",
    )
    retrieval_query_planner_fallback: bool | None = Field(
        None,
        description="Whether retrieval query planner fell back to original/effective query",
    )
    retrieval_query_planner_reason: str | None = Field(
        None,
        description="Planner result reason: ok/disabled/empty_query/model_unavailable/error",
    )
    query_original: str | None = Field(None, description="Original user query (trimmed)")
    query_effective: str | None = Field(None, description="Effective retrieval query (trimmed)")
    rerank_enabled: bool | None = Field(
        None, description="Whether rerank is enabled in retrieval config"
    )
    rerank_applied: bool | None = Field(None, description="Whether rerank was successfully applied")
    rerank_weight: float | None = Field(None, description="Blend weight for rerank score")
    rerank_model: str | None = Field(None, description="Configured rerank model")
    tool_search_count: int | None = Field(None, description="Number of search_knowledge calls")
    tool_search_unique_count: int | None = Field(
        None,
        description="Unique normalized search_knowledge query count",
    )
    tool_search_duplicate_count: int | None = Field(
        None,
        description="Duplicate search_knowledge query count",
    )
    tool_read_count: int | None = Field(None, description="Number of read_knowledge calls")
    tool_finalize_reason: (
        Literal["normal_no_tools", "max_round_force_finalize", "fallback_empty_answer"] | None
    ) = Field(
        None,
        description="Finalization reason of the tool loop",
    )
