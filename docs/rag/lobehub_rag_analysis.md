# LobeHub RAG 深度研究（主动式 / 工具式）

> 研究对象：`learn_proj/lobehub`（本地源码）
>
> 研究日期：2026-02-19
>
> 说明：本稿聚焦 LobeHub 当前主线实现里“主动式 RAG”的工程落地方式（工具调用 + 上下文注入）。

---

## 1. 结论先行

LobeHub 的 RAG 不是 sidecar，而是“应用内一体化”方案：上传、切分、向量化、检索都在主工程内完成。

1. **主动式 RAG 的核心不是“自动拼接检索结果”，而是“给模型一个知识库工具”**：`lobe-knowledge-base`，包含 `searchKnowledgeBase` + `readKnowledge` 两阶段。参考：`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/types.ts:3`、`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/manifest.ts:11`、`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/manifest.ts:35`。
2. **“文件内容直注入 + 知识库工具检索”双轨并存**：Agent files 会把全文注入上下文，Knowledge Base 只注入元信息并提示走工具检索。参考：`learn_proj/lobehub/packages/prompts/src/prompts/files/knowledgeBase.ts:49`、`learn_proj/lobehub/packages/prompts/src/prompts/files/knowledgeBase.ts:57`。
3. **在线检索是向量检索主导**：query embedding（1024 维）+ `cosineDistance` 排序 + topK。参考：`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:260`、`learn_proj/lobehub/packages/database/src/models/chunk.ts:191`。
4. **Rerank/Hybrid 配置已预留但主链路未实装**：有 `reranker_model` / `query_mode` 配置解析，但检索路径仍是向量召回，且代码留有 TODO rerank。参考：`learn_proj/lobehub/src/server/globalConfig/parseFilesConfig.ts:8`、`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:287`、`learn_proj/lobehub/.env.example:374`。

---

## 2. 架构总览（从数据层到运行时）

```text
Upload File
  -> files/documents (+ knowledge_base_files relation)
  -> async chunk task
  -> chunks + file_chunks
  -> async embedding task
  -> embeddings (vector 1024)

Runtime Chat
  -> context-engine:
      - inject full agent files
      - inject KB metadata + instruction
  -> tools-engine:
      - enable lobe-knowledge-base when agent has enabled KB
  -> model decides:
      searchKnowledgeBase(query) -> returns file-level summaries/chunks
      readKnowledge(fileIds)     -> returns full file contents
  -> model synthesis answer with citations
```

关键结构：
- RAG 表：`chunks` / `embeddings`（vector 1024）/ `knowledge_base_files`。参考：`learn_proj/lobehub/packages/database/src/schemas/rag.ts:19`、`learn_proj/lobehub/packages/database/src/schemas/rag.ts:72`、`learn_proj/lobehub/packages/database/src/schemas/file.ts:216`。
- agent 与知识绑定：`agentsFiles`、`agentsKnowledgeBases`。参考：`learn_proj/lobehub/packages/database/src/schemas/relations.ts:122`。

---

## 3. 入库链路（上传 -> 切分 -> 向量化）

### 3.1 上传后自动触发切分

前端上传完成后，会筛选支持切分的文件并调用 `parseFilesToChunks`：
- `pushDockFileList` 上传完成后自动触发解析：`learn_proj/lobehub/src/store/file/slices/fileManager/action.ts:263`
- 调用 RAG 服务创建解析任务：`learn_proj/lobehub/src/store/file/slices/fileManager/action.ts:184`

### 3.2 异步切分任务

- 任务创建与触发：`ChunkService.asyncParseFileToChunks`，并写回 `chunkTaskId`。参考：`learn_proj/lobehub/src/server/services/chunk/index.ts:70`、`learn_proj/lobehub/src/server/services/chunk/index.ts:84`。
- 切分执行入口：`async/file.ts -> parseFileToChunks`。参考：`learn_proj/lobehub/src/server/routers/async/file.ts:157`。
- 切分器默认走 LangChain loaders，规则可由 `FILE_TYPE_CHUNKING_RULES` 控制。参考：`learn_proj/lobehub/src/server/modules/ContentChunk/index.ts:26`。
- 默认 chunk 参数：`chunkSize=800`、`chunkOverlap=400`。参考：`learn_proj/lobehub/src/libs/langchain/loaders/config.ts:2`。

