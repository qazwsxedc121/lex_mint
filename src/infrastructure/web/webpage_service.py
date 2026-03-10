"""Webpage fetch and parsing service."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
import importlib.util
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import asyncio
import html
import ipaddress
import json
import logging
import os
import re
import socket
import ssl
import time

import httpx
import yaml

from src.api.models.search import SearchSource
from src.api.paths import (
    config_defaults_dir,
    config_local_dir,
    legacy_config_dir,
    ensure_local_file,
)

logger = logging.getLogger(__name__)

try:
    import trafilatura
    from trafilatura.metadata import extract_metadata
except Exception:
    trafilatura = None
    extract_metadata = None

try:
    from curl_cffi import requests as curl_requests
except Exception:
    curl_requests = None

URL_PATTERN = re.compile(r"https?://[^\s<>()\"']+", re.IGNORECASE)
TRAILING_PUNCTUATION = ".,);:]}>\"'"

BLOCK_TAGS = {
    "p", "div", "br", "hr", "section", "article", "header", "footer",
    "h1", "h2", "h3", "h4", "h5", "h6", "li", "ul", "ol", "table",
    "tr", "td", "th", "blockquote", "pre"
}
SKIP_TAGS = {"script", "style", "noscript"}


@dataclass
class WebpageConfig:
    enabled: bool = True
    max_urls: int = 2
    timeout_seconds: int = 10
    max_bytes: int = 3_000_000
    max_content_chars: int = 20_000
    user_agent: str = "lex_mint/1.0"
    proxy: Optional[str] = None
    trust_env: bool = True
    diagnostics_enabled: bool = True
    diagnostics_timeout_seconds: float = 2.0


@dataclass
class WebpageResult:
    url: str
    final_url: str
    title: str
    text: str
    truncated: bool
    error: Optional[str] = None
    status_code: Optional[int] = None
    content_type: Optional[str] = None


@dataclass(frozen=True)
class _FetchAttempt:
    name: str
    proxy: Optional[str]
    trust_env: bool
    headers: dict[str, str]


@dataclass
class _FetchedPage:
    final_url: str
    status_code: int
    content_type: str
    encoding: str
    body: bytes
    truncated_bytes: bool


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._lines: List[str] = []
        self._current: List[str] = []
        self._skip_depth = 0
        self._in_title = False
        self._title_parts: List[str] = []
        self._meta_title: Optional[str] = None
        self._meta_description: Optional[str] = None

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS:
            self._skip_depth += 1
            return
        if tag == "title":
            self._in_title = True
        if tag == "meta":
            attr_map = {k.lower(): (v or "") for k, v in attrs}
            prop = attr_map.get("property") or attr_map.get("name") or ""
            if prop.lower() in {"og:title", "twitter:title"}:
                content = attr_map.get("content")
                if content and not self._meta_title:
                    self._meta_title = content.strip()
            if prop.lower() in {"description", "og:description", "twitter:description"}:
                content = attr_map.get("content")
                if content and not self._meta_description:
                    self._meta_description = content.strip()
        if tag in BLOCK_TAGS:
            self._flush_line()

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in SKIP_TAGS and self._skip_depth:
            self._skip_depth -= 1
            return
        if tag == "title":
            self._in_title = False
        if tag in BLOCK_TAGS:
            self._flush_line()

    def handle_data(self, data: str) -> None:
        if self._skip_depth:
            return
        text = html.unescape(data or "").strip()
        if not text:
            return
        if self._in_title:
            self._title_parts.append(text)
        self._current.append(text)

    def _flush_line(self) -> None:
        if not self._current:
            return
        line = " ".join(self._current).strip()
        if line:
            self._lines.append(line)
        self._current = []

    def get_text(self) -> str:
        self._flush_line()
        return "\n\n".join(self._lines).strip()

    def get_title(self) -> str:
        if self._meta_title:
            return self._meta_title.strip()
        return " ".join(self._title_parts).strip()

    def get_description(self) -> str:
        return (self._meta_description or "").strip()


class WebpageService:
    """Service for fetching and parsing webpage content."""

    def __init__(self, config_path: Optional[Path] = None) -> None:
        self.defaults_path: Optional[Path] = None
        self.legacy_paths: list[Path] = []

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "webpage_config.yaml"
            self.config_path = config_local_dir() / "webpage_config.yaml"
            self.legacy_paths = [legacy_config_dir() / "webpage_config.yaml"]
        else:
            self.config_path = Path(config_path)
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        if not self.config_path.exists():
            default_config = {
                "webpage": {
                    "enabled": True,
                    "max_urls": 2,
                    "timeout_seconds": 10,
                    "max_bytes": 3_000_000,
                    "max_content_chars": 20_000,
                    "user_agent": "lex_mint/1.0",
                    "proxy": None,
                    "trust_env": True,
                    "diagnostics_enabled": True,
                    "diagnostics_timeout_seconds": 2,
                }
            }
            initial_text = yaml.safe_dump(default_config, allow_unicode=True, sort_keys=False)
            ensure_local_file(
                local_path=self.config_path,
                defaults_path=self.defaults_path,
                legacy_paths=self.legacy_paths,
                initial_text=initial_text,
            )

    def _load_config(self) -> WebpageConfig:
        self._ensure_config_exists()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            page_data = data.get("webpage", {})
            return WebpageConfig(
                enabled=bool(page_data.get("enabled", True)),
                max_urls=int(page_data.get("max_urls", 2)),
                timeout_seconds=int(page_data.get("timeout_seconds", 10)),
                max_bytes=int(page_data.get("max_bytes", 3_000_000)),
                max_content_chars=int(page_data.get("max_content_chars", 20_000)),
                user_agent=str(page_data.get("user_agent", "lex_mint/1.0")),
                proxy=self._normalize_proxy(page_data.get("proxy")),
                trust_env=bool(page_data.get("trust_env", True)),
                diagnostics_enabled=bool(page_data.get("diagnostics_enabled", True)),
                diagnostics_timeout_seconds=float(page_data.get("diagnostics_timeout_seconds", 2.0)),
            )
        except Exception as e:
            logger.warning(f"Failed to load webpage config: {e}")
            return WebpageConfig()

    def save_config(self, updates: dict) -> None:
        self._ensure_config_exists()
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

        if "webpage" not in data:
            data["webpage"] = {}

        if "proxy" in updates:
            updates["proxy"] = self._normalize_proxy(updates.get("proxy"))

        for key, value in updates.items():
            data["webpage"][key] = value

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        self.config = self._load_config()

    def extract_urls(self, text: str) -> List[str]:
        if not text:
            return []
        matches = URL_PATTERN.findall(text)
        seen = set()
        urls: List[str] = []
        for match in matches:
            url = match.strip().strip(TRAILING_PUNCTUATION)
            url = url.rstrip(TRAILING_PUNCTUATION)
            if not self._is_valid_url(url):
                continue
            if url in seen:
                continue
            seen.add(url)
            urls.append(url)
            if len(urls) >= max(self.config.max_urls, 1):
                break
        return urls

    async def build_context(self, text: str) -> Tuple[Optional[str], List[SearchSource]]:
        if not self.config.enabled:
            return None, []
        urls = self.extract_urls(text)
        if not urls:
            return None, []

        results = await self._fetch_urls(urls)
        if not results:
            return None, []

        context_lines = ["Webpage content (use for grounding; cite sources by URL):"]
        sources: List[SearchSource] = []

        for index, result in enumerate(results, start=1):
            label = self._label_for_result(result)
            context_lines.append(f"[{index}] {label}")
            context_lines.append(f"URL: {result.final_url}")
            if result.error:
                context_lines.append(f"Error: {result.error}")
                continue
            if result.title:
                context_lines.append(f"Title: {result.title}")
            context_lines.append("Content:")
            context_lines.append(result.text)
            if result.truncated:
                context_lines.append(f"[Content truncated to {self.config.max_content_chars} chars]")

            snippet = result.text.replace("\n", " ").strip()
            if len(snippet) > 200:
                snippet = snippet[:200] + "..."
            sources.append(
                SearchSource.model_validate(
                    {
                        "type": "webpage",
                        "title": label,
                        "url": result.final_url,
                        "snippet": snippet or None,
                    }
                )
            )
        if not sources:
            for result in results:
                label = self._label_for_result(result)
                snippet = result.error or None
                sources.append(
                    SearchSource.model_validate(
                        {
                            "type": "webpage",
                            "title": label,
                            "url": result.final_url,
                            "snippet": snippet,
                        }
                    )
                )

        return "\n".join(context_lines).strip(), sources

    async def _fetch_urls(self, urls: List[str]) -> List[WebpageResult]:
        tasks = [self.fetch_and_parse(url) for url in urls]
        results = await asyncio.gather(*tasks, return_exceptions=False)
        return [r for r in results if r]

    async def fetch_and_parse(self, url: str) -> WebpageResult:
        if not self._is_valid_url(url):
            return WebpageResult(
                url=url,
                final_url=url,
                title="",
                text="",
                truncated=False,
                error="URL not allowed",
                status_code=None,
                content_type=None,
            )

        timeout = httpx.Timeout(self.config.timeout_seconds)
        headers = self._browser_navigation_headers(url=url)
        proxy = self._resolve_proxy()
        http2_enabled = self._http2_supported()
        verify = self._ssl_verify_context()

        fetched: Optional[_FetchedPage] = None
        last_error: Optional[WebpageResult] = None
        attempts = self._build_fetch_attempts(url=url, headers=headers, proxy=proxy)
        for attempt in attempts:
            candidate = await self._fetch_once(
                url=url,
                timeout=timeout,
                http2_enabled=http2_enabled,
                verify=verify,
                attempt=attempt,
            )
            if isinstance(candidate, WebpageResult):
                last_error = candidate
                if not self._should_retry_after_error(url=url, result=candidate):
                    return candidate
                continue
            fetched = candidate
            break

        if fetched is None and self._should_try_curl_impersonation(url=url, last_error=last_error):
            curl_candidate = await self._fetch_with_curl_impersonation(
                url=url,
                proxy=proxy,
                timeout_seconds=float(self.config.timeout_seconds),
            )
            if isinstance(curl_candidate, _FetchedPage):
                fetched = curl_candidate
            elif curl_candidate is not None:
                last_error = curl_candidate

        if fetched is None:
            return last_error or WebpageResult(
                url=url,
                final_url=url,
                title="",
                text="",
                truncated=False,
                error="Fetch failed",
                status_code=None,
                content_type=None,
            )

        raw_text = fetched.body[: self.config.max_bytes].decode(fetched.encoding, errors="ignore")
        title, text, description = self._extract_text(raw_text, fetched.content_type)
        text = self._normalize_text(text)
        if (not text or len(text) < 200) and description:
            text = description.strip()

        if not text:
            return WebpageResult(
                url=url,
                final_url=fetched.final_url,
                title=title,
                text="",
                truncated=False,
                error="Empty content after parsing",
                status_code=fetched.status_code,
                content_type=fetched.content_type or None,
            )

        truncated = False
        if len(text) > self.config.max_content_chars:
            text = text[: self.config.max_content_chars].rstrip() + "..."
            truncated = True

        if fetched.truncated_bytes:
            truncated = True

        return WebpageResult(
            url=url,
            final_url=fetched.final_url,
            title=title,
            text=text,
            truncated=truncated,
            error=None,
            status_code=fetched.status_code,
            content_type=fetched.content_type or None,
        )

    async def _fetch_once(
        self,
        *,
        url: str,
        timeout: httpx.Timeout,
        http2_enabled: bool,
        verify: ssl.SSLContext,
        attempt: _FetchAttempt,
    ) -> _FetchedPage | WebpageResult:
        start_time = time.monotonic()

        try:
            logger.info("[Webpage] Fetching %s via %s", url, attempt.name)
            transport = httpx.AsyncHTTPTransport(retries=2)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                transport=transport,
                http2=http2_enabled,
                verify=verify,
                proxy=attempt.proxy,
                trust_env=attempt.trust_env,
            ) as client:
                async with client.stream("GET", url, headers=attempt.headers) as response:
                    status_code = response.status_code
                    content_type = (response.headers.get("content-type") or "").lower()
                    if status_code >= 400:
                        error_detail = f"HTTP {status_code} [{attempt.name}]"
                        logger.warning("[Webpage] %s failed: %s", url, error_detail)
                        return WebpageResult(
                            url=url,
                            final_url=str(response.url),
                            title="",
                            text="",
                            truncated=False,
                            error=error_detail,
                            status_code=status_code,
                            content_type=content_type or None,
                        )
                    if not self._is_supported_content_type(url=url, content_type=content_type):
                        error_detail = f"Unsupported content type: {content_type or 'unknown'} [{attempt.name}]"
                        logger.warning("[Webpage] %s failed: %s", url, error_detail)
                        return WebpageResult(
                            url=url,
                            final_url=str(response.url),
                            title="",
                            text="",
                            truncated=False,
                            error=error_detail,
                            status_code=status_code,
                            content_type=content_type or None,
                        )

                    body = bytearray()
                    truncated_bytes = False
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) >= self.config.max_bytes:
                            truncated_bytes = True
                            break

                    encoding = response.encoding or "utf-8"
                    logger.info(
                        "[Webpage] Fetched %s via=%s status=%s content_type=%s bytes=%s truncated=%s",
                        url,
                        attempt.name,
                        status_code,
                        content_type or "unknown",
                        len(body),
                        truncated_bytes,
                    )
                    return _FetchedPage(
                        final_url=str(response.url),
                        status_code=status_code,
                        content_type=content_type,
                        encoding=encoding,
                        body=bytes(body),
                        truncated_bytes=truncated_bytes,
                    )
        except httpx.TimeoutException as exc:
            elapsed = time.monotonic() - start_time
            host = urlparse(url).hostname or ""
            diag = await self._network_diagnostics(url)
            error_detail = (
                f"Timeout ({exc.__class__.__name__}) after {elapsed:.2f}s host={host}"
                f"{self._format_timeout_detail(timeout)}"
                f" [{attempt.name}]"
                f"{diag}"
            )
            logger.warning("[Webpage] %s failed: %s", url, error_detail)
            return WebpageResult(
                url=url,
                final_url=str(exc.request.url) if exc.request else url,
                title="",
                text="",
                truncated=False,
                error=error_detail,
                status_code=None,
                content_type=None,
            )
        except httpx.RequestError as exc:
            elapsed = time.monotonic() - start_time
            host = urlparse(url).hostname or ""
            message = str(exc).strip() or repr(exc)
            diag = await self._network_diagnostics(url)
            error_detail = (
                f"Request error ({exc.__class__.__name__}) after {elapsed:.2f}s host={host}: {message}"
                f" [{attempt.name}]"
                f"{diag}"
            )
            logger.warning("[Webpage] %s failed: %s", url, error_detail)
            return WebpageResult(
                url=url,
                final_url=str(exc.request.url) if exc.request else url,
                title="",
                text="",
                truncated=False,
                error=error_detail,
                status_code=None,
                content_type=None,
            )
        except Exception as exc:
            elapsed = time.monotonic() - start_time
            error_detail = f"Fetch failed after {elapsed:.2f}s [{attempt.name}]: {exc}"
            logger.warning("[Webpage] %s failed: %s", url, error_detail)
            return WebpageResult(
                url=url,
                final_url=url,
                title="",
                text="",
                truncated=False,
                error=error_detail,
                status_code=None,
                content_type=None,
            )

    def _build_fetch_attempts(
        self,
        *,
        url: str,
        headers: dict[str, str],
        proxy: Optional[str],
    ) -> List[_FetchAttempt]:
        attempts: List[_FetchAttempt] = []

        if self._is_wikimedia_url(url):
            direct_headers = dict(headers)
            direct_headers.setdefault("Accept-Language", "en-US,en;q=0.9")
            direct_headers.setdefault("Referer", "https://www.wikipedia.org/")
            attempts.append(
                _FetchAttempt(
                    name="wikimedia_direct",
                    proxy=None,
                    trust_env=False,
                    headers=direct_headers,
                )
            )

        attempts.append(
            _FetchAttempt(
                name="default",
                proxy=proxy,
                trust_env=self.config.trust_env,
                headers=dict(headers),
            )
        )

        deduped: List[_FetchAttempt] = []
        seen: set[tuple[Optional[str], bool]] = set()
        for attempt in attempts:
            key = (attempt.proxy, attempt.trust_env)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(attempt)
        return deduped

    @staticmethod
    def _should_try_curl_impersonation(
        *,
        url: str,
        last_error: Optional[WebpageResult],
    ) -> bool:
        if WebpageService._is_wikimedia_url(url):
            return True
        if curl_requests is None:
            return False
        if last_error is None:
            return False
        if last_error.status_code in {403, 429}:
            return True
        return False

    async def _fetch_with_curl_impersonation(
        self,
        *,
        url: str,
        proxy: Optional[str],
        timeout_seconds: float,
    ) -> _FetchedPage | WebpageResult | None:
        if curl_requests is None:
            return None

        headers = self._browser_navigation_headers(url=url)
        proxies = {"http": proxy, "https": proxy} if proxy else None

        def _do_request() -> _FetchedPage | WebpageResult:
            start_time = time.monotonic()
            try:
                response = curl_requests.get(
                    url,
                    impersonate="chrome",
                    proxies=proxies,
                    timeout=timeout_seconds,
                    verify=True,
                    headers=headers,
                )
                status_code = int(response.status_code)
                content_type = str(response.headers.get("content-type") or "").lower()
                if status_code >= 400:
                    return WebpageResult(
                        url=url,
                        final_url=str(response.url),
                        title="",
                        text="",
                        truncated=False,
                        error=f"HTTP {status_code} [curl_impersonate]",
                        status_code=status_code,
                        content_type=content_type or None,
                    )
                if not self._is_supported_content_type(url=url, content_type=content_type):
                    return WebpageResult(
                        url=url,
                        final_url=str(response.url),
                        title="",
                        text="",
                        truncated=False,
                        error=f"Unsupported content type: {content_type or 'unknown'} [curl_impersonate]",
                        status_code=status_code,
                        content_type=content_type or None,
                    )

                body = response.content or b""
                truncated_bytes = len(body) >= self.config.max_bytes
                if truncated_bytes:
                    body = body[: self.config.max_bytes]
                encoding = response.charset or response.encoding or "utf-8"
                logger.info(
                    "[Webpage] Fetched %s via=curl_impersonate status=%s content_type=%s bytes=%s truncated=%s",
                    url,
                    status_code,
                    content_type or "unknown",
                    len(body),
                    truncated_bytes,
                )
                return _FetchedPage(
                    final_url=str(response.url),
                    status_code=status_code,
                    content_type=content_type,
                    encoding=encoding,
                    body=body,
                    truncated_bytes=truncated_bytes,
                )
            except Exception as exc:
                elapsed = time.monotonic() - start_time
                error_detail = f"Fetch failed after {elapsed:.2f}s [curl_impersonate]: {exc}"
                logger.warning("[Webpage] %s failed: %s", url, error_detail)
                return WebpageResult(
                    url=url,
                    final_url=url,
                    title="",
                    text="",
                    truncated=False,
                    error=error_detail,
                    status_code=None,
                    content_type=None,
                )

        return await asyncio.to_thread(_do_request)

    @staticmethod
    def _should_retry_after_error(*, url: str, result: WebpageResult) -> bool:
        if result.error is None:
            return False
        if WebpageService._is_wikimedia_url(url):
            return True
        if result.status_code in {403, 408, 425, 429, 500, 502, 503, 504}:
            return True
        if result.status_code is None:
            return True
        return False

    def _extract_text(self, html_text: str, content_type: str) -> Tuple[str, str, str]:
        if self._is_json_content_type(content_type):
            return self._extract_json_text(html_text)
        if "text/html" in content_type:
            if trafilatura:
                try:
                    extracted = trafilatura.extract(
                        html_text,
                        output_format="txt",
                        include_comments=False,
                        include_tables=False,
                        include_images=False
                    )
                    if extracted:
                        logger.info("[Webpage] Extractor=trafilatura text_len=%s", len(extracted))
                        title = ""
                        description = ""
                        if extract_metadata:
                            meta = extract_metadata(html_text)
                            if meta:
                                title = meta.title or ""
                                description = meta.description or ""
                        return title, extracted, description
                except Exception:
                    pass
            parser = _HTMLTextExtractor()
            parser.feed(html_text)
            parser.close()
            text = parser.get_text()
            logger.info("[Webpage] Extractor=html_parser text_len=%s", len(text))
            return parser.get_title(), text, parser.get_description()
        return "", html_text, ""

    @staticmethod
    def _is_json_content_type(content_type: str) -> bool:
        return "application/json" in (content_type or "").lower()

    @classmethod
    def _is_supported_content_type(cls, *, url: str, content_type: str) -> bool:
        lowered = (content_type or "").lower()
        if "text/html" in lowered or lowered.startswith("text/"):
            return True
        if cls._is_wikimedia_url(url) and cls._is_json_content_type(lowered):
            return True
        return False

    @staticmethod
    def _extract_json_text(raw_text: str) -> Tuple[str, str, str]:
        try:
            payload = json.loads(raw_text)
        except Exception:
            return "", raw_text, ""

        if isinstance(payload, dict):
            title = str(payload.get("title") or "").strip()
            description = str(payload.get("description") or "").strip()
            extract = str(payload.get("extract") or "").strip()
            if extract:
                return title, extract, description

            query = payload.get("query")
            if isinstance(query, dict):
                pages = query.get("pages")
                if isinstance(pages, dict):
                    for page in pages.values():
                        if not isinstance(page, dict):
                            continue
                        page_title = str(page.get("title") or title).strip()
                        page_extract = str(page.get("extract") or "").strip()
                        if page_extract:
                            return page_title, page_extract, description

        return "", raw_text, ""

    @staticmethod
    def _normalize_text(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text or "")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    def _browser_navigation_headers(self, *, url: str) -> dict[str, str]:
        host = urlparse(url).hostname or ""
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": (
                "text/html,application/xhtml+xml,application/xml;q=0.9,"
                "image/avif,image/webp,image/apng,*/*;q=0.8"
            ),
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "sec-ch-ua": '"Not:A-Brand";v="99", "Google Chrome";v="145", "Chromium";v="145"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
        }
        if host.endswith("wikipedia.org") or host.endswith("wikimedia.org"):
            headers["Referer"] = "https://www.wikipedia.org/"
        return headers

    @staticmethod
    def _http2_supported() -> bool:
        """Enable HTTP/2 only when the optional h2 dependency is available."""
        return importlib.util.find_spec("h2") is not None

    @staticmethod
    def _ssl_verify_context() -> ssl.SSLContext:
        """Use the platform trust store so local/proxied cert chains can validate on Windows."""
        return ssl.create_default_context()

    @staticmethod
    def _label_for_result(result: WebpageResult) -> str:
        label = result.title.strip()
        if not label:
            label = urlparse(result.final_url).netloc or "Webpage"
        if len(label) > 60:
            label = label[:57].rstrip() + "..."
        return label

    @staticmethod
    def _format_timeout_detail(timeout: httpx.Timeout) -> str:
        parts = []
        for name in ("connect", "read", "write", "pool"):
            value = getattr(timeout, name, None)
            if value is None:
                continue
            parts.append(f"{name}={value}")
        if not parts:
            return ""
        return " (" + ", ".join(parts) + ")"

    @staticmethod
    def _normalize_proxy(value: object) -> Optional[str]:
        if not value:
            return None
        if isinstance(value, str):
            proxy = value.strip()
            return proxy or None
        return None

    def _resolve_proxy(self) -> Optional[str]:
        return self.config.proxy or None

    @staticmethod
    def _is_wikimedia_url(url: str) -> bool:
        host = (urlparse(url).hostname or "").lower()
        return host.endswith("wikipedia.org") or host.endswith("wikimedia.org")

    @staticmethod
    def _redact_proxy(proxy_url: str) -> str:
        parsed = urlparse(proxy_url)
        if not parsed.scheme or not parsed.netloc:
            return proxy_url
        if parsed.password:
            user = parsed.username or ""
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{user}:***@{host}{port}" if user else f"***@{host}{port}"
            return parsed._replace(netloc=netloc).geturl()
        return proxy_url

    async def _network_diagnostics(self, url: str) -> str:
        if not self.config.diagnostics_enabled:
            return ""
        parsed = urlparse(url)
        host = parsed.hostname or ""
        if not host:
            return ""
        scheme = parsed.scheme or "https"
        port = 443 if scheme == "https" else 80
        timeout = self._diagnostics_timeout()

        parts: List[str] = []
        proxy_env = self._proxy_env_summary()
        proxy_cfg = self._resolve_proxy()
        if proxy_cfg:
            parts.append(f"proxy_cfg={self._redact_proxy(proxy_cfg)}")
            parts.extend(await self._proxy_diagnostics(proxy_cfg, timeout))
        if proxy_env:
            parts.append(f"proxy_env={proxy_env}")
        else:
            parts.append("proxy_env=none")

        ips: List[str] = []
        try:
            loop = asyncio.get_running_loop()
            infos = await asyncio.wait_for(
                loop.getaddrinfo(host, port, type=socket.SOCK_STREAM),
                timeout=timeout,
            )
            for info in infos:
                addr = info[4][0]
                if addr not in ips:
                    ips.append(addr)
            if ips:
                ips_preview = ",".join(ips[:3])
                parts.append(f"dns={len(ips)} {ips_preview}")
            else:
                parts.append("dns=empty")
        except Exception as exc:
            parts.append(f"dns_error={exc.__class__.__name__}")
            return " diag[" + " ".join(parts) + "]"

        tcp_ok_ip = ""
        tcp_error = ""
        for ip in ips[:3]:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                tcp_ok_ip = ip
                break
            except Exception as exc:
                tcp_error = f"{ip}:{exc.__class__.__name__}"
        if tcp_ok_ip:
            parts.append(f"tcp_ok={tcp_ok_ip}:{port}")
        elif tcp_error:
            parts.append(f"tcp_fail={tcp_error}")
        else:
            parts.append("tcp_fail=unknown")

        if scheme == "https" and tcp_ok_ip:
            try:
                ctx = ssl.create_default_context()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        tcp_ok_ip,
                        port,
                        ssl=ctx,
                        server_hostname=host,
                    ),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                parts.append("tls_ok")
            except Exception as exc:
                parts.append(f"tls_fail={exc.__class__.__name__}")

        return " diag[" + " ".join(parts) + "]"

    def _diagnostics_timeout(self) -> float:
        try:
            value = float(self.config.diagnostics_timeout_seconds)
        except (TypeError, ValueError):
            value = 2.0
        return max(0.5, min(value, 5.0))

    async def _proxy_diagnostics(self, proxy_url: str, timeout: float) -> List[str]:
        parts: List[str] = []
        parsed = urlparse(proxy_url)
        host = parsed.hostname or ""
        if not host:
            parts.append("proxy_parse=missing_host")
            return parts
        scheme = parsed.scheme or "http"
        port = parsed.port or (443 if scheme == "https" else 80)

        ips: List[str] = []
        try:
            loop = asyncio.get_running_loop()
            infos = await asyncio.wait_for(
                loop.getaddrinfo(host, port, type=socket.SOCK_STREAM),
                timeout=timeout,
            )
            for info in infos:
                addr = info[4][0]
                if addr not in ips:
                    ips.append(addr)
            if ips:
                ips_preview = ",".join(ips[:3])
                parts.append(f"proxy_dns={len(ips)} {ips_preview}")
            else:
                parts.append("proxy_dns=empty")
        except Exception as exc:
            parts.append(f"proxy_dns_error={exc.__class__.__name__}")
            return parts

        tcp_ok_ip = ""
        tcp_error = ""
        for ip in ips[:3]:
            try:
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(ip, port),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                tcp_ok_ip = ip
                break
            except Exception as exc:
                tcp_error = f"{ip}:{exc.__class__.__name__}"
        if tcp_ok_ip:
            parts.append(f"proxy_tcp_ok={tcp_ok_ip}:{port}")
        elif tcp_error:
            parts.append(f"proxy_tcp_fail={tcp_error}")
        else:
            parts.append("proxy_tcp_fail=unknown")

        if scheme == "https" and tcp_ok_ip:
            try:
                ctx = ssl.create_default_context()
                reader, writer = await asyncio.wait_for(
                    asyncio.open_connection(
                        tcp_ok_ip,
                        port,
                        ssl=ctx,
                        server_hostname=host,
                    ),
                    timeout=timeout,
                )
                writer.close()
                await writer.wait_closed()
                parts.append("proxy_tls_ok")
            except Exception as exc:
                parts.append(f"proxy_tls_fail={exc.__class__.__name__}")

        return parts

    @staticmethod
    def _proxy_env_summary() -> str:
        keys = ("HTTP_PROXY", "HTTPS_PROXY", "NO_PROXY", "http_proxy", "https_proxy", "no_proxy")
        present = [key for key in keys if os.environ.get(key)]
        return ",".join(present)

    @staticmethod
    def _is_valid_url(url: str) -> bool:
        try:
            parsed = urlparse(url)
        except Exception:
            return False
        if parsed.scheme not in {"http", "https"}:
            return False
        if not parsed.netloc:
            return False
        host = parsed.hostname or ""
        if not host:
            return False
        if host.lower() in {"localhost"} or host.lower().endswith(".local"):
            return False
        try:
            ip = ipaddress.ip_address(host)
            if ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_reserved or ip.is_multicast:
                return False
        except ValueError:
            pass
        return True
