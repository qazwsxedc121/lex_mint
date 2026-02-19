# lex_mint 主动式 RAG 实施方案 v1（P0 设计稿）

> 基于当前代码现状拆解（`src/api/services/agent_service_simple.py`、`src/api/services/rag_service.py`、`src/agents/simple_llm.py`）  
> 目标：补齐“主动式 RAG 编排层”三件事：**Query Planner / 结构化 Source 注入 / 工具式 RAG**

---

## 1. 目标与边界

### 1.1 目标（P0）

1. 在检索前自动生成 1~3 个 retrieval queries（失败回退原 query）。  
2. 将 RAG 结果按结构化 source 协议注入 prompt（不是纯文本拼接）。  
3. 提供最小工具式 RAG：`search_knowledge` + `read_knowledge`。

### 1.2 非目标（本期不做）

- 不重写现有 RAG 检索内核（hybrid/RRF/rerank/CRAG 保持）。  
- 不改现有会话存储格式（仍兼容当前 `sources` 结构）。  
- 不做复杂 ACL 系统（放到 P1）。

---

## 2. 当前现状（与你们代码对齐）

### 2.1 已有强项

- RAG 检索引擎能力完整：`vector/bm25/hybrid + RRF + rerank + query_transform + CRAG`  
  参考：`src/api/services/rag_service.py:570`、`src/api/services/rag_service.py:877`、`src/api/services/rag_service.py:888`、`src/api/services/rag_service.py:979`。  
- 助手级 KB 绑定已打通：`assistant.knowledge_base_ids`  
  参考：`src/api/services/agent_service_simple.py:231`。  
- 前端可展示 RAG diagnostics 与 sources  
  参考：`frontend/src/shared/chat/components/MessageBubble.tsx:889`。

### 2.2 关键缺口

- 无 retrieval query 自动规划（当前仅 query rewrite，不是 multi-query planner）  
  参考：`src/api/services/rag_service.py:663`。  
- 无 RAG 工具（当前 tools 仅时间/计算器）  
  参考：`src/tools/registry.py:119`。  
- 上下文注入仍是文本拼接（`Knowledge base context...`），无结构化 `<source>` 协议  
  参考：`src/api/services/rag_service.py:1408`。

---

## 3. 目标架构（P0 完成态）

```text
User Query
  -> AgentService
     -> RetrievalQueryPlannerService (optional, generate N queries)
     -> RagService.retrieve_with_diagnostics_multi(queries)
        -> existing retrieval core (vector/bm25/hybrid/rerank/CRAG)
     -> SourceContextService (render <source id=...> context with template)
     -> call_llm_stream
        -> (optional) RAG tools: search_knowledge / read_knowledge
  -> response + sources + diagnostics
```

---

## 4. P0-1：Retrieval Query Planner 设计

## 4.1 新增模块

- `src/api/services/retrieval_query_planner_service.py`

### 接口草案

```python
@dataclass
class RetrievalQueryPlan:
    original_query: str
    planned_queries: list[str]      # 去重后的最终查询列表，至少包含 original
    planner_enabled: bool
    planner_applied: bool
    fallback_used: bool
    planner_model_id: str
    reason: str                     # disabled/timeout/error/ok


class RetrievalQueryPlannerService:
    async def plan_queries(
        self,
        *,
        query: str,
        runtime_model_id: str | None,
        enabled: bool,
        max_queries: int,
        timeout_seconds: int,
        model_id: str,              # auto or fixed provider:model
    ) -> RetrievalQueryPlan: ...
```

## 4.2 配置项（RAG retrieval 节）

在 `src/api/services/rag_config_service.py` 的 `RetrievalConfig` 增加：

- `retrieval_query_planner_enabled: bool = False`
- `retrieval_query_planner_model_id: str = "auto"`
- `retrieval_query_planner_max_queries: int = 3`
- `retrieval_query_planner_timeout_seconds: int = 4`

并同步：

- `src/api/routers/rag_config.py`（请求/响应模型）  
- `frontend/src/modules/settings/config/rag.config.ts`（设置页表单）。

## 4.3 接入点

优先在 `RagService.retrieve_with_diagnostics` 中接入（不改上层调用签名）：

1. 先生成 `planned_queries`（失败回退 `[original_query]`）。  
2. 对每个 query 复用现有检索核心流程，聚合候选。  
3. 继续走现有 dedup/diversity/rerank/reorder/neighbor/CRAG。  

### 关键设计点

- **默认兼容**：planner 关闭时行为与当前完全一致。  
- **成本控制**：最多 3 queries，且每 query 复用现有 recall_k/top_k。  
- **诊断可见**：在 diagnostics/source 里新增字段：
  - `retrieval_queries`
  - `retrieval_query_count`
  - `retrieval_query_planner_applied`
  - `retrieval_query_planner_model_id`
  - `retrieval_query_planner_fallback`

---

## 5. P0-2：结构化 Source 注入设计

## 5.1 新增模块

- `src/api/services/source_context_service.py`

### 接口草案

```python
class SourceContextService:
    def build_source_tags(self, query: str, sources: list[dict]) -> str: ...
    def apply_template(self, query: str, source_context: str, template: str) -> str: ...
```