### 3.3 异步 embedding 任务

- 任务创建：`ChunkService.asyncEmbeddingFileChunks`，写回 `embeddingTaskId`。参考：`learn_proj/lobehub/src/server/services/chunk/index.ts:33`、`learn_proj/lobehub/src/server/services/chunk/index.ts:44`。
- 批处理参数：`CHUNK_SIZE=50`、`CONCURRENCY=10`。参考：`learn_proj/lobehub/src/server/routers/async/file.ts:89`。
- embedding 维度固定 1024。参考：`learn_proj/lobehub/src/server/routers/async/file.ts:106`。
- 切分成功后可自动触发 embedding（默认非 `0` 即开）：`CHUNKS_AUTO_EMBEDDING`。参考：`learn_proj/lobehub/src/server/routers/async/file.ts:250`、`learn_proj/lobehub/src/envs/file.ts:24`。

---

## 4. 在线检索链路（主动式 RAG 主路径）

### 4.1 工具启用逻辑

- KnowledgeBase 工具注册为 builtin tool：`learn_proj/lobehub/src/tools/index.ts:47`。
- executor 注册：`learn_proj/lobehub/src/store/tool/slices/builtin/executors/index.ts:12`、`learn_proj/lobehub/src/store/tool/slices/builtin/executors/index.ts:128`。
- 仅当 agent 存在启用中的知识库时才启用该工具：`learn_proj/lobehub/src/server/modules/Mecha/AgentToolsEngine/index.ts:126`。

### 4.2 工具契约：先搜后读

- `searchKnowledgeBase`：返回相关文件摘要 + top chunks。`readKnowledge`：按 fileIds 拉全文。参考：`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/manifest.ts:9`、`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/manifest.ts:33`。
- 系统提示强约束“先 search，再 read”：`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/systemRole.ts:76`。

### 4.3 搜索执行细节

在 `knowledgeBaseExecutor.searchKnowledgeBase` 中：
- 取当前 agent 启用的 knowledgeBaseIds：`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/executor/index.ts:44`
- 调用 `ragService.semanticSearchForChat`：`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/executor/index.ts:50`

在后端 `semanticSearchForChat` 中：
- query 截断到 8000 字符再做 embedding：`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:257`
- embedding 维度 1024：`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:260`
- `knowledgeIds -> fileIds` 扩展：`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:269`
- 数据层按 `cosineDistance` 排序 + topK：`learn_proj/lobehub/packages/database/src/models/chunk.ts:191`、`learn_proj/lobehub/packages/database/src/models/chunk.ts:215`
- file 级相关度 = 文件内 top3 chunk 相似度均值：`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:75`

### 4.4 结果编排与二阶段读取

- Search 结果格式化为 XML（含 fileId/fileName/relevance/chunks），并明确提示再调用 read：`learn_proj/lobehub/packages/prompts/src/prompts/knowledgeBaseQA/formatSearchResults.ts:46`。
- Read 阶段读取全文并格式化为 XML files：`learn_proj/lobehub/packages/builtin-tool-knowledge-base/src/executor/index.ts:90`、`learn_proj/lobehub/packages/prompts/src/prompts/knowledgeBaseQA/formatFileContents.ts:27`。

---

## 5. 上下文注入策略（“主动式”的重要补充）

LobeHub 的“主动”不仅在工具调用，还在 **首轮用户消息前的知识注入**：

- `KnowledgeInjector` 把知识注入统一拼成 `promptAgentKnowledge`：`learn_proj/lobehub/packages/context-engine/src/providers/KnowledgeInjector.ts:38`。
- 注入发生在 first user message 之前（BaseFirstUserContentProvider）：`learn_proj/lobehub/packages/context-engine/src/base/BaseFirstUserContentProvider.ts:10`、`learn_proj/lobehub/packages/context-engine/src/base/BaseFirstUserContentProvider.ts:137`。
- MessagesEngine 管线明确把 KnowledgeInjector 放在前置注入阶段：`learn_proj/lobehub/packages/context-engine/src/engine/messages/MessagesEngine.ts:177`。
- Server 侧将 agent 配置里的 enabled files 内容与 enabled KB 元信息喂入 context-engine：`learn_proj/lobehub/src/server/services/aiAgent/index.ts:335`、`learn_proj/lobehub/src/server/services/aiAgent/index.ts:343`。

