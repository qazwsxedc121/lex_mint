"""Compare-models orchestrator for multiplexed multi-model streaming."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Callable, Dict, List, Optional

from src.providers.types import TokenUsage

from .base import BaseOrchestrator, OrchestrationCancelToken, OrchestrationEvent, OrchestrationRequest


@dataclass(frozen=True)
class CompareModelsSettings:
    """Settings for one compare-models orchestration run."""

    messages: List[Dict[str, Any]]
    model_ids: List[str]
    system_prompt: Optional[str]
    max_rounds: Optional[int]
    assistant_params: Dict[str, Any] = field(default_factory=dict)
    reasoning_effort: Optional[str] = None


class CompareModelsOrchestrator(BaseOrchestrator):
    """Runs multiple model streams concurrently and multiplexes events."""

    mode = "compare_models"

    def __init__(
        self,
        *,
        call_llm_stream: Callable[..., AsyncIterator[Any]],
        pricing_service: Any,
        file_service: Any,
        resolve_model_name: Optional[Callable[[str], str]] = None,
    ):
        self.call_llm_stream = call_llm_stream
        self.pricing_service = pricing_service
        self.file_service = file_service
        self.resolve_model_name = resolve_model_name

    async def stream(
        self,
        request: OrchestrationRequest,
        *,
        cancel_token: Optional[OrchestrationCancelToken] = None,
    ) -> AsyncIterator[OrchestrationEvent]:
        if request.mode and request.mode != self.mode:
            raise ValueError(f"CompareModelsOrchestrator only supports mode={self.mode}")
        if not isinstance(request.settings, CompareModelsSettings):
            raise ValueError("CompareModelsOrchestrator requires CompareModelsSettings")

        settings = request.settings
        queue: asyncio.Queue = asyncio.Queue()
        tasks: List[asyncio.Task] = []
        model_results: Dict[str, Dict[str, Any]] = {}
        finished = 0

        async def _stream_model(model_id: str) -> None:
            model_name = self._resolve_model_name(model_id)
            full_response = ""
            usage_data: Optional[TokenUsage] = None
            cost_data = None
            try:
                await queue.put(
                    {
                        "kind": "event",
                        "event": {"type": "model_start", "model_id": model_id, "model_name": model_name},
                    }
                )

                async for chunk in self.call_llm_stream(
                    settings.messages,
                    session_id=request.session_id,
                    model_id=model_id,
                    system_prompt=settings.system_prompt,
                    max_rounds=settings.max_rounds,
                    reasoning_effort=settings.reasoning_effort,
                    file_service=self.file_service,
                    **settings.assistant_params,
                ):
                    if isinstance(chunk, dict) and chunk.get("type") == "usage":
                        usage_data = chunk["usage"]
                        parts = model_id.split(":", 1)
                        provider_id = parts[0] if len(parts) > 1 else ""
                        simple_model_id = parts[1] if len(parts) > 1 else model_id
                        cost_data = self.pricing_service.calculate_cost(
                            provider_id, simple_model_id, usage_data
                        )
                        continue

                    if isinstance(chunk, dict):
                        continue

                    text = str(chunk)
                    full_response += text
                    await queue.put(
                        {
                            "kind": "event",
                            "event": {"type": "model_chunk", "model_id": model_id, "chunk": text},
                        }
                    )

                usage_dump = usage_data.model_dump() if usage_data else None
                cost_dump = cost_data.model_dump() if cost_data else None
                await queue.put(
                    {
                        "kind": "event",
                        "event": {
                            "type": "model_done",
                            "model_id": model_id,
                            "model_name": model_name,
                            "content": full_response,
                            "usage": usage_dump,
                            "cost": cost_dump,
                        },
                    }
                )
                model_results[model_id] = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "content": full_response,
                    "usage": usage_dump,
                    "cost": cost_dump,
                    "thinking_content": "",
                    "error": None,
                }
            except Exception as e:
                await queue.put(
                    {
                        "kind": "event",
                        "event": {
                            "type": "model_error",
                            "model_id": model_id,
                            "model_name": model_name,
                            "error": str(e),
                        },
                    }
                )
                model_results[model_id] = {
                    "model_id": model_id,
                    "model_name": model_name,
                    "content": "",
                    "usage": None,
                    "cost": None,
                    "thinking_content": "",
                    "error": str(e),
                }
            finally:
                await queue.put({"kind": "done"})

        for model_id in settings.model_ids:
            tasks.append(asyncio.create_task(_stream_model(model_id)))

        try:
            while finished < len(tasks):
                if self.is_cancelled(cancel_token):
                    break
                item = await queue.get()
                if item.get("kind") == "done":
                    finished += 1
                    continue
                event = item.get("event")
                if event:
                    yield self.normalize_event(event)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

        yield self.normalize_event({
            "type": "compare_complete",
            "model_results": model_results,
        })

    def _resolve_model_name(self, model_id: str) -> str:
        if self.resolve_model_name is None:
            return model_id
        try:
            return self.resolve_model_name(model_id)
        except Exception:
            return model_id
