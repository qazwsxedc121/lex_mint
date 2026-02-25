"""Compare-chat streaming flow orchestration extracted from AgentService."""

from __future__ import annotations

from dataclasses import dataclass
from typing import AsyncIterator, Awaitable, Callable, Dict, List, Optional, Protocol

from src.providers.types import CostInfo, TokenUsage

from .chat_input_service import PreparedUserInput
from .orchestration import CompareModelsSettings, OrchestrationRequest
from .service_contracts import (
    ContextPayload,
    SourcePayload,
    StreamEvent,
)


class _StorageLike(Protocol):
    async def append_message(
        self,
        session_id: str,
        role: str,
        content: str,
        attachments: Optional[List[SourcePayload]] = None,
        usage: Optional[TokenUsage] = None,
        cost: Optional[CostInfo] = None,
        sources: Optional[List[SourcePayload]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        assistant_id: Optional[str] = None,
    ) -> str: ...


class _ComparisonStorageLike(Protocol):
    async def save(
        self,
        session_id: str,
        assistant_message_id: str,
        responses: List[SourcePayload],
        context_type: str = "chat",
        project_id: Optional[str] = None,
    ) -> None: ...


class _ChatInputServiceLike(Protocol):
    async def prepare_user_input(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        expanded_user_message: str,
        attachments: Optional[List[SourcePayload]],
        skip_user_append: bool,
        context_type: str,
        project_id: Optional[str],
    ) -> PreparedUserInput: ...


class _CompareModelsOrchestratorLike(Protocol):
    def stream(self, request: OrchestrationRequest, /) -> AsyncIterator[StreamEvent]: ...


@dataclass(frozen=True)
class CompareFlowDeps:
    """Dependencies required by compare stream flow."""

    storage: _StorageLike
    comparison_storage: _ComparisonStorageLike
    chat_input_service: _ChatInputServiceLike
    compare_models_orchestrator: _CompareModelsOrchestratorLike
    prepare_context: Callable[..., Awaitable[ContextPayload]]
    build_file_context_block: Callable[[Optional[List[Dict[str, str]]]], Awaitable[str]]


class CompareFlowService:
    """Runs compare-model flow and keeps API-compatible event/persistence behavior."""

    def __init__(self, deps: CompareFlowDeps):
        self.deps = deps

    async def process_compare_stream(
        self,
        *,
        session_id: str,
        user_message: str,
        model_ids: List[str],
        reasoning_effort: Optional[str] = None,
        attachments: Optional[List[SourcePayload]] = None,
        context_type: str = "chat",
        project_id: Optional[str] = None,
        use_web_search: bool = False,
        search_query: Optional[str] = None,
        file_references: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[StreamEvent]:
        """Stream compare responses and persist both canonical and comparison results."""
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
            use_web_search=use_web_search,
            search_query=search_query,
        )
        if ctx.all_sources:
            yield {"type": "sources", "sources": ctx.all_sources}

        compare_request = OrchestrationRequest(
            session_id=session_id,
            mode="compare_models",
            user_message=prepared_input.raw_user_message,
            participants=model_ids,
            assistant_name_map={},
            assistant_config_map={},
            settings=CompareModelsSettings(
                messages=ctx.messages,
                model_ids=model_ids,
                system_prompt=ctx.system_prompt,
                max_rounds=ctx.max_rounds,
                assistant_params=ctx.assistant_params,
                reasoning_effort=reasoning_effort,
            ),
            reasoning_effort=reasoning_effort,
            context_type=context_type,
            project_id=project_id,
        )

        model_results: Dict[str, SourcePayload] = {}
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
        model_ids: List[str],
        model_results: Dict[str, SourcePayload],
        all_sources: List[SourcePayload],
        context_type: str,
        project_id: Optional[str],
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

