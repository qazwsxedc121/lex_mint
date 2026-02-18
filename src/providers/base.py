"""
Base LLM Adapter

Abstract base class for LLM provider adapters.
"""
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Dict, Any, Optional
from langchain_core.messages import BaseMessage

from .types import StreamChunk, LLMResponse, ProviderConfig, ModelConfig, ModelCapabilities


class BaseLLMAdapter(ABC):
    """
    Abstract base class for LLM adapters.

    Each adapter handles a specific SDK/API protocol and provides a unified
    interface for creating LLM instances and processing responses.
    """

    # Default model used for test_connection when no model_id is provided.
    # Subclasses should override for non-OpenAI providers.
    _DEFAULT_TEST_MODEL = "gpt-3.5-turbo"

    @abstractmethod
    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs
    ) -> Any:
        """
        Create an LLM instance for this adapter.

        Args:
            model: Model ID to use
            base_url: API base URL
            api_key: API key for authentication
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable thinking/reasoning mode
            **kwargs: Additional provider-specific parameters

        Returns:
            LLM instance (ChatOpenAI, ChatDeepSeek, etc.)
        """
        pass

    @abstractmethod
    async def stream(
        self,
        llm: Any,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from the LLM.

        Args:
            llm: LLM instance created by create_llm()
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with normalized content
        """
        pass

    @abstractmethod
    async def invoke(
        self,
        llm: Any,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke the LLM and get a complete response.

        Args:
            llm: LLM instance created by create_llm()
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with normalized content
        """
        pass

    def supports_thinking(self) -> bool:
        """
        Check if this adapter supports thinking/reasoning mode.

        Returns:
            True if thinking mode is supported
        """
        return False

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        Get parameters to enable thinking mode.

        Args:
            effort: Reasoning effort level ("low", "medium", "high")

        Returns:
            Dictionary of parameters to pass to the LLM
        """
        return {}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from the provider's API.

        Args:
            base_url: API base URL
            api_key: API key for authentication

        Returns:
            List of model info dicts with 'id' and 'name' keys
        """
        return []

    async def test_connection(
        self,
        base_url: str,
        api_key: str,
        model_id: str = None
    ) -> tuple[bool, str]:
        """
        Test connection to the provider.

        Args:
            base_url: API base URL
            api_key: API key for authentication
            model_id: Optional model ID to test with

        Returns:
            Tuple of (success, message)
        """
        try:
            llm = self.create_llm(
                model=model_id or self._DEFAULT_TEST_MODEL,
                base_url=base_url,
                api_key=api_key,
                temperature=0.0,
                streaming=False,
                timeout=15.0,
                max_retries=0,
                max_tokens=10,
                disable_thinking=True,
            )
            from langchain_core.messages import HumanMessage
            response = await self.invoke(llm, [HumanMessage(content="hi")])
            if response and (response.content or response.thinking):
                return True, "Connection successful"
            return False, "No response from API"
        except Exception as e:
            error_msg = str(e)
            if "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                return False, "Authentication failed: Invalid API key"
            elif "not found" in error_msg.lower() or "404" in error_msg:
                return False, "API endpoint not found: Check base URL"
            elif "timeout" in error_msg.lower():
                return False, "Connection timeout: API not responding"
            return False, f"Connection error: {error_msg}"
