# MTRAG Retrieval Benchmark Runbook

This project includes scripts to benchmark retrieval on MTRAG (IBM):

- `scripts/import_mtrag_corpus_to_kb.py`
- `scripts/run_mtrag_retrieval_benchmark.py`

## Why MTRAG for engineering-only benchmarking

MTRAG provides retrieval-only tasks in BEIR format, so we can evaluate retrieval engineering
independently from generation style.

Reference:

- `learn_proj/mt-rag-benchmark/human/retrieval_tasks/README.md`

Published retrieval baselines (all domains, from MTRAG README):

- BM25 (query rewrite): `nDCG@10 = 0.25`
- BGE-base v1.5 (query rewrite): `nDCG@10 = 0.38`
- ELSER (query rewrite): `nDCG@10 = 0.54`

## 1) Import FiQA passage corpus into KB

Create/import into KB `kb_mtrag_fiqa_v1`:

```powershell
.\venv\Scripts\python.exe .\scripts\import_mtrag_corpus_to_kb.py `
  --kb-id kb_mtrag_fiqa_v1 `
  --domain fiqa `
  --create-kb-if-missing `
  --workers 1
```

Smoke import:

```powershell
.\venv\Scripts\python.exe .\scripts\import_mtrag_corpus_to_kb.py `
  --kb-id kb_mtrag_fiqa_v1 `
  --domain fiqa `
  --create-kb-if-missing `
  --max-docs 200 `
  --dry-run
```

## 2) Run retrieval benchmark

Default config:

- `config/benchmarks/mtrag_fiqa_retrieval_v1.yaml`

Run:

```powershell
.\venv\Scripts\python.exe .\scripts\run_mtrag_retrieval_benchmark.py `
  --config .\config\benchmarks\mtrag_fiqa_retrieval_v1.yaml
```

Smoke (first 30 queries):

```powershell
.\venv\Scripts\python.exe .\scripts\run_mtrag_retrieval_benchmark.py `
  --config .\config\benchmarks\mtrag_fiqa_retrieval_v1.yaml `
  --max-cases 30
```

## 3) Outputs

Each run writes:

- `data/benchmarks/mtrag_fiqa_retrieval_v1_<timestamp>/dataset_converted.json`
- `data/benchmarks/mtrag_fiqa_retrieval_v1_<timestamp>/benchmark_manifest.json`
- `data/benchmarks/mtrag_fiqa_retrieval_v1_<timestamp>/rag_eval/summary.json`
- `data/benchmarks/mtrag_fiqa_retrieval_v1_<timestamp>/rag_eval/report.md`

`summary.json` now includes:

- `mean_ndcg_at_k`
- `mean_mrr`
- `mean_recall_at_k`

## 4) Notes

- This config evaluates FiQA domain only for a faster first iteration.
- For strict paper-level comparability, run all four domains with their corresponding corpora and query files.
