"""Unit tests for webpage fetching behavior."""

from __future__ import annotations

import ssl
import pytest

from src.api.services.webpage_service import WebpageService


class _FakeResponse:
    def __init__(self, url: str, body: bytes):
        self.status_code = 200
        self.headers = {"content-type": "text/html; charset=utf-8"}
        self.url = url
        self.encoding = "utf-8"
        self._body = body

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    async def aiter_bytes(self):
        yield self._body


class _FakeClient:
    def __init__(self, *, kwargs, body: bytes, captured: dict[str, object]):
        self._kwargs = kwargs
        self._body = body
        self._captured = captured

    async def __aenter__(self):
        self._captured.update(self._kwargs)
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return None

    def stream(self, method: str, url: str, headers: dict[str, str]):
        self._captured["method"] = method
        self._captured["url"] = url
        self._captured["headers"] = headers
        return _FakeResponse(
            url=url,
            body=self._body,
        )


@pytest.mark.asyncio
async def test_fetch_and_parse_disables_http2_when_h2_missing(monkeypatch, tmp_path):
    config_path = tmp_path / "webpage_config.yaml"
    service = WebpageService(config_path=config_path)
    captured: dict[str, object] = {}
    html = b"<html><head><title>Example</title></head><body><main><p>Hello web tool.</p></main></body></html>"

    monkeypatch.setattr(service, "_http2_supported", lambda: False)
    monkeypatch.setattr("src.infrastructure.web.webpage_service.httpx.AsyncHTTPTransport", lambda retries=2: object())
    monkeypatch.setattr(
        "src.infrastructure.web.webpage_service.httpx.AsyncClient",
        lambda **kwargs: _FakeClient(kwargs=kwargs, body=html, captured=captured),
    )

    result = await service.fetch_and_parse("https://example.com/article")

    assert captured["http2"] is False
    assert isinstance(captured["verify"], ssl.SSLContext)
    assert captured["method"] == "GET"
    assert captured["url"] == "https://example.com/article"
    assert result.error is None
    assert result.title == "Example"
    assert "Hello web tool." in result.text
    assert result.content_type == "text/html; charset=utf-8"


def test_http2_supported_reflects_optional_h2_dependency(monkeypatch, tmp_path):
    service = WebpageService(config_path=tmp_path / "webpage_config.yaml")

    monkeypatch.setattr("src.infrastructure.web.webpage_service.importlib.util.find_spec", lambda name: None)
    assert service._http2_supported() is False

    monkeypatch.setattr("src.infrastructure.web.webpage_service.importlib.util.find_spec", lambda name: object())
    assert service._http2_supported() is True


def test_build_fetch_attempts_prefers_direct_for_wikimedia_with_proxy(tmp_path):
    service = WebpageService(config_path=tmp_path / "webpage_config.yaml")
    headers = {"User-Agent": "test-agent", "Accept": "text/html"}

    attempts = service._build_fetch_attempts(
        url="https://en.wikipedia.org/wiki/OpenAI",
        headers=headers,
        proxy="http://127.0.0.1:7897",
    )

    assert [attempt.name for attempt in attempts] == ["wikimedia_direct", "default"]
    assert attempts[0].proxy is None
    assert attempts[0].trust_env is False
    assert attempts[1].proxy == "http://127.0.0.1:7897"


def test_extract_json_text_supports_wikimedia_summary_payload(tmp_path):
    service = WebpageService(config_path=tmp_path / "webpage_config.yaml")

    title, text, description = service._extract_text(
        '{"title":"OpenAI","description":"AI research","extract":"OpenAI is an AI company."}',
        "application/json",
    )

    assert title == "OpenAI"
    assert text == "OpenAI is an AI company."
    assert description == "AI research"


def test_browser_navigation_headers_include_browser_like_fields(tmp_path):
    service = WebpageService(config_path=tmp_path / "webpage_config.yaml")

    headers = service._browser_navigation_headers(url="https://en.wikipedia.org/wiki/OpenAI")

    assert headers["Upgrade-Insecure-Requests"] == "1"
    assert headers["Sec-Fetch-Dest"] == "document"
    assert headers["Sec-Fetch-Mode"] == "navigate"
    assert headers["Referer"] == "https://www.wikipedia.org/"


def test_should_try_curl_impersonation_for_wikimedia_even_without_error(tmp_path):
    service = WebpageService(config_path=tmp_path / "webpage_config.yaml")

    result = service._should_try_curl_impersonation(
        url="https://en.wikipedia.org/wiki/OpenAI",
        last_error=None,
    )

    assert result is True
