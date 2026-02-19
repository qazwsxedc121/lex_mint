# RAG TODO Roadmap

Status legend:
- `[ ]` pending
- `[-]` in progress
- `[x]` done

## Phase 0 - Active RAG Foundation (P0)

- `[x]` Implement retrieval query planner service and wire it into RAG diagnostics
- `[x]` Implement structured source-context injection with runtime toggle
- `[x]` Implement tool-based RAG (`search_knowledge` / `read_knowledge`) with assistant-scoped KB access
- `[x]` Add tool-loop finalization fallback after max tool rounds (avoid incomplete tail responses)

## Phase 1 - Evaluation and Optimization Loop

- `[x]` Build a retrieval evaluation loop (dataset format + script + report output)
- `[x]` Add a small labeled dataset for local regression checks
- `[ ]` Define baseline metrics and acceptance thresholds (Recall@K, MRR, citation hit rate)

## Phase 2 - Performance and Architecture

- `[ ]` Upgrade sqlite vector retrieval path to avoid full-table scan at query time
- `[ ]` Introduce a unified vector backend interface to reduce backend-specific branching
- `[ ]` Align memory vector backend with RAG backend strategy (sqlite/chroma)

## Phase 3 - Product and Quality

- `[ ]` Add RAG benchmark command to CI/regression workflow
- `[ ]` Add dashboard-style summary for retrieval diagnostics over time
- `[ ]` Expand document loader and preprocessing coverage (OCR/web sources)
