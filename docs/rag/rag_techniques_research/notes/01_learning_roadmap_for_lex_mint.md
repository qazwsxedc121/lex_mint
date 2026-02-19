# Learning Roadmap for lex_mint_rag (Based on RAG_Techniques)

## Progress snapshot (2026-02-19)

- [x] Query-side rewrite + guard is already in production.
- [x] Retrieval query planner (multi-query) is now integrated.
- [x] Structured source-context injection is available behind config.
- [x] Tool-based active RAG (`search_knowledge` / `read_knowledge`) is online.
- [ ] Adaptive routing by query type is not implemented yet.
- [ ] Baseline acceptance thresholds and CI gating are not finalized yet.

## Current baseline in our codebase

From `src/api/services/rag_service.py` and `src/api/services/rag_config_service.py`, we already have:
- Hybrid retrieval (`vector`/`bm25`/`hybrid`)
- RRF-style fusion controls
- Optional API reranking
- Document-level diversity control
- Long-context reorder strategy
- Retrieval diagnostics path

So the biggest gains are likely from **new retrieval strategies**, not from basic vector/BM25 setup.

## High-value learning opportunities

## 1) Query-side intelligence
- Source references:
  - `learn_proj/RAG_Techniques/all_rag_techniques/query_transformations.ipynb`
  - `learn_proj/RAG_Techniques/all_rag_techniques_runnable_scripts/query_transformations.py`
- What to learn:
  - query rewrite, step-back query, sub-query decomposition
- Why it matters:
  - should improve recall on vague and multi-hop queries before retrieval even starts

## 2) Adaptive routing by query type
- Source references:
  - `learn_proj/RAG_Techniques/all_rag_techniques/adaptive_retrieval.ipynb`
  - `learn_proj/RAG_Techniques/all_rag_techniques_runnable_scripts/adaptive_retrieval.py`
- What to learn:
  - classify query intent (factual/analytical/opinion/contextual)
  - apply retrieval policy per class
- Why it matters:
  - matches retrieval effort to query type, not one-size-fits-all

## 3) Context shaping after retrieval
- Source references:
  - `.../context_enrichment_window_around_chunk.ipynb`
  - `.../contextual_compression.ipynb`
  - `.../semantic_chunking.ipynb`
- What to learn:
  - neighborhood expansion around hits
  - compress long retrieved context before generation
  - semantic chunk boundaries vs fixed windows
- Why it matters:
  - helps answer completeness without flooding the prompt

## 4) Self-correction loops
- Source references:
  - `.../self_rag.ipynb`, `.../crag.ipynb`, `.../retrieval_with_feedback_loop.ipynb`
- What to learn:
  - retrieval necessity checks
  - relevance/support/utility grading
  - fallback behavior on low-confidence retrieval
- Why it matters:
  - better robustness on hard or out-of-domain queries

## 5) Longer-term architecture bets
- Source references:
  - `.../graph_rag.ipynb`, `.../Microsoft_GraphRag.ipynb`, `.../raptor.ipynb`
- What to learn:
  - graph-based retrieval paths
  - hierarchy and summary-tree retrieval
- Why it matters:
  - may unlock complex reasoning over large corpora, but higher integration cost

## Suggested execution order

1. Context enrichment/compression  
2. Adaptive retrieval routing  
3. Self-correction (Self-RAG/CRAG-lite)  
4. Graph/RAPTOR exploration (only after measurable gains in 1-3)
