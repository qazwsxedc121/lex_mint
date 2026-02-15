# Hierarchical Context Compression Plan

Last updated: 2026-02-15
Owner: Codex + project maintainers
Scope: Improve context compression for local/small-context LLMs

## 1) Problem

When compression uses a local LLM with limited context, the current single-pass summarization can overflow prompt budget and fail or produce unstable summaries.

## 2) Goals

- Make compression robust under limited context windows.
- Keep critical technical details (numbers, paths, commands, identifiers).
- Keep the summary compact enough for follow-up turns.
- Preserve existing UX and API behavior.

## 3) Strategy (V1)

Use hierarchical compression:

1. Map stage (chunk summaries)
   - Split old messages into token-bounded chunks.
   - Summarize each chunk independently.
2. Reduce stage (merge summaries)
   - Merge chunk summaries in rounds until one summary remains.
   - Deduplicate repeated facts and preserve hard constraints.
3. Final output
   - Save one final summary as the `summary` message (same as current behavior).

Fallback behavior:
- If content fits budget: keep single-pass compression.
- If hierarchical pass fails: return non-fatal error and continue chat flow (existing behavior).

## 4) Budgeting Rules (V1 defaults)

- Token estimate heuristic: ~4 chars per token.
- Local compression input budget: conservative fraction of `local_gguf_n_ctx`.
- Chunk target: conservative fraction of local context.
- Overlap: small message overlap between chunks to reduce boundary loss.
- Max hierarchy levels: hard cap to avoid endless reduction loops.

Note: V1 uses internal defaults in service code; UI-exposed knobs can be added in V1.5.

## 5) Data/Behavior Compatibility

- No API contract break for `/api/chat/compress`.
- Stored summary format unchanged (still one `summary` message).
- Existing auto-compress trigger remains in `AgentService`.

## 6) Milestones

- V1: backend hierarchical compression for local GGUF.
- V1.5: expose hierarchy settings in compression config + settings UI.
- V2: quality guard (fact checklist), metrics, and A/B tuning.

## 7) Progress Board

| ID | Work Item | Status | Notes |
|---|---|---|---|
| P1 | Define hierarchical design and rollout plan | DONE | This doc |
| P2 | Implement service-level map/reduce pipeline | DONE | Implemented in `CompressionService` local GGUF path |
| P3 | Add safe budgeting/chunking utilities | DONE | Added token estimator + chunk builders + hard level cap |
| P4 | Add tests for chunking/reduction helpers | DONE | Added unit tests in `tests/unit/test_services/test_compression_service.py` |
| P5 | Add config/UI knobs for hierarchy controls | DONE | Added compression strategy + hierarchy params in API and settings UI |
| P6 | Add quality guard and compression metrics | DONE | Added critical-fact guard + compression telemetry/meta |

## 8) Acceptance Criteria

- Compression does not fail on long history due to local context overflow.
- Final summary remains compact and useful for continuation.
- Auto-compress flow remains non-blocking on failure.
- Lint/tests pass for changed code.

## 9) Change Log

- 2026-02-15: Created plan + progress board for hierarchical compression.
- 2026-02-15: Completed V1 backend hierarchy pipeline + initial unit tests.
- 2026-02-15: Completed V1.5 config and UI controls for hierarchy strategy/knobs.
- 2026-02-15: Completed V2 quality guard + compression metrics (config/API/UI + local guard/repair path).
- 2026-02-15: Added online-model comparison benchmark artifacts under `data/benchmarks/compression_compare_20260215_163233_deepseek_deepseek-chat`.
- 2026-02-15: Added configurable compression output language (`auto`/`none`/forced language) in config/API/UI, and enforced language hints in map/reduce/repair prompts.
- 2026-02-15: Unified path selector for local and online compression to context-budget based routing (fit => single-pass, overflow => hierarchical).
- 2026-02-15: Added compression model option `same_as_chat` so summarization can follow the current conversation model.
