"""Session-scoped RAG tools for function calling."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import BaseTool, StructuredTool
from pydantic import BaseModel, Field, ValidationError

from .source_context_service import SourceContextService

logger = logging.getLogger(__name__)


class SearchKnowledgeArgs(BaseModel):
    """Arguments for search_knowledge tool."""

    query: str = Field(..., min_length=1, max_length=500, description="Natural-language search query")
    top_k: int = Field(5, ge=1, le=8, description="Maximum number of hits to return")
    include_diagnostics: bool = Field(
        False,
        description="Whether to include condensed retrieval diagnostics in the result",
    )


class ReadKnowledgeArgs(BaseModel):
    """Arguments for read_knowledge tool."""

    refs: List[str] = Field(
        ...,
        min_length=1,
        max_length=8,
        description="Reference ids returned by search_knowledge, e.g. kb:foo|doc:bar|chunk:3",
    )
    max_chars: int = Field(6000, ge=1000, le=12000, description="Total max characters to return")
    neighbor_window: int = Field(
        0,
        ge=0,
        le=2,
        description="Include +/- N adjacent chunks around each requested chunk",
    )


class RagToolService:
    """Provides retrieval and read tools limited to assistant-bound knowledge bases."""

    _MAX_TOP_K = 8
    _MAX_REFS = 8
    _REF_PATTERN = re.compile(r"^kb:(?P<kb>[^|]+)\|doc:(?P<doc>[^|]+)\|chunk:(?P<chunk>\d+)$")

    def __init__(
        self,
        *,
        assistant_id: str,
        allowed_kb_ids: List[str],
        runtime_model_id: Optional[str] = None,
        rag_service: Optional[Any] = None,
        bm25_service: Optional[Any] = None,
        sqlite_vec_service: Optional[Any] = None,
    ):
        from .bm25_service import Bm25Service
        from .rag_service import RagService
        from .sqlite_vec_service import SqliteVecService

        self.assistant_id = assistant_id
        self.allowed_kb_ids = sorted({str(kb_id).strip() for kb_id in (allowed_kb_ids or []) if str(kb_id).strip()})
        self.runtime_model_id = runtime_model_id
        self.rag_service = rag_service or RagService()
        self.bm25_service = bm25_service or Bm25Service()
        self.sqlite_vec_service = sqlite_vec_service or SqliteVecService()
        self.source_context_service = SourceContextService()

        self._citation_to_ref: Dict[str, str] = {}
        self._ref_to_citation: Dict[str, str] = {}
        self._search_cache: Dict[str, Dict[str, Any]] = {}

    @staticmethod
    def _json(data: Dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False)

    def _error(self, code: str, message: str, **extra: Any) -> str:
        payload: Dict[str, Any] = {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
        }
        payload.update(extra)
        return self._json(payload)

    @staticmethod
    def _normalize_snippet(text: str, max_chars: int = 360) -> str:
        compact = " ".join((text or "").split())
        if len(compact) <= max_chars:
            return compact
        return f"{compact[:max_chars]}..."

    @staticmethod
    def _normalize_query(query: str) -> str:
        lowered = (query or "").strip().lower()
        # Keep only word-ish tokens so tiny punctuation changes hit the same cache key.
        lowered = re.sub(r"[^\w\s]", " ", lowered)
        return " ".join(lowered.split())

    @staticmethod
    def _search_cache_key(normalized_query: str, top_k: int) -> str:
        return f"{normalized_query}|k:{int(top_k)}"

    def _restore_ref_maps_from_hits(self, hits: List[Dict[str, Any]]) -> None:
        self._citation_to_ref.clear()
        self._ref_to_citation.clear()
        for hit in hits:
            citation_id = str(hit.get("citation_id") or "").strip()
            ref_id = str(hit.get("ref_id") or "").strip()
            if not citation_id or not ref_id:
                continue
            self._citation_to_ref[citation_id] = ref_id
            self._ref_to_citation[ref_id] = citation_id

    @staticmethod
    def build_ref_id(*, kb_id: str, doc_id: str, chunk_index: int) -> str:
        return f"kb:{kb_id}|doc:{doc_id}|chunk:{int(chunk_index)}"

    @classmethod
    def parse_ref_id(cls, ref_id: str) -> Optional[Tuple[str, str, int]]:
        match = cls._REF_PATTERN.match((ref_id or "").strip())
        if not match:
            return None
        kb_id = match.group("kb")
        doc_id = match.group("doc")
        chunk_index = int(match.group("chunk"))
        return kb_id, doc_id, chunk_index

    async def search_knowledge(
        self,
        *,
        query: str,
        top_k: int = 5,
        include_diagnostics: bool = False,
    ) -> str:
        query_text = (query or "").strip()
        if not query_text:
            return self._error("INVALID_QUERY", "query cannot be empty")
        if not self.allowed_kb_ids:
            return self._error("NO_KB_ACCESS", "assistant has no bound knowledge bases")

        safe_top_k = max(1, min(int(top_k or 5), self._MAX_TOP_K))
        normalized_query = self._normalize_query(query_text)
        cache_key = self._search_cache_key(normalized_query, safe_top_k)
        cached = self._search_cache.get(cache_key)
        if cached:
            cached_hits = list(cached.get("hits") or [])
            self._restore_ref_maps_from_hits(cached_hits)
            payload: Dict[str, Any] = {
                "ok": True,
                "query_original": query_text,
                "query_effective": cached.get("query_effective", query_text),
                "retrieval_queries": cached.get("retrieval_queries", [query_text]),
                "planner_applied": bool(cached.get("planner_applied", False)),
                "normalized_query": normalized_query,
                "from_cache": True,
                "duplicate_suppressed": True,
                "hits": cached_hits,
            }
            if include_diagnostics:
                payload["diagnostics"] = dict(cached.get("diagnostics") or {})
            return self._json(payload)

        try:
            results, diagnostics = await self.rag_service.retrieve_with_diagnostics(
                query=query_text,
                kb_ids=self.allowed_kb_ids,
                top_k=safe_top_k,
                runtime_model_id=self.runtime_model_id,
            )
        except Exception as e:
            logger.warning("search_knowledge failed: %s", e)
            return self._error("RETRIEVAL_FAILED", f"search failed: {e}")

        hits: List[Dict[str, Any]] = []
        for index, result in enumerate(results[:safe_top_k], start=1):
            ref_id = self.build_ref_id(
                kb_id=result.kb_id,
                doc_id=result.doc_id,
                chunk_index=result.chunk_index,
            )
            citation_id = f"S{index}"
            score_value = result.final_score if result.final_score is not None else result.score
            hits.append(
                {
                    "ref_id": ref_id,
                    "citation_id": citation_id,
                    "kb_id": result.kb_id,
                    "doc_id": result.doc_id,
                    "filename": result.filename,
                    "chunk_index": int(result.chunk_index),
                    "score": float(score_value),
                    "snippet": self._normalize_snippet(result.content),
                }
            )
        self._restore_ref_maps_from_hits(hits)

        condensed_diagnostics = {
            "retrieval_mode": diagnostics.get("retrieval_mode"),
            "raw_count": diagnostics.get("raw_count"),
            "selected_count": diagnostics.get("selected_count"),
            "retrieval_query_count": diagnostics.get("retrieval_query_count"),
            "query_transform_applied": diagnostics.get("query_transform_applied"),
            "rerank_applied": diagnostics.get("rerank_applied"),
        }
        payload: Dict[str, Any] = {
            "ok": True,
            "query_original": query_text,
            "query_effective": diagnostics.get("query_effective", query_text),
            "retrieval_queries": diagnostics.get("retrieval_queries", [query_text]),
            "planner_applied": bool(diagnostics.get("retrieval_query_planner_applied", False)),
            "normalized_query": normalized_query,
            "from_cache": False,
            "duplicate_suppressed": False,
            "hits": hits,
        }
        self._search_cache[cache_key] = {
            "query_effective": payload["query_effective"],
            "retrieval_queries": list(payload["retrieval_queries"] or [query_text]),
            "planner_applied": payload["planner_applied"],
            "diagnostics": condensed_diagnostics,
            "hits": hits,
        }
        if include_diagnostics:
            payload["diagnostics"] = condensed_diagnostics

        return self._json(payload)

    def _resolve_refs(self, refs: List[str]) -> Tuple[List[Tuple[str, str]], List[str]]:
        resolved: List[Tuple[str, str]] = []
        invalid_refs: List[str] = []
        seen = set()

        for raw_ref in refs[: self._MAX_REFS]:
            token = str(raw_ref or "").strip()
            if not token:
                continue

            if token in self._citation_to_ref:
                citation_id = token
                ref_id = self._citation_to_ref[token]
            else:
                citation_id = self._ref_to_citation.get(token, "")
                ref_id = token

            if ref_id in seen:
                continue
            seen.add(ref_id)

            if self.parse_ref_id(ref_id) is None:
                invalid_refs.append(token)
                continue

            resolved.append((citation_id, ref_id))

        return resolved, invalid_refs

    def _list_rows_in_range(
        self,
        *,
        kb_id: str,
        doc_id: str,
        start_index: int,
        end_index: int,
    ) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        try:
            rows = self.bm25_service.list_document_chunks_in_range(
                kb_id=kb_id,
                doc_id=doc_id,
                start_index=start_index,
                end_index=end_index,
                limit=64,
            )
        except Exception as e:
            logger.warning("BM25 chunk range read failed: %s", e)

        if rows:
            return rows

        try:
            if hasattr(self.sqlite_vec_service, "list_document_chunks_in_range"):
                rows = self.sqlite_vec_service.list_document_chunks_in_range(
                    kb_id=kb_id,
                    doc_id=doc_id,
                    start_index=start_index,
                    end_index=end_index,
                    limit=64,
                )
        except Exception as e:
            logger.warning("SQLite vector chunk range read failed: %s", e)
        return rows

    @staticmethod
    def _pick_content(rows: List[Dict[str, Any]], target_chunk_index: int, neighbor_window: int) -> str:
        if not rows:
            return ""

        sorted_rows = sorted(rows, key=lambda row: int(row.get("chunk_index", 0)))
        if neighbor_window <= 0:
            exact = next(
                (row for row in sorted_rows if int(row.get("chunk_index", -1)) == int(target_chunk_index)),
                None,
            )
            chosen = exact or sorted_rows[0]
            return str(chosen.get("content") or "").strip()

        merged_parts: List[str] = []
        for row in sorted_rows:
            idx = int(row.get("chunk_index", 0))
            content = str(row.get("content") or "").strip()
            if not content:
                continue
            merged_parts.append(f"[chunk {idx}]\n{content}")
        return "\n\n".join(merged_parts)

    async def read_knowledge(
        self,
        *,
        refs: List[str],
        max_chars: int = 6000,
        neighbor_window: int = 0,
    ) -> str:
        if not self.allowed_kb_ids:
            return self._error("NO_KB_ACCESS", "assistant has no bound knowledge bases")

        safe_max_chars = max(1000, min(int(max_chars or 6000), 12000))
        safe_neighbor_window = max(0, min(int(neighbor_window or 0), 2))
        resolved_refs, invalid_refs = self._resolve_refs(refs)
        if not resolved_refs:
            return self._error(
                "INVALID_REF",
                "no valid refs provided",
                invalid_refs=invalid_refs,
            )

        used_chars = 0
        truncated = False
        missing_refs: List[str] = list(invalid_refs)
        sources: List[Dict[str, Any]] = []
        context_sources: List[Dict[str, Any]] = []
        read_index = 1

        for citation_id, ref_id in resolved_refs:
            parsed = self.parse_ref_id(ref_id)
            if parsed is None:
                missing_refs.append(ref_id)
                continue
            kb_id, doc_id, chunk_index = parsed
            if kb_id not in self.allowed_kb_ids:
                missing_refs.append(ref_id)
                continue

            start_index = max(0, chunk_index - safe_neighbor_window)
            end_index = chunk_index + safe_neighbor_window
            rows = self._list_rows_in_range(
                kb_id=kb_id,
                doc_id=doc_id,
                start_index=start_index,
                end_index=end_index,
            )
            content = self._pick_content(rows, chunk_index, safe_neighbor_window)
            if not content:
                missing_refs.append(ref_id)
                continue

            remaining = safe_max_chars - used_chars
            if remaining <= 0:
                truncated = True
                break
            if len(content) > remaining:
                content = content[:remaining]
                truncated = True

            filename = str(rows[0].get("filename") or "") if rows else ""
            if not citation_id:
                citation_id = f"R{read_index}"
            read_index += 1

            source_row = {
                "citation_id": citation_id,
                "ref_id": ref_id,
                "kb_id": kb_id,
                "doc_id": doc_id,
                "filename": filename,
                "chunk_index": int(chunk_index),
                "content": content,
            }
            sources.append(source_row)
            context_sources.append(
                {
                    "type": "rag",
                    "kb_id": kb_id,
                    "doc_id": doc_id,
                    "filename": filename,
                    "chunk_index": int(chunk_index),
                    "content": content,
                }
            )
            used_chars += len(content)

        if not sources:
            return self._error(
                "NOT_FOUND",
                "no chunks found for provided refs",
                missing_refs=missing_refs,
            )

        context_block = self.source_context_service.build_source_tags(
            query="",
            sources=context_sources,
            max_sources=self._MAX_REFS,
            max_chars_per_source=2000,
        )

        return self._json(
            {
                "ok": True,
                "total_chars": used_chars,
                "truncated": truncated,
                "missing_refs": missing_refs,
                "sources": sources,
                "context_block": context_block,
            }
        )

    def get_tools(self) -> List[BaseTool]:
        """Build session-scoped tool schemas for function calling."""

        async def _search_knowledge(
            query: str,
            top_k: int = 5,
            include_diagnostics: bool = False,
        ) -> str:
            return await self.search_knowledge(
                query=query,
                top_k=top_k,
                include_diagnostics=include_diagnostics,
            )

        async def _read_knowledge(
            refs: List[str],
            max_chars: int = 6000,
            neighbor_window: int = 0,
        ) -> str:
            return await self.read_knowledge(
                refs=refs,
                max_chars=max_chars,
                neighbor_window=neighbor_window,
            )

        return [
            StructuredTool.from_function(
                coroutine=_search_knowledge,
                name="search_knowledge",
                description=(
                    "Search assistant-bound knowledge bases and return concise hits with ref_id. "
                    "Call this before read_knowledge."
                ),
                args_schema=SearchKnowledgeArgs,
            ),
            StructuredTool.from_function(
                coroutine=_read_knowledge,
                name="read_knowledge",
                description=(
                    "Read full chunk content by refs returned from search_knowledge. "
                    "Use this when you need exact wording for grounded answers."
                ),
                args_schema=ReadKnowledgeArgs,
            ),
        ]

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Optional[str]:
        """Execute a supported RAG tool by name. Return None if unknown."""
        try:
            if name == "search_knowledge":
                parsed = SearchKnowledgeArgs(**(args or {}))
                return await self.search_knowledge(
                    query=parsed.query,
                    top_k=parsed.top_k,
                    include_diagnostics=parsed.include_diagnostics,
                )
            if name == "read_knowledge":
                parsed = ReadKnowledgeArgs(**(args or {}))
                return await self.read_knowledge(
                    refs=parsed.refs,
                    max_chars=parsed.max_chars,
                    neighbor_window=parsed.neighbor_window,
                )
            return None
        except ValidationError as e:
            return self._error("INVALID_ARGS", f"{e}")
        except Exception as e:
            logger.error("RAG tool execution error (%s): %s", name, e, exc_info=True)
            return self._error("TOOL_ERROR", f"{e}")
