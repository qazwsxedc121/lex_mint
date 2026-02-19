# RAG Evaluation Quickstart

This repository now includes a retrieval evaluation script:

- `scripts/run_rag_eval.py`

## 1) Prepare a labeled dataset

Start from:

- `docs/rag_eval_dataset.example.json`

For each case, define:

- `query`: user query text
- `kb_ids`: knowledge base ids to search
- `expected.doc_ids` and/or `expected.filenames`
- optional `expected.keywords` for lightweight fallback matching

## 2) Run evaluation

```powershell
.\venv\Scripts\python.exe .\scripts\run_rag_eval.py --dataset .\docs\rag_eval_dataset.example.json
```

Optional overrides:

```powershell
.\venv\Scripts\python.exe .\scripts\run_rag_eval.py `
  --dataset .\docs\rag_eval_dataset.example.json `
  --modes vector,bm25,hybrid `
  --top-k 5 `
  --score-threshold 0.3 `
  --max-cases 50
```

## 3) Output artifacts

The script writes files under:

- `data/benchmarks/rag_eval_<timestamp>/`

Including:

- `summary.json` (mode-level metrics)
- `mode_<mode>_cases.json` (per-case details + diagnostics)
- `report.md` (human-readable summary)
- `dataset_snapshot.json` (frozen dataset copy)

## 4) Metrics

Current metrics:

- `Hit Rate` (Hit@K)
- `Citation Hit Rate` (proxy from retrieval matches)
- `Mean MRR`
- `Mean Precision@K`
- `Mean Recall@K`

These are retrieval-layer quality metrics and should be used as the baseline gate
before trying rerank/fusion/parameter changes.
