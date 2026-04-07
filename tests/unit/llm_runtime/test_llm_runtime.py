"""Unit tests for llm_runtime public entrypoints."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from src.llm_runtime import (
    _build_context_plan,
    _build_reasoning_decision_payload,
    _get_context_limit,
    _is_context_plan_truncated,
    _truncate_by_rounds,
    build_context_info_event,
    call_llm,
    call_llm_stream,
)
from src.providers.types import TokenUsage


class TestCallLLM:
    """Test cases for call_llm function."""

    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
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
        mock_model.id = "deepseek-chat"
        mock_provider = Mock()
        mock_provider.id = "deepseek"
        mock_provider.base_url = "https://api.deepseek.com"
        mock_capabilities = Mock()
        mock_capabilities.context_length = None
        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.get_llm_instance.return_value = mock_llm
        mock_model_service_class.return_value = mock_service

        # Mock logger
        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        # Test
        messages = [{"role": "user", "content": "What is Python?"}]

        result = call_llm(messages, session_id="test-session")

        assert result == "Python is a high-level programming language."
        mock_llm.invoke.assert_called_once()
        mock_llm_logger.log_interaction.assert_called_once()

    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    def test_call_llm_with_history(self, mock_model_service_class, mock_logger):
        """Test LLM call with conversation history."""
        mock_llm = Mock()
        mock_response = Mock()
        mock_response.content = "Python has dynamic typing and automatic memory management."
        mock_llm.invoke.return_value = mock_response
        mock_llm.model_name = "deepseek-chat"

        mock_model = Mock()
        mock_model.id = "deepseek-chat"
        mock_provider = Mock()
        mock_provider.id = "deepseek"
        mock_provider.base_url = "https://api.deepseek.com"
        mock_capabilities = Mock()
        mock_capabilities.context_length = None
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
            {"role": "user", "content": "What are its features?"},
        ]

        call_llm(messages)

        # Verify that all messages were converted
        call_args = mock_llm.invoke.call_args[0][0]
        assert len(call_args) == 3
        assert isinstance(call_args[0], HumanMessage)
        assert isinstance(call_args[1], AIMessage)
        assert isinstance(call_args[2], HumanMessage)

    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    def test_call_llm_error(self, mock_model_service_class, mock_logger):
        """Test LLM call error handling."""
        mock_llm = Mock()
        mock_llm.invoke.side_effect = Exception("API Error")
        mock_llm.model_name = "deepseek-chat"

        mock_model = Mock()
        mock_model.id = "deepseek-chat"
        mock_provider = Mock()
        mock_provider.id = "deepseek"
        mock_provider.base_url = "https://api.deepseek.com"
        mock_capabilities = Mock()
        mock_capabilities.context_length = None
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


def test_get_context_limit_uses_small_config_window_instead_of_default():
    llm = SimpleNamespace(profile=None)
    capabilities = SimpleNamespace(context_length=2048)

    budget, window = _get_context_limit(llm=llm, capabilities=capabilities)

    assert window == 2048
    assert budget == 1024


def test_get_context_limit_prefers_profile_over_config():
    llm = SimpleNamespace(profile={"max_input_tokens": 12000})
    capabilities = SimpleNamespace(context_length=32000)

    budget, window = _get_context_limit(llm=llm, capabilities=capabilities)

    assert window == 12000
    assert budget == 11400


def test_truncate_by_rounds_preserves_all_leading_system_messages():
    messages = [
        SystemMessage(content="assistant-system"),
        SystemMessage(content="compressed-summary"),
        HumanMessage(content="u1"),
        AIMessage(content="a1"),
        HumanMessage(content="u2"),
        AIMessage(content="a2"),
        HumanMessage(content="u3"),
    ]

    result = _truncate_by_rounds(messages, max_rounds=1, system_prompt="assistant-system")

    assert [msg.content for msg in result] == [
        "assistant-system",
        "compressed-summary",
        "u3",
    ]


def test_truncate_by_rounds_keeps_last_user_anchored_rounds():
    messages = [
        SystemMessage(content="assistant-system"),
        SystemMessage(content="compressed-summary"),
        HumanMessage(content="u1"),
        AIMessage(content="a1"),
        HumanMessage(content="u2"),
        AIMessage(content="a2"),
        HumanMessage(content="u3"),
        AIMessage(content="a3"),
    ]

    result = _truncate_by_rounds(messages, max_rounds=2, system_prompt="assistant-system")

    assert [msg.content for msg in result] == [
        "assistant-system",
        "compressed-summary",
        "u2",
        "a2",
        "u3",
        "a3",
    ]


def test_build_context_plan_prefers_segmented_context_and_reports_history():
    plan = _build_context_plan(
        messages=[
            {"role": "user", "content": "hello"},
            {"role": "assistant", "content": "hi"},
        ],
        system_prompt="legacy-system",
        context_segments={
            "base_system_prompt": "base-system",
            "memory_context": "memory",
            "rag_context": "rag",
        },
        summary_content="summary",
        max_rounds=1,
        context_budget_tokens=800,
    )

    assert [segment.name for segment in plan.system_segments[:4]] == [
        "system",
        "summary",
        "memory",
        "rag",
    ]
    assert plan.system_segments[0].content == "base-system"
    assert [msg["content"] for msg in plan.chat_messages] == ["hello", "hi"]
    history_report = next(segment for segment in plan.segment_reports if segment.name == "history")
    assert history_report.included is True


def test_build_reasoning_decision_payload_contains_effective_adapter_args():
    capabilities = SimpleNamespace(reasoning=True, requires_interleaved_thinking=True)
    reasoning_controls = SimpleNamespace(
        mode="enum",
        param="reasoning.effort",
        options=["minimal", "low", "medium", "high"],
        disable_supported=True,
    )

    payload = _build_reasoning_decision_payload(
        session_id="session-1",
        provider_id="openrouter",
        model_id="google/gemini-3-flash-preview",
        call_mode="auto",
        requested_reasoning_mode="high",
        capabilities=capabilities,
        reasoning_controls=reasoning_controls,
        thinking_enabled=True,
        disable_thinking=False,
        effective_reasoning_option="high",
        effective_reasoning_effort="high",
    )

    assert payload["requested_reasoning_mode"] == "high"
    assert payload["capabilities_reasoning"] is True
    assert payload["requires_interleaved_thinking"] is True
    assert payload["reasoning_controls"]["param"] == "reasoning.effort"
    assert payload["decision"]["thinking_enabled"] is True
    assert payload["adapter_args"]["reasoning_option"] == "high"
    assert payload["adapter_args"]["reasoning_effort"] == "high"


def test_context_info_event_excludes_segments_and_includes_truncation_flag():
    plan = _build_context_plan(
        messages=[{"role": "user", "content": "hello"}],
        system_prompt="system",
        context_segments={"memory_context": "x" * 2000},
        summary_content=None,
        max_rounds=None,
        context_budget_tokens=120,
    )

    assert _is_context_plan_truncated(plan) is True

    event = build_context_info_event(
        context_plan=plan,
        context_budget=120,
        context_window=160,
        estimated_prompt_tokens=80,
        context_truncated=True,
    )

    assert event["type"] == "context_info"
    assert event["context_truncated"] is True
    assert "segments" not in event


class TestCallLLMStream:
    """Test cases for call_llm_stream function."""

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
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
            final_chunk.usage = None
            final_chunk.raw = SimpleNamespace(
                usage_metadata={
                    "input_tokens": 10,
                    "output_tokens": 20,
                    "total_tokens": 30,
                }
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
        usage_chunks = [
            c for c in result_chunks if isinstance(c, dict) and c.get("type") == "usage"
        ]
        assert len(usage_chunks) == 1
        assert usage_chunks[0]["type"] == "usage"
        assert usage_chunks[0]["usage"].total_tokens == 30

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    async def test_call_llm_stream_prefers_chunk_usage_over_merged_raw_usage(
        self, mock_model_service_class, mock_logger
    ):
        """Avoid inflated usage when merged raw chunks over-count cumulative metadata."""
        mock_model = Mock()
        mock_model.id = "step-3.5-flash"

        mock_provider = Mock()
        mock_provider.id = "stepfun"
        mock_provider.base_url = "https://api.stepfun.com/v1"

        mock_capabilities = Mock()
        mock_capabilities.reasoning = False

        mock_service = Mock()
        mock_service.get_model_and_provider_sync.return_value = (mock_model, mock_provider)
        mock_service.get_merged_capabilities.return_value = mock_capabilities
        mock_service.resolve_provider_api_key_sync.return_value = "test_key_123"

        mock_adapter = Mock()
        mock_llm = Mock()
        mock_adapter.create_llm.return_value = mock_llm

        async def mock_stream(*args, **kwargs):
            chunk = Mock()
            chunk.content = "hello"
            chunk.thinking = None
            chunk.usage = TokenUsage(prompt_tokens=440, completion_tokens=95, total_tokens=535)
            chunk.raw = None
            yield chunk

            inflated_raw = SimpleNamespace(
                usage_metadata={
                    "input_tokens": 44000,
                    "output_tokens": 9526,
                    "total_tokens": 53526,
                }
            )
            final_chunk = Mock()
            final_chunk.content = ""
            final_chunk.thinking = None
            final_chunk.usage = TokenUsage(
                prompt_tokens=440, completion_tokens=95, total_tokens=535
            )
            final_chunk.raw = inflated_raw
            yield final_chunk

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service
        mock_logger.return_value = Mock()

        result_chunks = []
        async for chunk in call_llm_stream(
            [{"role": "user", "content": "你好"}], session_id="test-session"
        ):
            result_chunks.append(chunk)

        usage_chunks = [
            c for c in result_chunks if isinstance(c, dict) and c.get("type") == "usage"
        ]
        assert len(usage_chunks) == 1
        assert usage_chunks[0]["usage"].prompt_tokens == 440
        assert usage_chunks[0]["usage"].completion_tokens == 95
        assert usage_chunks[0]["usage"].total_tokens == 535

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
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
        async for chunk in call_llm_stream(messages, system_prompt="You are a helpful assistant."):
            chunks.append(chunk)

        assert "Response" in "".join([c for c in chunks if isinstance(c, str)])

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
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

        async for chunk in call_llm_stream(messages, reasoning_effort="medium"):
            if isinstance(chunk, str):
                chunks.append(chunk)

        # Verify thinking tags were inserted
        full_response = "".join(chunks)
        assert "<think>" in full_response
        assert "</think>" in full_response
        assert "Let me analyze this..." in full_response
        assert "The answer is 42." in full_response

    @pytest.mark.asyncio
    @patch("src.tools.registry.get_tool_registry")
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    async def test_call_llm_stream_forces_final_answer_after_max_tool_rounds(
        self,
        mock_model_service_class,
        mock_logger,
        mock_get_tool_registry,
    ):
        """When tool rounds hit the cap, stream should force a non-tool finalization pass."""
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

        mock_adapter = Mock()
        mock_llm = Mock()
        mock_bound_llm = Mock()
        mock_llm.bind_tools.return_value = mock_bound_llm
        mock_adapter.create_llm.return_value = mock_llm

        class _Raw:
            def __init__(self, tool_calls=None):
                self.tool_calls = tool_calls or []

            def __add__(self, other):
                return _Raw(
                    tool_calls=list(self.tool_calls) + list(getattr(other, "tool_calls", []) or [])
                )

        class _Chunk:
            def __init__(self, content, tool_calls):
                self.content = content
                self.thinking = None
                self.raw = _Raw(tool_calls=tool_calls)

        stream_state = {"count": 0}

        async def mock_stream(active_llm, _messages):
            idx = stream_state["count"]
            stream_state["count"] += 1

            if idx < 4:
                assert active_llm is mock_bound_llm
                yield _Chunk(
                    content=f"round{idx + 1};",
                    tool_calls=[
                        {
                            "name": "search_knowledge",
                            "args": {"query": f"q{idx + 1}", "top_k": 5},
                            "id": f"tc{idx + 1}",
                        }
                    ],
                )
                return

            assert active_llm is mock_llm
            yield _Chunk(content="FINAL_ANSWER", tool_calls=[])

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        mock_registry = Mock()
        mock_registry.execute_tool.return_value = '{"ok": true}'
        mock_get_tool_registry.return_value = mock_registry

        tool_executor = Mock(return_value='{"ok": true}')
        messages = [{"role": "user", "content": "Test tool loop"}]
        collected = []

        async for chunk in call_llm_stream(
            messages,
            tools=[Mock()],
            tool_executor=tool_executor,
        ):
            collected.append(chunk)

        text = "".join([c for c in collected if isinstance(c, str)])
        assert "FINAL_ANSWER" in text
        assert stream_state["count"] == 5
        assert tool_executor.call_count == 3

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    async def test_call_llm_stream_injects_read_compensation_for_evidence_requests(
        self,
        mock_model_service_class,
        mock_logger,
    ):
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

        mock_adapter = Mock()
        mock_llm = Mock()
        mock_bound_llm = Mock()
        mock_llm.bind_tools.return_value = mock_bound_llm
        mock_adapter.create_llm.return_value = mock_llm

        class _Raw:
            def __init__(self, tool_calls=None):
                self.tool_calls = tool_calls or []

            def __add__(self, other):
                return _Raw(
                    tool_calls=list(self.tool_calls) + list(getattr(other, "tool_calls", []) or [])
                )

        class _Chunk:
            def __init__(self, content, tool_calls):
                self.content = content
                self.thinking = None
                self.raw = _Raw(tool_calls=tool_calls)

        stream_state = {"count": 0}

        async def mock_stream(active_llm, _messages):
            assert active_llm is mock_bound_llm
            idx = stream_state["count"]
            stream_state["count"] += 1

            if idx == 0:
                yield _Chunk(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_knowledge",
                            "args": {"query": "policy details", "top_k": 5},
                            "id": "tc1",
                        }
                    ],
                )
                return
            if idx == 1:
                # No tool call here; compensation prompt should trigger another pass.
                yield _Chunk(content="draft answer", tool_calls=[])
                return
            if idx == 2:
                yield _Chunk(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_knowledge",
                            "args": {"refs": ["kb:kb_test|doc:doc_1|chunk:3"]},
                            "id": "tc2",
                        }
                    ],
                )
                return

            yield _Chunk(content="FINAL_ANSWER", tool_calls=[])

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        def _tool_executor(name, _args):
            if name == "search_knowledge":
                return (
                    '{"ok": true, "hits": [{"ref_id": "kb:kb_test|doc:doc_1|chunk:3", '
                    '"filename": "doc.md", "snippet": "snippet"}]}'
                )
            if name == "read_knowledge":
                return (
                    '{"ok": true, "sources": [{"ref_id": "kb:kb_test|doc:doc_1|chunk:3", '
                    '"filename": "doc.md", "content": "exact quote"}]}'
                )
            return '{"ok": true}'

        tool_executor = Mock(side_effect=_tool_executor)
        messages = [{"role": "user", "content": "请给我逐字引用并附上出处"}]
        collected = []

        async for chunk in call_llm_stream(messages, tools=[Mock()], tool_executor=tool_executor):
            collected.append(chunk)

        diagnostics = [
            c for c in collected if isinstance(c, dict) and c.get("type") == "tool_diagnostics"
        ]
        assert len(diagnostics) == 1
        assert diagnostics[0]["tool_search_count"] == 1
        assert diagnostics[0]["tool_search_unique_count"] == 1
        assert diagnostics[0]["tool_search_duplicate_count"] == 0
        assert diagnostics[0]["tool_read_count"] == 1
        assert diagnostics[0]["tool_finalize_reason"] == "normal_no_tools"
        assert stream_state["count"] == 4
        executed_tools = [call.args[0] for call in tool_executor.call_args_list]
        assert executed_tools[0] == "search_knowledge"
        assert "read_knowledge" in executed_tools
        assert executed_tools.index("read_knowledge") > executed_tools.index("search_knowledge")

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    async def test_call_llm_stream_injects_fallback_when_final_answer_empty(
        self,
        mock_model_service_class,
        mock_logger,
    ):
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

        mock_adapter = Mock()
        mock_llm = Mock()
        mock_bound_llm = Mock()
        mock_llm.bind_tools.return_value = mock_bound_llm
        mock_adapter.create_llm.return_value = mock_llm

        class _Raw:
            def __init__(self, tool_calls=None):
                self.tool_calls = tool_calls or []

            def __add__(self, other):
                return _Raw(
                    tool_calls=list(self.tool_calls) + list(getattr(other, "tool_calls", []) or [])
                )

        class _Chunk:
            def __init__(self, content, tool_calls):
                self.content = content
                self.thinking = None
                self.raw = _Raw(tool_calls=tool_calls)

        stream_state = {"count": 0}

        async def mock_stream(active_llm, _messages):
            assert active_llm is mock_bound_llm
            idx = stream_state["count"]
            stream_state["count"] += 1
            if idx == 0:
                yield _Chunk(
                    content="",
                    tool_calls=[
                        {
                            "name": "search_knowledge",
                            "args": {"query": "q1", "top_k": 5},
                            "id": "tc1",
                        }
                    ],
                )
                return
            yield _Chunk(content="", tool_calls=[])

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        tool_executor = Mock(
            return_value='{"ok": true, "hits": [{"filename": "doc.md", "snippet": "snippet"}]}'
        )
        messages = [{"role": "user", "content": "normal request"}]
        collected = []

        async for chunk in call_llm_stream(messages, tools=[Mock()], tool_executor=tool_executor):
            collected.append(chunk)

        text = "".join([c for c in collected if isinstance(c, str)])
        diagnostics = [
            c for c in collected if isinstance(c, dict) and c.get("type") == "tool_diagnostics"
        ]
        assert "I could not finalize a complete answer from the model stream." in text
        assert len(diagnostics) == 1
        assert diagnostics[0]["tool_search_count"] == 1
        assert diagnostics[0]["tool_read_count"] == 0
        assert diagnostics[0]["tool_finalize_reason"] == "fallback_empty_answer"

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    async def test_call_llm_stream_expands_tool_round_budget_for_web_research(
        self,
        mock_model_service_class,
        mock_logger,
    ):
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

        mock_adapter = Mock()
        mock_llm = Mock()
        mock_bound_llm = Mock()
        mock_llm.bind_tools.return_value = mock_bound_llm
        mock_adapter.create_llm.return_value = mock_llm

        class _Raw:
            def __init__(self, tool_calls=None):
                self.tool_calls = tool_calls or []

            def __add__(self, other):
                return _Raw(
                    tool_calls=list(self.tool_calls) + list(getattr(other, "tool_calls", []) or [])
                )

        class _Chunk:
            def __init__(self, content, tool_calls):
                self.content = content
                self.thinking = None
                self.raw = _Raw(tool_calls=tool_calls)

        class _Tool:
            def __init__(self, name):
                self.name = name

        stream_state = {"count": 0}

        async def mock_stream(active_llm, _messages):
            idx = stream_state["count"]
            stream_state["count"] += 1

            if idx < 6:
                assert active_llm is mock_bound_llm
                yield _Chunk(
                    content=f"round{idx + 1};",
                    tool_calls=[
                        {
                            "name": "web_search",
                            "args": {"query": f"q{idx + 1}"},
                            "id": f"tc{idx + 1}",
                        }
                    ],
                )
                return

            assert active_llm is mock_bound_llm
            yield _Chunk(content="FINAL_ANSWER", tool_calls=[])

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        tool_executor = Mock(return_value='{"ok": true, "results": []}')
        messages = [
            {
                "role": "user",
                "content": "How many athletes were there by country at the 1928 Summer Olympics?",
            }
        ]
        collected = []

        async for chunk in call_llm_stream(
            messages,
            tools=[_Tool("web_search"), _Tool("read_webpage")],
            tool_executor=tool_executor,
        ):
            collected.append(chunk)

        text = "".join([c for c in collected if isinstance(c, str)])
        diagnostics = [
            c for c in collected if isinstance(c, dict) and c.get("type") == "tool_diagnostics"
        ]
        assert "FINAL_ANSWER" in text
        assert stream_state["count"] == 7
        assert tool_executor.call_count == 6
        assert len(diagnostics) == 1
        assert diagnostics[0]["max_tool_rounds"] == 6

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
    async def test_call_llm_stream_injects_read_webpage_compensation_for_web_research(
        self,
        mock_model_service_class,
        mock_logger,
    ):
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

        mock_adapter = Mock()
        mock_llm = Mock()
        mock_bound_llm = Mock()
        mock_llm.bind_tools.return_value = mock_bound_llm
        mock_adapter.create_llm.return_value = mock_llm

        class _Raw:
            def __init__(self, tool_calls=None):
                self.tool_calls = tool_calls or []

            def __add__(self, other):
                return _Raw(
                    tool_calls=list(self.tool_calls) + list(getattr(other, "tool_calls", []) or [])
                )

        class _Chunk:
            def __init__(self, content, tool_calls):
                self.content = content
                self.thinking = None
                self.raw = _Raw(tool_calls=tool_calls)

        class _Tool:
            def __init__(self, name):
                self.name = name

        stream_state = {"count": 0}

        async def mock_stream(active_llm, _messages):
            assert active_llm is mock_bound_llm
            idx = stream_state["count"]
            stream_state["count"] += 1

            if idx == 0:
                yield _Chunk(
                    content="",
                    tool_calls=[
                        {
                            "name": "web_search",
                            "args": {"query": "Mercedes Sosa discography"},
                            "id": "tc1",
                        }
                    ],
                )
                return
            if idx == 1:
                yield _Chunk(content="draft answer", tool_calls=[])
                return
            if idx == 2:
                yield _Chunk(
                    content="",
                    tool_calls=[
                        {
                            "name": "read_webpage",
                            "args": {"url": "https://example.com/discography"},
                            "id": "tc2",
                        }
                    ],
                )
                return

            yield _Chunk(content="FINAL_ANSWER", tool_calls=[])

        mock_adapter.stream = mock_stream
        mock_service.get_adapter_for_provider.return_value = mock_adapter
        mock_model_service_class.return_value = mock_service

        mock_llm_logger = Mock()
        mock_logger.return_value = mock_llm_logger

        def _tool_executor(name, _args):
            if name == "web_search":
                return (
                    '{"ok": true, "results": [{"title": "Discography", "url": "https://example.com/discography", '
                    '"snippet": "Album list"}]}'
                )
            if name == "read_webpage":
                return (
                    '{"ok": true, "url": "https://example.com/discography", '
                    '"title": "Discography", "preview": "Album list"}'
                )
            return '{"ok": true}'

        tool_executor = Mock(side_effect=_tool_executor)
        messages = [
            {
                "role": "user",
                "content": "How many studio albums did Mercedes Sosa release between 2000 and 2009?",
            }
        ]
        collected = []

        async for chunk in call_llm_stream(
            messages,
            tools=[_Tool("web_search"), _Tool("read_webpage")],
            tool_executor=tool_executor,
        ):
            collected.append(chunk)

        diagnostics = [
            c for c in collected if isinstance(c, dict) and c.get("type") == "tool_diagnostics"
        ]
        assert len(diagnostics) == 1
        assert diagnostics[0]["web_search_count"] == 1
        assert diagnostics[0]["web_read_count"] == 1
        executed_tools = [call.args[0] for call in tool_executor.call_args_list]
        assert executed_tools[0] == "web_search"
        assert "read_webpage" in executed_tools
        assert executed_tools.index("read_webpage") > executed_tools.index("web_search")

    @pytest.mark.asyncio
    @patch("src.llm_runtime.get_llm_logger")
    @patch("src.llm_runtime.ModelConfigService")
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
