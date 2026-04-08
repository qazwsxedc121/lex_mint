"""Web tool plugin entrypoint."""

from __future__ import annotations

from typing import Any

from src.infrastructure.web.search_service import SearchService
from src.infrastructure.web.web_tool_service import WebToolService
from src.infrastructure.web.webpage_service import WebpageService
from src.tools.plugins.web_tools_definitions import READ_WEBPAGE_TOOL, WEB_SEARCH_TOOL

from .models import ToolPluginContribution


def register() -> ToolPluginContribution:
    web_tool_service = WebToolService()
    search_service = SearchService()
    webpage_service = WebpageService()

    async def _build_web_search_context(
        *,
        raw_user_message: str,
        args: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        query = str(payload.get("query") or raw_user_message or "").strip()
        if not query:
            return {"context_key": "search_context", "context": None, "sources": []}
        if len(query) > 200:
            query = query[:200]
        page = payload.get("page", 1)
        try:
            page_num = max(1, min(int(page), 5))
        except Exception:
            page_num = 1
        sources = await search_service.search(query, page=page_num)
        search_context = search_service.build_search_context(query, sources) if sources else None
        return {
            "context_key": "search_context",
            "context": search_context,
            "sources": [source.model_dump() for source in sources],
        }

    async def _build_webpage_context(
        *,
        raw_user_message: str,
        args: dict[str, Any] | None = None,
        **_kwargs: Any,
    ) -> dict[str, Any]:
        payload = args if isinstance(args, dict) else {}
        text = str(payload.get("text") or raw_user_message or "").strip()
        if not text:
            return {"context_key": "webpage_context", "context": None, "sources": []}
        webpage_context, source_models = await webpage_service.build_context(text)
        return {
            "context_key": "webpage_context",
            "context": webpage_context,
            "sources": [source.model_dump() for source in source_models],
        }

    return ToolPluginContribution(
        definitions=[WEB_SEARCH_TOOL, READ_WEBPAGE_TOOL],
        tools=web_tool_service.get_tools(),
        tool_handlers={
            "web_search": web_tool_service.web_search,
            "read_webpage": web_tool_service.read_webpage,
        },
        context_capability_handlers={
            "web.search_context": _build_web_search_context,
            "web.webpage_context": _build_webpage_context,
        },
    )
