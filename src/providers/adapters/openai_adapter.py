"""
OpenAI SDK Adapter

Adapter for OpenAI and OpenAI-compatible APIs (OpenRouter, Groq, Together, etc.)
"""
import logging
from typing import AsyncIterator, List, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_openai.chat_models.base import BaseChatOpenAI

from ..base import BaseLLMAdapter
from ..types import CallMode, StreamChunk, LLMResponse, TokenUsage
from ..model_capability_rules import apply_interleaved_hint_to_capabilities
from .reasoning_openai import ChatReasoningOpenAI, inject_tool_call_reasoning_content
from .utils import extract_tool_calls

logger = logging.getLogger(__name__)


class ChatOpenAIInterleaved(ChatReasoningOpenAI):
    """ChatReasoningOpenAI wrapper with conditional interleaved payload patching."""

    def _get_request_payload(
        self,
        input_: Any,
        *,
        stop: list[str] | None = None,
        **kwargs: Any,
    ) -> dict:
        payload = super()._get_request_payload(input_, stop=stop, **kwargs)
        source_messages = self._convert_input(input_).to_messages()
        return inject_tool_call_reasoning_content(
            payload,
            source_messages=source_messages,
            enabled=bool(getattr(self, "_requires_interleaved_thinking", False)),
        )


