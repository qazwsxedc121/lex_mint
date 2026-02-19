"""Unit tests for simple_llm module."""

import pytest
from unittest.mock import patch, Mock, AsyncMock, MagicMock
from langchain_core.messages import HumanMessage, AIMessage

from src.agents.simple_llm import call_llm, call_llm_stream
from src.providers.types import TokenUsage


class TestCallLLM:
    """Test cases for call_llm function."""

    @patch('src.agents.simple_llm.get_llm_logger')
    @patch('src.agents.simple_llm.ModelConfigService')
    def test_call_llm_success(self, mock_model_service_class, mock_logger):
        """Test successful LLM call."""
        # Mock LLM response
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Python is a high-level programming language."
        mock_llm.invoke.return_value = mock_response
        mock_llm.model_name = "deepseek-chat"

        # Mock ModelConfigService
        mock_model = Mock()
        mock_provider = Mock()
        mock_capabilities = Mock()
        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.get_llm_instance.return_value = mock_llm
        mock_model_service_class.return_value = mock_service

        # Mock logger
        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        # Test
        messages = [
            {"role": "user", "content": "What is Python?"}
        ]

        result = call_llm(messages, session_id="test-session")

        assert result == "Python is a high-level programming language."
        mock_llm.invoke.assert_called_once()
        mock_llm_logger.log_interaction.assert_called_once()

    @patch('src.agents.simple_llm.get_llm_logger')
    @patch('src.agents.simple_llm.ModelConfigService')
    def test_call_llm_with_history(self, mock_model_service_class, mock_logger):
        """Test LLM call with conversation history."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Python has dynamic typing and automatic memory management."
        mock_llm.invoke.return_value = mock_response
        mock_llm.model_name = "deepseek-chat"

        mock_model = Mock()
        mock_provider = Mock()
        mock_capabilities = Mock()
        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.get_llm_instance.return_value = mock_llm
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
            {"role": "user", "content": "What are its features?"}
        ]

        result = call_llm(messages)

        # Verify that all messages were converted
        call_args = mock_llm.invoke.call_args[0][0]
        assert len(call_args) == 3
        assert isinstance(call_args[0], HumanMessage)
        assert isinstance(call_args[1], AIMessage)
        assert isinstance(call_args[2], HumanMessage)

    @patch('src.agents.simple_llm.get_llm_logger')
    @patch('src.agents.simple_llm.ModelConfigService')
    def test_call_llm_error(self, mock_model_service_class, mock_logger):
        """Test LLM call error handling."""
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_llm.model_name = "deepseek-chat"

        mock_model = Mock()
        mock_provider = Mock()
        mock_capabilities = Mock()
        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.get_llm_instance.return_value = mock_llm
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(Exception, match="API Error"):
            call_llm(messages)

        # Verify error was logged
        mock_llm_logger.log_error.assert_called_once()


class TestCallLLMStream:
    """Test cases for call_llm_stream function."""

    @pytest.mark.asyncio
    @patch('src.agents.simple_llm.get_llm_logger')
    @patch('src.agents.simple_llm.ModelConfigService')
    async def test_call_llm_stream_success(self, mock_model_service_class, mock_logger):
        """Test successful streaming LLM call."""
        # Mock model and provider config
        mock_model = Mock()
        mock_model.id = "deepseek-chat"

        mock_provider = Mock()
        mock_provider.id = "deepseek"
        mock_provider.base_url = "https://api.deepseek.com"

        # Mock capabilities
        mock_capabilities = Mock()
        mock_capabilities.reasoning = False

        # Mock service
        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.resolve_provider_api_key_sync.return_value = "test_key_123"

        # Mock adapter
        mock_adapter = Mock()
        mock_llm = Mock()
        mock_adapter.create_llm.return_value = mock_llm

        # Mock streaming response
        async def mock_stream(*args, **kwargs):
            chunks = ["Hello", " world", "!"]
            for chunk_text in chunks:
                chunk = Mock()
                chunk.content = chunk_text
                chunk.thinking = None
                chunk.usage = None
                chunk.raw = None
                yield chunk

            # Final chunk with usage
            usage_raw = Mock()
            usage_raw.usage_metadata = {
                "input_tokens": 10,
                "output_tokens": 20,
                "total_tokens": 30,
            }
            usage_raw.tool_calls = []
            final_chunk = Mock()
            final_chunk.content = ""
            final_chunk.thinking = None
            final_chunk.usage = TokenUsage(
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30
            )
            final_chunk.raw = usage_raw
            yield final_chunk

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter

        mock_model_service_class.return_value = mock_service

        # Mock logger
        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        # Test
        messages = [{"role": "user", "content": "Hello"}]
        result_chunks = []

        async for chunk in call_llm_stream(messages, session_id="test-session"):
            result_chunks.append(chunk)

        # Verify tokens
        text_chunks = [c for c in result_chunks if isinstance(c, str)]
        assert "".join(text_chunks) == "Hello world!"

        # Verify usage data
        usage_chunks = [c for c in result_chunks if isinstance(c, dict) and c.get("type") == "usage"]
        assert len(usage_chunks) == 1
        assert usage_chunks[0]["type"] == "usage"
        assert usage_chunks[0]["usage"].total_tokens == 30

    @pytest.mark.asyncio
    @patch('src.agents.simple_llm.get_llm_logger')
    @patch('src.agents.simple_llm.ModelConfigService')
    async def test_call_llm_stream_with_system_prompt(self, mock_model_service_class, mock_logger):
        """Test streaming with system prompt."""
        mock_model = Mock()
        mock_model.id = "deepseek-chat"

        mock_provider = Mock()
        mock_provider.id = "deepseek"
        mock_provider.base_url = "https://api.deepseek.com"

        mock_capabilities = Mock()
        mock_capabilities.reasoning = False

        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.resolve_provider_api_key_sync.return_value = "test_key_123"

        # Mock adapter
        mock_adapter = Mock()
        mock_llm = Mock()
        mock_adapter.create_llm.return_value = mock_llm

        async def mock_stream(llm, messages):
            # Verify system prompt was injected
            from langchain_core.messages import SystemMessage
            assert isinstance(messages[0], SystemMessage)
            assert messages[0].content == "You are a helpful assistant."

            chunk = Mock()
            chunk.content = "Response"
            chunk.thinking = None
            chunk.usage = None
            chunk.raw = None
            yield chunk

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        messages = [{"role": "user", "content": "Hello"}]

        chunks = []
        async for chunk in call_llm_stream(
            messages,
            system_prompt="You are a helpful assistant."
        ):
            chunks.append(chunk)

        assert "Response" in "".join([c for c in chunks if isinstance(c, str)])

    @pytest.mark.asyncio
    @patch('src.agents.simple_llm.get_llm_logger')
    @patch('src.agents.simple_llm.ModelConfigService')
    async def test_call_llm_stream_with_thinking(self, mock_model_service_class, mock_logger):
        """Test streaming with thinking/reasoning mode."""
        mock_model = Mock()
        mock_model.id = "deepseek-reasoner"

        mock_provider = Mock()
        mock_provider.id = "deepseek"
        mock_provider.base_url = "https://api.deepseek.com"

        # Enable reasoning capability
        mock_capabilities = Mock()
        mock_capabilities.reasoning = True

        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.resolve_provider_api_key_sync.return_value = "test_key_123"

        # Mock adapter
        mock_adapter = Mock()
        mock_llm = Mock()
        mock_adapter.create_llm.return_value = mock_llm

        async def mock_stream(*args, **kwargs):
            # Thinking phase
            thinking_chunk = Mock()
            thinking_chunk.content = None
            thinking_chunk.thinking = "Let me analyze this..."
            thinking_chunk.usage = None
            thinking_chunk.raw = None
            yield thinking_chunk

            # Content phase
            content_chunk = Mock()
            content_chunk.content = "The answer is 42."
            content_chunk.thinking = None
            content_chunk.usage = None
            content_chunk.raw = None
            yield content_chunk

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        messages = [{"role": "user", "content": "Question"}]
        chunks = []

        async for chunk in call_llm_stream(
            messages,
            reasoning_effort="medium"
        ):
            if isinstance(chunk, str):
                chunks.append(chunk)

        # Verify thinking tags were inserted
        full_response = "".join(chunks)
        assert "<think>" in full_response
        assert "</think>" in full_response
        assert "Let me analyze this..." in full_response
        assert "The answer is 42." in full_response

    @pytest.mark.asyncio
    @patch('src.agents.simple_llm.get_llm_logger')
    @patch('src.agents.simple_llm.ModelConfigService')
    async def test_call_llm_stream_error(self, mock_model_service_class, mock_logger):
        """Test streaming error handling."""
        mock_model = Mock()
        mock_model.id = "deepseek-chat"

        mock_provider = Mock()
        mock_provider.id = "deepseek"

        mock_capabilities = Mock()
        mock_capabilities.reasoning = False

        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.resolve_provider_api_key_sync.return_value = "test_key_123"

        mock_adapter = Mock()
        mock_llm = Mock()
        mock_adapter.create_llm.return_value = mock_llm

        # Mock stream error
        async def mock_stream_error(*args, **kwargs):
            raise Exception("Stream error")
            yield  # unreachable

        mock_adapter.stream = mock_stream_error
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        messages = [{"role": "user", "content": "Test"}]

        with pytest.raises(Exception, match="Stream error"):
            async for _ in call_llm_stream(messages):
                pass

        # Verify error was logged
        mock_llm_logger.log_error.assert_called_once()
