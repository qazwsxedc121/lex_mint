"""Request-scoped web tools backed by SearchService and WebpageService."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import BaseTool
from pydantic import ValidationError

from plugins.web_tools.definitions import (
    READ_WEBPAGE_TOOL,
    WEB_SEARCH_TOOL,
    ReadWebpageArgs,
    WebSearchArgs,
)

from .search_service import SearchService
from .webpage_service import WebpageService

logger = logging.getLogger(__name__)


class WebToolService:
    """Provides public web search and webpage reading tools."""

    def __init__(
        self,
        *,
        search_service: Any | None = None,
        webpage_service: Any | None = None,
    ):
        self.search_service = search_service or SearchService()
        self.webpage_service = webpage_service or WebpageService()

    @staticmethod
    def _json(data: dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False)

    def _error(self, code: str, message: str, **extra: Any) -> str:
        payload: dict[str, Any] = {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
        }
        payload.update(extra)
        return self._json(payload)

    @staticmethod
    def _ui_field(*, label: str, value: Any) -> dict[str, Any]:
        return {"label": label, "value": "" if value is None else str(value)}

    def _build_web_search_ui(
        self,
        *,
        query: str,
        provider: str,
        total_results: int,
        results: list[dict[str, Any]],
        ok: bool,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        fields = [
            self._ui_field(label="Query", value=query),
            self._ui_field(label="Provider", value=provider or "-"),
            self._ui_field(label="Results", value=total_results),
        ]
        item_cards: list[dict[str, Any]] = []
        for item in results:
            rank = item.get("rank")
            domain = str(item.get("domain") or "").strip()
            rank_text = f"#{rank}" if rank is not None else ""
            subtitle = " · ".join([part for part in [rank_text, domain] if part])
            item_cards.append(
                {
                    "title": str(item.get("title") or item.get("url") or "-"),
                    "subtitle": subtitle,
                    "description": str(item.get("snippet") or ""),
                    "url": str(item.get("url") or ""),
                }
            )
        return {
            "version": 1,
            "kind": "report",
            "summary": (f"{total_results} results" if ok else (error_message or "Search failed")),
            "status": "ok" if ok else "error",
            "error_message": error_message,
            "sections": [
                {"kind": "fields", "fields": fields},
                {
                    "kind": "items",
                    "title": "Results",
                    "empty_message": "No results returned.",
                    "items": item_cards,
                },
            ],
        }

    def _build_read_webpage_ui(
        self,
        *,
        url: str,
        final_url: str,
        domain: str,
        title: str,
        content: str,
        content_chars: int,
        truncated: bool,
        status_code: int | None,
        content_type: str | None,
        ok: bool,
        error_message: str | None = None,
    ) -> dict[str, Any]:
        target = final_url or url
        label = title or target or "Webpage"
        return {
            "version": 1,
            "kind": "report",
            "summary": label if ok else (error_message or "Read failed"),
            "status": "ok" if ok else "error",
            "error_message": error_message,
            "sections": [
                {
                    "kind": "fields",
                    "fields": [
                        self._ui_field(label="Requested URL", value=url),
                        self._ui_field(label="Final URL", value=final_url or "-"),
                        self._ui_field(label="Domain", value=domain or "-"),
                        self._ui_field(label="Content Type", value=content_type or "-"),
                        self._ui_field(
                            label="Status",
                            value=status_code if status_code is not None else "-",
                        ),
                        self._ui_field(label="Content Chars", value=content_chars),
                        self._ui_field(label="Truncated", value="yes" if truncated else "no"),
                    ],
                },
                {
                    "kind": "text",
                    "title": "Extracted content",
                    "text": content or "-",
                    "truncated": bool(truncated),
                },
            ],
        }

    @staticmethod
    def _normalize_text(value: Any, *, limit: int | None = None) -> str:
        text = str(value or "")
        text = " ".join(text.split())
        if limit is not None and len(text) > limit:
            return text[: max(0, limit - 3)].rstrip() + "..."
        return text

    @classmethod
    def _domain_from_url(cls, url: Any) -> str:
        text = str(url or "").strip()
        if not text:
            return ""
        try:
            return urlparse(text).netloc.lower()
        except Exception:
            return ""

    @classmethod
    def _is_supported_url(cls, url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    async def web_search(self, *, query: str, page: int = 1) -> str:
        query_text = (query or "").strip()
        if not query_text:
            return self._error(
                "EMPTY_QUERY",
                "query must not be empty",
                ui=self._build_web_search_ui(
                    query="",
                    provider="",
                    total_results=0,
                    results=[],
                    ok=False,
                    error_message="query must not be empty",
                ),
            )
        safe_page = max(1, int(page or 1))

        try:
            raw_results = await self.search_service.search(query_text, page=safe_page)
        except ValueError as exc:
            logger.warning("web_search pagination not supported: %s", exc)
            return self._error(
                "UNSUPPORTED_PAGE",
                f"{exc}",
                query=query_text,
                page=safe_page,
                ui=self._build_web_search_ui(
                    query=query_text,
                    provider=str(
                        getattr(getattr(self.search_service, "config", None), "provider", "")
                    ),
                    total_results=0,
                    results=[],
                    ok=False,
                    error_message=str(exc),
                ),
            )
        except Exception as exc:
            logger.error("web_search failed: %s", exc, exc_info=True)
            return self._error(
                "SEARCH_FAILED",
                f"{exc}",
                query=query_text,
                page=safe_page,
                ui=self._build_web_search_ui(
                    query=query_text,
                    provider=str(
                        getattr(getattr(self.search_service, "config", None), "provider", "")
                    ),
                    total_results=0,
                    results=[],
                    ok=False,
                    error_message=str(exc),
                ),
            )

        provider = getattr(getattr(self.search_service, "config", None), "provider", "unknown")
        page_size = max(
            1,
            int(
                getattr(
                    getattr(self.search_service, "config", None),
                    "max_results",
                    len(raw_results) or 1,
                )
            ),
        )
        offset = max(0, (safe_page - 1) * page_size)
        results: list[dict[str, Any]] = []
        for index, item in enumerate(raw_results, start=1):
            if hasattr(item, "model_dump"):
                payload = item.model_dump()
            else:
                payload = dict(item)
            url = str(payload.get("url") or "").strip()
            results.append(
                {
                    "rank": offset + index,
                    "title": self._normalize_text(payload.get("title"), limit=300),
                    "url": url,
                    "domain": self._domain_from_url(url),
                    "snippet": self._normalize_text(payload.get("snippet"), limit=600),
                }
            )

        return self._json(
            {
                "ok": True,
                "query": query_text,
                "page": safe_page,
                "page_size": page_size,
                "offset": offset,
                "provider": provider,
                "pagination_mode": (
                    "native"
                    if provider == "duckduckgo"
                    else "simulated"
                    if provider == "tavily"
                    else "unknown"
                ),
                "has_results": bool(results),
                "total_results": len(results),
                "has_more": (
                    len(raw_results) >= page_size
                    and len(raw_results) == page_size
                    and (
                        (provider == "duckduckgo" and safe_page < 5)
                        or (provider == "tavily" and safe_page < 2)
                    )
                ),
                "results": results,
                "ui": self._build_web_search_ui(
                    query=query_text,
                    provider=str(provider),
                    total_results=len(results),
                    results=results,
                    ok=True,
                ),
            }
        )

    async def read_webpage(self, *, url: str) -> str:
        url_text = (url or "").strip()
        if not url_text:
            return self._error(
                "EMPTY_URL",
                "url must not be empty",
                ui=self._build_read_webpage_ui(
                    url="",
                    final_url="",
                    domain="",
                    title="",
                    content="",
                    content_chars=0,
                    truncated=False,
                    status_code=None,
                    content_type=None,
                    ok=False,
                    error_message="url must not be empty",
                ),
            )
        if not self._is_supported_url(url_text):
            return self._error(
                "INVALID_URL",
                "url must be an absolute http or https URL",
                url=url_text,
                ui=self._build_read_webpage_ui(
                    url=url_text,
                    final_url="",
                    domain="",
                    title="",
                    content="",
                    content_chars=0,
                    truncated=False,
                    status_code=None,
                    content_type=None,
                    ok=False,
                    error_message="url must be an absolute http or https URL",
                ),
            )

        try:
            result = await self.webpage_service.fetch_and_parse(url_text)
        except Exception as exc:
            logger.error("read_webpage failed: %s", exc, exc_info=True)
            return self._error(
                "READ_WEBPAGE_FAILED",
                f"{exc}",
                url=url_text,
                ui=self._build_read_webpage_ui(
                    url=url_text,
                    final_url=url_text,
                    domain=self._domain_from_url(url_text),
                    title="",
                    content="",
                    content_chars=0,
                    truncated=False,
                    status_code=None,
                    content_type=None,
                    ok=False,
                    error_message=str(exc),
                ),
            )

        final_url = str(result.final_url or result.url or url_text)
        title = self._normalize_text(result.title, limit=300)
        content = str(result.text or "").strip()
        preview = self._normalize_text(content, limit=500)

        if result.error:
            return self._error(
                "READ_WEBPAGE_FAILED",
                result.error,
                url=result.url,
                final_url=final_url,
                domain=self._domain_from_url(final_url),
                status_code=result.status_code,
                content_type=result.content_type,
                ui=self._build_read_webpage_ui(
                    url=str(result.url or url_text),
                    final_url=final_url,
                    domain=self._domain_from_url(final_url),
                    title=title,
                    content="",
                    content_chars=0,
                    truncated=False,
                    status_code=result.status_code,
                    content_type=result.content_type,
                    ok=False,
                    error_message=str(result.error),
                ),
            )

        return self._json(
            {
                "ok": True,
                "url": result.url,
                "final_url": final_url,
                "domain": self._domain_from_url(final_url),
                "title": title,
                "content": content,
                "preview": preview,
                "content_chars": len(content),
                "truncated": result.truncated,
                "status_code": result.status_code,
                "content_type": result.content_type,
                "ui": self._build_read_webpage_ui(
                    url=str(result.url or url_text),
                    final_url=final_url,
                    domain=self._domain_from_url(final_url),
                    title=title,
                    content=content,
                    content_chars=len(content),
                    truncated=bool(result.truncated),
                    status_code=result.status_code,
                    content_type=result.content_type,
                    ok=True,
                ),
            }
        )

    def get_tools(self) -> list[BaseTool]:
        """Build request-scoped web tools for function calling."""

        async def _web_search(query: str, page: int = 1) -> str:
            return await self.web_search(query=query, page=page)

        async def _read_webpage(url: str) -> str:
            return await self.read_webpage(url=url)

        return [
            WEB_SEARCH_TOOL.build_tool(coroutine=_web_search),
            READ_WEBPAGE_TOOL.build_tool(coroutine=_read_webpage),
        ]

    async def execute_tool(self, name: str, args: dict[str, Any]) -> str | None:
        """Execute a supported web tool by name. Return None if unknown."""
        try:
            if name == "web_search":
                search_args = WebSearchArgs.model_validate(args or {})
                return await self.web_search(query=search_args.query, page=search_args.page)
            if name == "read_webpage":
                read_args = ReadWebpageArgs.model_validate(args or {})
                return await self.read_webpage(url=read_args.url)
            return None
        except ValidationError as exc:
            return self._error("INVALID_ARGS", f"{exc}")
        except Exception as exc:
            logger.error("Web tool execution error (%s): %s", name, exc, exc_info=True)
            return self._error("TOOL_ERROR", f"{exc}")
