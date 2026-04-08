"""Unit tests for single-chat flow service extraction."""

import asyncio
from types import SimpleNamespace
from typing import cast

import pytest

from src.application.chat.chat_input_service import PreparedUserInput
from src.application.chat.request_contexts import (
    ConversationScope,
    EditorContext,
    SearchOptions,
    SingleChatRequestContext,
    StreamOptions,
    ToolResolutionContext,
    UserInputPayload,
)
from src.application.chat.service_contracts import ContextPayload
from src.application.chat.single_chat_flow_service import (
    SingleChatFlowDeps,
    SingleChatFlowService,
    SingleChatResolvedTools,
    SingleDirectOrchestrator,
)
from src.providers.types import CostInfo, TokenUsage


async def _collect_events(async_iter):
    events = []
    async for event in async_iter:
        events.append(event)
    return events


class _FakePricingService:
    def calculate_cost(self, *_args, **_kwargs):
        return CostInfo(input_cost=0.01, output_cost=0.02, total_cost=0.03, currency="USD")


async def _fake_call_llm_stream(*_args, **_kwargs):
    usage = TokenUsage(prompt_tokens=5, completion_tokens=7, total_tokens=12)
    yield {
        "type": "context_info",
        "context_budget": 100,
        "context_window": 128,
        "estimated_prompt_tokens": 4,
        "remaining_tokens": 96,
        "context_truncated": False,
    }
    yield "hello"
    yield {"type": "usage", "usage": usage}


class _FakePostTurnService:
    def __init__(self):
        self.finalize_calls = []
        self.partial_calls = []

    async def save_partial_assistant_message(self, **kwargs):
        self.partial_calls.append(kwargs)
        return None

    async def finalize_single_turn(self, **kwargs):
        self.finalize_calls.append(kwargs)
        return "assistant-msg-1"

    async def generate_followup_questions(self, **_kwargs):
        return ["next question"]


class _FakeInputService:
    def __init__(self):
        self.calls = []

    async def prepare_user_input(self, **kwargs):
        self.calls.append(dict(kwargs))
        skip_user_append = bool(kwargs.get("skip_user_append"))
        return PreparedUserInput(
            raw_user_message="hello",
            full_message_content="hello",
            attachment_metadata=[],
            user_message_id=None if skip_user_append else "user-msg-1",
        )


@pytest.mark.asyncio
async def test_single_chat_flow_streams_events_and_finalizes(monkeypatch):
    post_turn = _FakePostTurnService()
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: None),
        chat_input_service=_FakeInputService(),
        post_turn_service=post_turn,
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt=None,
                assistant_params={},
                all_sources=[{"type": "memory"}],
                max_rounds=None,
                assistant_memory_enabled=True,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(
        service,
        "_maybe_auto_compress",
        lambda **kwargs: _return_async((kwargs["messages"], None)),
    )
    monkeypatch.setattr(
        service,
        "_resolve_tools",
        lambda **_kwargs: _return_async((None, None)),
    )

    events = await _collect_events(
        service.process_message_stream(
            request=SingleChatRequestContext(
                scope=ConversationScope(session_id="s1", context_type="chat"),
                user_input=UserInputPayload(user_message="hello"),
            )
        )
    )

    assert events[0] == {"type": "user_message_id", "message_id": "user-msg-1"}
    assert events[1] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[2]["type"] == "context_info"
    assert events[3] == "hello"
    assert events[4]["type"] == "usage"
    assert events[5] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[6] == {"type": "assistant_message_id", "message_id": "assistant-msg-1"}
    assert events[7] == {"type": "followup_questions", "questions": ["next question"]}
    assert len(post_turn.finalize_calls) == 1
    assert post_turn.finalize_calls[0]["assistant_message"] == "hello"
    assert post_turn.finalize_calls[0]["usage_data"] == TokenUsage(
        prompt_tokens=5,
        completion_tokens=7,
        total_tokens=12,
    )

    response, sources = await service.process_message(
        request=SingleChatRequestContext(
            scope=ConversationScope(session_id="s1", context_type="chat"),
            user_input=UserInputPayload(user_message="hello"),
        )
    )
    assert response == "hello"
    assert sources == [{"type": "memory"}]


