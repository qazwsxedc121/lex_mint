"""Webpage fetch and parsing service."""

from __future__ import annotations

from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import List, Optional, Tuple
from urllib.parse import urlparse
import asyncio
import html
import ipaddress
import logging
import os
import re
import socket
import ssl
import time

import httpx
import yaml

from ..models.search import SearchSource

logger = logging.getLogger(__name__)

try:
    import trafilatura
    from trafilatura.metadata import extract_metadata
except Exception:
    trafilatura = None
    extract_metadata = None

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
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "webpage_config.yaml"
        self.config_path = config_path
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
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

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
            sources.append(SearchSource(type="webpage", title=label, url=result.final_url, snippet=snippet or None))
        if not sources:
            for result in results:
                label = self._label_for_result(result)
                snippet = result.error or None
                sources.append(SearchSource(type="webpage", title=label, url=result.final_url, snippet=snippet))

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
        headers = {
            "User-Agent": self.config.user_agent,
            "Accept": "text/html, text/plain;q=0.9,*/*;q=0.1",
        }
        start_time = time.monotonic()

        proxy = self._resolve_proxy()

        try:
            logger.info(f"[Webpage] Fetching {url}")
            transport = httpx.AsyncHTTPTransport(retries=2)
            async with httpx.AsyncClient(
                timeout=timeout,
                follow_redirects=True,
                transport=transport,
                http2=True,
                proxy=proxy,
                trust_env=self.config.trust_env,
            ) as client:
                async with client.stream("GET", url, headers=headers) as response:
                    status_code = response.status_code
                    content_type = (response.headers.get("content-type") or "").lower()
                    if status_code >= 400:
                        error_detail = f"HTTP {status_code}"
                        logger.warning(f"[Webpage] {url} failed: {error_detail}")
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
                    if "text/html" not in content_type and not content_type.startswith("text/"):
                        error_detail = f"Unsupported content type: {content_type or 'unknown'}"
                        logger.warning(f"[Webpage] {url} failed: {error_detail}")
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
            html_text = body[: self.config.max_bytes].decode(encoding, errors="ignore")
            logger.info(
                "[Webpage] Fetched %s status=%s content_type=%s bytes=%s truncated=%s",
                url,
                status_code,
                content_type or "unknown",
                len(body),
                truncated_bytes,
            )
        except httpx.TimeoutException as e:
            elapsed = time.monotonic() - start_time
            host = urlparse(url).hostname or ""
            diag = await self._network_diagnostics(url)
            error_detail = (
                f"Timeout ({e.__class__.__name__}) after {elapsed:.2f}s host={host}"
                f"{self._format_timeout_detail(timeout)}"
                f"{diag}"
            )
            logger.warning(f"[Webpage] {url} failed: {error_detail}")
            return WebpageResult(
                url=url,
                final_url=str(e.request.url) if e.request else url,
                title="",
                text="",
                truncated=False,
                error=error_detail,
                status_code=None,
                content_type=None,
            )
        except httpx.HTTPStatusError as e:
            status = e.response.status_code if e.response else None
            error_detail = f"HTTP {status}" if status else "HTTP status error"
            logger.warning(f"[Webpage] {url} failed: {error_detail}")
            return WebpageResult(
                url=url,
                final_url=str(e.response.url) if e.response else url,
                title="",
                text="",
                truncated=False,
                error=error_detail,
                status_code=status,
                content_type=(e.response.headers.get('content-type') if e.response else None),
            )
        except httpx.RequestError as e:
            elapsed = time.monotonic() - start_time
            host = urlparse(url).hostname or ""
            message = str(e).strip() or repr(e)
            diag = await self._network_diagnostics(url)
            error_detail = f"Request error ({e.__class__.__name__}) after {elapsed:.2f}s host={host}: {message}{diag}"
            logger.warning(f"[Webpage] {url} failed: {error_detail}")
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
        except Exception as e:
            elapsed = time.monotonic() - start_time
            error_detail = f"Fetch failed after {elapsed:.2f}s: {e}"
            logger.warning(f"[Webpage] {url} failed: {error_detail}")
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

        title, text, description = self._extract_text(html_text, content_type)
        text = self._normalize_text(text)
        if (not text or len(text) < 200) and description:
            text = description.strip()

        if not text:
            return WebpageResult(
                url=url,
                final_url=str(response.url),
                title=title,
                text="",
                truncated=False,
                error="Empty content after parsing",
                status_code=status_code,
                content_type=content_type or None,
            )

        truncated = False
        if len(text) > self.config.max_content_chars:
            text = text[: self.config.max_content_chars].rstrip() + "..."
            truncated = True

        if truncated_bytes:
            truncated = True

        return WebpageResult(
            url=url,
            final_url=str(response.url),
            title=title,
            text=text,
            truncated=truncated,
            error=None,
            status_code=status_code,
            content_type=content_type or None,
        )

    def _extract_text(self, html_text: str, content_type: str) -> Tuple[str, str, str]:
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
    def _normalize_text(text: str) -> str:
        text = re.sub(r"[ \t]+", " ", text or "")
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

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
