# Knowledge Base Bulk Import

This repo includes a local bulk import script:

- `scripts/bulk_import_kb.py`

It supports:

- local file import from one or more directories
- optional URL import from a text file (one URL per line)
- embedding runtime guard (blocks API embedding by default)

## 1) Dry run

```powershell
.\venv\Scripts\python.exe .\scripts\bulk_import_kb.py `
  --kb-id kb_crud_rag_v1 `
  --source-dir .\learn_proj\CRUD_RAG\data\80000_docs `
  --dry-run
```

## 2) Import local files

```powershell
.\venv\Scripts\python.exe .\scripts\bulk_import_kb.py `
  --kb-id kb_crud_rag_v1 `
  --source-dir .\learn_proj\CRUD_RAG\data\80000_docs `
  --allow-extensionless-txt `
  --continue-on-error
```

## 3) Import URLs in batch

Prepare `urls.txt` with one URL per line, then:

```powershell
.\venv\Scripts\python.exe .\scripts\bulk_import_kb.py `
  --kb-id kb_crud_rag_v1 `
  --urls-file .\urls.txt `
  --continue-on-error
```

## 4) Embedding safety guard

By default, the script refuses to run when embedding provider is API-based.

Use these overrides only when needed:

- `--allow-api-embedding`: allow API embedding
- `--allow-cpu-embedding`: allow local embedding without GPU offload

