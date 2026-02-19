# Phase 1 Experiment Plan (Transfer to lex_mint_rag)

Goal: run small, low-risk experiments that can be merged into our existing RAG stack with measurable retrieval gains.

## Status update (2026-02-19)

- Experiment A core goals are already achieved in production:
  - query rewrite/transform layer
  - retrieval query planner (multi-query + fallback)
- Phase 1 focus should now move to B/C/D with measurable gains.

## Experiment A: Query Transformation Layer

- Source: `query_transformations.py`
- Hypothesis:
  - rewrite + decomposition improves hit rate on complex user questions
- Integration sketch:
  - add an optional pre-retrieval transformer in `src/api/services/rag_service.py`
  - config gate in `src/api/services/rag_config_service.py`
- Metrics:
  - Hit@K, MRR, Recall@K from `scripts/run_rag_eval.py`

## Experiment B: Context Window Enrichment

- Source: `context_enrichment_window_around_chunk.py`
- Hypothesis:
  - adding neighbor chunks around top hits improves answer completeness
- Integration sketch:
  - after top-k retrieval, fetch adjacent chunk indexes from same doc
  - cap by token budget and max-per-doc
- Metrics:
  - Recall@K and citation hit rate

## Experiment C: Contextual Compression

- Source: `contextual_compression.py`
- Hypothesis:
  - compressed context keeps answer quality while reducing prompt tokens
- Integration sketch:
  - optional compression stage before final prompt assembly
  - fallback to raw context on timeout/error
- Metrics:
  - quality parity + token reduction + latency delta

## Experiment D: Adaptive Retrieval Routing (Lite)

- Source: `adaptive_retrieval.py`
- Hypothesis:
  - query-type routing (factual vs analytical) outperforms fixed retrieval policy
- Integration sketch:
  - small classifier prompt picks one of 2-3 retrieval policies
  - start with conservative mapping to existing retrieval modes
- Metrics:
  - per-query-class Recall@K and failure rate

## Exit criteria for Phase 1

- At least one experiment shows a stable gain on our eval dataset.
- No major regression in latency or failure rate.
- Feature is behind config toggles and can be disabled quickly.

## Recommended immediate order (updated)

1. Experiment B (Context Window Enrichment tuning)  
2. Experiment C (Contextual Compression)  
3. Experiment D (Adaptive Routing Lite)
