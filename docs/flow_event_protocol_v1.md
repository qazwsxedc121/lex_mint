# FlowEvent Protocol v1

This document defines the `flow_event` envelope attached to chat SSE payloads.

## Scope

- Stage 1 rollout target: `POST /api/chat/stream`
- Mode: backward compatible dual output
  - Legacy fields are preserved (`chunk`, `type`, `done`, `error`, ...)
  - New structured field is attached as `flow_event`

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
    "event_type": "assistant_text_delta",
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

## Event types in v1

- transport
  - `stream_started`
  - `stream_ended`
  - `stream_error`
- content
  - `assistant_text_delta`
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
- meta
  - `usage_reported`
  - `sources_reported`
  - `context_reported`
  - `user_message_identified`
  - `assistant_message_identified`
  - `followup_questions_reported`
  - `legacy_event` (fallback)

## Compatibility

- Clients that do not parse `flow_event` continue to work with legacy fields.
- Clients that parse `flow_event` should prefer it and ignore duplicated legacy fields.
