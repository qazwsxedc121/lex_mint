"""
Retrieval Query Planner Service

Optional pre-retrieval query planning for RAG.
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from dataclasses import dataclass
from typing import Optional

from .model_config_service import ModelConfigService

logger = logging.getLogger(__name__)


@dataclass
class RetrievalQueryPlan:
    """Result payload for retrieval query planning."""

    original_query: str
    planned_queries: list[str]
    planner_enabled: bool
    planner_applied: bool
    fallback_used: bool
    planner_model_id: str
    reason: str


class RetrievalQueryPlannerService:
    """Service for optional multi-query planning before retrieval."""

    def __init__(self):
        self.model_config_service = ModelConfigService()

    @staticmethod
    def _resolve_model_id(
        configured_model_id: str, runtime_model_id: Optional[str]
    ) -> tuple[Optional[str], str]:
        configured = str(configured_model_id or "auto").strip() or "auto"
        if configured.lower() == "auto":
            runtime = str(runtime_model_id or "").strip()
            if runtime:
                return runtime, runtime
            return None, "auto"
        return configured, configured

    @staticmethod
    def _build_planner_prompt(query: str, max_queries: int) -> str:
        capped = max(1, min(8, int(max_queries or 3)))
        return (
            "You are a retrieval query planner for a RAG system.\n"
            "Generate concise retrieval queries for the same user intent.\n"
            "Rules:\n"
            "1) Keep the original language.\n"
            "2) Preserve named entities, numbers, dates, and constraints.\n"
            "3) Do not answer the question.\n"
            "4) Return JSON only.\n"
            f'5) Return at most {capped} queries as: {{"queries":["..."]}}.\n\n'
            f"User query: {query}\n"
            "Output JSON:"
        )

    @staticmethod
    def _extract_text(response: object) -> str:
        content = getattr(response, "content", "")
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict):
                    text = item.get("text")
                    if text:
                        parts.append(str(text))
                elif isinstance(item, str):
                    parts.append(item)
            content = "".join(parts)
        return str(content or "").strip()

    @staticmethod
    def _parse_queries_from_text(text: str) -> list[str]:
        raw = str(text or "").strip()
        if not raw:
            return []

        # First try strict JSON.
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                queries = parsed.get("queries", [])
                if isinstance(queries, list):
                    return [str(item).strip() for item in queries if str(item).strip()]
        except Exception:
            pass

        # Try to recover a JSON object from mixed output.
        try:
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                parsed = json.loads(raw[start : end + 1])
                queries = parsed.get("queries", []) if isinstance(parsed, dict) else []
                if isinstance(queries, list):
                    return [str(item).strip() for item in queries if str(item).strip()]
        except Exception:
            pass

        # Fallback: one query per non-empty line (supports bullet lists).
        lines = []
        for line in raw.splitlines():
            cleaned = re.sub(r"^\s*[-*\d.)]+\s*", "", line).strip()
            if cleaned:
                lines.append(cleaned)
        return lines

    @staticmethod
    def _normalize_queries(
        original_query: str, candidate_queries: list[str], max_queries: int
    ) -> list[str]:
        limit = max(1, min(8, int(max_queries or 3)))
        normalized_original = " ".join(str(original_query or "").split()).strip()
        if not normalized_original:
            return []

        final_queries = [normalized_original]
        seen = {normalized_original.lower()}

        for candidate in candidate_queries:
            query = " ".join(str(candidate or "").split()).strip()
            if not query:
                continue
            key = query.lower()
            if key in seen:
                continue
            seen.add(key)
            final_queries.append(query)
            if len(final_queries) >= limit:
                break

        return final_queries

    async def plan_queries(
        self,
        *,
        query: str,
        runtime_model_id: Optional[str],
        enabled: bool,
        max_queries: int,
        timeout_seconds: int,
        model_id: str,
    ) -> RetrievalQueryPlan:
        original_query = " ".join(str(query or "").split()).strip()
        if not enabled:
            return RetrievalQueryPlan(
                original_query=original_query,
                planned_queries=[original_query] if original_query else [],
                planner_enabled=False,
                planner_applied=False,
                fallback_used=False,
                planner_model_id=str(model_id or "auto"),
                reason="disabled",
            )

        if not original_query:
            return RetrievalQueryPlan(
                original_query=original_query,
                planned_queries=[],
                planner_enabled=True,
                planner_applied=False,
                fallback_used=True,
                planner_model_id=str(model_id or "auto"),
                reason="empty_query",
            )

        resolved_model_id, resolved_model_label = self._resolve_model_id(
            model_id, runtime_model_id
        )
        if not resolved_model_id:
            return RetrievalQueryPlan(
                original_query=original_query,
                planned_queries=[original_query],
                planner_enabled=True,
                planner_applied=False,
                fallback_used=True,
                planner_model_id=resolved_model_label,
                reason="model_unavailable",
            )

        try:
            llm = self.model_config_service.get_llm_instance(
                model_id=resolved_model_id,
                temperature=0.0,
                max_tokens=220,
            )
            prompt = self._build_planner_prompt(original_query, max_queries)
            response = await asyncio.wait_for(
                llm.ainvoke(prompt),
                timeout=max(1, int(timeout_seconds or 4)),
            )
            planner_output = self._extract_text(response)
            parsed_queries = self._parse_queries_from_text(planner_output)
            planned_queries = self._normalize_queries(
                original_query, parsed_queries, max_queries
            )

            if not planned_queries:
                planned_queries = [original_query]
                return RetrievalQueryPlan(
                    original_query=original_query,
                    planned_queries=planned_queries,
                    planner_enabled=True,
                    planner_applied=False,
                    fallback_used=True,
                    planner_model_id=resolved_model_label,
                    reason="empty_plan",
                )

            return RetrievalQueryPlan(
                original_query=original_query,
                planned_queries=planned_queries,
                planner_enabled=True,
                planner_applied=len(planned_queries) > 1,
                fallback_used=False,
                planner_model_id=resolved_model_label,
                reason="ok",
            )
        except Exception as e:
            logger.warning(
                "Retrieval query planner failed; fallback to original query: %s", e
            )
            return RetrievalQueryPlan(
                original_query=original_query,
                planned_queries=[original_query],
                planner_enabled=True,
                planner_applied=False,
                fallback_used=True,
                planner_model_id=resolved_model_label,
                reason="error",
            )