@pytest.mark.asyncio
async def test_single_chat_flow_temporary_turn_skips_persistence_and_followups(monkeypatch):
    post_turn = _FakePostTurnService()
    input_service = _FakeInputService()
    sent_messages: list[list[dict]] = []

    async def _capture_call_llm_stream(messages, *_args, **_kwargs):
        sent_messages.append(messages)
        usage = TokenUsage(prompt_tokens=5, completion_tokens=7, total_tokens=12)
        yield {
            "type": "context_info",
            "context_budget": 100,
            "context_window": 128,
            "estimated_prompt_tokens": 4,
            "remaining_tokens": 96,
            "context_truncated": False,
        }
        yield "hello"
        yield {"type": "usage", "usage": usage}

    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: None),
        chat_input_service=input_service,
        post_turn_service=post_turn,
        call_llm_stream=_capture_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt=None,
                assistant_params={},
                all_sources=[{"type": "memory"}],
                max_rounds=None,
                assistant_memory_enabled=True,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = SingleChatFlowService(deps)

    auto_compress_calls: list[dict] = []

    async def _track_auto_compress(**kwargs):
        auto_compress_calls.append(kwargs)
        return kwargs["messages"], None

    monkeypatch.setattr(service, "_maybe_auto_compress", _track_auto_compress)
    monkeypatch.setattr(service, "_resolve_tools", lambda **_kwargs: _return_async((None, None)))

    events = await _collect_events(
        service.process_message_stream(
            request=SingleChatRequestContext(
                scope=ConversationScope(session_id="s1", context_type="chat"),
                user_input=UserInputPayload(user_message="hello"),
                stream=StreamOptions(temporary_turn=True),
            )
        )
    )

    assert events[0] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[1]["type"] == "context_info"
    assert events[2] == "hello"
    assert events[3]["type"] == "usage"
    assert events[4] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert all(
        not (isinstance(event, dict) and event.get("type") == "assistant_message_id")
        for event in events
    )
    assert all(
        not (isinstance(event, dict) and event.get("type") == "followup_questions")
        for event in events
    )
    assert post_turn.finalize_calls == []
    assert post_turn.partial_calls == []
    assert auto_compress_calls == []
    assert len(input_service.calls) == 1
    assert input_service.calls[0]["skip_user_append"] is True
    assert sent_messages
    assert sent_messages[0][-1]["role"] == "user"
    assert sent_messages[0][-1]["content"] == "hello"


async def _return_async(value):
    return value


@pytest.mark.asyncio
async def test_should_prefer_web_tools_when_model_supports_function_calling(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(
            get_session=lambda *args, **kwargs: _return_async(
                {
                    "model_id": "provider:model-a",
                    "param_overrides": {},
                }
            )
        ),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        tool_registry_getter=lambda: SimpleNamespace(is_plugin_loaded=lambda _plugin_id: True),
    )
    service = SingleChatFlowService(deps)

    import src.infrastructure.config.model_config_service as model_config_service

    class _FakeModelService:
        def get_model_and_provider_sync(self, _model_id):
            return SimpleNamespace(), SimpleNamespace()

        def get_merged_capabilities(self, _model_cfg, _provider_cfg):
            return SimpleNamespace(function_calling=True)

    monkeypatch.setattr(model_config_service, "ModelConfigService", _FakeModelService)

    result = await service._should_prefer_web_tools(
        session_id="s1",
        context_type="chat",
        project_id=None,
        use_web_search=True,
    )

    assert result is True


