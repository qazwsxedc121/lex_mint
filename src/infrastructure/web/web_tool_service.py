"""Request-scoped web tools backed by SearchService and WebpageService."""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import urlparse

from langchain_core.tools import BaseTool
from pydantic import ValidationError

from src.tools.request_scoped import (
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
            return self._error("EMPTY_QUERY", "query must not be empty")
        safe_page = max(1, int(page or 1))

        try:
            raw_results = await self.search_service.search(query_text, page=safe_page)
        except ValueError as exc:
            logger.warning("web_search pagination not supported: %s", exc)
            return self._error("UNSUPPORTED_PAGE", f"{exc}", query=query_text, page=safe_page)
        except Exception as exc:
            logger.error("web_search failed: %s", exc, exc_info=True)
            return self._error("SEARCH_FAILED", f"{exc}", query=query_text, page=safe_page)

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
            }
        )

    async def read_webpage(self, *, url: str) -> str:
        url_text = (url or "").strip()
        if not url_text:
            return self._error("EMPTY_URL", "url must not be empty")
        if not self._is_supported_url(url_text):
            return self._error(
                "INVALID_URL", "url must be an absolute http or https URL", url=url_text
            )

        try:
            result = await self.webpage_service.fetch_and_parse(url_text)
        except Exception as exc:
            logger.error("read_webpage failed: %s", exc, exc_info=True)
            return self._error("READ_WEBPAGE_FAILED", f"{exc}", url=url_text)

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
