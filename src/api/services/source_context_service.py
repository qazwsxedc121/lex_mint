"""Structured source context rendering for prompt injection."""

from __future__ import annotations

from html import escape
from typing import Any, Dict, List, Optional


class SourceContextService:
    """Builds a structured source block that can be injected into system prompts."""

    DEFAULT_TEMPLATE = (
        "Use the following structured sources to answer the user query.\n"
        "Prefer citing source ids like [1], [2] when applicable.\n\n"
        "<query>{{QUERY}}</query>\n"
        "<sources>\n"
        "{{CONTEXT}}\n"
        "</sources>"
    )

    @staticmethod
    def _truncate_text(text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return f"{text[:max_chars]}..."

    @staticmethod
    def _build_diagnostics_body(source: Dict[str, Any]) -> str:
        parts: List[str] = []
        snippet = str(source.get("snippet") or "").strip()
        if snippet:
            parts.append(f"summary: {snippet}")

        fields = [
            "retrieval_mode",
            "raw_count",
            "selected_count",
            "retrieval_query_count",
            "query_transform_mode",
            "query_transform_crag_decision",
            "query_effective",
        ]
        metrics: List[str] = []
        for key in fields:
            if key not in source:
                continue
            value = source.get(key)
            if value is None or str(value).strip() == "":
                continue
            metrics.append(f"{key}={value}")
        if metrics:
            parts.append("metrics: " + ", ".join(metrics))

        return "\n".join(parts)

    def _build_source_body(self, source: Dict[str, Any], max_chars_per_source: int) -> str:
        source_type = str(source.get("type") or "").strip().lower()
        if source_type == "rag_diagnostics":
            body = self._build_diagnostics_body(source)
            return self._truncate_text(body, max_chars_per_source).strip()

        for key in ("content", "snippet"):
            value = str(source.get(key) or "").strip()
            if value:
                return self._truncate_text(value, max_chars_per_source)

        fallback_parts: List[str] = []
        title = str(source.get("title") or "").strip()
        url = str(source.get("url") or "").strip()
        if title:
            fallback_parts.append(f"title: {title}")
        if url:
            fallback_parts.append(f"url: {url}")
        fallback_text = "\n".join(fallback_parts).strip()
        return self._truncate_text(fallback_text, max_chars_per_source) if fallback_text else ""

    def build_source_tags(
        self,
        *,
        query: str,
        sources: List[Dict[str, Any]],
        max_sources: int = 20,
        max_chars_per_source: int = 1200,
    ) -> str:
        """Render `<source ...>` tags from source dict items."""
        _ = query
        if not sources:
            return ""

        limited_sources = list(sources)[: max(1, int(max_sources or 20))]
        tags: List[str] = []
        for index, source in enumerate(limited_sources, start=1):
            if not isinstance(source, dict):
                continue

            body = self._build_source_body(source, max_chars_per_source=max(120, max_chars_per_source))
            if not body:
                continue

            attrs: Dict[str, Optional[str]] = {
                "id": str(index),
                "type": str(source.get("type") or "unknown"),
                "title": str(source.get("title") or ""),
                "url": str(source.get("url") or ""),
                "kb_id": str(source.get("kb_id") or ""),
                "doc_id": str(source.get("doc_id") or ""),
                "filename": str(source.get("filename") or ""),
                "chunk_index": (
                    str(source.get("chunk_index"))
                    if source.get("chunk_index") is not None
                    else ""
                ),
                "scope": str(source.get("scope") or ""),
                "layer": str(source.get("layer") or ""),
            }

            attr_text = " ".join(
                f'{key}="{escape(str(value), quote=True)}"'
                for key, value in attrs.items()
                if value is not None and str(value).strip() != ""
            )
            tags.append(f"<source {attr_text}>\n{escape(body)}\n</source>")

        return "\n".join(tags)

    def apply_template(
        self,
        *,
        query: str,
        source_context: str,
        template: Optional[str] = None,
    ) -> str:
        """Apply a source template with `{{QUERY}}` and `{{CONTEXT}}` placeholders."""
        if not source_context:
            return ""
        selected_template = str(template or self.DEFAULT_TEMPLATE)
        query_text = str(query or "").strip()
        return (
            selected_template.replace("{{QUERY}}", escape(query_text))
            .replace("{{CONTEXT}}", source_context.strip())
            .strip()
        )
