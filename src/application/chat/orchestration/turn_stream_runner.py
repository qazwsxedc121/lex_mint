"""Streaming runner for one group assistant turn."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, AsyncIterator, Callable, Dict, Optional

from src.llm_runtime import call_llm_stream


@dataclass
class GroupTurnStreamState:
    """Mutable stream state collected during one turn."""

    full_response: str = ""
    usage_data: Optional[Any] = None
    cost_data: Optional[Any] = None


class GroupTurnStreamRunner:
    """Runs model stream and maps chunks to assistant turn events."""

    def __init__(
        self,
        *,
        pricing_service: Any,
        file_service: Any,
        assistant_params_from_config: Callable[[Any], Dict[str, Any]],
    ):
        self.pricing_service = pricing_service
        self.file_service = file_service
        self.assistant_params_from_config = assistant_params_from_config

    async def stream_turn(
        self,
        *,
        state: GroupTurnStreamState,
        session_id: str,
        assistant_id: str,
        assistant_turn_id: str,
        assistant_obj: Any,
        model_id: str,
        messages: Any,
        system_prompt: str,
        reasoning_effort: Optional[str],
    ) -> AsyncIterator[Dict[str, Any]]:
        """Run streaming model call for one group assistant turn."""
        assistant_params = self.assistant_params_from_config(assistant_obj)
        max_rounds = assistant_obj.max_rounds

        async for chunk in call_llm_stream(
            messages,
            session_id=session_id,
            model_id=model_id,
            system_prompt=system_prompt,
            max_rounds=max_rounds,
            reasoning_effort=reasoning_effort,
            file_service=self.file_service,
            **assistant_params,
        ):
            if isinstance(chunk, dict) and chunk.get("type") == "usage":
                state.usage_data = chunk["usage"]
                parts = model_id.split(":", 1)
                provider_id = parts[0] if len(parts) > 1 else ""
                simple_model_id = parts[1] if len(parts) > 1 else model_id
                state.cost_data = self.pricing_service.calculate_cost(
                    provider_id,
                    simple_model_id,
                    state.usage_data,
                )
                continue

            if isinstance(chunk, dict):
                event = dict(chunk)
                event["assistant_id"] = assistant_id
                event["assistant_turn_id"] = assistant_turn_id
                yield event
                continue

            text = str(chunk)
            state.full_response += text
            yield {
                "type": "assistant_chunk",
                "assistant_id": assistant_id,
                "assistant_turn_id": assistant_turn_id,
                "chunk": text,
            }
