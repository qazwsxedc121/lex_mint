"""
Ollama SDK Adapter

Adapter for Ollama local models using langchain-ollama.
"""
import logging
from typing import AsyncIterator, List, Dict, Any

from langchain_core.messages import BaseMessage

from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage
from .utils import extract_tool_calls

logger = logging.getLogger(__name__)


class OllamaAdapter(BaseLLMAdapter):
    """
    Adapter for Ollama local models.

    Uses langchain-ollama package for local Ollama integration.
    Supports reasoning mode for compatible models.
    """

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
        Create a ChatOllama instance.

        Args:
            model: Model name (llama3.1, qwen3, etc.)
            base_url: Ollama server URL (default: http://localhost:11434)
            api_key: Not used for Ollama (local)
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable reasoning mode
            **kwargs: Additional parameters

        Returns:
            ChatOllama instance
        """
        from langchain_ollama import ChatOllama

        llm_kwargs = {
            "model": model,
            "base_url": base_url or "http://localhost:11434",
            "temperature": temperature,
        }

        # Enable reasoning mode if requested
        # Ollama reasoning mode captures thinking in reasoning_content
        if thinking_enabled:
            llm_kwargs["reasoning"] = True
            logger.info(f"Ollama reasoning mode enabled for {model}")

        # Map max_tokens to num_predict (before explicit num_predict check)
        if "max_tokens" in kwargs:
            llm_kwargs["num_predict"] = kwargs["max_tokens"]

        # Add optional parameters
        if "num_ctx" in kwargs:
            llm_kwargs["num_ctx"] = kwargs["num_ctx"]
        if "num_predict" in kwargs:
            llm_kwargs["num_predict"] = kwargs["num_predict"]
        if "top_p" in kwargs:
            llm_kwargs["top_p"] = kwargs["top_p"]
        if "top_k" in kwargs:
            llm_kwargs["top_k"] = kwargs["top_k"]

        return ChatOllama(**llm_kwargs)

    async def stream(
        self,
        llm,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from Ollama.

        Handles reasoning_content for thinking mode.
        Includes usage data in the final chunk when available.

        Args:
            llm: ChatOllama instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content and thinking
        """
        usage_data = None

        async for chunk in llm.astream(messages):
            content = chunk.content if hasattr(chunk, 'content') else ""
            thinking = ""

            # Check for reasoning content in additional_kwargs
            if hasattr(chunk, 'additional_kwargs'):
                thinking = chunk.additional_kwargs.get('reasoning_content', '')

            # Extract usage from chunk (usually only in final chunk)
            extracted = TokenUsage.extract_from_chunk(chunk)
            if extracted:
                usage_data = extracted

            yield StreamChunk(
                content=content,
                thinking=thinking,
                tool_calls=extract_tool_calls(chunk),
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
        Invoke Ollama and get complete response.

        Args:
            llm: ChatOllama instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with content and thinking
        """
        response = await llm.ainvoke(messages)

        thinking = ""
        if hasattr(response, 'additional_kwargs'):
            thinking = response.additional_kwargs.get('reasoning_content', '')

        usage = None
        if hasattr(response, 'response_metadata'):
            raw_usage = response.response_metadata.get('usage')
            usage = TokenUsage.from_dict(raw_usage)

        return LLMResponse(
            content=response.content,
            thinking=thinking,
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        """Ollama supports reasoning mode for compatible models."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        Get parameters for Ollama reasoning mode.

        Note: Ollama reasoning is binary (enabled/disabled), no effort levels.
        """
        return {"reasoning": True}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from local Ollama instance.

        Args:
            base_url: Ollama server URL
            api_key: Not used

        Returns:
            List of model info dicts from Ollama
        """
        import httpx

        try:
            url = (base_url or "http://localhost:11434").rstrip('/')
            tags_url = f"{url}/api/tags"

            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(tags_url)
                response.raise_for_status()

                data = response.json()
                models = []
                for model in data.get("models", []):
                    model_name = model.get("name", "")
                    # Remove tag suffix for display name
                    display_name = model_name.split(":")[0] if ":" in model_name else model_name

                    entry = {
                        "id": model_name,
                        "name": display_name.title(),
                    }

                    # Parse Ollama details for capability hints
                    details = model.get("details", {})
                    if details:
                        families = details.get("families") or []
                        family = details.get("family", "")
                        all_families = set(families + ([family] if family else []))

                        has_vision = any(
                            f in all_families
                            for f in ("clip", "mllama", "llava")
                        ) or "vision" in model_name.lower()

                        tags = []
                        if has_vision:
                            tags.append("vision")
                        if not tags:
                            tags.append("chat")

                        entry["capabilities"] = {
                            "context_length": 4096,
                            "vision": has_vision,
                            "function_calling": False,
                            "reasoning": False,
                            "streaming": True,
                            "file_upload": False,
                            "image_output": False,
                        }
                        entry["tags"] = tags

                    models.append(entry)

                return sorted(models, key=lambda x: x["id"])

        except httpx.ConnectError:
            logger.warning(f"Cannot connect to Ollama at {base_url}. Is Ollama running?")
            return []
        except Exception as e:
            logger.warning(f"Failed to fetch Ollama models: {e}")
            return []

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: str = None
    ) -> tuple[bool, str]:
        """
        Test connection to Ollama server.

        Args:
            base_url: Ollama server URL
            api_key: Not used
            model_id: Optional model to test

        Returns:
            Tuple of (success, message)
        """
        import httpx

        try:
            url = (base_url or "http://localhost:11434").rstrip('/')

            async with httpx.AsyncClient(timeout=10.0) as client:
                # First check if Ollama is running
                response = await client.get(f"{url}/api/tags")
                response.raise_for_status()

                data = response.json()
                model_count = len(data.get("models", []))

                if model_count == 0:
                    return True, "Ollama is running but no models installed. Run 'ollama pull <model>' to add models."

                return True, f"Connected to Ollama with {model_count} model(s) available"

        except httpx.ConnectError:
            return False, "Cannot connect to Ollama. Make sure Ollama is running (ollama serve)"
        except httpx.TimeoutException:
            return False, "Connection timeout. Ollama may be starting up or overloaded"
        except Exception as e:
            return False, f"Connection error: {str(e)}"
