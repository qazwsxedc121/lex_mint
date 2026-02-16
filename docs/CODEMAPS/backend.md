<!-- Generated: 2026-02-17 (Updated) | Files scanned: ~100 | Token estimate: ~950 -->

# Backend Architecture

## Entry Point
`src/api/main.py` (154 lines) - FastAPI app, startup hooks, router registration

## Route Map

### Core Chat
```
POST /api/chat/stream         -> chat.py -> AgentServiceSimple.stream_chat() -> simple_llm.call_llm_stream()
POST /api/chat/{id}/regenerate/{idx} -> chat.py -> AgentServiceSimple.regenerate()
DELETE /api/chat/{id}/messages/{idx} -> chat.py -> ConversationStorage
POST /api/chat/compress-context -> chat.py -> CompressionService
POST /api/chat/compare        -> chat.py -> AgentServiceSimple (multi-model SSE)
POST /api/chat/upload          -> chat.py -> FileService
```

### Sessions
```
CRUD /api/sessions             -> sessions.py -> ConversationStorage
PATCH /api/sessions/{id}/model -> sessions.py -> ConversationStorage.update_metadata()
POST /api/sessions/{id}/branch -> sessions.py -> ConversationStorage.branch()
POST /api/sessions/import/*    -> sessions.py -> ConversationStorage (ChatGPT JSON/ZIP, Markdown)
POST /api/sessions/search      -> sessions.py -> ConversationStorage.search()
```

### Models & Providers
```
CRUD /api/models               -> models.py -> ModelConfigService
CRUD /api/providers            -> models.py -> ModelConfigService
POST /api/providers/{id}/test  -> models.py -> AdapterRegistry.test_connection()
POST /api/providers/{id}/fetch-models -> models.py -> AdapterRegistry.fetch_models()
```

### Knowledge & Memory
```
CRUD /api/knowledge-bases      -> knowledge_base.py -> KnowledgeBaseService -> ChromaDB
POST /api/knowledge-bases/{id}/documents -> knowledge_base.py -> DocumentProcessingService
CRUD /api/memory               -> memory.py -> MemoryService -> ChromaDB
POST /api/memory/extract       -> memory.py -> MemoryService.extract_from_session()
```

### Projects
```
CRUD /api/projects             -> projects.py -> ProjectService
GET /api/projects/{id}/tree    -> projects.py -> ProjectService.get_file_tree()
CRUD /api/projects/{id}/files  -> projects.py -> ProjectService (file ops)
POST /api/projects/{id}/search -> projects.py -> ProjectService.search()
```

### Feature Configs (pattern: GET + PUT for each)
```
/api/title-generation-config, /api/followup-config, /api/compression-config,
/api/translation-config, /api/tts-config, /api/search-config,
/api/webpage-config, /api/rag-config, /api/file-reference-config
```

### Prompt Templates
```
CRUD /api/prompt-templates     -> prompt_templates.py -> PromptTemplateConfigService
GET /api/prompt-templates/{id} -> prompt_templates.py -> PromptTemplateConfigService.get_template()
```

## Key Services

| Service | File | Lines | Purpose |
|---------|------|-------|---------|
| ConversationStorage | conversation_storage.py | 1,504 | Markdown file persistence, per-file locks |
| AgentServiceSimple | agent_service_simple.py | 1,224 | Chat orchestration, RAG/memory/search integration |
| CompressionService | compression_service.py | 1,260 | Hierarchical context compression |
| ProjectService | project_service.py | 1,066 | File tree, CRUD, search |
| ModelConfigService | model_config_service.py | 929 | Provider/model YAML config management |
| RagService | rag_service.py | ~400 | Vector retrieval via ChromaDB |
| RerankService | rerank_service.py | ~100 | Model-based reranking of retrieval results |
| PromptTemplateConfigService | prompt_template_service.py | ~100 | YAML-backed prompt template CRUD |
| MemoryService | memory_service.py | 729 | Long-term memory extraction/retrieval |
| WebpageService | webpage_service.py | 751 | Web scraping via trafilatura |
| PricingService | pricing_service.py | ~300 | Token cost calculation |

## Provider Adapter Pattern

```
src/providers/
  base.py          - Abstract adapter interface (create_llm, stream, invoke, fetch_models, test_connection)
  registry.py      - AdapterRegistry: provider -> adapter mapping
  types.py         - StreamChunk, ProviderConfig types
  builtin.py       - Default provider configs
  adapters/
    openai_adapter.py     - OpenAI SDK + compatible providers
    deepseek_adapter.py   - DeepSeek (thinking mode support)
    anthropic_adapter.py  - Claude models
    ollama_adapter.py     - Local Ollama models
    xai_adapter.py        - Grok models
```

## Chat Request Flow
1. Frontend POST `/api/chat/stream` (SSE)
2. Router validates, extracts session_id + message
3. AgentServiceSimple loads session, assistant, model config
4. Optional: RAG retrieval, memory injection, web search
5. `call_llm_stream()` -> AdapterRegistry -> provider adapter
6. SSE chunks streamed back: `{type: "token", content: "..."}`, `{type: "usage", ...}`
7. ConversationStorage appends messages to Markdown file
