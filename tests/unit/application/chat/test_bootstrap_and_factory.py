"""Tests for chat bootstrap wiring and small factory helpers."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from src.application.chat import bootstrap, factory


def test_factory_builders_only_pass_non_none_optional_dependencies(monkeypatch):
    captured: dict[str, Any] = {}
    monkeypatch.setattr(
        factory,
        "ChatApplicationService",
        lambda deps: captured.setdefault("chat", deps) or SimpleNamespace(),
    )

    single = factory.build_single_chat_flow_service(
        storage="storage",
        chat_input_service="chat_input",
        post_turn_service="post_turn",
        call_llm_stream="call_llm_stream",
        pricing_service="pricing",
        file_service="files",
        prepare_context="prepare",
        build_file_context_block="file_block",
        model_service_factory="model_factory",
    )
    assert single.deps.model_service_factory == "model_factory"
    assert callable(single.deps.compression_service_factory)

    compare = factory.build_compare_flow_service(
        storage="storage",
        comparison_storage="comparison_storage",
        chat_input_service="chat_input",
        compare_models_orchestrator="orchestrator",
        prepare_context="prepare",
        build_file_context_block="file_block",
    )
    assert compare.deps.comparison_storage == "comparison_storage"

    _ = factory.build_chat_application_service(
        storage="storage",
        single_chat_flow_service="single",
        compare_flow_service="compare",
        group_chat_service="group",
        session_command_service=None,
    )
    chat_deps = captured["chat"]
    assert chat_deps.single_chat_flow_service == "single"
    assert chat_deps.group_chat_service == "group"


def test_bootstrap_helpers_and_builder(monkeypatch):
    records: dict[str, Any] = {}

    monkeypatch.setenv("LEX_MINT_GROUP_TRACE", "true")
    assert bootstrap._is_group_trace_enabled() is True
    monkeypatch.setenv("LEX_MINT_GROUP_TRACE", "off")
    assert bootstrap._is_group_trace_enabled() is False

    messages: list[str] = []

    def _capture_info(message, *args, **kwargs):
        _ = kwargs
        messages.append(message % args if args else message)

    monkeypatch.setattr(bootstrap.logger, "info", _capture_info)
    monkeypatch.setenv("LEX_MINT_GROUP_TRACE", "true")
    bootstrap._log_group_trace("trace-1", "stage-1", {"ok": True})
    bootstrap._log_group_trace("trace-1", "stage-1", {"bad": object()})
    assert any("GroupTrace" in message for message in messages)

    class _ModelService:
        def get_model_and_provider_sync(self, model_id: str):
            if model_id == "broken":
                raise RuntimeError("bad model")
            return SimpleNamespace(name="Friendly Name"), None

    monkeypatch.setattr(bootstrap, "ModelConfigService", _ModelService)
    assert bootstrap._resolve_compare_model_name("provider:model") == "Friendly Name"
    assert bootstrap._resolve_compare_model_name("broken") == "broken"

    monkeypatch.setattr(
        bootstrap,
        "settings",
        SimpleNamespace(attachments_dir="/tmp/attachments", max_file_size_mb=8),
    )
    monkeypatch.setattr(bootstrap, "PricingService", lambda: "pricing")
    monkeypatch.setattr(bootstrap, "SearchService", lambda: "search")
    monkeypatch.setattr(bootstrap, "WebpageService", lambda: "webpage")
    monkeypatch.setattr(bootstrap, "MemoryService", lambda: "memory")
    monkeypatch.setattr(bootstrap, "ProjectService", lambda: "project_service")
    monkeypatch.setattr(bootstrap, "FileReferenceConfigService", lambda: "file_ref_config")
    monkeypatch.setattr(
        bootstrap,
        "FileReferenceContextBuilder",
        lambda *args: SimpleNamespace(build_context_block="file_context_block"),
    )
    monkeypatch.setattr(bootstrap, "RagConfigService", lambda: "rag_config")
    monkeypatch.setattr(bootstrap, "SourceContextService", lambda: "source_context")
    monkeypatch.setattr(
        bootstrap, "ComparisonStorage", lambda storage: ("comparison_storage", storage)
    )
    monkeypatch.setattr(
        bootstrap,
        "ChatInputService",
        lambda storage, file_service: ("chat_input", storage, file_service),
    )
    monkeypatch.setattr(
        bootstrap,
        "RagContextBuilderService",
        lambda: SimpleNamespace(build_context_and_sources="rag_context_builder"),
    )
    monkeypatch.setattr(bootstrap, "PostTurnService", lambda **kwargs: ("post_turn", kwargs))
    monkeypatch.setattr(
        bootstrap,
        "ContextAssemblyService",
        lambda **kwargs: SimpleNamespace(prepare_context=("prepare_context", kwargs)),
    )

    class _GroupOrchestrationSupportService:
        def __init__(self, **kwargs):
            records["group_orchestration_support"] = kwargs

        def create_committee_turn_executor(self):
            return SimpleNamespace(
                stream_group_assistant_turn="committee_stream",
                get_message_content_by_id="get_message_content",
            )

        def create_committee_orchestrator(self, **kwargs):
            records["committee_orchestrator"] = kwargs
            return "committee_orchestrator"

        def create_round_robin_orchestrator(self, **kwargs):
            records["round_robin_orchestrator"] = kwargs
            return "round_robin_orchestrator"

    monkeypatch.setattr(
        bootstrap, "GroupOrchestrationSupportService", _GroupOrchestrationSupportService
    )

    class _GroupRuntimeSupportService:
        def build_group_runtime_assistant(self, *args, **kwargs):
            return "runtime_assistant"

        def resolve_group_settings(self, **kwargs):
            return {"settings": kwargs}

    monkeypatch.setattr(bootstrap, "GroupRuntimeSupportService", _GroupRuntimeSupportService)
    monkeypatch.setattr(
        bootstrap, "CommitteePolicy", SimpleNamespace(resolve_committee_round_policy="round_policy")
    )
    monkeypatch.setattr(bootstrap, "call_llm_stream", "call_llm_stream")
    monkeypatch.setattr(bootstrap, "call_llm", "call_llm")
    monkeypatch.setattr(
        bootstrap, "CompareModelsOrchestrator", lambda **kwargs: ("compare_orchestrator", kwargs)
    )
    monkeypatch.setattr(bootstrap, "GroupChatDeps", lambda **kwargs: kwargs)
    monkeypatch.setattr(bootstrap, "GroupChatService", lambda deps: ("group_chat", deps))
    monkeypatch.setattr(
        bootstrap,
        "build_single_chat_flow_service",
        lambda **kwargs: records.setdefault("single_flow", kwargs) or "single_flow",
    )
    monkeypatch.setattr(
        bootstrap,
        "build_compare_flow_service",
        lambda **kwargs: records.setdefault("compare_flow", kwargs) or "compare_flow",
    )
    monkeypatch.setattr(bootstrap, "ChatSessionCommandDeps", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        bootstrap, "ChatSessionCommandService", lambda deps: ("session_command_service", deps)
    )
    monkeypatch.setattr(
        bootstrap,
        "build_chat_application_service",
        lambda **kwargs: (
            records.setdefault("chat_application", kwargs) or SimpleNamespace(**kwargs)
        ),
    )
    monkeypatch.setattr(
        bootstrap,
        "FileService",
        lambda attachments_dir, max_size: ("file_service", attachments_dir, max_size),
    )
    monkeypatch.setattr(bootstrap, "CompressionConfigService", lambda: "compression_config")
    monkeypatch.setattr(
        bootstrap, "CompressionService", lambda *args, **kwargs: "compression_service"
    )
    monkeypatch.setattr(
        bootstrap, "ProjectDocumentToolService", lambda: "project_document_tool_service"
    )
    monkeypatch.setattr(bootstrap, "ProjectKnowledgeBaseResolver", lambda: "project_kb_resolver")
    monkeypatch.setattr(
        bootstrap, "ProjectToolPolicyResolver", lambda: "project_tool_policy_resolver"
    )
    monkeypatch.setattr(bootstrap, "WebToolService", lambda: "web_tool_service")
    monkeypatch.setattr(bootstrap, "get_tool_registry", lambda: "tool_registry")

    _ = bootstrap.build_default_chat_application_service(storage="storage")

    assert records["chat_application"]["single_chat_flow_service"] == records["single_flow"]
    assert records["chat_application"]["compare_flow_service"] == records["compare_flow"]
    assert records["single_flow"]["tool_registry_getter"] is bootstrap.get_tool_registry
    assert (
        records["group_orchestration_support"]["build_rag_context_and_sources"]
        == "rag_context_builder"
    )
