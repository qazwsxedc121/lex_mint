# CRUD-RAG E2E Protocol v1

This document freezes the end-to-end benchmark protocol used for competitor comparison.
Use this protocol for all official scorecards.

Config source:

- `config/benchmarks/crud_e2e_v1.yaml`

## Scope

- Benchmark family: CRUD-RAG
- Evaluation type: end-to-end (retrieve + generate + score)
- Dataset split: `learn_proj/CRUD_RAG/data/crud_split/split_merged.json`
- Retrieval corpus: `learn_proj/CRUD_RAG/data/80000_docs`
- Tasks:
  - `event_summary`
  - `continuing_writing`
  - `hallu_modified`
  - `questanswer_1doc`
  - `questanswer_2docs`
  - `questanswer_3docs`

## Fixed Retrieval Settings

- chunk size: `128`
- chunk overlap: `0`
- top_k: `8`
- retrieval modes: `bm25`, `vector`, `hybrid`
- score threshold: `0.65`
- bm25 lexical coverage threshold: `0.35`

## Fixed Generation Settings

- temperature: `0.1`
- max new tokens: `1280`
- query transform: disabled

## Fixed Metrics

Primary:

- `ragquesteval`

Secondary:

- `bleu`
- `rouge`
- `bertscore`
- retrieval `hit_rate`, `mrr`, `recall_at_k`

## Reproducibility Rules

- seed: `42`
- run repeats: `3`
- report: mean + 95% CI
- no protocol changes inside the same version

## Policy

- `crud_e2e_v1` is immutable once used for official comparison.
- Any change to dataset, prompts, chunking, retrieval params, model params, or metrics requires a new protocol version (for example `crud_e2e_v2`).
- Smoke runs on reduced corpus (for example 1000 docs) are allowed for debugging, but they are non-comparable and must be labeled as smoke only.

## Reference Comparison

Public reference values are tracked in:

- `config/benchmarks/crud_e2e_reference_v1.yaml`

Current baseline keys:

- `gpt4o`
- `qwen2_7b`

Compare local result JSON with:

```powershell
.\venv\Scripts\python.exe .\scripts\compare_crud_e2e_reference.py `
  --result path\to\e2e_result.json `
  --baseline-model gpt4o
```

Recommended pass/fail gate for "not far behind":

- macro ratio >= `0.85` versus selected reference baseline.

## Run E2E Benchmark

Script:

- `scripts/run_crud_e2e_benchmark.py`

Smoke run (recommended first):

```powershell
.\venv\Scripts\python.exe .\scripts\run_crud_e2e_benchmark.py `
  --config .\config\benchmarks\crud_e2e_v1.yaml `
  --model-id qwen3.5-plus `
  --modes hybrid `
  --per-task-max 20
```

Then compare to paper baseline:

```powershell
.\venv\Scripts\python.exe .\scripts\compare_crud_e2e_reference.py `
  --result .\data\benchmarks\<run_dir>\summary.json `
  --baseline-model gpt4o
```
