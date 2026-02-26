# CRUD-RAG Benchmark Runbook

This project now includes a CRUD-RAG wrapper script:

- `scripts/run_crud_rag_benchmark.py`

It converts CRUD-RAG `split_merged.json` into this repo's `run_rag_eval.py` schema,
then runs the existing retrieval evaluation pipeline.

For official competitor comparison protocol, see:

- `docs/rag_crud_e2e_protocol_v1.md`
- `config/benchmarks/crud_e2e_v1.yaml`

## 1) Dataset clone location and git tracking

Use this clone target:

- `learn_proj/CRUD_RAG`

This repo already ignores `learn_proj/`, so the cloned benchmark data is not tracked
by this project.

## 2) Configure benchmark profile

Edit:

- `config/benchmarks/crud_rag_v1.yaml`

Required field:

- `benchmark.kb_ids`: set KB IDs that contain your imported CRUD-RAG corpus

Default profile:

- tasks: `questanswer_1doc`, `questanswer_2docs`, `questanswer_3docs`
- per-task sample size: `200`
- retrieval mode: `hybrid`

## 3) Run benchmark

Dry run (only convert dataset + write manifest):

```powershell
.\venv\Scripts\python.exe .\scripts\run_crud_rag_benchmark.py --dry-run
```

Full run:

```powershell
.\venv\Scripts\python.exe .\scripts\run_crud_rag_benchmark.py
```

Override KB IDs from CLI:

```powershell
.\venv\Scripts\python.exe .\scripts\run_crud_rag_benchmark.py `
  --kb-ids kb_crud_main,kb_crud_delta `
  --per-task-max 300 `
  --modes hybrid
```

## 4) Output artifacts

Each run writes:

- `data/benchmarks/crud_rag_v1_<timestamp>/dataset_converted.json`
- `data/benchmarks/crud_rag_v1_<timestamp>/benchmark_manifest.json`
- `data/benchmarks/crud_rag_v1_<timestamp>/rag_eval/summary.json`
- `data/benchmarks/crud_rag_v1_<timestamp>/rag_eval/report.md`

## 5) Notes on labels

The CRUD wrapper currently uses keyword anchors from source texts as expected labels
for retrieval matching. This keeps integration lightweight and reproducible with the
existing `run_rag_eval.py` metric pipeline.
