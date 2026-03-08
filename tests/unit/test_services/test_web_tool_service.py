"""Unit tests for request-scoped web tools."""

from __future__ import annotations

import asyncio
import json

from src.api.models.search import SearchSource
from src.api.services.web_tool_service import WebToolService


class _FakeSearchConfig:
    provider = "duckduckgo"


class _FakeSearchService:
    def __init__(self):
        self.config = _FakeSearchConfig()

    async def search(self, query: str):
        assert query == "latest llm news"
        return [
            SearchSource(type="search", title="Result A", url="https://a.test", snippet="Snippet A"),
            SearchSource(type="search", title="Result B", url="https://b.test", snippet="Snippet B"),
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


def test_web_search_returns_structured_results():
    service = WebToolService(
        search_service=_FakeSearchService(),
        webpage_service=_FakeWebpageService(),
    )

    payload = json.loads(asyncio.run(service.web_search(query="latest llm news")))

    assert payload["ok"] is True
    assert payload["provider"] == "duckduckgo"
    assert payload["has_results"] is True
    assert payload["total_results"] == 2
    assert payload["results"][0] == {
        "rank": 1,
        "title": "Result A",
        "url": "https://a.test",
        "domain": "a.test",
        "snippet": "Snippet A",
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
