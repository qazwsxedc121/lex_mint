# OpenWebUI RAG 深度研究（主动式 / 检索增强）

> 研究对象：`learn_proj/open-webui`（本地源码）
>
> 研究日期：2026-02-19
>
> 说明：本稿聚焦 OpenWebUI 当前实现里“主动式 RAG”与“混合检索”主路径，重点回答它如何在对话时自动发起检索、拼接上下文并回传引用。

---

## 1. 结论先行

OpenWebUI 的 RAG 是“应用内一体化”实现，不是 sidecar 服务，核心特征有四点：

1. **主动式检索触发**：对话时先用 LLM 生成 retrieval queries（`type: "retrieval"`），再去知识源检索；失败则回退到“最后一条用户消息”作为查询词。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1204`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1206`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1244`。
2. **自动注入检索上下文**：检索结果被格式化为 `<source ...>` 片段，经 `RAG_TEMPLATE` 注入消息（system 或 user 侧），模型直接消费。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:289`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:312`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:324`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1876`。
3. **“模型绑定知识”自动参检**：`model.meta.knowledge` 会在每轮推理前并入 `files`，无需用户手动附加。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1485`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1503`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1524`。
4. **检索策略可切换**：向量检索与 Hybrid（BM25 + 向量 + rerank）并存，且有权重、阈值、topK 等参数。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:2399`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:210`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:270`、`learn_proj/open-webui/backend/open_webui/config.py:2707`。

---

## 2. 架构总览（入库 + 在线检索）

```text
Upload/File/URL/WebSearch
  -> routers/retrieval.py
  -> save_docs_to_vector_db (split/chunk/embed/insert)
  -> VECTOR_DB collections (file-{id} / knowledge_id / web-search-{hash})

Chat Runtime
  -> utils/middleware.py
     1) gather files (incl. model.meta.knowledge auto attach)
     2) generate retrieval queries (optional, proactive)
     3) get_sources_from_items(...)
     4) apply_source_context_to_messages(..., RAG_TEMPLATE)
     5) emit sources for citations/UI

Retrieval Engine
  -> retrieval/utils.py
     - vector query_doc/query_collection
     - hybrid query_doc_with_hybrid_search
       (BM25 + vector + contextual compression + rerank)
```

主要模块分工：

- **API 编排层**：`routers/retrieval.py` 负责文件/网页处理、入库、查询接口。
- **检索算法层**：`retrieval/utils.py` 负责向量召回、Hybrid 合并、重排、source 组装。
- **对话集成层**：`utils/middleware.py` 负责主动 query 生成、调用检索、上下文注入、引用事件。
- **知识关系层**：`models/knowledge.py` + `routers/knowledge.py` 负责 KB 与文件关系和权限。

---

## 3. 入库链路（File / URL / Web Search）

### 3.1 文件入库：`process_file`

入口：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1581`

关键行为：

1. **collection 命名**：默认 `file-{file.id}`。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1600`。
2. **三种来源路径**：
   - 直接内容更新（`form_data.content`），用于内容更新/音频转写后写回。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1603`。
   - 追加到现有 collection（知识库 add/update 场景）。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1630`。
   - 从存储读取文件并走 Loader 抽取文本（pdf/doc 等）。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1664`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1699`。
3. **可绕过 embedding/retrieval**：`BYPASS_EMBEDDING_AND_RETRIEVAL` 开启时只保留文本，不写向量库。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1739`。
4. **正常路径写向量库**：调用 `save_docs_to_vector_db`，附带 `file_id/name/hash` metadata。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1750`。

### 3.2 切分 + Embedding：`save_docs_to_vector_db`

入口：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1380`

关键机制：

1. **重复内容检测**：按 metadata.hash 查询，命中即报重复。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1410`。
2. **双层切分策略**：
   - 可选 markdown header splitter；
   - 再走 character 或 token splitter（`CHUNK_SIZE`/`CHUNK_OVERLAP`）。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1424`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1458`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1470`。
3. **embedding 抽象层**：根据 `RAG_EMBEDDING_ENGINE/MODEL` 动态选择函数，支持 async batching。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1510`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:789`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:827`。
4. **最终写入向量库**：每 chunk 生成 `id/text/vector/metadata` 后 insert。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1551`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1562`。

### 3.3 URL 与 Web Search 入库

- **单 URL**：`process_web` 抓取内容后可直接写入 collection（默认 URL hash）。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1861`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1876`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:1879`。
- **多查询网页搜索**：`process_web_search` 先 search engine 拿 URL，再 loader 抓正文，最后写入 `web-search-{hash}` collection。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:2214`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:2272`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:2318`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:2350`。

