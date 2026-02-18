# RAG_Techniques Repository Landscape (Initial Scan)

Date: 2026-02-18  
Snapshot commit: `69a08b03154ea6087456ad44efebc9292d96667e` (`main`)

## 1) What is in this repository

- Path: `learn_proj/RAG_Techniques`
- Main tutorial notebooks: `all_rag_techniques/*.ipynb` (35 notebooks)
- Runnable scripts: `all_rag_techniques_runnable_scripts/*.py` (19 scripts)
- Evaluation material: `evaluation/*.ipynb` (3 notebooks) + `evaluation/evalute_rag.py`
- Shared helper utilities: `helper_functions.py`

## 2) Technique coverage (high level)

- Foundational retrieval: simple RAG, CSV RAG, chunk-size tuning, reliable RAG
- Query enhancement: query rewriting, step-back, decomposition, HyDE, HyPE
- Context enrichment: semantic chunking, context window expansion, contextual compression, chunk headers
- Retrieval optimization: fusion retrieval, reranking, hierarchical indices, explainable retrieval
- Advanced orchestration: adaptive retrieval, feedback loop retrieval, Self-RAG, CRAG, Agentic RAG
- Graph/hierarchical approaches: Graph RAG, Microsoft GraphRAG, RAPTOR, GraphRAG + Milvus
- Multi-modal paths: captioning-based and ColPali-based variants

## 3) Practical execution signals

- Most examples are notebook-first; script coverage is partial (19/35).
- Most runnable examples assume API access (OpenAI and sometimes others).
- Several examples install packages inline with `!pip install` inside notebooks.
- `README.md` references some notebooks that are not present in the clone:
  - `all_rag_techniques/multi_faceted_filtering.ipynb`
  - `all_rag_techniques/ensemble_retrieval.ipynb`
  - `all_rag_techniques/iterative_retrieval.ipynb`

## 4) Dependency and environment profile

Common stack found in notebooks/scripts:
- LangChain ecosystem (`langchain`, `langchain_openai`, `langchain_community`)
- FAISS, BM25 (`rank_bm25`)
- LlamaIndex (in selected tutorials)
- Optional graph/multimodal stack (`networkx`, `spacy`, `nltk`, `pandas`, `PIL`)

Observed environment keys:
- Frequent: `OPENAI_API_KEY`
- Also used in specific notebooks: `COHERE_API_KEY`, `CO_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`, `CONTEXTUAL_API_KEY`
- Microsoft GraphRAG notebook expects Azure OpenAI variables.

## 5) Initial value for our project

This repository is strongest as:
- A pattern library for retrieval strategies and routing ideas.
- A source of prototype logic that can be ported into service-layer code.
- A benchmark inspiration source (especially retrieval diagnostics + eval framing).

It is weaker as:
- A production-ready package (notebooks are the main delivery format).
- A reproducible dependency baseline (no clear locked dependency manifest in this snapshot).

