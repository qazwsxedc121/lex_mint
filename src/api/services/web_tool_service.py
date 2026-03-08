"""Request-scoped web tools backed by SearchService and WebpageService."""

from __future__ import annotations

import json
import logging
from urllib.parse import urlparse
from typing import Any, Dict, List, Optional

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
        search_service: Optional[Any] = None,
        webpage_service: Optional[Any] = None,
    ):
        self.search_service = search_service or SearchService()
        self.webpage_service = webpage_service or WebpageService()

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
    def _normalize_text(value: Any, *, limit: Optional[int] = None) -> str:
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

    async def web_search(self, *, query: str) -> str:
        query_text = (query or "").strip()
        if not query_text:
            return self._error("EMPTY_QUERY", "query must not be empty")

        try:
            raw_results = await self.search_service.search(query_text)
        except Exception as exc:
            logger.error("web_search failed: %s", exc, exc_info=True)
            return self._error("SEARCH_FAILED", f"{exc}", query=query_text)

        results: List[Dict[str, Any]] = []
        for index, item in enumerate(raw_results, start=1):
            if hasattr(item, "model_dump"):
                payload = item.model_dump()
            else:
                payload = dict(item)
            url = str(payload.get("url") or "").strip()
            results.append(
                {
                    "rank": index,
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
                "provider": getattr(getattr(self.search_service, "config", None), "provider", "unknown"),
                "has_results": bool(results),
                "total_results": len(results),
                "results": results,
            }
        )

    async def read_webpage(self, *, url: str) -> str:
        url_text = (url or "").strip()
        if not url_text:
            return self._error("EMPTY_URL", "url must not be empty")
        if not self._is_supported_url(url_text):
            return self._error("INVALID_URL", "url must be an absolute http or https URL", url=url_text)

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

    def get_tools(self) -> List[BaseTool]:
        """Build request-scoped web tools for function calling."""

        async def _web_search(query: str) -> str:
            return await self.web_search(query=query)

        async def _read_webpage(url: str) -> str:
            return await self.read_webpage(url=url)

        return [
            WEB_SEARCH_TOOL.build_tool(coroutine=_web_search),
            READ_WEBPAGE_TOOL.build_tool(coroutine=_read_webpage),
        ]

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Optional[str]:
        """Execute a supported web tool by name. Return None if unknown."""
        try:
            if name == "web_search":
                parsed = WebSearchArgs.model_validate(args or {})
                return await self.web_search(query=parsed.query)
            if name == "read_webpage":
                parsed = ReadWebpageArgs.model_validate(args or {})
                return await self.read_webpage(url=parsed.url)
            return None
        except ValidationError as exc:
            return self._error("INVALID_ARGS", f"{exc}")
        except Exception as exc:
            logger.error("Web tool execution error (%s): %s", name, exc, exc_info=True)
            return self._error("TOOL_ERROR", f"{exc}")
