# CRUD Corpus Specialized Importer

For CRUD-RAG alignment, use:

- `scripts/import_crud_corpus_to_kb.py`

This importer is specialized for `learn_proj/CRUD_RAG/data/80000_docs`, but it
**uses the normal KB upload processing flow**:

- write source file into KB storage path
- create `KnowledgeBaseDocument` record
- call `DocumentProcessingService.process_document(...)`

So behavior stays consistent with normal upload indexing logic.

## Preconditions

- target KB already exists (example: `kb_crud_rag_v1`)
- embedding runtime is local GPU (script blocks API embedding by default)

## Dry run

```powershell
.\venv\Scripts\python.exe .\scripts\import_crud_corpus_to_kb.py `
  --kb-id kb_crud_rag_v1 `
  --dry-run `
  --max-docs 500
```

## Full import

```powershell
.\venv\Scripts\python.exe .\scripts\import_crud_corpus_to_kb.py `
  --kb-id kb_crud_rag_v1 `
  --workers 2 `
  --continue-on-error `
  --progress-every 100
```

## Resume controls

- `--skip-existing` (default): skip existing deterministic `doc_id`
- `--start-offset N`: skip first N corpus records
- `--max-docs N`: cap this run for phased import
- `--workers N`: concurrent processing workers (start with `2`, then tune)
- `--lines-per-doc N`: merge N source lines into one imported doc for faster ingest
- `--metadata-flush-size N`: batch metadata writes to reduce YAML save overhead

## Notes

- By default one corpus line maps to one `.txt` document in KB (`--lines-per-doc 1`).
- This keeps alignment with CRUD corpus while preserving indexing consistency.
- Import logs include `elapsed_s` and `import_per_s` to compare settings.
- GPU usage can look "spiky" for small text docs; fan speed may stay low even when
  CUDA offload is enabled.
- For speed-sensitive benchmark runs, `--lines-per-doc 16` or `32` is recommended.
- For large runs, keep `--metadata-flush-size` at `50` or higher for better throughput.
