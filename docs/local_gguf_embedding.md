# Local GGUF Embedding Setup

This project supports local GGUF embedding models via `llama-cpp-python`.

## 1) Install dependency

Use the project venv:

```powershell
./venv/Scripts/pip install llama-cpp-python
```

## 2) Put GGUF model file

Default path in RAG settings:

```text
models/embeddings/qwen3-embedding-0.6b.gguf
```

You can also set a custom absolute path in **Settings -> RAG -> Embedding Provider = Local GGUF**.

## 3) Configure RAG settings

- `Embedding Provider`: `Local GGUF (llama.cpp)`
- `GGUF Model Path`: path to your `.gguf`
- `GGUF Context Length`: default `2048`
- `GGUF CPU Threads`: `0` (auto)
- `GGUF GPU Layers`: `0` for CPU-only, increase if GPU is available
- `Normalize Embeddings`: recommended `on`

## 4) Rebuild vectors

If you switch embedding model/provider, existing vectors may have different dimensions.
Re-process knowledge base documents (and memory vectors if needed) after switching.
