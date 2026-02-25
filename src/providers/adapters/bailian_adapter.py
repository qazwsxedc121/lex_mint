"""
Alibaba Cloud Bailian (DashScope) OpenAI-Compatible Adapter.

Adapter for Qwen models via DashScope's OpenAI-compatible API.
Supports thinking mode, web search, tool calls, and streaming
through pass-through request parameters.
"""
import logging
from typing import AsyncIterator, List, Dict, Any, Optional

from langchain_core.messages import BaseMessage

from .reasoning_openai import ChatReasoningOpenAI
from .utils import extract_tool_calls
from ..base import BaseLLMAdapter
from ..types import StreamChunk, LLMResponse, TokenUsage

logger = logging.getLogger(__name__)


class BailianAdapter(BaseLLMAdapter):
    """
    Adapter for Alibaba Cloud Bailian (DashScope) OpenAI-compatible API.

    Uses ChatReasoningOpenAI (a ChatOpenAI subclass that parses
    reasoning_content) with the DashScope OpenAI-compatible endpoint,
    and passes Qwen-specific capabilities (thinking, web search, etc.)
    via extra_body / model_kwargs.
    """

    _DEFAULT_TEST_MODEL = "qwen-plus"

    _CURATED_MODELS: List[Dict[str, str]] = [
        {"id": "qwen3-max", "name": "Qwen3 Max"},
        {"id": "qwen-max", "name": "Qwen Max"},
        {"id": "qwen3-coder-plus", "name": "Qwen3 Coder Plus"},
        {"id": "qwen-plus", "name": "Qwen Plus"},
        {"id": "qwen-turbo", "name": "Qwen Turbo"},
        {"id": "qwen-long", "name": "Qwen Long"},
        {"id": "qvq-plus", "name": "QVQ Plus"},
        {"id": "qwen3-vl-plus", "name": "Qwen3 VL Plus"},
        {"id": "qwen3-vl-flash", "name": "Qwen3 VL Flash"},
    ]

    # Models with always-on thinking (no enable_thinking toggle).
    # These only accept thinking_budget, not enable_thinking.
    _ALWAYS_THINKING_MODELS = {"qwq-plus", "qwq-max"}

    # DashScope thinking budget range
    _DEFAULT_THINKING_BUDGET = 4096

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        thinking_budget: Optional[int] = None,
        **kwargs
    ) -> ChatReasoningOpenAI:
        """Create ChatReasoningOpenAI client for DashScope OpenAI-compatible endpoint."""
        llm_kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url,
            "api_key": api_key,
            "streaming": streaming,
            "stream_usage": True,
        }

        # Common direct parameters ChatOpenAI already supports.
        for key in ["timeout", "max_retries", "max_tokens"]:
            if key in kwargs and kwargs[key] is not None:
                llm_kwargs[key] = kwargs[key]

        model_kwargs: Dict[str, Any] = {}
        extra_body: Dict[str, Any] = {}
        disable_thinking = bool(kwargs.get("disable_thinking", False))

        # DashScope thinking mode.
        # QwQ models have always-on thinking: only thinking_budget applies.
        # Qwen3 hybrid models use enable_thinking + thinking_budget.
        is_always_thinking = any(p in model.lower() for p in self._ALWAYS_THINKING_MODELS)

        if is_always_thinking:
            # QwQ: thinking is always on, only set budget
            budget = thinking_budget or self._DEFAULT_THINKING_BUDGET
            if not disable_thinking:
                extra_body["thinking_budget"] = budget
                logger.info(f"Bailian always-thinking model {model}, budget={budget}")
            else:
                logger.info(f"Bailian disable_thinking requested for always-thinking model {model}, ignoring")
        elif disable_thinking:
            extra_body["enable_thinking"] = False
            logger.info(f"Bailian thinking mode disabled for {model}")
        elif thinking_enabled:
            extra_body["enable_thinking"] = True
            budget = thinking_budget or self._DEFAULT_THINKING_BUDGET
            extra_body["thinking_budget"] = budget
            logger.info(f"Bailian thinking mode enabled for {model}, budget={budget}")

        # DashScope web search feature.
        enable_search = kwargs.get("enable_search")
        if enable_search is not None:
            extra_body["enable_search"] = bool(enable_search)
            search_options = kwargs.get("search_options")
            if search_options:
                extra_body["search_options"] = search_options

        # Sampling and OpenAI-compatible extras.
        passthrough_keys = [
            "top_p",
            "top_k",
            "frequency_penalty",
            "presence_penalty",
            "repetition_penalty",
            "stop",
            "seed",
        ]
        for key in passthrough_keys:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        # Feature passthrough (tools, structured output, etc.).
        feature_keys = [
            "tools",
            "tool_choice",
            "response_format",
        ]
        for key in feature_keys:
            if key in kwargs and kwargs[key] is not None:
                model_kwargs[key] = kwargs[key]

        if extra_body:
            llm_kwargs["extra_body"] = extra_body

        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        return ChatReasoningOpenAI(**llm_kwargs)

    async def stream(
        self,
        llm: ChatReasoningOpenAI,
        messages: List[BaseMessage],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """Stream DashScope responses, including reasoning and tool-call chunks."""
        usage_data = None

        async for chunk in llm.astream(messages):
            content_raw = chunk.content if hasattr(chunk, "content") else ""
            content = content_raw if isinstance(content_raw, str) else str(content_raw or "")
            thinking = ""
            tool_calls = extract_tool_calls(chunk)

            if hasattr(chunk, "additional_kwargs") and chunk.additional_kwargs:
                thinking = chunk.additional_kwargs.get("reasoning_content", "")

            extracted = TokenUsage.extract_from_chunk(chunk)
            if extracted:
                usage_data = extracted

            yield StreamChunk(
                content=content,
                thinking=thinking,
                tool_calls=tool_calls,
                usage=usage_data,
                raw=chunk,
            )

    async def invoke(
        self,
        llm: ChatReasoningOpenAI,
        messages: List[BaseMessage],
        **kwargs
    ) -> LLMResponse:
        """Invoke DashScope and return normalized full response."""
        response = await llm.ainvoke(messages)

        thinking = ""
        if hasattr(response, "additional_kwargs") and response.additional_kwargs:
            thinking = response.additional_kwargs.get("reasoning_content", "")

        usage = None
        if hasattr(response, "response_metadata") and response.response_metadata:
            usage = TokenUsage.from_dict(response.response_metadata.get("usage"))

        content_raw = response.content if hasattr(response, "content") else ""
        content = content_raw if isinstance(content_raw, str) else str(content_raw or "")

        return LLMResponse(
            content=content,
            thinking=thinking,
            tool_calls=extract_tool_calls(response),
            usage=usage,
            raw=response,
        )

    def supports_thinking(self) -> bool:
        """Qwen3 hybrid thinking models support enable_thinking."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """
        DashScope thinking mode uses enable_thinking + thinking_budget.

        For Qwen3 hybrid models, both enable_thinking and thinking_budget are set.
        For QwQ models (always-on thinking), callers should only pass
        thinking_budget via create_llm; enable_thinking is handled automatically.

        Args:
            effort: Reasoning effort level mapped to thinking_budget.

        Returns:
            Dict with enable_thinking and thinking_budget parameters.
        """
        budget_map = {
            "minimal": 1024,
            "low": 2048,
            "medium": self._DEFAULT_THINKING_BUDGET,
            "high": 8192,
        }
        budget = budget_map.get(effort, self._DEFAULT_THINKING_BUDGET)
        return {
            "enable_thinking": True,
            "thinking_budget": budget,
        }

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from DashScope /models endpoint.

        Falls back to curated list on any error.
        """
        import httpx

        try:
            url = base_url.rstrip("/")
            models_url = f"{url}/models"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    models_url,
                    headers={"Authorization": f"Bearer {api_key}"}
                )
                response.raise_for_status()

                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    if model_id:
                        models.append({
                            "id": model_id,
                            "name": model.get("name", model_id),
                        })

                if models:
                    return sorted(models, key=lambda x: x["id"])

        except Exception as e:
            logger.warning(f"Failed to fetch DashScope models, using curated list: {e}")

        return sorted(self._CURATED_MODELS, key=lambda x: x["id"])
