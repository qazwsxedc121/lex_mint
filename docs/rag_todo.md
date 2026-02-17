# RAG TODO Roadmap

Status legend:
- `[ ]` pending
- `[-]` in progress
- `[x]` done

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
