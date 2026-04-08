"""Compare-chat streaming flow orchestration."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from src.application.chat.chat_input_service import PreparedUserInput
from src.application.chat.chat_runtime import CompareModelsSettings
from src.application.chat.request_contexts import CompareChatRequestContext
from src.application.chat.service_contracts import (
    ContextPayload,
    SourcePayload,
    StreamEvent,
)
from src.providers.types import CostInfo, TokenUsage

if TYPE_CHECKING:
    from src.application.chat.chat_runtime import ChatOrchestrationRequest


class _StorageLike(Protocol):
    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        attachments: list[SourcePayload] | None = None,
        usage: TokenUsage | None = None,
        cost: CostInfo | None = None,
        sources: list[SourcePayload] | None = None,
        context_type: str = "chat",
        project_id: str | None = None,
        assistant_id: str | None = None,
    ) -> str: ...


class _ComparisonStorageLike(Protocol):
    async def save(
        self,
        session_id: str,
        assistant_message_id: str,
        responses: list[SourcePayload],
        context_type: str = "chat",
        project_id: str | None = None,
    ) -> None: ...


class _ChatInputServiceLike(Protocol):
    async def prepare_user_input(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        expanded_user_message: str,
        attachments: list[SourcePayload] | None,
        skip_user_append: bool,
        context_type: str,
        project_id: str | None,
    ) -> PreparedUserInput: ...


class _CompareModelsOrchestratorLike(Protocol):
    def stream(self, request: ChatOrchestrationRequest, /) -> AsyncIterator[StreamEvent]: ...


@dataclass(frozen=True)
class CompareFlowDeps:
    """Dependencies required by compare stream flow."""

    storage: _StorageLike
    comparison_storage: _ComparisonStorageLike
    chat_input_service: _ChatInputServiceLike
    compare_models_orchestrator: _CompareModelsOrchestratorLike
    prepare_context: Callable[..., Awaitable[ContextPayload]]
    build_file_context_block: Callable[[list[dict[str, str]] | None], Awaitable[str]]


class CompareFlowService:
    """Runs compare-model flow and keeps API-compatible event/persistence behavior."""

    def __init__(self, deps: CompareFlowDeps):
        self.deps = deps

    async def process_compare_stream(
        self,
        *,
        request: CompareChatRequestContext,
    ) -> AsyncIterator[StreamEvent]:
        """Stream compare responses and persist both canonical and comparison results."""
        session_id = request.scope.session_id
        context_type = request.scope.context_type
        project_id = request.scope.project_id
        user_message = request.user_input.user_message
        attachments = request.user_input.attachments
        file_references = request.user_input.file_references
        model_ids = request.model_ids
        context_capabilities = request.context_capabilities.context_capabilities
        context_capability_args = request.context_capabilities.context_capability_args
        reasoning_effort = request.stream.reasoning_effort

        original_user_message = user_message
        file_context_block = await self.deps.build_file_context_block(file_references)
        if file_context_block:
            user_message = f"{file_context_block}\n\n{user_message}"

        prepared_input = await self.deps.chat_input_service.prepare_user_input(
            session_id=session_id,
            raw_user_message=original_user_message,
            expanded_user_message=user_message,
            attachments=attachments,
            skip_user_append=False,
            context_type=context_type,
            project_id=project_id,
        )
        yield {"type": "user_message_id", "message_id": prepared_input.user_message_id}

        ctx = await self.deps.prepare_context(
            session_id=session_id,
            raw_user_message=prepared_input.raw_user_message,
            context_type=context_type,
            project_id=project_id,
            context_capabilities=context_capabilities,
            context_capability_args=context_capability_args,
        )
        if ctx.all_sources:
            yield {"type": "sources", "sources": ctx.all_sources}

        compare_request = request.to_orchestration_request(
            settings=CompareModelsSettings(
                messages=ctx.messages,
                model_ids=model_ids,
                system_prompt=ctx.system_prompt,
                max_rounds=ctx.max_rounds,
                context_segments={
                    "base_system_prompt": ctx.base_system_prompt,
                    "memory_context": ctx.memory_context,
                    "webpage_context": ctx.webpage_context,
                    "search_context": ctx.search_context,
                    "rag_context": ctx.rag_context,
                    "structured_source_context": ctx.structured_source_context,
                },
                assistant_params=ctx.assistant_params,
                reasoning_effort=reasoning_effort,
            ),
            user_message=prepared_input.raw_user_message,
        )

        model_results: dict[str, SourcePayload] = {}
        async for event in self.deps.compare_models_orchestrator.stream(compare_request):
            event_type = event.get("type")
            if event_type == "compare_complete":
                model_results = event.get("model_results", {}) or {}
                continue
            yield event

        assistant_message_id = await self._persist_compare_results(
            session_id=session_id,
            model_ids=model_ids,
            model_results=model_results,
            all_sources=ctx.all_sources,
            context_type=context_type,
            project_id=project_id,
        )
        yield {"type": "assistant_message_id", "message_id": assistant_message_id}

    async def _persist_compare_results(
        self,
        *,
        session_id: str,
        model_ids: list[str],
        model_results: dict[str, SourcePayload],
        all_sources: list[SourcePayload],
        context_type: str,
        project_id: str | None,
    ) -> str:
        """Persist canonical assistant message plus all compare responses."""
        first_model_id = model_ids[0]
        first_result = model_results.get(first_model_id, {})
        first_content = first_result.get("content", "")
        first_usage = TokenUsage(**first_result["usage"]) if first_result.get("usage") else None
        first_cost = CostInfo(**first_result["cost"]) if first_result.get("cost") else None

        assistant_message_id = await self.deps.storage.append_message(
            session_id,
            "assistant",
            first_content,
            usage=first_usage,
            cost=first_cost,
            sources=all_sources if all_sources else None,
            context_type=context_type,
            project_id=project_id,
        )
        responses_list = [model_results[mid] for mid in model_ids if mid in model_results]
        await self.deps.comparison_storage.save(
            session_id,
            assistant_message_id,
            responses_list,
            context_type=context_type,
            project_id=project_id,
        )
        return assistant_message_id