这使得模型在第一轮就知道：
1) 哪些“文件全文”可直接用；
2) 哪些“知识库”需要先走 `searchKnowledgeBase`。

---

## 6. 权限模型与生命周期

### 6.1 正向设计

- 多数模型查询按 `userId` 过滤（如 `FileModel.findById`、`KnowledgeBaseModel.findById`、`AgentModel.getAgentConfig`）。参考：`learn_proj/lobehub/packages/database/src/models/file.ts:299`、`learn_proj/lobehub/packages/database/src/models/knowledgeBase.ts:143`、`learn_proj/lobehub/packages/database/src/models/agent.ts:82`。

### 6.2 删除清理链路

- 删文件会级联清理 embeddings/documentChunks/chunks/fileChunks，且分批并发处理。参考：`learn_proj/lobehub/packages/database/src/models/file.ts:355`、`learn_proj/lobehub/packages/database/src/models/file.ts:386`、`learn_proj/lobehub/packages/database/src/models/file.ts:418`。

### 6.3 边界风险（需重点复核）

在检索路径里有两个点值得安全复核：
1. `semanticSearchForChat` 里通过 `knowledgeIds` 查 `knowledge_base_files` 时，条件只看 `knowledgeBaseId`，未显式加 `userId`。参考：`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:270`。
2. `ChunkModel.semanticSearchForChat` 的 where 条件仅为 `fileId in (...)`，未显式加 `chunks.userId/fileChunks.userId`。参考：`learn_proj/lobehub/packages/database/src/models/chunk.ts:212`。

> 这不一定等于漏洞（取决于上游 ID 不可猜测性、DB 隔离策略等），但对多租户场景建议做显式 userId 约束加固。

---

## 7. 配置项与当前实现差距

1. `DEFAULT_FILES_CONFIG` 支持配置 `embedding_model`、`reranker_model`、`query_mode`。参考：`learn_proj/lobehub/src/server/globalConfig/parseFilesConfig.ts:6`。
2. 默认常量也包含 rerank 与 queryMode。参考：`learn_proj/lobehub/packages/const/src/settings/knowledge.ts:21`。
3. 但检索主链路仅使用 embedding model，且有 `TODO: need to rerank the chunks`。参考：`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:249`、`learn_proj/lobehub/src/server/routers/lambda/chunk.ts:287`。
4. `.env.example` 也直接标注 reranker “unImplemented”。参考：`learn_proj/lobehub/.env.example:374`。

---

## 8. 与 LibreChat 的关键差异（为 lex_mint 选型）

相较我们刚分析的 LibreChat（主应用 + 外部 rag_api）：

1. **架构形态**：LobeHub 是应用内一体化；LibreChat 是 sidecar RAG API。
2. **主动式实现**：LobeHub 强调“知识库工具 + 上下文注入协同”；LibreChat 主体是 `file_search` 工具 + 独立向量服务。
3. **知识分层策略**：LobeHub 明确区分“agent files 直接注入”与“knowledge bases 先检索后读取”，这点非常值得借鉴。

---

## 9. 对 lex_mint_rag 的落地启发（按当前进展重排）

### Sprint 1（质量门禁）
- 固化真实问题回归集（不显式提示 function call）。
- 明确基线阈值：Recall@K / MRR / citation hit rate，并接入 CI 阻断。
- 新增工具链路指标：`read` 触发率、重复 `search` 比率、最终收敛轮次。

### Sprint 2（工具行为治理）
- 强化“先搜后读”策略稳定性（证据型请求优先 `read_knowledge`）。
- 加入重复 search 抑制（相似 query 限次）。
- 保持聊天前知识感知注入，但避免过量全文注入。

### Sprint 3（治理与扩展）
- 统一附件/网页/KB 的 source/citation 协议与渲染。
- 设计并落地 KB ACL（owner/read/write 或 assistant scope）。
- 在现有检索栈基础上引入轻量 intent routing（按 query 类型切策略）。

---

## 10. 一句话结论

LobeHub 的“主动式 RAG”本质是：**前置知识感知（context injection）+ 工具驱动两阶段检索（search -> read）+ 应用内向量链路**。这条路线非常适合我们在 lex_mint_rag 里做“可控、可解释、可扩展”的 Agent RAG。

