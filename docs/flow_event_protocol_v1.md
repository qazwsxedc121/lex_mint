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
      "chunk": "hello"
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
  - `legacy_event` (fallback)

## Compatibility

- Clients must parse `flow_event`.

## Resume semantics (Stage 2)

- Server keeps an in-memory replay window per `stream_id`.
- Client can reconnect with `stream_id + last_event_id` to request replay.
- On success, server replays events after `last_event_id`, then continues live events.
- If `last_event_id` is no longer in replay window, server returns:
  - HTTP `410`, code `replay_cursor_gone`
