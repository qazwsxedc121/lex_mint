"""
Google Gemini SDK Adapter

Adapter for Google Gemini API using langchain-google-genai.
Supports thinking mode (Gemini 2.5+), vision, and function calling.
"""
import logging
import importlib
from typing import AsyncIterator, List, Dict, Any

from langchain_core.messages import BaseMessage

from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage
from .utils import extract_tool_calls

logger = logging.getLogger(__name__)

# Gemini REST API base for model listing / connection testing
_GEMINI_API_BASE = "https://generativelanguage.googleapis.com/v1beta"


def _parse_content_blocks(content) -> tuple[str, str]:
    """
    Parse Gemini response content which may be a plain string or a list
    of typed blocks (when thinking mode is active).

    Returns:
        (text_content, thinking_content)
    """
    if isinstance(content, str):
        return content, ""

    if isinstance(content, list):
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        for block in content:
            if isinstance(block, dict):
                block_type = block.get("type", "text")
                block_text = block.get("text", "")
                if block_type == "thinking":
                    thinking_parts.append(block_text)
                else:
                    text_parts.append(block_text)
            elif isinstance(block, str):
                text_parts.append(block)
        return "".join(text_parts), "".join(thinking_parts)

    return str(content) if content else "", ""


class GeminiAdapter(BaseLLMAdapter):
    """
    Adapter for Google Gemini API.

    Uses langchain-google-genai package for proper Gemini integration.
    Supports thinking mode for Gemini 2.5 models via thinking_budget.
    """

    _DEFAULT_TEST_MODEL = "gemini-2.0-flash"

    _THINKING_BUDGETS = {
        "low": 2048,
        "medium": 8192,
        "high": 24576,
    }

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs
    ):
        """
        Create a ChatGoogleGenerativeAI instance.

        Args:
            model: Model ID (gemini-2.5-flash, etc.)
            base_url: API base URL (accepted but not used - SDK manages its own endpoint)
            api_key: Google API key
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable thinking mode
            **kwargs: Additional parameters (thinking_budget, max_tokens, top_p, top_k)

        Returns:
            ChatGoogleGenerativeAI instance
        """
        module = importlib.import_module("langchain_google_genai")
        ChatGoogleGenerativeAI = getattr(module, "ChatGoogleGenerativeAI")

        llm_kwargs: Dict[str, Any] = {
            "model": model,
            "google_api_key": api_key,
            "temperature": temperature,
            "streaming": streaming,
        }

        # Map max_tokens -> max_output_tokens (Gemini SDK convention)
        if "max_tokens" in kwargs and kwargs["max_tokens"] is not None:
            llm_kwargs["max_output_tokens"] = kwargs["max_tokens"]

        # Enable thinking mode if requested (Gemini 2.5+)
        if thinking_enabled:
            budget = kwargs.get("thinking_budget", self._THINKING_BUDGETS["medium"])
            llm_kwargs["thinking_budget"] = budget
            logger.info(f"Gemini thinking mode enabled for {model} (budget={budget})")

        # Sampling parameters
        if "top_p" in kwargs and kwargs["top_p"] is not None:
            llm_kwargs["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs and kwargs["top_k"] is not None:
            llm_kwargs["top_k"] = kwargs["top_k"]

        return ChatGoogleGenerativeAI(**llm_kwargs)

    async def stream(
        self,
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from Google Gemini.

        Handles content as either a plain string or a list of typed blocks
        (thinking / text) when thinking mode is active.

        Args:
            llm: ChatGoogleGenerativeAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content and thinking
        """
        usage_data = None

        async for chunk in llm.astream(messages):
            raw_content = chunk.content if hasattr(chunk, "content") else ""
            text_content, thinking = _parse_content_blocks(raw_content)

            # Also check additional_kwargs for thinking content
            if not thinking and hasattr(chunk, "additional_kwargs") and chunk.additional_kwargs:
                thinking = chunk.additional_kwargs.get("thinking", "")

            tool_calls = extract_tool_calls(chunk)

            # Extract usage from chunk (usually only in final chunk)
            extracted = TokenUsage.extract_from_chunk(chunk)
            if extracted:
                usage_data = extracted

            yield StreamChunk(
                content=text_content,
                thinking=thinking,
                tool_calls=tool_calls,
                usage=usage_data,
                raw=chunk,
            )

    async def invoke(
        self,
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke Google Gemini and get complete response.

        Args:
            llm: ChatGoogleGenerativeAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with content and thinking
        """
        response = await llm.ainvoke(messages)

        raw_content = response.content if hasattr(response, "content") else ""
        text_content, thinking = _parse_content_blocks(raw_content)

        # Fallback: check additional_kwargs
        if not thinking and hasattr(response, "additional_kwargs") and response.additional_kwargs:
            thinking = response.additional_kwargs.get("thinking", "")

        # Extract usage from usage_metadata or response_metadata
        usage = TokenUsage.extract_from_chunk(response)
        if usage is None and hasattr(response, "response_metadata") and response.response_metadata:
            raw_usage = response.response_metadata.get("usage")
            if raw_usage:
                usage = TokenUsage.from_dict(raw_usage)

        return LLMResponse(
            content=text_content,
            thinking=thinking,
            tool_calls=extract_tool_calls(response),
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        """Gemini 2.5 models support thinking mode."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        Get parameters for Gemini thinking mode.

        Maps effort levels to thinking_budget tokens:
        - low: 2048 tokens
        - medium: 8192 tokens
        - high: 24576 tokens
        """
        budget = self._THINKING_BUDGETS.get(effort, self._THINKING_BUDGETS["medium"])
        return {"thinking_budget": budget}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from Google Gemini API.

        Uses the REST API to list models that support generateContent.
        Paginates through all results.

        Args:
            base_url: API base URL (ignored, uses Gemini REST endpoint)
            api_key: Google API key

        Returns:
            List of model dicts with 'id', 'name', and optional capability info
        """
        import httpx

        models: List[Dict[str, str]] = []
        page_token = None

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                while True:
                    params: Dict[str, str] = {"key": api_key, "pageSize": "100"}
                    if page_token:
                        params["pageToken"] = page_token

                    response = await client.get(
                        f"{_GEMINI_API_BASE}/models",
                        params=params,
                    )
                    response.raise_for_status()
                    data = response.json()

                    for model in data.get("models", []):
                        # Only include models that support content generation
                        methods = model.get("supportedGenerationMethods", [])
                        if "generateContent" not in methods:
                            continue

                        model_name = model.get("name", "")
                        # model_name is like "models/gemini-2.5-flash"
                        model_id = model_name.replace("models/", "") if model_name.startswith("models/") else model_name
                        display_name = model.get("displayName", model_id)

                        models.append({
                            "id": model_id,
                            "name": display_name,
                        })

                    page_token = data.get("nextPageToken")
                    if not page_token:
                        break

        except Exception as e:
            logger.warning(f"Failed to fetch Gemini models: {e}")
            # Return curated fallback list
            return self._curated_models()

        return sorted(models, key=lambda x: x["id"]) if models else self._curated_models()

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: str | None = None
    ) -> tuple[bool, str]:
        """
        Test connection to Google Gemini API.

        Uses a lightweight models list call to validate the API key
        without consuming generation quota.

        Args:
            base_url: API base URL (ignored)
            api_key: Google API key
            model_id: Optional model ID (not used for validation)

        Returns:
            Tuple of (success, message)
        """
        import httpx

        if not api_key:
            return False, "API key is required"

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                response = await client.get(
                    f"{_GEMINI_API_BASE}/models",
                    params={"key": api_key, "pageSize": "1"},
                )
                if response.status_code in (400, 403):
                    try:
                        error_data = response.json()
                        error_msg = error_data.get("error", {}).get("message", "Bad request")
                    except Exception:
                        error_msg = response.text or "Bad request"
                    label = "Invalid API key" if response.status_code == 400 else "Authentication failed"
                    return False, f"{label}: {error_msg}"
                response.raise_for_status()

                data = response.json()
                model_count = len(data.get("models", []))
                if model_count > 0:
                    return True, "Connection successful"
                return False, "API responded but returned no models"

        except httpx.TimeoutException:
            return False, "Connection timeout: API not responding"
        except httpx.HTTPStatusError as e:
            return False, f"HTTP error: {e.response.status_code}"
        except Exception as e:
            return False, f"Connection error: {str(e)}"

    @staticmethod
    def _curated_models() -> List[Dict[str, str]]:
        """Fallback curated model list when API fetch fails."""
        return [
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash"},
            {"id": "gemini-1.5-pro", "name": "Gemini 1.5 Pro"},
            {"id": "gemini-1.5-flash", "name": "Gemini 1.5 Flash"},
        ]
