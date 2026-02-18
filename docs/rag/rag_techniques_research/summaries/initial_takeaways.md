# Initial Takeaways: What We Can Learn

## What this repository gives us immediately

- A broad catalog of RAG strategy patterns, from basic retrieval to corrective and graph-based flows.
- Concrete runnable references for many methods (19 scripts), which are useful for fast prototyping.
- Clear examples of retrieval-time control logic (routing, reranking, context shaping, correction loops).

## Most relevant learning areas for lex_mint_rag now

1. Query transformations before retrieval  
2. Context window enrichment and contextual compression  
3. Adaptive retrieval strategy selection  
4. Self-correction loops (Self-RAG/CRAG-lite)

These are likely to produce gains faster than large architecture changes (GraphRAG, full agentic pipelines).

## Caveats before direct adoption

- Notebook-first format means code quality and production concerns vary.
- Most demos depend on hosted APIs and LLM grading logic.
- Some README-linked notebooks are not present in this snapshot.
- Dependency setup is not packaged as a strict lockfile in this clone.

## Practical next move

Implement one thin experimental layer at a time on top of the existing retrieval service, and evaluate using our current `docs/rag_eval*.json` datasets before any broad rollout.