---

## 4. 在线检索链路（主动式 RAG 主路径）

### 4.1 对话前半段：自动生成 retrieval 查询词

入口：`chat_completion_files_handler`  
`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1193`

流程：

1. 读取 `body.metadata.files`；若并非全部 full-context，则触发 query generation。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1199`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1204`。
2. 调用 `generate_queries(..., type="retrieval")`，并解析 JSON。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1206`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1211`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1225`。
3. 若失败或空列表，回退 `queries=[last_user_message]`。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1244`。
4. 发 `queries_generated` 与 `sources_retrieved` 状态事件给 UI。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1233`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1298`。

### 4.2 查询生成实现：`routers/tasks.py`

入口：`learn_proj/open-webui/backend/open_webui/routers/tasks.py:460`

要点：

- 仅在 `ENABLE_RETRIEVAL_QUERY_GENERATION` 开启时允许 retrieval query 生成。参考：`learn_proj/open-webui/backend/open_webui/routers/tasks.py:472`、`learn_proj/open-webui/backend/open_webui/routers/tasks.py:473`。
- 使用模板 `QUERY_GENERATION_PROMPT_TEMPLATE`，未配置则回退默认模板。参考：`learn_proj/open-webui/backend/open_webui/routers/tasks.py:510`、`learn_proj/open-webui/backend/open_webui/routers/tasks.py:513`。
- 最终走一次非流式 chat completion 获取查询列表。参考：`learn_proj/open-webui/backend/open_webui/routers/tasks.py:517`、`learn_proj/open-webui/backend/open_webui/routers/tasks.py:536`。

### 4.3 检索聚合：`get_sources_from_items`

入口：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:934`

能力：

1. 统一处理多种 item：`text/note/chat/url/file/collection/docs`。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:959`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:995`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1041`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1087`。
2. full-context 或 bypass 时走“全文直接注入”；否则回退到 collection 名并向量/混合检索。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1043`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1088`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1145`。
3. 权限检查内建于 note/chat/collection 分支（owner/admin/access_control）。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:999`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1014`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1091`。
4. 最终统一组装 `sources=[{source, document, metadata, distances?}]`，供注入与引用展示。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1192`。

### 4.4 上下文注入：`apply_source_context_to_messages`

入口：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:289`

行为：

- 将检索到的 doc+meta 转成 `<source id="n" name="...">...</source>` 上下文串。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:305`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:312`。
- 按 `RAG_TEMPLATE` 生成最终提示内容，追加到 system 或 user message。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:321`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:324`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:330`。
- 主聊天流程中，在真正请求模型前执行此注入。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1875`。

---

## 5. Hybrid / Rerank 机制

### 5.1 纯向量检索

- 单 collection：`query_doc` -> `VECTOR_DB_CLIENT.search`。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:138`。
- 多 collection：`query_collection` 先批量算 query embeddings，再线程池并发查询并 merge/sort。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:405`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:429`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:456`。

### 5.2 Hybrid 检索（BM25 + 向量 + 压缩重排）

- 核心函数：`query_doc_with_hybrid_search`。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:210`。
- BM25 文本可选 enriched（文件名、标题、章节、source、snippet）增强召回。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:172`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:243`。
- 用 `hybrid_bm25_weight` 控制 BM25 与向量比例。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:261`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:270`。
- 用 `RerankCompressor`（外部 reranker 或余弦相似度）做 top_n+阈值裁剪。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:275`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1259`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1294`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1317`。

### 5.3 API 层开关

- `/query/doc` 和 `/query/collection` 根据 `ENABLE_RAG_HYBRID_SEARCH` 与请求参数 `hybrid` 选择路径。参考：`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:2399`、`learn_proj/open-webui/backend/open_webui/routers/retrieval.py:2473`。

---

## 6. 知识库模型与权限

### 6.1 数据模型

- `knowledge` 主表（含 `access_control`）+ `knowledge_file` 关联表（knowledge_id/file_id 唯一）。参考：`learn_proj/open-webui/backend/open_webui/models/knowledge.py:43`、`learn_proj/open-webui/backend/open_webui/models/knowledge.py:91`、`learn_proj/open-webui/backend/open_webui/models/knowledge.py:105`。

### 6.2 文件与知识库关系维护

- add/update/remove file 到知识库并同步向量库。参考：`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:532`、`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:601`、`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:670`。
- remove 时会清理 knowledge collection 与 `file-{id}` collection（可选删除文件实体）。参考：`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:708`、`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:723`。
- 删除知识库时会遍历模型，把 `model.meta.knowledge` 中该 KB 引用移除。参考：`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:751`、`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:780`、`learn_proj/open-webui/backend/open_webui/routers/knowledge.py:788`。

