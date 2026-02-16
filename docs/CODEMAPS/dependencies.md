<!-- Generated: 2026-02-17 | Files scanned: ~10 | Token estimate: ~600 -->

# Dependencies

## External LLM Providers (via adapter pattern)

| Provider | Adapter | SDK | Notes |
|----------|---------|-----|-------|
| DeepSeek | deepseek_adapter.py | langchain-deepseek | Primary provider, thinking mode |
| OpenAI | openai_adapter.py | langchain-openai | Also handles OpenAI-compatible APIs |
| Anthropic | anthropic_adapter.py | langchain-anthropic | Claude models |
| Ollama | ollama_adapter.py | langchain-openai | Local models |
| XAI | xai_adapter.py | langchain-openai | Grok models |
| OpenRouter | (via openai_adapter) | langchain-openai | Model aggregator |

## Backend Dependencies (key packages)

**Framework:**
- fastapi >= 0.109.0, uvicorn, pydantic >= 2.5.0, pydantic-settings

**LangChain Ecosystem:**
- langgraph >= 0.2.0, langchain-openai, langchain-deepseek, langchain-anthropic
- langchain-chroma, langchain-text-splitters

**RAG & Embeddings:**
- chromadb >= 0.5.0 (vector DB)
- llama-cpp-python >= 0.3.0 (local GGUF embeddings)
- pypdf, python-docx (document parsing)

**Tools:**
- ddgs >= 9.10.0 (DuckDuckGo web search)
- trafilatura >= 1.8.0 (web scraping)
- edge-tts >= 6.1.0 (text-to-speech, Microsoft Edge)
- langdetect (language detection)

**Storage:**
- python-frontmatter (Markdown + YAML)
- aiofiles (async file I/O)
- pyyaml (YAML config)

## Frontend Dependencies (key packages)

**Core:** react 19.2.0, react-dom, react-router-dom 7.13.0, vite 7.2.4, typescript 5.9.3

**UI:** @tailwindcss/postcss 4, @headlessui/react, @heroicons/react, lucide-react, @dnd-kit/*

**Markdown:** react-markdown, remark-gfm, remark-math, rehype-katex, react-syntax-highlighter, mermaid

**Editor:** @uiw/react-codemirror, @codemirror/lang-*

**State:** zustand 5.0.10, axios, i18next, react-i18next

## Observability (Optional)
- LangSmith tracing via LANGCHAIN_API_KEY env var

## Infrastructure
- Docker: docker-compose.yml, Dockerfile.backend, Dockerfile.frontend
- No external database service required