@pytest.mark.asyncio
async def test_resolve_tools_adds_web_tools_when_enabled(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = SingleChatFlowService(deps)

    import src.infrastructure.config.assistant_tool_policy_resolver as assistant_tool_policy_resolver
    import src.infrastructure.config.model_config_service as model_config_service
    import src.infrastructure.projects.project_knowledge_base_resolver as project_knowledge_base_resolver
    import src.infrastructure.projects.project_tool_policy_resolver as project_tool_policy_resolver
    import src.tools.registry as tool_registry

    class _FakeModelService:
        def get_model_and_provider_sync(self, _model_id):
            return SimpleNamespace(), SimpleNamespace()

        def get_merged_capabilities(self, _model_cfg, _provider_cfg):
            return SimpleNamespace(function_calling=True)

    class _FakeKnowledgeResolver:
        async def resolve_effective_kb_ids(self, **_kwargs):
            return []

    class _FakePolicyResolver:
        async def get_allowed_tool_names(self, **kwargs):
            return set(kwargs["candidate_tool_names"])

    class _FakeAssistantPolicyResolver:
        async def get_allowed_tool_names(self, **kwargs):
            return set(kwargs["candidate_tool_names"])

    class _FakeRegistry:
        def get_all_tools(self):
            return [
                SimpleNamespace(name="simple_calculator"),
                SimpleNamespace(name="web_search"),
                SimpleNamespace(name="read_webpage"),
            ]

    monkeypatch.setattr(model_config_service, "ModelConfigService", _FakeModelService)
    monkeypatch.setattr(
        project_knowledge_base_resolver, "ProjectKnowledgeBaseResolver", _FakeKnowledgeResolver
    )
    monkeypatch.setattr(
        project_tool_policy_resolver, "ProjectToolPolicyResolver", _FakePolicyResolver
    )
    monkeypatch.setattr(
        assistant_tool_policy_resolver, "AssistantToolPolicyResolver", _FakeAssistantPolicyResolver
    )
    monkeypatch.setattr(tool_registry, "get_tool_registry", lambda: _FakeRegistry())

    tools, executor = await service._resolve_tools(
        request=ToolResolutionContext(
            assistant_id=None,
            assistant_obj=None,
            model_id="provider:model-a",
            scope=ConversationScope(session_id="s1", context_type="chat"),
            editor=EditorContext(),
            use_web_search=True,
        ),
    )

    assert tools is not None
    assert [tool.name for tool in tools] == [
        "simple_calculator",
        "web_search",
        "read_webpage",
    ]
    assert executor is not None


@pytest.mark.asyncio
async def test_resolve_tools_applies_regex_gate(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        tool_gate_config_service_factory=lambda: SimpleNamespace(
            config=SimpleNamespace(
                enabled=True,
                rules=[
                    SimpleNamespace(
                        id="common_knowledge",
                        enabled=True,
                        priority=10,
                        pattern="常识|定义|是什么",
                        flags="",
                        include_tools=["web_search"],
                        exclude_tools=["execute_python", "execute_javascript"],
                    )
                ],
            )
        ),
    )
    service = SingleChatFlowService(deps)

    import src.infrastructure.config.assistant_tool_policy_resolver as assistant_tool_policy_resolver
    import src.infrastructure.config.model_config_service as model_config_service
    import src.infrastructure.projects.project_knowledge_base_resolver as project_knowledge_base_resolver
    import src.infrastructure.projects.project_tool_policy_resolver as project_tool_policy_resolver
    import src.tools.registry as tool_registry

    class _FakeModelService:
        def get_model_and_provider_sync(self, _model_id):
            return SimpleNamespace(), SimpleNamespace()

        def get_merged_capabilities(self, _model_cfg, _provider_cfg):
            return SimpleNamespace(function_calling=True)

    class _FakeKnowledgeResolver:
        async def resolve_effective_kb_ids(self, **_kwargs):
            return []

    class _FakePolicyResolver:
        async def get_allowed_tool_names(self, **kwargs):
            return set(kwargs["candidate_tool_names"])

    class _FakeAssistantPolicyResolver:
        async def get_allowed_tool_names(self, **kwargs):
            return set(kwargs["candidate_tool_names"])

    class _FakeRegistry:
        def get_all_tools(self):
            return [
                SimpleNamespace(name="execute_python"),
                SimpleNamespace(name="web_search"),
            ]

    monkeypatch.setattr(model_config_service, "ModelConfigService", _FakeModelService)
    monkeypatch.setattr(
        project_knowledge_base_resolver, "ProjectKnowledgeBaseResolver", _FakeKnowledgeResolver
    )
    monkeypatch.setattr(
        project_tool_policy_resolver, "ProjectToolPolicyResolver", _FakePolicyResolver
    )
    monkeypatch.setattr(
        assistant_tool_policy_resolver, "AssistantToolPolicyResolver", _FakeAssistantPolicyResolver
    )
    monkeypatch.setattr(tool_registry, "get_tool_registry", lambda: _FakeRegistry())

    tools, _executor = await service._resolve_tools(
        request=ToolResolutionContext(
            assistant_id=None,
            assistant_obj=None,
            model_id="provider:model-a",
            scope=ConversationScope(session_id="s1", context_type="chat"),
            editor=EditorContext(),
            use_web_search=True,
            user_message="这是常识题，定义是什么？",
        ),
    )

    assert tools is not None
    assert [tool.name for tool in tools] == ["web_search"]


@pytest.mark.asyncio
async def test_resolve_tools_applies_description_overrides(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        tool_description_config_service_factory=lambda: SimpleNamespace(
            get_effective_description_map=lambda: {"execute_python": "custom python guidance"}
        ),
    )
    service = SingleChatFlowService(deps)

    import src.infrastructure.config.assistant_tool_policy_resolver as assistant_tool_policy_resolver
    import src.infrastructure.config.model_config_service as model_config_service
    import src.infrastructure.projects.project_knowledge_base_resolver as project_knowledge_base_resolver
    import src.infrastructure.projects.project_tool_policy_resolver as project_tool_policy_resolver
    import src.tools.registry as tool_registry

    class _FakeModelService:
        def get_model_and_provider_sync(self, _model_id):
            return SimpleNamespace(), SimpleNamespace()

        def get_merged_capabilities(self, _model_cfg, _provider_cfg):
            return SimpleNamespace(function_calling=True)

    class _FakeKnowledgeResolver:
        async def resolve_effective_kb_ids(self, **_kwargs):
            return []

    class _FakePolicyResolver:
        async def get_allowed_tool_names(self, **kwargs):
            return set(kwargs["candidate_tool_names"])

    class _FakeAssistantPolicyResolver:
        async def get_allowed_tool_names(self, **kwargs):
            return set(kwargs["candidate_tool_names"])

    class _FakeTool:
        def __init__(self, name: str, description: str):
            self.name = name
            self.description = description

        def model_copy(self, update):
            return _FakeTool(
                name=self.name, description=update.get("description", self.description)
            )

    class _FakeRegistry:
        def get_all_tools(self):
            return [_FakeTool(name="execute_python", description="old description")]

    monkeypatch.setattr(model_config_service, "ModelConfigService", _FakeModelService)
    monkeypatch.setattr(
        project_knowledge_base_resolver, "ProjectKnowledgeBaseResolver", _FakeKnowledgeResolver
    )
    monkeypatch.setattr(
        project_tool_policy_resolver, "ProjectToolPolicyResolver", _FakePolicyResolver
    )
    monkeypatch.setattr(
        assistant_tool_policy_resolver, "AssistantToolPolicyResolver", _FakeAssistantPolicyResolver
    )
    monkeypatch.setattr(tool_registry, "get_tool_registry", lambda: _FakeRegistry())

    tools, _executor = await service._resolve_tools(
        request=ToolResolutionContext(
            assistant_id=None,
            assistant_obj=None,
            model_id="provider:model-a",
            scope=ConversationScope(session_id="s1", context_type="chat"),
            editor=EditorContext(),
            use_web_search=False,
        ),
    )

    assert tools is not None
    assert tools[0].description == "custom python guidance"


@pytest.mark.asyncio
async def test_prepare_runtime_strips_preloaded_web_context_when_preferring_tools(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt="base\n\nweb\n\nsearch\n\nrag",
                assistant_params={},
                all_sources=[
                    {"type": "memory", "title": "memory"},
                    {"type": "webpage", "title": "webpage"},
                    {"type": "search", "title": "search"},
                    {"type": "rag", "title": "rag"},
                ],
                max_rounds=None,
                assistant_memory_enabled=True,
                base_system_prompt="base",
                memory_context="memory",
                webpage_context="web",
                search_context="search",
                rag_context="rag",
                structured_source_context="structured",
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = SingleChatFlowService(deps)

    monkeypatch.setattr(
        service, "_maybe_auto_compress", lambda **kwargs: _return_async((kwargs["messages"], None))
    )
    monkeypatch.setattr(service, "_should_prefer_web_tools", lambda **_kwargs: _return_async(True))

    runtime = await service._prepare_runtime(
        request=SingleChatRequestContext(
            scope=ConversationScope(session_id="s1", context_type="chat"),
            user_input=UserInputPayload(user_message="hello"),
            search=SearchOptions(use_web_search=True),
        )
    )

    assert runtime.system_prompt == "base\n\nmemory\n\nrag\n\nstructured"
    assert runtime.context_segments["webpage_context"] is None
    assert runtime.context_segments["search_context"] is None
    assert runtime.all_sources == [
        {"type": "memory", "title": "memory"},
        {"type": "rag", "title": "rag"},
    ]


@pytest.mark.asyncio
async def test_single_chat_flow_streams_tool_events_from_runtime(monkeypatch):
    post_turn = _FakePostTurnService()
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: None),
        chat_input_service=_FakeInputService(),
        post_turn_service=post_turn,
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt=None,
                assistant_params={},
                all_sources=[{"type": "memory"}],
                max_rounds=None,
                assistant_memory_enabled=True,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(
        service,
        "_maybe_auto_compress",
        lambda **kwargs: _return_async((kwargs["messages"], None)),
    )
    monkeypatch.setattr(
        service,
        "_resolve_tools",
        lambda **_kwargs: _return_async(([SimpleNamespace(name="web_search")], None)),
    )

    async def _fake_stream(*_args, **_kwargs):
        yield {
            "type": "context_info",
            "context_budget": 100,
            "context_window": 128,
            "estimated_prompt_tokens": 4,
            "remaining_tokens": 96,
            "context_truncated": False,
        }
        yield {
            "type": "tool_calls",
            "calls": [{"id": "call-1", "name": "web_search", "args": {"query": "hello"}}],
        }
        yield {
            "type": "tool_results",
            "results": [{"name": "web_search", "result": "{}", "tool_call_id": "call-1"}],
        }
        yield "round-1"
        yield "round-2"

    service._single_direct_orchestrator.call_llm_stream = _fake_stream

    events = await _collect_events(
        service.process_message_stream(
            request=SingleChatRequestContext(
                scope=ConversationScope(session_id="s1", context_type="chat"),
                user_input=UserInputPayload(user_message="hello"),
            )
        )
    )

    assert {
        "type": "context_info",
        "context_budget": 100,
        "context_window": 128,
        "estimated_prompt_tokens": 4,
        "remaining_tokens": 96,
        "context_truncated": False,
    } in events
    assert "round-1" in events and "round-2" in events
    assert any(isinstance(event, dict) and event.get("type") == "tool_calls" for event in events)
    assert any(isinstance(event, dict) and event.get("type") == "tool_results" for event in events)
    assert events[-2] == {"type": "assistant_message_id", "message_id": "assistant-msg-1"}
    assert events[-1] == {"type": "followup_questions", "questions": ["next question"]}


@pytest.mark.asyncio
async def test_single_chat_flow_uses_base_system_prompt(monkeypatch):
    post_turn = _FakePostTurnService()
    captured_system_prompts: list[str | None] = []

    class _CaptureOrchestrator:
        async def stream(self, request):
            captured_system_prompts.append(request.settings.system_prompt)
            yield {"type": "assistant_chunk", "chunk": "ok"}

    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: None),
        chat_input_service=_FakeInputService(),
        post_turn_service=post_turn,
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt="base prompt",
                assistant_params={},
                all_sources=[],
                max_rounds=None,
                assistant_memory_enabled=True,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
        single_direct_orchestrator=cast(SingleDirectOrchestrator, _CaptureOrchestrator()),
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(
        service,
        "_maybe_auto_compress",
        lambda **kwargs: _return_async((kwargs["messages"], None)),
    )
    monkeypatch.setattr(
        service,
        "_resolve_tools",
        lambda **_kwargs: _return_async((None, None)),
    )

    events = await _collect_events(
        service.process_message_stream(
            request=SingleChatRequestContext(
                scope=ConversationScope(session_id="s1", context_type="chat"),
                user_input=UserInputPayload(user_message="hello"),
            )
        )
    )

    assert any(isinstance(item, str) and item == "ok" for item in events)
    assert captured_system_prompts
    assert captured_system_prompts[0] == "base prompt"


