# Initial Takeaways: What We Can Learn

## Progress snapshot (2026-02-19)

- Active RAG foundation is already in production (query planner + source context + search/read tools).
- This research track should now focus on measurable quality gains, not repeating baseline feature work.

## What this repository gives us immediately

- A broad catalog of RAG strategy patterns, from basic retrieval to corrective and graph-based flows.
- Concrete runnable references for many methods (19 scripts), which are useful for fast prototyping.
- Clear examples of retrieval-time control logic (routing, reranking, context shaping, correction loops).

## Most relevant learning areas for lex_mint_rag now

1. Context window enrichment and contextual compression  
2. Adaptive retrieval strategy selection  
3. Self-correction loops (Self-RAG/CRAG-lite)  
4. Deeper query-transform variants beyond current planner baseline

These are likely to produce gains faster than large architecture changes (GraphRAG, full agentic pipelines).

## Caveats before direct adoption

- Notebook-first format means code quality and production concerns vary.
- Most demos depend on hosted APIs and LLM grading logic.
- Some README-linked notebooks are not present in this snapshot.
- Dependency setup is not packaged as a strict lockfile in this clone.

## Practical next move

Implement one thin experimental layer at a time on top of the existing retrieval service, and evaluate using our current `docs/rag_eval*.json` datasets before any broad rollout.
