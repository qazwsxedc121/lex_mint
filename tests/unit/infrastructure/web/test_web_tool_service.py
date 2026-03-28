"""Unit tests for request-scoped web tools."""

from __future__ import annotations

import asyncio
import json
from typing import Any, cast

from src.domain.models.search import SearchSource
from src.infrastructure.web.web_tool_service import WebToolService


def _make_search_source(**kwargs: Any) -> SearchSource:
    return cast(Any, SearchSource)(**kwargs)


class _FakeSearchConfig:
    provider = "duckduckgo"
    max_results = 10


class _FakeSearchService:
    def __init__(self):
        self.config = _FakeSearchConfig()
        self.last_query = None
        self.last_page = None

    async def search(self, query: str, *, page: int = 1):
        self.last_query = query
        self.last_page = page
        assert query in {"latest llm news", "latest llm news page 2"}
        return [
            _make_search_source(
                type="search", title="Result A", url="https://a.test", snippet="Snippet A"
            ),
            _make_search_source(
                type="search", title="Result B", url="https://b.test", snippet="Snippet B"
            ),
        ]


class _FakeWebpageResult:
    def __init__(self, *, error=None):
        self.url = "https://example.com/article"
        self.final_url = "https://example.com/article"
        self.title = "Example Article"
        self.text = "Main article content"
        self.truncated = False
        self.error = error
        self.status_code = 200 if error is None else 500
        self.content_type = "text/html"


class _FakeWebpageService:
    async def fetch_and_parse(self, url: str):
        if url == "https://example.com/article":
            return _FakeWebpageResult()
        return _FakeWebpageResult(error="HTTP 500")


class _FakeTavilyConfig:
    provider = "tavily"
    max_results = 10


class _FakeTavilySearchService:
    def __init__(self):
        self.config = _FakeTavilyConfig()

    async def search(self, query: str, *, page: int = 1):
        _ = query
        if page > 2:
            raise ValueError(
                "Search provider 'tavily' supports simulated pagination only up to page 2"
            )
        return [
            _make_search_source(
                type="search", title="Result T", url="https://t.test", snippet="Snippet T"
            ),
        ]


def test_web_search_returns_structured_results():
    fake_search = _FakeSearchService()
    service = WebToolService(
        search_service=fake_search,
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.web_search(query="latest llm news")))

    assert payload["ok"] is True
    assert payload["page"] == 1
    assert payload["offset"] == 0
    assert payload["provider"] == "duckduckgo"
    assert payload["pagination_mode"] == "native"
    assert payload["has_results"] is True
    assert payload["total_results"] == 2
    assert fake_search.last_page == 1
    assert payload["results"][0] == {
        "rank": 1,
        "title": "Result A",
        "url": "https://a.test",
        "domain": "a.test",
        "snippet": "Snippet A",
    }


def test_web_search_supports_pagination_metadata():
    fake_search = _FakeSearchService()
    service = WebToolService(
        search_service=fake_search,
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.web_search(query="latest llm news page 2", page=2)))

    assert payload["ok"] is True
    assert payload["page"] == 2
    assert payload["page_size"] == 10
    assert payload["offset"] == 10
    assert payload["pagination_mode"] == "native"
    assert payload["results"][0]["rank"] == 11
    assert fake_search.last_page == 2


def test_web_search_supports_simulated_pagination_for_tavily():
    service = WebToolService(
        search_service=_FakeTavilySearchService(),
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.web_search(query="latest llm news", page=2)))

    assert payload["ok"] is True
    assert payload["provider"] == "tavily"
    assert payload["page"] == 2
    assert payload["pagination_mode"] == "simulated"
    assert payload["results"][0]["rank"] == 11


def test_web_search_rejects_page_beyond_simulated_tavily_limit():
    service = WebToolService(
        search_service=_FakeTavilySearchService(),
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.web_search(query="latest llm news", page=3)))

    assert payload == {
        "ok": False,
        "error": {
            "code": "UNSUPPORTED_PAGE",
            "message": "Search provider 'tavily' supports simulated pagination only up to page 2",
        },
        "query": "latest llm news",
        "page": 3,
    }


def test_read_webpage_returns_research_friendly_payload():
    service = WebToolService(
        search_service=_FakeSearchService(),
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.read_webpage(url="https://example.com/article")))

    assert payload == {
        "ok": True,
        "url": "https://example.com/article",
        "final_url": "https://example.com/article",
        "domain": "example.com",
        "title": "Example Article",
        "content": "Main article content",
        "preview": "Main article content",
        "content_chars": 20,
        "truncated": False,
        "status_code": 200,
        "content_type": "text/html",
    }


def test_read_webpage_returns_structured_error():
    service = WebToolService(
        search_service=_FakeSearchService(),
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.read_webpage(url="https://example.com/fail")))

    assert payload["ok"] is False
    assert payload["error"]["code"] == "READ_WEBPAGE_FAILED"


def test_read_webpage_rejects_non_http_url():
    service = WebToolService(
        search_service=_FakeSearchService(),
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.read_webpage(url="file:///tmp/test.txt")))

    assert payload == {
        "ok": False,
        "error": {
            "code": "INVALID_URL",
            "message": "url must be an absolute http or https URL",
        },
        "url": "file:///tmp/test.txt",
    }


def test_get_tools_include_web_metadata():
    service = WebToolService(
        search_service=_FakeSearchService(),
        webpage_service=_FakeWebpageService(),
    )

    tools = service.get_tools()
    metadata_by_name = {tool.name: tool.metadata for tool in tools}

    assert metadata_by_name["web_search"] == {
        "group": "web",
        "source": "web",
        "enabled_by_default": False,
        "requires_project_knowledge": False,
    }
    assert metadata_by_name["read_webpage"] == {
        "group": "web",
        "source": "web",
        "enabled_by_default": False,
        "requires_project_knowledge": False,
    }