@pytest.mark.asyncio
async def test_single_chat_flow_cancellation_saves_partial_response(monkeypatch):
    post_turn = _FakePostTurnService()

    class _CancelledOrchestrator:
        async def stream(self, *_args, **_kwargs):
            yield {"type": "assistant_chunk", "chunk": "partial"}
            raise asyncio.CancelledError

    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: None),
        chat_input_service=_FakeInputService(),
        post_turn_service=post_turn,
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt=None,
                assistant_params={},
                all_sources=[],
                max_rounds=None,
                assistant_memory_enabled=True,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
        single_direct_orchestrator=cast(SingleDirectOrchestrator, _CancelledOrchestrator()),
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(
        service,
        "_maybe_auto_compress",
        lambda **kwargs: _return_async((kwargs["messages"], None)),
    )
    monkeypatch.setattr(service, "_resolve_tools", lambda **_kwargs: _return_async((None, None)))

    with pytest.raises(BaseException) as exc:
        _ = await _collect_events(
            service.process_message_stream(
                request=SingleChatRequestContext(
                    scope=ConversationScope(session_id="s1", context_type="chat"),
                    user_input=UserInputPayload(user_message="hello"),
                )
            )
        )
    assert exc.type.__name__ == "CancelledError"
    assert len(post_turn.partial_calls) == 1
    assert post_turn.partial_calls[0]["assistant_message"] == "partial"


