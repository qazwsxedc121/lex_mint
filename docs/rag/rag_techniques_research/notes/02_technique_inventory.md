# Technique Inventory (Initial)

Legend:
- Script = runnable `.py` exists in `all_rag_techniques_runnable_scripts`
- Priority = initial transfer priority for `lex_mint_rag`

## Progress snapshot (2026-02-19)

- Query rewrite + retrieval query planner baseline is already integrated in mainline.
- Current transfer priority should focus on context shaping, adaptive routing, and evaluation-driven quality gains.

| Technique | Notebook | Script | Priority | Notes |
|---|---|---|---|---|
| Simple RAG | `simple_rag.ipynb` | Yes | Low | Baseline only |
| Query Transformations | `query_transformations.ipynb` | Yes | Medium | Baseline already done; keep for advanced variants |
| HyDE | `HyDe_Hypothetical_Document_Embedding.ipynb` | Yes | Medium | Query-time synthetic doc |
| HyPE | `HyPE_Hypothetical_Prompt_Embeddings.ipynb` | Yes | Medium | Index-time synthetic prompts |
| Semantic Chunking | `semantic_chunking.ipynb` | Yes | High | Better chunk boundaries |
| Context Window Enrichment | `context_enrichment_window_around_chunk.ipynb` | Yes | High | Neighbor chunk expansion |
| Contextual Compression | `contextual_compression.ipynb` | Yes | High | Prompt budget reduction |
| Fusion Retrieval | `fusion_retrieval.ipynb` | Yes | Medium | We already have hybrid + fusion; compare methods |
| Reranking | `reranking.ipynb` | Yes | Medium | Compare LLM rerank vs cross-encoder flow |
| Hierarchical Indices | `hierarchical_indices.ipynb` | Yes | Medium | Two-stage retrieval |
| Adaptive Retrieval | `adaptive_retrieval.ipynb` | Yes | High | Query-intent-based strategy routing |
| Retrieval with Feedback Loop | `retrieval_with_feedback_loop.ipynb` | Yes | Medium | User-feedback-driven adjustment |
| Self-RAG | `self_rag.ipynb` | Yes | High | Retrieval decision + support/utility checks |
| CRAG | `crag.ipynb` | Yes | High | Corrective branch + fallback behavior |
| RAPTOR | `raptor.ipynb` | Yes | Medium | Hierarchical summaries + clustering |
| Graph RAG | `graph_rag.ipynb` | Yes | Medium | Graph-enhanced retrieval path |
| Microsoft GraphRAG | `Microsoft_GraphRag.ipynb` | No | Low | High setup complexity |
| Agentic RAG | `Agentic_RAG.ipynb` | No | Low | External platform coupling |
| Proposition Chunking | `proposition_chunking.ipynb` | No | High | Promising for fact-heavy corpora |
| Relevant Segment Extraction | `relevant_segment_extraction.ipynb` | No | Medium | Improves continuity of evidence |

## Notebook-only techniques to review manually

No script in current snapshot:
- `Agentic_RAG.ipynb`
- `Microsoft_GraphRag.ipynb`
- `contextual_chunk_headers.ipynb`
- `graphrag_with_milvus_vectordb.ipynb`
- `multi_model_rag_with_captioning.ipynb`
- `multi_model_rag_with_colpali.ipynb`
- `proposition_chunking.ipynb`
- `relevant_segment_extraction.ipynb`
- plus LlamaIndex variants and CSV variants

## README linkage mismatch to verify later

Referenced in README but notebook file not found in clone:
- `all_rag_techniques/multi_faceted_filtering.ipynb`
- `all_rag_techniques/ensemble_retrieval.ipynb`
- `all_rag_techniques/iterative_retrieval.ipynb`
