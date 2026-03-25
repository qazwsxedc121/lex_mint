"""Shared helpers for source aggregation and diagnostics enrichment."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.application.chat.service_contracts import SourcePayload


def merge_source_groups(*source_groups: Optional[List[SourcePayload]]) -> List[SourcePayload]:
    """Return a flat source list while ignoring empty groups."""
    merged: List[SourcePayload] = []
    for group in source_groups:
        if group:
            merged.extend(group)
    return merged


def merge_tool_diagnostics_into_sources(
    all_sources: List[SourcePayload],
    tool_diagnostics: Optional[Dict[str, Any]],
) -> List[SourcePayload]:
    """Merge low-level tool diagnostics into the stable rag diagnostics source."""
    merged_sources = list(all_sources or [])
    if not tool_diagnostics:
        return merged_sources

    payload = {
        "tool_search_count": int(tool_diagnostics.get("tool_search_count", 0) or 0),
        "tool_search_unique_count": int(
            tool_diagnostics.get("tool_search_unique_count", 0) or 0
        ),
        "tool_search_duplicate_count": int(
            tool_diagnostics.get("tool_search_duplicate_count", 0) or 0
        ),
        "tool_read_count": int(tool_diagnostics.get("tool_read_count", 0) or 0),
        "tool_finalize_reason": str(
            tool_diagnostics.get("tool_finalize_reason", "normal_no_tools") or "normal_no_tools"
        ),
    }

    diagnostics_index: Optional[int] = None
    for index in range(len(merged_sources) - 1, -1, -1):
        if str(merged_sources[index].get("type", "")) == "rag_diagnostics":
            diagnostics_index = index
            break

    should_create_new = (
        payload["tool_search_count"] > 0
        or payload["tool_read_count"] > 0
        or payload["tool_search_duplicate_count"] > 0
        or payload["tool_finalize_reason"] != "normal_no_tools"
    )
    if diagnostics_index is None:
        if not should_create_new:
            return merged_sources
        diagnostics_source: SourcePayload = {
            "type": "rag_diagnostics",
            "title": "RAG Diagnostics",
            "snippet": "Tool diagnostics",
        }
        merged_sources.append(diagnostics_source)
    else:
        diagnostics_source = dict(merged_sources[diagnostics_index])
        merged_sources[diagnostics_index] = diagnostics_source

    diagnostics_source.update(payload)
    tool_snippet = (
        f"tool s:{payload['tool_search_count']} "
        f"u:{payload['tool_search_unique_count']} "
        f"d:{payload['tool_search_duplicate_count']} "
        f"r:{payload['tool_read_count']} "
        f"f:{payload['tool_finalize_reason']}"
    )
    existing_snippet = str(diagnostics_source.get("snippet", "") or "").strip()
    existing_parts = [part.strip() for part in existing_snippet.split("|") if part.strip()]
    existing_parts = [part for part in existing_parts if not part.startswith("tool s:")]
    existing_parts.append(tool_snippet)
    diagnostics_source["snippet"] = " | ".join(existing_parts)
    return merged_sources