@pytest.mark.asyncio
async def test_single_chat_flow_merges_tool_diagnostics_before_finalize(monkeypatch):
    post_turn = _FakePostTurnService()
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: None),
        chat_input_service=_FakeInputService(),
        post_turn_service=post_turn,
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(
            ContextPayload(
                messages=[{"role": "user", "content": "hello"}],
                assistant_id="assistant-1",
                assistant_obj=None,
                model_id="provider:model-a",
                system_prompt=None,
                assistant_params={},
                all_sources=[{"type": "rag_diagnostics", "title": "RAG", "snippet": "base"}],
                max_rounds=None,
                assistant_memory_enabled=True,
            )
        ),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(
        service,
        "_maybe_auto_compress",
        lambda **kwargs: _return_async((kwargs["messages"], None)),
    )
    monkeypatch.setattr(service, "_resolve_tools", lambda **_kwargs: _return_async((None, None)))

    async def _fake_stream(*_args, **_kwargs):
        yield {"type": "tool_diagnostics", "tool_search_count": 1, "tool_finalize_reason": "done"}
        yield "hello"

    service._single_direct_orchestrator.call_llm_stream = _fake_stream

    events = await _collect_events(
        service.process_message_stream(
            request=SingleChatRequestContext(
                scope=ConversationScope(session_id="s1", context_type="chat"),
                user_input=UserInputPayload(user_message="hello"),
            )
        )
    )

    assert any(isinstance(item, str) and item == "hello" for item in events)
    saved_sources = post_turn.finalize_calls[0]["sources"]
    assert saved_sources[0]["type"] == "rag_diagnostics"
    assert saved_sources[0]["tool_search_count"] == 1
    assert "tool s:1" in saved_sources[0]["snippet"]


