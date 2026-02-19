# Provider Refactor TODO

Date: 2026-02-19

- [x] P1 - Add `call_mode` schema fields with backward-compatible defaults.
- [x] P2 - Add runtime resolution helpers (`auto` policy, OpenAI-official detection with base_url fallback).
- [x] P3 - Wire effective call mode into core call paths and add `responses -> chat/completions` fallback.
- [x] P4 - Update provider settings UI: advanced section collapsed by default, expose overrides there.
- [x] P5 - Fix provider test availability and API key requirement logic (avoid `has_api_key` only gating).
- [x] P6 - Add/adjust tests and run regression validation.
- [x] P6.1 - Align `simple_llm` unit tests with new provider resolution/call-mode flow and stream metadata behavior.
- [x] P7 - Improve provider UX wording: replace technical `protocol/call_mode` copy with user-facing labels and clearer auto-policy help text.
- [x] P8 - Fix OpenAI responses fallback cloning for bound tool runnables and add regression test.