## 5.2 Source 协议（后端内部）

注入内容形态：

```xml
<source id="1" type="rag" kb_id="kb_x" doc_id="doc_y" name="xxx.md">
...chunk content...
</source>
```

模板形态（配置化）：

```text
### Task
Use sources to answer the user query.
Only cite [id] if source has id.

<context>
{{CONTEXT}}
</context>

Query: {{QUERY}}
```

## 5.3 接入点

在 `agent_service_simple` 的三条主路径统一接入：

- `process_message`（`src/api/services/agent_service_simple.py:254`）  
- `process_message_stream`（`src/api/services/agent_service_simple.py:454`）  
- `_prepare_context`（`src/api/services/agent_service_simple.py:911`，供 compare/其他复用）

处理方式：

1. 现有 `rag_context` 仍保留（兼容开关）。  
2. 开启 `structured_source_context_enabled` 时，使用 `SourceContextService` 产出结构化 context block。  
3. 该 block 追加到 `system_prompt`（与 memory/web/search 同层级）。

---

## 6. P0-3：工具式 RAG（search/read）设计

## 6.1 当前约束

`call_llm_stream` 虽支持工具调用，但执行器固定走全局 registry：  
`src/agents/simple_llm.py:667`、`src/agents/simple_llm.py:672`。  
这不利于“按会话/助手注入上下文”的 RAG 工具。

## 6.2 关键改造

### A. `call_llm_stream` 增加可注入执行器

新增参数：

```python
tool_executor: Optional[Callable[[str, dict], str]] = None
```

执行优先级：

1. `tool_executor`（请求级）  
2. 退回 `registry.execute_tool(...)`（保持兼容）。

### B. 新增 `RagToolService`

- 文件：`src/api/services/rag_tool_service.py`

接口草案：

```python
class RagToolService:
    async def search_knowledge(
        self,
        *,
        assistant_id: str,
        runtime_model_id: str | None,
        query: str,
        top_k: int = 5,
    ) -> dict: ...   # 返回 hit 列表（含 ref_id）

    async def read_knowledge(
        self,
        *,
        refs: list[str],   # e.g. ["kb:doc:chunk"]
        max_chars: int = 6000,
    ) -> dict: ...
```

## 6.3 工具定义（给模型的 schema）

在工具层增加：

- `search_knowledge(query, top_k?)`
- `read_knowledge(refs[])`

并在 `AgentService` 里按会话构造执行闭包（带 assistant_id/model_id）。

## 6.4 事件与前端

前端已支持 `tool_calls` / `tool_results` 事件：  
`frontend/src/services/api.ts:822`、`frontend/src/services/api.ts:829`。  
因此 P0 不需要新增协议，只要返回结果结构稳定即可。

---

## 7. 文件级改动清单（按优先顺序）

### 第一批（P0 必做）

1. `src/api/services/retrieval_query_planner_service.py`（新增）  
2. `src/api/services/source_context_service.py`（新增）  
3. `src/api/services/rag_tool_service.py`（新增）  
4. `src/api/services/rag_service.py`（接入 planner + 多 query 聚合 + diagnostics 字段）  
5. `src/api/services/agent_service_simple.py`（统一注入 source context；传入 tool_executor）  
6. `src/agents/simple_llm.py`（支持请求级 tool_executor）  
7. `src/api/services/rag_config_service.py`（新增 planner/source 相关配置）  
8. `src/api/routers/rag_config.py`（配置 API）  
9. `frontend/src/modules/settings/config/rag.config.ts`（新增配置项）  
10. `src/tools/registry.py`（注册 RAG 工具或改为动态注入机制）

### 第二批（文档与测试）

1. `docs/rag/active_rag_runtime_flow.md`（可选）  
2. `tests/unit/test_services/test_retrieval_query_planner_service.py`  
3. `tests/unit/test_services/test_source_context_service.py`  
4. `tests/unit/test_services/test_rag_tool_service.py`  
5. `tests/unit/test_services/test_rag_service.py`（multi-query 回归）

---

## 8. 迭代拆分建议（3 个小里程碑）

### 里程碑 A：Planner（1~2 天）

- 完成 query planner 服务 + 配置 + rag_service 接入。  
- 验收：planner 开/关下结果兼容；diagnostics 可见 planned queries。

### 里程碑 B：结构化 source 注入（1 天）

- 完成 source context 服务 + system_prompt 注入开关。  
- 验收：模型输出可见更稳定引用，且不破坏原有 sources 展示。

### 里程碑 C：工具式 RAG（2 天）

- 完成 tool_executor 注入与 `search_knowledge/read_knowledge`。  
- 验收：模型可主动调用工具，前端可看到 tool_calls/tool_results。

---

## 9. 验收标准（P0 完成定义）

1. 当 `retrieval_query_planner_enabled=true` 时，检索使用 >=1 条 planner 产出的 query。  
2. diagnostics 中可追踪 query 规划与 fallback 原因。  
3. source 注入可切换为结构化模板，且与现有聊天流程兼容。  
4. 模型在 function-calling 模式下可调用 `search_knowledge/read_knowledge`。  
5. 普通模式（不开 planner/不开工具）行为与当前版本一致。

