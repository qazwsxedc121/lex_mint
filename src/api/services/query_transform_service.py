"""
Query Transform Service

Optional pre-retrieval query transformation for RAG.
"""
from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional, Set

from .model_config_service import ModelConfigService

logger = logging.getLogger(__name__)


@dataclass
class QueryTransformResult:
    """Result payload for a query transformation attempt."""

    original_query: str
    effective_query: str
    applied: bool
    mode: str
    configured_model_id: str
    resolved_model_id: str
    guard_blocked: bool
    guard_reason: str


class QueryTransformService:
    """Service for optional query rewriting before retrieval."""

    def __init__(self):
        self.model_config_service = ModelConfigService()

    @staticmethod
    def _normalize_mode(mode: str) -> str:
        normalized = str(mode or "none").strip().lower()
        if normalized in {"none", "rewrite"}:
            return normalized
        return "none"

    @staticmethod
    def _resolve_model_id(configured_model_id: str, runtime_model_id: Optional[str]) -> tuple[Optional[str], str]:
        configured = str(configured_model_id or "auto").strip() or "auto"
        if configured.lower() == "auto":
            runtime = str(runtime_model_id or "").strip()
            if runtime:
                return runtime, runtime
            return None, "auto"
        return configured, configured

    @staticmethod
    def _build_rewrite_prompt(query: str) -> str:
        return (
            "You are a retrieval query rewriter for RAG systems.\n"
            "Rewrite the user query to improve retrieval quality.\n"
            "Rules:\n"
            "1) Keep the original language.\n"
            "2) Preserve named entities, numbers, dates, and constraints.\n"
            "3) Do not answer the question.\n"
            "4) Do not add new facts.\n"
            "5) Output only one rewritten query line.\n\n"
            f"Original query: {query}\n"
            "Rewritten query:"
        )

    @staticmethod
    def _extract_quoted_phrases(text: str) -> Set[str]:
        matches = re.findall(r"[\"“”'‘’]([^\"“”'‘’]{2,120})[\"“”'‘’]", text or "")
        return {m.strip() for m in matches if m and m.strip()}

    @staticmethod
    def _extract_numbers(text: str) -> Set[str]:
        return {m for m in re.findall(r"\d+(?:[./:-]\d+)*", text or "") if m}

    @staticmethod
    def _tokenize_significant_terms(text: str) -> Set[str]:
        raw = str(text or "").lower()
        if not raw:
            return set()

        # Keep English words and CJK phrases for conservative rewrite guarding.
        tokens = re.findall(r"[a-z][a-z0-9_/.-]{2,}|[\u4e00-\u9fff]{2,}", raw)
        if not tokens:
            return set()

        stopwords = {
            "what", "which", "when", "where", "who", "whom", "whose", "why", "how",
            "the", "and", "for", "with", "from", "into", "that", "this", "these", "those",
            "about", "there", "their", "them", "your", "our", "his", "her", "its",
            "一个", "一种", "这个", "那个", "这些", "那些", "什么", "如何", "为什么", "以及",
            "相关", "有关", "问题", "内容", "信息", "出现", "对应", "哪章", "一章",
        }
        return {tok for tok in tokens if tok not in stopwords}

    @staticmethod
    def _missing_constraint_keyword(original_query: str, rewritten_query: str) -> Optional[str]:
        # Guard constraints/time qualifiers to reduce false-positive retrieval.
        protected_keywords = [
            "最终", "最后", "首次", "仅", "只", "必须", "不能", "不得",
            "至少", "最多", "不超过", "不少于",
            "only", "must", "must not", "cannot", "never", "at least", "at most",
        ]
        orig = str(original_query or "").lower()
        rew = str(rewritten_query or "").lower()
        for keyword in protected_keywords:
            key = keyword.lower()
            if key in orig and key not in rew:
                return keyword
        return None

    def _validate_rewrite(
        self,
        *,
        original_query: str,
        rewritten_query: str,
        max_new_terms: int,
    ) -> Optional[str]:
        original = str(original_query or "").strip()
        rewritten = str(rewritten_query or "").strip()
        if not original or not rewritten:
            return "empty_query"

        if original == rewritten:
            return None

        # Do not lose quoted phrases from the user query.
        original_quotes = self._extract_quoted_phrases(original)
        for phrase in sorted(original_quotes):
            if phrase not in rewritten:
                return f"missing_quoted_phrase:{phrase[:32]}"

        # Do not lose explicit numbers/dates.
        original_numbers = self._extract_numbers(original)
        rewritten_numbers = self._extract_numbers(rewritten)
        if not original_numbers.issubset(rewritten_numbers):
            missing = sorted(original_numbers - rewritten_numbers)
            return f"missing_numeric_constraint:{','.join(missing[:3])}"

        missing_constraint = self._missing_constraint_keyword(original, rewritten)
        if missing_constraint:
            return f"missing_constraint_keyword:{missing_constraint}"

        # Conservative anti-hallucination check: block rewrites that inject too many new terms.
        original_terms = self._tokenize_significant_terms(original)
        rewritten_terms = self._tokenize_significant_terms(rewritten)
        if original_terms and rewritten_terms:
            new_terms = sorted(rewritten_terms - original_terms)
            if len(new_terms) > max(0, int(max_new_terms)):
                return f"too_many_new_terms:{','.join(new_terms[:5])}"
        return None

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
        text = str(content or "").strip()
        if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
            text = text[1:-1].strip()
        return " ".join(text.split())

    async def transform_query(
        self,
        *,
        query: str,
        enabled: bool,
        mode: str,
        configured_model_id: str,
        runtime_model_id: Optional[str],
        timeout_seconds: int,
        guard_enabled: bool = True,
        guard_max_new_terms: int = 2,
    ) -> QueryTransformResult:
        original_query = str(query or "").strip()
        normalized_mode = self._normalize_mode(mode)
        resolved_model_id, resolved_label = self._resolve_model_id(configured_model_id, runtime_model_id)

        if not enabled or normalized_mode == "none" or not original_query:
            return QueryTransformResult(
                original_query=original_query,
                effective_query=original_query,
                applied=False,
                mode=normalized_mode,
                configured_model_id=str(configured_model_id or "auto"),
                resolved_model_id=resolved_label,
                guard_blocked=False,
                guard_reason="",
            )

        if normalized_mode != "rewrite":
            return QueryTransformResult(
                original_query=original_query,
                effective_query=original_query,
                applied=False,
                mode="none",
                configured_model_id=str(configured_model_id or "auto"),
                resolved_model_id=resolved_label,
                guard_blocked=False,
                guard_reason="",
            )

        try:
            llm = self.model_config_service.get_llm_instance(
                model_id=resolved_model_id,
                temperature=0.0,
                max_tokens=96,
                disable_thinking=True,
            )
            prompt = self._build_rewrite_prompt(original_query)
            response = await asyncio.wait_for(
                llm.ainvoke(prompt),
                timeout=max(1, int(timeout_seconds or 4)),
            )
            rewritten_query = self._extract_text(response)
            if not rewritten_query:
                rewritten_query = original_query

            guard_reason = ""
            guard_blocked = False
            if guard_enabled:
                guard_reason = self._validate_rewrite(
                    original_query=original_query,
                    rewritten_query=rewritten_query,
                    max_new_terms=guard_max_new_terms,
                ) or ""
                if guard_reason:
                    guard_blocked = True
                    rewritten_query = original_query
                    logger.info("Query transform blocked by guard: %s", guard_reason)

            return QueryTransformResult(
                original_query=original_query,
                effective_query=rewritten_query,
                applied=rewritten_query != original_query,
                mode=normalized_mode,
                configured_model_id=str(configured_model_id or "auto"),
                resolved_model_id=resolved_label,
                guard_blocked=guard_blocked,
                guard_reason=guard_reason,
            )
        except Exception as e:
            logger.warning("Query transform failed; fallback to original query: %s", e)
            return QueryTransformResult(
                original_query=original_query,
                effective_query=original_query,
                applied=False,
                mode=normalized_mode,
                configured_model_id=str(configured_model_id or "auto"),
                resolved_model_id=resolved_label,
                guard_blocked=False,
                guard_reason="",
            )
