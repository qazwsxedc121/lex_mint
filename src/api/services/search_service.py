"""Web search service using Tavily or DuckDuckGo."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import logging
import asyncio
import yaml
import httpx
from ..models.search import SearchSource
from .model_config_service import ModelConfigService

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
    max_results: int = 6
    timeout_seconds: int = 10


class SearchService:
    """Service for web search and result normalization."""

    def __init__(self, config_path: Optional[Path] = None, keys_path: Optional[Path] = None):
        if config_path is None:
            config_path = Path(__file__).parent.parent.parent.parent / "config" / "search_config.yaml"
        self.config_path = config_path
        self.model_config_service = ModelConfigService(keys_path=keys_path)
        self.config = self._load_config()

    def _ensure_config_exists(self) -> None:
        if not self.config_path.exists():
            default_config = {
                "search": {
                    "provider": "duckduckgo",
                    "max_results": 6,
                    "timeout_seconds": 10,
                }
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.safe_dump(default_config, f, allow_unicode=True, sort_keys=False)

    def _load_config(self) -> SearchConfig:
        self._ensure_config_exists()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
            search_data = data.get("search", {})
            return SearchConfig(
                provider=search_data.get("provider", "duckduckgo"),
                max_results=search_data.get("max_results", 6),
                timeout_seconds=search_data.get("timeout_seconds", 10),
            )
        except Exception as e:
            logger.warning(f"Failed to load search config: {e}")
            return SearchConfig()

    def save_config(self, updates: dict) -> None:
        self._ensure_config_exists()
        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f) or {}
        except Exception:
            data = {}

        if "search" not in data:
            data["search"] = {}

        for key, value in updates.items():
            data["search"][key] = value

        with open(self.config_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False)

        self.config = self._load_config()

    async def search(self, query: str) -> List[SearchSource]:
        query = (query or "").strip()
        if not query:
            return []

        provider = (self.config.provider or "").lower()
        if provider == "tavily":
            return await self._search_tavily(query)
        if provider == "duckduckgo":
            return await self._search_duckduckgo(query)

        logger.warning(f"Search provider '{provider}' is not supported")
        return []

    async def _search_tavily(self, query: str) -> List[SearchSource]:
        api_key = await self.model_config_service.get_api_key("tavily")
        if not api_key:
            logger.warning("Tavily API key not found in config/keys_config.yaml")
            return []

        payload = {
            "query": query,
            "search_depth": "basic",
            "max_results": self.config.max_results,
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
                "https://api.tavily.com/search",
                json=payload,
                headers=headers
            )
            response.raise_for_status()
            data = response.json()

        sources: List[SearchSource] = []
        for result in data.get("results", []) or []:
            url = result.get("url")
            title = result.get("title") or url or "Source"
            snippet = result.get("content")
            score = result.get("score")
            if not url:
                continue
            sources.append(SearchSource(type="search", title=title, url=url, snippet=snippet, score=score))

        return sources

    async def _search_duckduckgo(self, query: str) -> List[SearchSource]:
        if DDGS_CLIENT is None:
            logger.warning("ddgs is not installed")
            return []

        def run_search() -> List[SearchSource]:
            backends = ["lite", "html"]
            last_error: Optional[Exception] = None

            with DDGS_CLIENT() as ddgs:
                for backend in backends:
                    try:
                        try:
                            iterator = ddgs.text(
                                query,
                                max_results=self.config.max_results,
                                backend=backend
                            )
                        except TypeError:
                            iterator = ddgs.text(
                                query,
                                max_results=self.config.max_results
                            )

                        results: List[SearchSource] = []
                        for result in iterator:
                            url = result.get("href") or result.get("url")
                            title = result.get("title") or url or "Source"
                            snippet = result.get("body") or result.get("snippet")
                            if not url:
                                continue
                            results.append(SearchSource(type="search", title=title, url=url, snippet=snippet))

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
                asyncio.to_thread(run_search),
                timeout=self.config.timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning("DuckDuckGo search timed out")
            return []

    @staticmethod
    def build_search_context(query: str, sources: List[SearchSource]) -> str:
        lines = [
            "Web search results (use for grounding; cite sources by URL):",
            f"Query: {query}",
        ]
        for index, source in enumerate(sources, start=1):
            snippet = (source.snippet or "").strip()
            if len(snippet) > 400:
                snippet = snippet[:400] + "..."
            lines.append(f"[{index}] {source.title}")
            lines.append(f"URL: {source.url}")
            if snippet:
                lines.append(f"Snippet: {snippet}")
        return "\n".join(lines)
