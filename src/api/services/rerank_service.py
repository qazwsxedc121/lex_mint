"""
Rerank Service

Optional API-based reranking for retrieved RAG chunks.
"""
from __future__ import annotations

from typing import Dict, List
import logging

import httpx


logger = logging.getLogger(__name__)


class RerankService:
    """Service for optional rerank API calls."""

    async def rerank(
        self,
        *,
        query: str,
        documents: List[str],
        model: str,
        base_url: str,
        api_key: str,
        timeout_seconds: int,
    ) -> Dict[int, float]:
        if not query or not documents:
            return {}

        payload = {
            "model": model,
            "query": query,
            "documents": documents,
            "top_n": len(documents),
            "return_documents": False,
        }
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        timeout = httpx.Timeout(max(1, int(timeout_seconds)))
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(base_url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        scores = self._extract_scores(data)
        return self._normalize_scores(scores)

    @staticmethod
    def _extract_scores(data: dict) -> Dict[int, float]:
        rows = data.get("results") or data.get("data") or []
        if not isinstance(rows, list):
            raise ValueError("Rerank response missing results list.")

        scores: Dict[int, float] = {}
        for item in rows:
            if not isinstance(item, dict):
                continue
            idx = item.get("index")
            score = item.get("relevance_score")
            if score is None:
                score = item.get("score")
            if isinstance(idx, int) and isinstance(score, (float, int)):
                scores[idx] = float(score)
        return scores

    @staticmethod
    def _normalize_scores(scores: Dict[int, float]) -> Dict[int, float]:
        if not scores:
            return {}

        values = list(scores.values())
        all_in_unit = all(0.0 <= val <= 1.0 for val in values)
        if all_in_unit:
            return scores

        min_val = min(values)
        max_val = max(values)
        if max_val - min_val <= 1e-12:
            return {idx: 1.0 for idx in scores}
        return {idx: (val - min_val) / (max_val - min_val) for idx, val in scores.items()}
