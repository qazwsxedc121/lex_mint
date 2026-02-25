"""Single-turn orchestrator for standard chat streaming."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional, Tuple

from src.providers.types import CostInfo, TokenUsage

from .base import BaseOrchestrator, OrchestrationCancelToken, OrchestrationEvent, OrchestrationRequest


@dataclass(frozen=True)
class SingleTurnSettings:
    """Execution settings for one streaming LLM turn."""

    messages: List[Dict[str, Any]]
    model_id: str
    system_prompt: Optional[str]
    max_rounds: Optional[int]
    assistant_params: Dict[str, Any] = field(default_factory=dict)
    reasoning_effort: Optional[str] = None
    llm_tools: Optional[List[Any]] = None
    tool_executor: Optional[Callable[[str, Dict[str, Any]], Any]] = None


class SingleTurnOrchestrator(BaseOrchestrator):
    """Unified streaming orchestrator for single assistant/model chat."""

    mode = "single_turn"

    def __init__(
        self,
        *,
        call_llm_stream: Callable[..., AsyncIterator[Any]],
        pricing_service: Any,
        file_service: Any,
    ):
        self.call_llm_stream = call_llm_stream
        self.pricing_service = pricing_service
        self.file_service = file_service

    async def stream(
        self,
        request: OrchestrationRequest,
        *,
        cancel_token: Optional[OrchestrationCancelToken] = None,
    ) -> AsyncIterator[OrchestrationEvent]:
        if request.mode and request.mode != self.mode:
            raise ValueError(f"SingleTurnOrchestrator only supports mode={self.mode}")
        if not isinstance(request.settings, SingleTurnSettings):
            raise ValueError("SingleTurnOrchestrator requires SingleTurnSettings")

        settings = request.settings
        full_response = ""
        usage_data: Optional[TokenUsage] = None
        cost_data: Optional[CostInfo] = None
        tool_diagnostics: Optional[Dict[str, Any]] = None

        async for chunk in self.call_llm_stream(
            settings.messages,
            session_id=request.session_id,
            model_id=settings.model_id,
            system_prompt=settings.system_prompt,
            max_rounds=settings.max_rounds,
            reasoning_effort=settings.reasoning_effort,
            file_service=self.file_service,
            tools=settings.llm_tools,
            tool_executor=settings.tool_executor,
            **settings.assistant_params,
        ):
            if self.is_cancelled(cancel_token):
                break

            if isinstance(chunk, dict) and chunk.get("type") == "usage":
                usage_data = chunk["usage"]
                if settings.model_id and usage_data:
                    parts = settings.model_id.split(":", 1)
                    provider_id = parts[0] if len(parts) > 1 else ""
                    simple_model_id = parts[1] if len(parts) > 1 else settings.model_id
                    cost_data = self.pricing_service.calculate_cost(
                        provider_id, simple_model_id, usage_data
                    )
                yield self.normalize_event({
                    "type": "usage",
                    "usage": usage_data,
                    "cost": cost_data,
                })
                continue

            if isinstance(chunk, dict) and chunk.get("type") in (
                "context_info",
                "thinking_duration",
                "tool_calls",
                "tool_results",
            ):
                yield self.normalize_event(dict(chunk))
                continue

            if isinstance(chunk, dict) and chunk.get("type") == "tool_diagnostics":
                tool_diagnostics = dict(chunk)
                continue

            full_response += str(chunk)
            yield self.normalize_event({
                "type": "assistant_chunk",
                "chunk": str(chunk),
            })

        yield self.normalize_event({
            "type": "single_turn_complete",
            "content": full_response,
            "usage": usage_data,
            "cost": cost_data,
            "tool_diagnostics": tool_diagnostics,
        })

    @staticmethod
    def parse_completion_event(event: Dict[str, Any]) -> Tuple[str, Optional[TokenUsage], Optional[CostInfo], Optional[Dict[str, Any]]]:
        """Extract final streaming result from single_turn_complete event."""
        if event.get("type") != "single_turn_complete":
            raise ValueError("event is not single_turn_complete")
        usage = event.get("usage")
        if isinstance(usage, dict):
            usage = TokenUsage(**usage)
        cost = event.get("cost")
        if isinstance(cost, dict):
            cost = CostInfo(**cost)
        return (
            str(event.get("content") or ""),
            usage,
            cost,
            event.get("tool_diagnostics"),
        )
