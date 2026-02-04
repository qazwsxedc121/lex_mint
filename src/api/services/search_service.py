"""Web search service using Tavily."""

from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional
import logging
import yaml
import httpx

from ..models.search import SearchSource
from .model_config_service import ModelConfigService

logger = logging.getLogger(__name__)


@dataclass
class SearchConfig:
    provider: str = "tavily"
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
                    "provider": "tavily",
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
                provider=search_data.get("provider", "tavily"),
                max_results=search_data.get("max_results", 6),
                timeout_seconds=search_data.get("timeout_seconds", 10),
            )
        except Exception as e:
            logger.warning(f"Failed to load search config: {e}")
            return SearchConfig()

    async def search(self, query: str) -> List[SearchSource]:
        query = (query or "").strip()
        if not query:
            return []

        provider = (self.config.provider or "").lower()
        if provider != "tavily":
            logger.warning(f"Search provider '{provider}' is not supported")
            return []

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
            sources.append(SearchSource(title=title, url=url, snippet=snippet, score=score))

        return sources

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