@pytest.mark.asyncio
async def test_maybe_auto_compress_returns_original_when_disabled():
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        compression_config_service_factory=lambda: SimpleNamespace(
            config=SimpleNamespace(auto_compress_enabled=False, auto_compress_threshold=0.7)
        ),
    )
    service = SingleChatFlowService(deps)

    messages = [{"role": "user", "content": "hello"}]
    result_messages, event = await service._maybe_auto_compress(
        session_id="s1",
        model_id="provider:model-a",
        messages=messages,
        context_type="chat",
        project_id=None,
    )
    assert result_messages == messages
    assert event is None


@pytest.mark.asyncio
async def test_maybe_auto_compress_returns_compressed_messages(monkeypatch):
    class _Storage:
        async def get_session(self, *_args, **_kwargs):
            return {"state": {"messages": [{"role": "assistant", "content": "compressed"}]}}

    class _ModelService:
        def get_model_and_provider_sync(self, _model_id):
            return (
                SimpleNamespace(capabilities=SimpleNamespace(context_length=1000)),
                SimpleNamespace(default_capabilities=SimpleNamespace(context_length=1000)),
            )

    class _CompressionService:
        async def compress_context(self, **_kwargs):
            return ("compress-msg-1", 4)

    deps = SingleChatFlowDeps(
        storage=_Storage(),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        model_service_factory=_ModelService,
        compression_config_service_factory=lambda: SimpleNamespace(
            config=SimpleNamespace(auto_compress_enabled=True, auto_compress_threshold=0.5)
        ),
        compression_service_factory=lambda _storage: _CompressionService(),
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(
        "src.application.chat.single_chat_flow_service.estimate_total_tokens",
        lambda _messages: 900,
    )

    messages, event = await service._maybe_auto_compress(
        session_id="s1",
        model_id="provider:model-a",
        messages=[{"role": "user", "content": "hello"}],
        context_type="chat",
        project_id=None,
    )
    assert messages == [{"role": "assistant", "content": "compressed"}]
    assert event == {
        "type": "auto_compressed",
        "compressed_count": 4,
        "message_id": "compress-msg-1",
    }


@pytest.mark.asyncio
async def test_resolve_tools_handles_resolution_exception(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        tool_registry_getter=lambda: (_ for _ in ()).throw(RuntimeError("registry failed")),
    )
    service = SingleChatFlowService(deps)
    monkeypatch.setattr(service, "_supports_function_calling", lambda _model_id: True)

    tools, executor = await service._resolve_tools(
        request=ToolResolutionContext(
            assistant_id=None,
            assistant_obj=None,
            model_id="provider:model-a",
            scope=ConversationScope(session_id="s1", context_type="chat"),
            editor=EditorContext(),
            use_web_search=False,
        ),
    )
    assert tools is None
    assert executor is None


@pytest.mark.asyncio
async def test_combined_tool_executor_blocks_and_falls_back():
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
    )
    service = SingleChatFlowService(deps)

    async def _async_executor(_name, _args):
        return "async-result"

    async def _broken_executor(_name, _args):
        raise RuntimeError("boom")

    blocked_request = ToolResolutionContext(
        assistant_id=None,
        assistant_obj=None,
        model_id="provider:model-a",
        scope=ConversationScope(session_id="s1", context_type="project", project_id="p1"),
        editor=EditorContext(),
        use_web_search=False,
    )
    resolved_tools = SingleChatResolvedTools(
        allowed_tool_names={"allowed_tool"},
        tool_executors=[_broken_executor, _async_executor],
    )
    blocked_executor = service._build_combined_tool_executor(
        request=blocked_request,
        resolved_tools=resolved_tools,
    )
    blocked_result = await blocked_executor("not_allowed", {})
    assert blocked_result == "Error: Tool 'not_allowed' is disabled for this project or assistant"

    allowed_result = await blocked_executor("allowed_tool", {})
    assert allowed_result == "async-result"


