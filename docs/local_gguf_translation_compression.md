# Local GGUF Translation and Compression

You can run translation and context summarization with local GGUF LLMs via `llama-cpp-python`.

## 1) Prepare model files

Recommended default paths:

- Translation model: `models/llm/local-translate.gguf`
- Summarization model: `models/llm/local-summarizer.gguf`

You can also set absolute paths in settings.

## 2) Translation settings

Open **Settings -> Translation**:

- `Translation Provider`: `Local GGUF (llama.cpp)`
- Set GGUF path and runtime params (`n_ctx`, threads, GPU layers, max tokens)

## 3) Compression settings

Open **Settings -> Compression**:

- `Compression Provider`: `Local GGUF (llama.cpp)`
- Set GGUF path and runtime params (`n_ctx`, threads, GPU layers, max tokens)

## 4) Notes

- `temperature` in settings still applies to local GGUF generation.
- For longer history/input, increase `n_ctx`.
- If generation is too short, increase `GGUF Max Output Tokens`.
- `<think>...</think>` blocks are automatically filtered from displayed/stored translation and summaries.