### 6.3 模型知识自动参与检索

- 聊天中自动把 `model.meta.knowledge` 转为 file/collection 条目并并入 `form_data["files"]`。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1485`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1503`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1525`。

---

## 7. Web Search 与工具引用并轨

OpenWebUI 的“检索上下文”不仅来自文件向量检索，还来自工具结果：

1. `search_web` / `view_knowledge_file` / `query_knowledge_files` 的 tool result 会被解析为 citation sources。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:163`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:191`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:220`。
2. 工具调用循环里，这些 sources 一方面 `event_emitter` 发给 UI，另一方面也会再次注入消息上下文。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:3340`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:3387`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:3394`。

这意味着：**文件 RAG 与工具检索共享同一套“引用-注入”机制**，前端引用体验与模型可见上下文一致。

---

## 8. 配置面（主动式 RAG 关键开关）

### 8.1 查询生成

- `ENABLE_SEARCH_QUERY_GENERATION`、`ENABLE_RETRIEVAL_QUERY_GENERATION`。参考：`learn_proj/open-webui/backend/open_webui/config.py:1866`、`learn_proj/open-webui/backend/open_webui/config.py:1872`。
- `QUERY_GENERATION_PROMPT_TEMPLATE` 与默认模板（强调“有不确定就倾向生成查询”）。参考：`learn_proj/open-webui/backend/open_webui/config.py:1879`、`learn_proj/open-webui/backend/open_webui/config.py:1885`。

### 8.2 RAG 检索策略

- `RAG_TOP_K`、`RAG_TOP_K_RERANKER`、`RAG_RELEVANCE_THRESHOLD`、`RAG_HYBRID_BM25_WEIGHT`。参考：`learn_proj/open-webui/backend/open_webui/config.py:2707`。
- `ENABLE_RAG_HYBRID_SEARCH`、`ENABLE_RAG_HYBRID_SEARCH_ENRICHED_TEXTS`、`RAG_FULL_CONTEXT`。参考：`learn_proj/open-webui/backend/open_webui/config.py:2726`、`learn_proj/open-webui/backend/open_webui/config.py:2732`、`learn_proj/open-webui/backend/open_webui/config.py:2739`。

### 8.3 切分与模板

- `CHUNK_SIZE` 默认 `1000`，`CHUNK_OVERLAP` 默认 `100`。参考：`learn_proj/open-webui/backend/open_webui/config.py:2911`、`learn_proj/open-webui/backend/open_webui/config.py:2921`。
- `RAG_TEMPLATE` 默认模板明确要求仅在 `<source id>` 存在时输出 `[id]` 引用。参考：`learn_proj/open-webui/backend/open_webui/config.py:2927`、`learn_proj/open-webui/backend/open_webui/config.py:2953`。

---

## 9. 风险与边界（实现细节观察）

1. **Hybrid 回退逻辑疑似条件不一致**：代码注释写“hybrid 失败回退 non-hybrid”，但条件是 `if not hybrid_search and query_result is None`，当 `hybrid_search=True` 且 hybrid 失败时可能不会真正执行 non-hybrid。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1171`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1175`。
2. **主动 query 生成依赖 LLM 输出可解析 JSON**：虽然有字符串兜底，但质量受模型与模板强相关，存在 query 漂移风险。参考：`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1218`、`learn_proj/open-webui/backend/open_webui/utils/middleware.py:1227`。
3. **full-context 模式可能放大上下文 token 成本**：collection/file 走全文拼接时，长文档会直接进入 prompt。参考：`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1050`、`learn_proj/open-webui/backend/open_webui/retrieval/utils.py:1120`。

---

## 10. 对 lex_mint_rag 的落地启发（按当前进展重排）

面向当前阶段（主动式主链路已具备），建议优先级如下：

1. **先做质量门禁**：把 retrieval 查询生成与工具调用效果放进真实问题回归，阈值化并接入 CI。
2. **统一 source 协议**：对齐 OpenWebUI 的 `source/document/metadata` 思路，把 KB/附件/网页/工具结果并轨到同一 citation 渲染链路。
3. **增强策略调度**：在现有 planner 基础上做轻量 query intent routing，动态选择检索参数与策略。
4. **优化工具行为**：针对证据型问题提高 `read_knowledge` 触发率，抑制重复 `search_knowledge`。
5. **持续保留可回退路径**：主动检索失败时回退策略必须稳定，避免链路在真实请求中中断或半截输出。

