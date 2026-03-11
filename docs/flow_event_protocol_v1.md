# FlowEvent Protocol v1

This document defines the canonical `flow_event` envelope for streaming SSE APIs.

## Scope

- Scope endpoints:
  - `POST /api/chat/stream`
  - `POST /api/chat/stream/resume`
  - `POST /api/chat/compare`
  - `POST /api/chat/compress`
  - `POST /api/translate`
- Mode: `flow_event` only

## Envelope

```json
{
  "flow_event": {
    "event_id": "uuid",
    "seq": 1,
    "ts": 1760000000000,
    "stream_id": "uuid",
    "conversation_id": "session_id",
    "turn_id": "optional_assistant_turn_id",
    "event_type": "text_delta",
    "stage": "content",
    "payload": {
      "text": "hello"
    }
  }
}
```

## Stage values

- `transport`
- `content`
- `tool`
- `orchestration`
- `meta`

## Event types in v1 (full-chain)

Backend source of truth: `src/application/flow/flow_event_types.py`

- transport
  - `stream_started`
  - `stream_ended`
  - `stream_error`
  - `resume_started`
  - `replay_finished`
- content
  - `text_delta`
  - `reasoning_duration_reported`
- tool
  - `tool_call_started`
  - `tool_call_finished`
- orchestration
  - `assistant_turn_started`
  - `assistant_turn_finished`
  - `group_round_started`
  - `group_action_reported`
  - `group_done_reported`
  - `compare_model_started`
  - `compare_model_finished`
  - `compare_model_failed`
  - `compare_completed`
- meta
  - `usage_reported`
  - `sources_reported`
  - `context_reported`
  - `user_message_identified`
  - `assistant_message_identified`
  - `followup_questions_reported`
  - `language_detected`
  - `translation_completed`
  - `compression_completed`

## Compatibility

- Clients must parse `flow_event`.

## Protocol guard tests

- Contract test entry: `tests/unit/api/routers/test_flow_event_stream_contract.py`
- Covered endpoints:
  - `POST /api/chat/stream`
  - `POST /api/chat/compare`
  - `POST /api/chat/compress`
  - `POST /api/translate`
- Guard assertions:
  - SSE top-level payload is `{"flow_event": ...}` only.
  - `flow_event.seq` is strictly increasing within one stream.
  - `text_delta` uses `payload.text`.
  - `stream_error` terminates stream early.
  - Unknown upstream event types must emit `stream_error` and terminate immediately.

## Strictness policy

- Legacy transport fallback events are removed.
- Unknown event types are treated as protocol violations (`stream_error` + terminate).
- No compatibility mapping is performed for legacy event payloads.

Run only contract tests:

```bash
./venv/Scripts/pytest tests/unit/api/routers/test_flow_event_stream_contract.py
```

Run backend full tests:

```bash
./venv/Scripts/pytest
```

## Resume semantics (Stage 2)

- Server keeps an in-memory replay window per `stream_id`.
- Client can reconnect with `stream_id + last_event_id` to request replay.
- On success, server replays events after `last_event_id`, then continues live events.
- If `last_event_id` is no longer in replay window, server returns:
  - HTTP `410`, code `replay_cursor_gone`