@pytest.mark.asyncio
async def test_execute_python_falls_back_to_server_execution_when_enabled(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        code_execution_config_service_factory=lambda: SimpleNamespace(
            config=SimpleNamespace(
                enable_client_tool_execution=True,
                enable_server_jupyter_execution=True,
                enable_server_subprocess_execution=True,
                execution_priority=["client", "server_jupyter", "server_subprocess"],
                jupyter_kernel_name="python3",
            )
        ),
    )
    service = SingleChatFlowService(deps)

    class _TimeoutCoordinator:
        async def await_result(
            self, *, session_id: str, tool_call_id: str, timeout_s: float
        ) -> str:
            _ = session_id
            _ = tool_call_id
            _ = timeout_s
            raise asyncio.TimeoutError

    async def _fake_server_exec(
        *,
        code: str,
        timeout_ms: int,
        backend: str,
        jupyter_kernel_name: str,
    ) -> str:
        assert code == "print('hi')\n1+1"
        assert timeout_ms == 30000
        assert backend == "jupyter"
        assert jupyter_kernel_name == "python3"
        return '{"ok": true, "stdout": "hi\\n", "stderr": "", "value": "2"}'

    monkeypatch.setattr(
        "src.application.chat.single_chat_flow_service.get_client_tool_call_coordinator",
        lambda: _TimeoutCoordinator(),
    )
    monkeypatch.setattr(
        "src.application.chat.single_chat_flow_service.execute_python_server_side_with_backend",
        _fake_server_exec,
    )

    executor = service._build_combined_tool_executor(
        request=ToolResolutionContext(
            assistant_id=None,
            assistant_obj=None,
            model_id="provider:model-a",
            scope=ConversationScope(session_id="s1", context_type="chat"),
            editor=EditorContext(),
            use_web_search=False,
        ),
        resolved_tools=SingleChatResolvedTools(
            llm_tools=[],
            tool_executors=[],
            allowed_tool_names={"execute_python"},
        ),
    )

    result = await executor(
        "execute_python",
        {"code": "print('hi')\n1+1", "timeout_ms": 30000},
        tool_call_id="call-1",
    )
    assert result == '{"ok": true, "stdout": "hi\\n", "stderr": "", "value": "2"}'


