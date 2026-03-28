"""Decision parser for committee supervisor outputs."""

from __future__ import annotations

import json
import re

from .committee_types import CommitteeDecision


class CommitteeSupervisorDecisionParser:
    """Parses raw supervisor model output into normalized decision payload."""

    _ACTION_MAP = {
        "speak": "speak",
        "call_agent": "speak",
        "ask_member": "speak",
        "parallel_speak": "parallel_speak",
        "parallel": "parallel_speak",
        "broadcast": "parallel_speak",
        "finish": "finish",
        "end": "finish",
        "done": "finish",
    }

    def parse(self, raw_output: str) -> CommitteeDecision:
        payload = self._extract_json_payload(raw_output)
        if not payload:
            return CommitteeDecision(action="speak", reason="invalid_supervisor_output")

        action_raw = str(payload.get("action", "")).strip().lower()
        action = self._ACTION_MAP.get(action_raw, "speak")

        assistant_id = payload.get("assistant_id") or payload.get("agent_id")
        assistant_ids_raw = (
            payload.get("assistant_ids") or payload.get("agent_ids") or payload.get("agents")
        )
        assistant_ids: list[str] = []
        if isinstance(assistant_ids_raw, list):
            for value in assistant_ids_raw:
                text = str(value).strip()
                if text:
                    assistant_ids.append(text)
        elif isinstance(assistant_ids_raw, str):
            assistant_ids = [part.strip() for part in assistant_ids_raw.split(",") if part.strip()]

        instruction = payload.get("instruction")
        reason = payload.get("reason") or ""
        final_response = payload.get("final_response") or payload.get("summary")

        return CommitteeDecision(
            action=action,  # type: ignore[arg-type]
            assistant_id=str(assistant_id).strip() if assistant_id else None,
            assistant_ids=assistant_ids or None,
            instruction=str(instruction).strip() if instruction else None,
            reason=str(reason).strip(),
            final_response=str(final_response).strip() if final_response else None,
        )

    @staticmethod
    def _extract_json_payload(raw_output: str) -> dict | None:
        text = (raw_output or "").strip()
        if not text:
            return None

        fenced = re.search(r"```(?:json)?\s*(\{[\s\S]*\})\s*```", text, re.IGNORECASE)
        candidates = [fenced.group(1)] if fenced else []
        candidates.append(text)

        start_idx = text.find("{")
        end_idx = text.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidates.append(text[start_idx : end_idx + 1])

        for candidate in candidates:
            try:
                data = json.loads(candidate)
                if isinstance(data, dict):
                    return data
            except Exception:
                continue
        return None
