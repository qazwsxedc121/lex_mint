"""Run a live committee-mode group chat smoke flow and print timeline + result.

This script uses the local FastAPI app via TestClient, so it exercises:
- session creation with group_mode=committee
- /api/chat/stream SSE flow
- session persistence
"""

from __future__ import annotations

import argparse
import builtins
import json
import logging
import re
import sys
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi.testclient import TestClient

# Ensure repository root is importable when script is run via relative path.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.api.main import app


def _ascii_safe(value: str) -> str:
    text = re.sub(r"\s+", " ", value or "").strip()
    return text.encode("ascii", "ignore").decode("ascii")


def _choose_assistants(assistants: List[Dict[str, Any]]) -> List[str]:
    enabled_ids = [a.get("id") for a in assistants if a.get("enabled")]
    if "general-assistant" in enabled_ids and "creative-writer" in enabled_ids:
        return ["general-assistant", "creative-writer"]
    if len(enabled_ids) >= 2:
        return enabled_ids[:2]
    raise RuntimeError("Need at least 2 enabled assistants for committee mode.")


@dataclass
class TurnTranscript:
    assistant_id: str
    assistant_name: str
    text: str = ""
    chunk_count: int = 0


def run_smoke(message: str) -> Dict[str, Any]:
    logging.disable(logging.CRITICAL)

    original_print = builtins.print
    builtins.print = lambda *args, **kwargs: None

    session_id: Optional[str] = None
    try:
        with TestClient(app) as client:
            assistants_resp = client.get("/api/assistants")
            assistants_resp.raise_for_status()
            assistants = assistants_resp.json()
            group_ids = _choose_assistants(assistants)
            assistant_name_map = {a.get("id"): a.get("name", a.get("id")) for a in assistants}

            create_resp = client.post(
                "/api/sessions",
                json={
                    "temporary": True,
                    "group_assistants": group_ids,
                    "group_mode": "committee",
                },
            )
            create_resp.raise_for_status()
            session_id = create_resp.json()["session_id"]

            events: List[Dict[str, Any]] = []
            turns: "OrderedDict[str, TurnTranscript]" = OrderedDict()

            with client.stream(
                "POST",
                "/api/chat/stream",
                json={"session_id": session_id, "message": message},
            ) as stream_resp:
                stream_resp.raise_for_status()
                for raw_line in stream_resp.iter_lines():
                    if not raw_line:
                        continue
                    line = raw_line.decode() if isinstance(raw_line, bytes) else raw_line
                    if not line.startswith("data: "):
                        continue

                    payload = json.loads(line[6:])
                    events.append(payload)

                    evt_type = payload.get("type")
                    if evt_type == "assistant_start":
                        turn_id = payload.get("assistant_turn_id")
                        assistant_id = payload.get("assistant_id", "")
                        if turn_id:
                            turns[turn_id] = TurnTranscript(
                                assistant_id=assistant_id,
                                assistant_name=assistant_name_map.get(assistant_id, assistant_id),
                            )
                    elif evt_type == "assistant_chunk":
                        turn_id = payload.get("assistant_turn_id")
                        chunk = payload.get("chunk", "")
                        if turn_id and turn_id in turns:
                            turns[turn_id].text += chunk
                            turns[turn_id].chunk_count += 1

                    if payload.get("done") is True:
                        break

            session_resp = client.get(f"/api/sessions/{session_id}")
            session_resp.raise_for_status()
            session_data = session_resp.json()
            messages = session_data["state"]["messages"]

            delete_resp = client.delete(f"/api/sessions/{session_id}")
            delete_resp.raise_for_status()

    finally:
        builtins.print = original_print

    event_counts: Counter = Counter()
    compact_sequence: List[str] = []
    action_events: List[Dict[str, Any]] = []
    group_done: Optional[Dict[str, Any]] = None
    first_error: Optional[Dict[str, Any]] = None

    interesting_types = {
        "user_message_id",
        "group_round_start",
        "group_action",
        "assistant_start",
        "assistant_message_id",
        "assistant_done",
        "usage",
        "group_done",
    }

    for event in events:
        event_type = event.get("type")
        if event_type:
            event_counts[event_type] += 1
            if event_type in interesting_types:
                compact_sequence.append(event_type)
        elif event.get("done") is True:
            event_counts["done"] += 1
            compact_sequence.append("done")

        if "type" in event:
            pass
        if event.get("type") == "group_action":
            action_events.append(
                {
                    "round": event.get("round"),
                    "action": event.get("action"),
                    "assistant_id": event.get("assistant_id"),
                    "assistant_name": event.get("assistant_name"),
                    "reason": _ascii_safe(event.get("reason", ""))[:180],
                }
            )
        if event.get("type") == "group_done":
            group_done = event
        if event.get("error") and first_error is None:
            first_error = event

    assistant_messages = [m for m in messages if m.get("role") == "assistant"]
    stored_assistant_messages = [
        {
            "assistant_id": m.get("assistant_id"),
            "preview": _ascii_safe(m.get("content", ""))[:140],
        }
        for m in assistant_messages
    ]

    streamed_turns = [
        {
            "assistant_id": turn.assistant_id,
            "assistant_name": turn.assistant_name,
            "chunk_count": turn.chunk_count,
            "preview": _ascii_safe(turn.text)[:180],
        }
        for turn in turns.values()
    ]

    return {
        "session_id": session_id,
        "group_assistants": group_ids,
        "event_counts": dict(event_counts),
        "compact_event_sequence": compact_sequence,
        "group_actions": action_events,
        "group_done": group_done,
        "error": first_error,
        "streamed_turns": streamed_turns,
        "stored_assistant_messages": stored_assistant_messages,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run committee mode group chat smoke flow.")
    parser.add_argument(
        "--message",
        default="Give an implementation plan for committee mode in 6 concise bullet points.",
        help="User message to send.",
    )
    args = parser.parse_args()

    result = run_smoke(args.message)
    print(json.dumps(result, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