@pytest.mark.asyncio
async def test_execute_python_uses_priority_when_client_disabled(monkeypatch):
    deps = SingleChatFlowDeps(
        storage=SimpleNamespace(get_session=lambda *args, **kwargs: _return_async(None)),
        chat_input_service=_FakeInputService(),
        post_turn_service=_FakePostTurnService(),
        call_llm_stream=_fake_call_llm_stream,
        pricing_service=_FakePricingService(),
        file_service=None,
        prepare_context=lambda **_kwargs: _return_async(None),
        build_file_context_block=lambda _refs: _return_async(""),
        code_execution_config_service_factory=lambda: SimpleNamespace(
            config=SimpleNamespace(
                enable_client_tool_execution=False,
                enable_server_jupyter_execution=False,
                enable_server_subprocess_execution=True,
                execution_priority=["client", "server_jupyter", "server_subprocess"],
                jupyter_kernel_name="python3",
            )
        ),
    )
    service = SingleChatFlowService(deps)

    class _CoordinatorMustNotBeCalled:
        async def await_result(
            self, *, session_id: str, tool_call_id: str, timeout_s: float
        ) -> str:
            _ = session_id
            _ = tool_call_id
            _ = timeout_s
            raise AssertionError("client method should not be used when disabled")

    async def _fake_server_exec(
        *,
        code: str,
        timeout_ms: int,
        backend: str,
        jupyter_kernel_name: str,
    ) -> str:
        assert code == "print('ok')"
        assert timeout_ms == 5000
        assert backend == "subprocess"
        assert jupyter_kernel_name == "python3"
        return '{"ok": true, "stdout": "ok\\n", "stderr": "", "value": ""}'

    monkeypatch.setattr(
        "src.application.chat.single_chat_flow_service.get_client_tool_call_coordinator",
        lambda: _CoordinatorMustNotBeCalled(),
    )
    monkeypatch.setattr(
        "src.application.chat.single_chat_flow_service.execute_python_server_side_with_backend",
        _fake_server_exec,
    )

    executor = service._build_combined_tool_executor(
        request=ToolResolutionContext(
            assistant_id=None,
            assistant_obj=None,
            model_id="provider:model-a",
            scope=ConversationScope(session_id="s1", context_type="chat"),
            editor=EditorContext(),
            use_web_search=False,
        ),
        resolved_tools=SingleChatResolvedTools(
            llm_tools=[],
            tool_executors=[],
            allowed_tool_names={"execute_python"},
        ),
    )

    result = await executor(
        "execute_python",
        {"code": "print('ok')", "timeout_ms": 5000},
        tool_call_id="",
    )
    assert result == '{"ok": true, "stdout": "ok\\n", "stderr": "", "value": ""}'
