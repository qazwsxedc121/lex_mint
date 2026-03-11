"""Unit tests for single-chat flow service extraction."""

from types import SimpleNamespace

import pytest

from src.application.chat.chat_input_service import PreparedUserInput
from src.application.chat.service_contracts import ContextPayload
from src.application.chat.single_chat_flow_service import (
    SingleChatFlowDeps,
    SingleChatFlowService,
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
    yield "hello"
    yield {"type": "usage", "usage": usage}


class _FakePostTurnService:
    def __init__(self):
        self.finalize_calls = []

    async def save_partial_assistant_message(self, **_kwargs):
        return None

    async def finalize_single_turn(self, **kwargs):
        self.finalize_calls.append(kwargs)
        return "assistant-msg-1"

    async def generate_followup_questions(self, **_kwargs):
        return ["next question"]


class _FakeInputService:
    async def prepare_user_input(self, **_kwargs):
        return PreparedUserInput(
            raw_user_message="hello",
            full_message_content="hello",
            attachment_metadata=[],
            user_message_id="user-msg-1",
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
                is_legacy_assistant=False,
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
            session_id="s1",
            user_message="hello",
            context_type="chat",
            project_id=None,
        )
    )

    assert events[0] == {"type": "user_message_id", "message_id": "user-msg-1"}
    assert events[1] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[2] == "hello"
    assert events[3]["type"] == "usage"
    assert events[4] == {"type": "sources", "sources": [{"type": "memory"}]}
    assert events[5] == {"type": "assistant_message_id", "message_id": "assistant-msg-1"}
    assert events[6] == {"type": "followup_questions", "questions": ["next question"]}
    assert len(post_turn.finalize_calls) == 1
    assert post_turn.finalize_calls[0]["assistant_message"] == "hello"

    response, sources = await service.process_message(
        session_id="s1",
        user_message="hello",
        context_type="chat",
        project_id=None,
    )
    assert response == "hello"
    assert sources == [{"type": "memory"}]


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

    import src.infrastructure.config.model_config_service as model_config_service
    import src.infrastructure.projects.project_knowledge_base_resolver as project_knowledge_base_resolver
    import src.infrastructure.projects.project_tool_policy_resolver as project_tool_policy_resolver
    import src.infrastructure.web.web_tool_service as web_tool_service
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

    class _FakeWebToolService:
        def get_tools(self):
            return [SimpleNamespace(name="web_search"), SimpleNamespace(name="read_webpage")]

        async def execute_tool(self, _name, _args):
            return None

    class _FakeRegistry:
        def get_all_tools(self):
            return [SimpleNamespace(name="simple_calculator")]

    monkeypatch.setattr(model_config_service, "ModelConfigService", _FakeModelService)
    monkeypatch.setattr(project_knowledge_base_resolver, "ProjectKnowledgeBaseResolver", _FakeKnowledgeResolver)
    monkeypatch.setattr(project_tool_policy_resolver, "ProjectToolPolicyResolver", _FakePolicyResolver)
    monkeypatch.setattr(web_tool_service, "WebToolService", _FakeWebToolService)
    monkeypatch.setattr(tool_registry, "get_tool_registry", lambda: _FakeRegistry())

    tools, executor = await service._resolve_tools(
        assistant_id=None,
        assistant_obj=None,
        model_id="provider:model-a",
        is_legacy_assistant=False,
        context_type="chat",
        project_id=None,
        session_id="s1",
        active_file_path=None,
        active_file_hash=None,
        use_web_search=True,
    )

    assert [tool.name for tool in tools] == [
        "simple_calculator",
        "web_search",
        "read_webpage",
    ]
    assert executor is not None


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
                is_legacy_assistant=False,
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

    monkeypatch.setattr(service, "_maybe_auto_compress", lambda **kwargs: _return_async((kwargs["messages"], None)))
    monkeypatch.setattr(service, "_should_prefer_web_tools", lambda **_kwargs: _return_async(True))

    runtime = await service._prepare_runtime(
        session_id="s1",
        user_message="hello",
        skip_user_append=False,
        attachments=None,
        context_type="chat",
        project_id=None,
        use_web_search=True,
        search_query=None,
        file_references=None,
        active_file_path=None,
        active_file_hash=None,
    )

    assert runtime.system_prompt == "base\n\nmemory\n\nrag\n\nstructured"
    assert runtime.context_segments["webpage_context"] is None
    assert runtime.context_segments["search_context"] is None
    assert runtime.all_sources == [
        {"type": "memory", "title": "memory"},
        {"type": "rag", "title": "rag"},
    ]