class OpenAIAdapter(BaseLLMAdapter):
    """
    Adapter for OpenAI SDK.

    Supports OpenAI API and compatible providers like OpenRouter, Groq, Together AI.
    """

    @staticmethod
    def _normalize_call_mode(raw_mode: Any) -> str:
        """Normalize call mode from enum/string into a lowercase adapter hint."""
        if isinstance(raw_mode, CallMode):
            return raw_mode.value
        if raw_mode is None:
            return ""
        return str(raw_mode).strip().lower()

    @staticmethod
    def _mode_uses_responses(call_mode: str) -> bool:
        """Return whether the given normalized mode should use Responses API."""
        return call_mode == CallMode.RESPONSES.value

    @staticmethod
    def _secret_to_plain(value: Any) -> Any:
        """Unwrap pydantic SecretStr-like values to plain strings."""
        return value.get_secret_value() if hasattr(value, "get_secret_value") else value

    @staticmethod
    def _unwrap_chat_openai(llm: Any) -> tuple[BaseChatOpenAI, Dict[str, Any], Dict[str, Any]]:
        """
        Unwrap a ChatOpenAI or ChatOpenAI-bound runnable to its base model.

        Returns:
            (base_chat_openai, bind_kwargs, bind_config)
        """
        if isinstance(llm, BaseChatOpenAI):
            return llm, {}, {}

        bound = getattr(llm, "bound", None)
        if isinstance(bound, BaseChatOpenAI):
            bind_kwargs = getattr(llm, "kwargs", {}) or {}
            bind_config = getattr(llm, "config", {}) or {}
            return bound, bind_kwargs, bind_config

        raise TypeError(f"Unsupported LLM type for fallback cloning: {type(llm)!r}")

    def _clone_with_mode(self, llm: Any, *, use_responses_api: bool) -> Any:
        """Clone ChatOpenAI (or its binding) with a different Responses API toggle."""
        source_llm, bind_kwargs, bind_config = self._unwrap_chat_openai(llm)
        data = source_llm.model_dump()
        model_name = data.get("model_name") or getattr(source_llm, "model_name", None)
        llm_kwargs: Dict[str, Any] = {
            "model": model_name,
            "base_url": data.get("openai_api_base") or getattr(source_llm, "openai_api_base", None),
            "api_key": self._secret_to_plain(
                data.get("openai_api_key") or getattr(source_llm, "openai_api_key", None)
            ),
            "streaming": data.get("streaming", True),
            "stream_usage": data.get("stream_usage", True),
            "use_responses_api": use_responses_api,
        }

        optional_map = {
            "temperature": data.get("temperature"),
            "timeout": data.get("request_timeout"),
            "max_retries": data.get("max_retries"),
            "max_tokens": data.get("max_tokens"),
            "top_p": data.get("top_p"),
            "frequency_penalty": data.get("frequency_penalty"),
            "presence_penalty": data.get("presence_penalty"),
            "reasoning": data.get("reasoning"),
            "model_kwargs": data.get("model_kwargs"),
        }
        for key, value in optional_map.items():
            if value is not None:
                llm_kwargs[key] = value

        llm_cls = source_llm.__class__
        fallback_llm: Any = llm_cls(**llm_kwargs)
        if hasattr(source_llm, "_requires_interleaved_thinking"):
            object.__setattr__(
                fallback_llm,
                "_requires_interleaved_thinking",
                bool(getattr(source_llm, "_requires_interleaved_thinking", False)),
            )
        if bind_kwargs:
            fallback_llm = fallback_llm.bind(**bind_kwargs)
        if bind_config:
            fallback_llm = fallback_llm.with_config(**bind_config)

        return fallback_llm

    def create_llm(
        self,
        model: str,
        base_url: str,
        api_key: str,
        temperature: float = 0.7,
        streaming: bool = True,
        thinking_enabled: bool = False,
        **kwargs
    ) -> BaseChatOpenAI:
        """
        Create a ChatOpenAI instance.

        Args:
            model: Model ID to use
            base_url: API base URL
            api_key: API key for authentication
            temperature: Sampling temperature
            streaming: Whether to enable streaming
            thinking_enabled: Whether to enable reasoning mode (for o1 models)
            **kwargs: Additional parameters passed to ChatOpenAI

        Returns:
            ChatOpenAI instance
        """
        call_mode = self._normalize_call_mode(kwargs.get("call_mode"))
        use_responses_api = self._mode_uses_responses(call_mode)

        llm_kwargs: Dict[str, Any] = {
            "model": model,
            "temperature": temperature,
            "base_url": base_url,
            "api_key": api_key,
            "streaming": streaming,
            "stream_usage": True,
            "use_responses_api": use_responses_api,
        }

        # For OpenAI o1/o3 models, enable reasoning via responses API
        if thinking_enabled:
            llm_kwargs["reasoning"] = {
                "effort": kwargs.get("reasoning_effort", "medium"),
                "summary": "auto"
            }
            logger.info(f"OpenAI reasoning mode enabled for {model}")

        # Add any extra kwargs
        extra_keys = ["timeout", "max_retries", "max_tokens"]
        for key in extra_keys:
            if key in kwargs:
                llm_kwargs[key] = kwargs[key]

        # Add sampling parameters via model_kwargs
        model_kwargs = {}
        for key in ["top_p", "frequency_penalty", "presence_penalty"]:
            if key in kwargs:
                model_kwargs[key] = kwargs[key]
        if model_kwargs:
            llm_kwargs["model_kwargs"] = model_kwargs

        if use_responses_api:
            logger.info(f"OpenAI Responses API enabled for {model}")

        requires_interleaved = bool(kwargs.get("requires_interleaved_thinking", False))
        llm_cls = ChatOpenAIInterleaved if requires_interleaved else ChatOpenAI
        llm = llm_cls(**llm_kwargs)
        if requires_interleaved:
            object.__setattr__(llm, "_requires_interleaved_thinking", True)
        return llm

    async def stream(
        self,
        llm: Any,
        messages: List[Any],
        **kwargs
    ) -> AsyncIterator[StreamChunk]:
        """
        Stream responses from OpenAI.

        Includes usage data in the final chunk when available.

        Args:
            llm: ChatOpenAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Yields:
            StreamChunk objects with content
        """
        usage_data = None
        yielded_payload = False
        allow_responses_fallback = bool(kwargs.get("allow_responses_fallback", False))

        try:
            async for chunk in llm.astream(messages):
                content = chunk.content if hasattr(chunk, 'content') else ""
                thinking = ""

                # Check for reasoning content in additional_kwargs (OpenAI responses API)
                if hasattr(chunk, 'additional_kwargs'):
                    thinking = chunk.additional_kwargs.get('reasoning_content', '')

                # Extract usage from chunk (usually only in final chunk)
                extracted = TokenUsage.extract_from_chunk(chunk)
                if extracted:
                    usage_data = extracted

                if content or thinking:
                    yielded_payload = True

                yield StreamChunk(
                    content=content,
                    thinking=thinking,
                    tool_calls=extract_tool_calls(chunk),
                    usage=usage_data,
                    raw=chunk,
                )
        except Exception as e:
            in_responses_mode = bool(getattr(llm, "use_responses_api", False))
            if allow_responses_fallback and in_responses_mode and not yielded_payload:
                logger.warning(
                    "Responses stream failed, retrying with chat/completions: %s",
                    e,
                )
                fallback_llm = self._clone_with_mode(llm, use_responses_api=False)
                async for fallback_chunk in self.stream(
                    fallback_llm,
                    messages,
                    allow_responses_fallback=False,
                ):
                    yield fallback_chunk
                return
            raise

    async def invoke(
        self,
        llm: Any,
        messages: List[Any],
        **kwargs
    ) -> LLMResponse:
        """
        Invoke OpenAI and get complete response.

        Args:
            llm: ChatOpenAI instance
            messages: List of LangChain messages
            **kwargs: Additional parameters

        Returns:
            LLMResponse with content
        """
        allow_responses_fallback = bool(kwargs.get("allow_responses_fallback", False))
        try:
            response = await llm.ainvoke(messages)
        except Exception as e:
            in_responses_mode = bool(getattr(llm, "use_responses_api", False))
            if allow_responses_fallback and in_responses_mode:
                logger.warning(
                    "Responses invoke failed, retrying with chat/completions: %s",
                    e,
                )
                fallback_llm = self._clone_with_mode(llm, use_responses_api=False)
                response = await fallback_llm.ainvoke(messages)
            else:
                raise

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
        """OpenAI o1/o3 models support reasoning."""
        return True

    def get_thinking_params(self, effort: str = "medium") -> Dict[str, Any]:
        """Get parameters for OpenAI reasoning mode."""
        return {
            "reasoning": {
                "effort": effort,
                "summary": "auto"
            }
        }

    @staticmethod
    def _parse_model_metadata(model: dict) -> dict | None:
        """
        Parse rich model metadata from provider API responses.

        Detects OpenRouter-style responses (architecture, supported_parameters)
        and extracts capabilities and tags.

        Returns:
            Dict with 'capabilities' and 'tags', or None if no rich metadata.
        """
        architecture = model.get("architecture")
        supported_params = model.get("supported_parameters")
        context_length = model.get("context_length")

        # Only parse if rich metadata is present (e.g. OpenRouter)
        if not architecture and not supported_params and not context_length:
            return None

        input_modalities = (architecture or {}).get("input_modalities", [])
        output_modalities = (architecture or {}).get("output_modalities", [])
        params = supported_params or []

        has_vision = "image" in input_modalities
        has_function_calling = "tools" in params
        has_reasoning = "reasoning" in params or "include_reasoning" in params
        has_image_output = "image" in output_modalities
        has_file_upload = "file" in input_modalities
        has_streaming = True  # Assumed for OpenAI-compatible APIs

        capabilities = {
            "context_length": context_length or 4096,
            "vision": has_vision,
            "function_calling": has_function_calling,
            "reasoning": has_reasoning,
            "streaming": has_streaming,
            "file_upload": has_file_upload,
            "image_output": has_image_output,
        }

        # Derive tags from capabilities
        tags = []
        if has_vision:
            tags.append("vision")
        if has_function_calling:
            tags.append("function-calling")
        if has_reasoning:
            tags.append("reasoning")
        if has_image_output:
            tags.append("image-output")
        if has_file_upload:
            tags.append("file-upload")
        if not tags:
            tags.append("chat")

        capabilities = apply_interleaved_hint_to_capabilities(model.get("id", ""), capabilities)
        return {"capabilities": capabilities, "tags": tags}

    async def fetch_models(
        self,
        base_url: str,
        api_key: str
    ) -> List[Dict[str, str]]:
        """
        Fetch available models from OpenAI-compatible API.

        Args:
            base_url: API base URL
            api_key: API key

        Returns:
            List of model info dicts
        """
        import httpx

        try:
            # Normalize base URL
            url = base_url.rstrip('/')
            if not url.endswith('/v1'):
                url = f"{url}/v1"
            models_url = f"{url}/models"

            headers = {}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(
                    models_url,
                    headers=headers,
                )
                response.raise_for_status()

                data = response.json()
                models = []
                for model in data.get("data", []):
                    model_id = model.get("id", "")
                    entry = {
                        "id": model_id,
                        "name": model.get("name", model_id),
                    }

                    # Parse rich metadata if available (e.g. OpenRouter)
                    caps_and_tags = self._parse_model_metadata(model)
                    if caps_and_tags:
                        entry["capabilities"] = caps_and_tags["capabilities"]
                        entry["tags"] = caps_and_tags["tags"]
                    else:
                        hinted_caps = apply_interleaved_hint_to_capabilities(model_id, None)
                        if hinted_caps:
                            entry["capabilities"] = hinted_caps

                    models.append(entry)

                return sorted(models, key=lambda x: x["id"])

        except Exception as e:
            logger.warning(f"Failed to fetch models: {e}")
            return []
