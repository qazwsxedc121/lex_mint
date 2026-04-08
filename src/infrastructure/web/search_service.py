"""Web search service using Tavily or DuckDuckGo."""

import asyncio
import logging
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import httpx
import yaml

from src.core.paths import (
    config_defaults_dir,
    config_local_dir,
    ensure_local_file,
)
from src.domain.models.search import SearchSource
from src.infrastructure.config.model_config_service import ModelConfigService
from src.infrastructure.web.web_tools_settings import load_effective_web_tools_settings

logger = logging.getLogger(__name__)

DDGS_CLIENT = None
try:
    from ddgs import DDGS as DDGSClient  # type: ignore

    DDGS_CLIENT = DDGSClient
except Exception:  # pragma: no cover - optional dependency
    DDGS_CLIENT = None


@dataclass
class SearchConfig:
    provider: str = "duckduckgo"
    max_results: int = 10
    timeout_seconds: int = 10


class SearchService:
    """Service for web search and result normalization."""

    _MAX_PAGE = 5
    _TAVILY_MAX_PAGE = 2

    def __init__(self, config_path: Path | None = None, keys_path: Path | None = None):
        self.defaults_path: Path | None = None

        if config_path is None:
            self.defaults_path = config_defaults_dir() / "search_config.yaml"
            self.config_path = config_local_dir() / "search_config.yaml"
        else:
            self.config_path = Path(config_path)

        self._ensure_config_exists()
        if keys_path is None:
            self.model_config_service = ModelConfigService()
        else:
            self.model_config_service = ModelConfigService(keys_path=keys_path)
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        if not self.config_path.exists():
            default_config = {
                "search": {
                    "provider": "duckduckgo",
                    "max_results": 10,
                    "timeout_seconds": 10,
                }
            }
            initial_text = yaml.safe_dump(default_config, allow_unicode=True, sort_keys=False)
            ensure_local_file(
                local_path=self.config_path,
                defaults_path=self.defaults_path,
                initial_text=initial_text,
            )

    def _load_config(self) -> SearchConfig:
        plugin_config = self._load_plugin_search_config()
        if plugin_config is not None:
            return plugin_config

        self._ensure_config_exists()
        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
            search_data = data.get("search", {})
            return SearchConfig(
                provider=search_data.get("provider", "duckduckgo"),
                max_results=search_data.get("max_results", 10),
                timeout_seconds=search_data.get("timeout_seconds", 10),
            )
        except Exception as e:
            logger.warning(f"Failed to load search config: {e}")
            return SearchConfig()

    @staticmethod
    def _load_plugin_search_config() -> SearchConfig | None:
        try:
            settings = load_effective_web_tools_settings()
            search_data = settings.get("search", {})
            if not isinstance(search_data, dict):
                return None
            return SearchConfig(
                provider=str(search_data.get("provider", "duckduckgo")),
                max_results=int(search_data.get("max_results", 10)),
                timeout_seconds=int(search_data.get("timeout_seconds", 10)),
            )
        except Exception as exc:
            logger.warning("Failed to load web_tools.search settings: %s", exc)
            return None

    def save_config(self, updates: dict) -> None:
        self._ensure_config_exists()
        try:
            with open(self.config_path, encoding="utf-8") as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

        if "search" not in data:
            data["search"] = {}

        for key, value in updates.items():
            data["search"][key] = value

        with open(self.config_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        self.config = self._load_config()

    async def search(self, query: str, *, page: int = 1) -> list[SearchSource]:
        query = (query or "").strip()
        if not query:
            return []
        safe_page = max(1, min(int(page), self._MAX_PAGE))

        provider = (self.config.provider or "").lower()
        if provider == "tavily":
            return await self._search_tavily(query, page=safe_page)
        if provider == "duckduckgo":
            return await self._search_duckduckgo(query, page=safe_page)

        logger.warning(f"Search provider '{provider}' is not supported")
        return []

    @staticmethod
    def _dedupe_sources(sources: list[SearchSource]) -> list[SearchSource]:
        seen_urls: set[str] = set()
        deduped: list[SearchSource] = []
        for source in sources:
            url = str(getattr(source, "url", "") or "").strip()
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            deduped.append(source)
        return deduped

    def _paginate_sources(self, sources: list[SearchSource], *, page: int) -> list[SearchSource]:
        deduped = self._dedupe_sources(sources)
        page_size = max(1, int(self.config.max_results))
        start = (page - 1) * page_size
        end = start + page_size
        return deduped[start:end]

    async def _search_tavily(self, query: str, *, page: int) -> list[SearchSource]:
        if page > self._TAVILY_MAX_PAGE:
            raise ValueError(
                f"Search provider 'tavily' supports simulated pagination only up to page {self._TAVILY_MAX_PAGE}"
            )

        api_key = await self.model_config_service.get_api_key("tavily")
        if not api_key:
            logger.warning("Tavily API key not found in config/local/keys_config.yaml")
            return []

        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": max(1, int(self.config.max_results)) * max(1, int(page)),
            "include_answer": False,
            "include_raw_content": False,
        }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

        timeout = httpx.Timeout(self.config.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.post(
                "https://api.tavily.com/search", json=payload, headers=headers
            )
            response.raise_for_status()
            data = response.json()

        sources: list[SearchSource] = []
        for result in data.get("results", []) or []:
            url = result.get("url")
            title = result.get("title") or url or "Source"
            snippet = result.get("content")
            score = result.get("score")
            if not url:
                continue
            sources.append(
                SearchSource.model_validate(
                    {
                        "type": "search",
                        "title": title,
                        "url": url,
                        "snippet": snippet,
                        "score": score,
                    }
                )
            )

        return self._paginate_sources(sources, page=page)

    async def _search_duckduckgo(self, query: str, *, page: int) -> list[SearchSource]:
        if DDGS_CLIENT is None:
            logger.warning("ddgs is not installed")
            return []

        def run_search() -> list[SearchSource]:
            backends = ["lite", "html"]
            last_error: Exception | None = None
            ddgs_cls = DDGS_CLIENT
            if ddgs_cls is None:
                return []
            request_limit = max(1, int(self.config.max_results))

            with ddgs_cls() as ddgs:
                for backend in backends:
                    try:
                        try:
                            iterator = ddgs.text(
                                query, max_results=request_limit, page=page, backend=backend
                            )
                        except TypeError:
                            iterator = ddgs.text(query, max_results=request_limit)

                        results: list[SearchSource] = []
                        for result in iterator:
                            url = result.get("href") or result.get("url")
                            title = result.get("title") or url or "Source"
                            snippet = result.get("body") or result.get("snippet")
                            if not url:
                                continue
                            results.append(
                                SearchSource.model_validate(
                                    {
                                        "type": "search",
                                        "title": title,
                                        "url": url,
                                        "snippet": snippet,
                                    }
                                )
                            )

                        if results:
                            return results
                    except Exception as e:
                        last_error = e
                        continue

            if last_error:
                logger.warning(f"DuckDuckGo search failed via ddgs: {last_error}")
            return []

        try:
            return await asyncio.wait_for(
                asyncio.to_thread(run_search), timeout=self.config.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning("DuckDuckGo search timed out")
            return []

    @staticmethod
    def build_search_context(query: str, sources: Sequence[Any]) -> str:
        lines = [
            "Web search results (use for grounding; cite sources by URL):",
            f"Query: {query}",
        ]
        for index, source in enumerate(sources, start=1):
            source_payload = source.model_dump() if hasattr(source, "model_dump") else source
            if not isinstance(source_payload, dict):
                continue
            snippet = str(source_payload.get("snippet") or "").strip()
            if len(snippet) > 400:
                snippet = snippet[:400] + "..."
            title = str(source_payload.get("title") or "")
            url = str(source_payload.get("url") or "")
            lines.append(f"[{index}] {title}")
            lines.append(f"URL: {url}")
            if snippet:
                lines.append(f"Snippet: {snippet}")
        return "\n".join(lines)
