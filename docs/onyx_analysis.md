# Onyx 技术分析与对比报告

> 分析版本: Onyx `3bc1b89fee639a583125671826afda6921c19951` (main)
> 对比项目: lex_mint (当前仓库实现)
> 报告日期: 2026-02-26
> 研究重点: 按竞品模板分析 Onyx，重点深挖 Deep Research / KG-RAG / 多模态执行；企业化与多用户仅作背景说明

---

## 目录

1. [概述](#1-概述)
2. [技术栈对比](#2-技术栈对比)
3. [架构设计对比](#3-架构设计对比)
4. [功能模块逐项对比](#4-功能模块逐项对比)
5. [Onyx 独特功能深挖](#5-onyx-独特功能深挖)
6. [对比总结表](#6-对比总结表)
7. [Onyx 值得借鉴的设计](#7-onyx-值得借鉴的设计)
8. [功能引入优先级建议](#8-功能引入优先级建议)
9. [实施路线图（面向 lex_mint）](#9-实施路线图面向-lex_mint)
10. [附录：关键证据索引](#10-附录关键证据索引)
11. [跨项目 Packet 设计结论与最佳方案](#11-跨项目-packet-设计结论与最佳方案)

---

## 1. 概述

### 1.1 Onyx 简介

Onyx 定位为「可自托管、面向生产的 AI 平台」。其 README 明确主打 Agents、Web Search、RAG、MCP、Deep Research、Code Interpreter、Image Generation，以及 40+ 连接器能力（`learn_proj/onyx/README.md:33`, `learn_proj/onyx/README.md:47`）。

本地源码结构呈现为多端一体：

- 后端：`learn_proj/onyx/backend/onyx/`
- Web 前端（Next.js）：`learn_proj/onyx/web/`
- 其他端：`learn_proj/onyx/widget/`, `learn_proj/onyx/desktop/`

### 1.2 lex_mint 简介（当前基线）

lex_mint 当前为 FastAPI + React(Vite) 架构，路由集中在 `src/api/main.py`，会话主存储是 Markdown + YAML frontmatter（`src/api/services/conversation_storage.py:1`）。  
RAG 与工具调用已落地，但整体仍以「单轮主流程 + 有限工具循环」为核心（`src/api/services/single_chat_flow_service.py:82`, `src/agents/tool_loop_runner.py:53`）。

### 1.3 本报告目标

- 按现有竞品报告格式，给出 Onyx 与 lex_mint 的结构化对比；
- 深挖 Onyx 独特能力（Deep Research / KG-RAG / 多模态执行）；
- 给出可执行的功能借鉴优先级与落地路线。

---

## 2. 技术栈对比


| 维度            | Onyx                                                                                                                                   | lex_mint                                                                                                  |
| ------------- | -------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------- |
| 后端框架          | FastAPI（模块化单体）                                                                                                                         | FastAPI                                                                                                   |
| 前端框架          | Next.js + React 19（`learn_proj/onyx/web/package.json:9`, `learn_proj/onyx/web/package.json:77`, `learn_proj/onyx/web/package.json:82`） | Vite + React 19（`frontend/package.json:7`, `frontend/package.json:37`）                                    |
| 对话存储          | PostgreSQL + 结构化消息/工具调用（含 replay）                                                                                                      | Markdown 文件 + frontmatter（`src/api/services/conversation_storage.py:1`）                                   |
| 检索/索引         | Hybrid 检索 + Federated 检索 + ACL 过滤                                                                                                      | 本地知识库检索 + Hybrid/RRF 配置（`src/api/services/rag_config_service.py:43`）                                      |
| Deep Research | 原生多阶段模式（clarify/plan/orchestrate/report）                                                                                               | 暂无独立 Deep Research 模式                                                                                     |
| MCP           | 原生支持 MCP 工具发现/调用                                                                                                                       | 暂无                                                                                                        |
| 代码执行          | 内置 Python Tool + 外部 Code Interpreter 服务                                                                                                | 暂无                                                                                                        |
| 图像能力          | 内置 image generation tool                                                                                                               | 暂无独立图像生成工具                                                                                                |
| Web 搜索        | 内置工具链（web_search/open_urls）+ 深度编排                                                                                                      | DuckDuckGo/Tavily + 网页抓取（`src/api/services/search_service.py:1`, `src/api/services/webpage_service.py:1`） |


**关键结论**：  
Onyx 相比 lex_mint 的核心差异不在「是否有检索」，而在「是否有可观测、可回放、可并行的复杂研究流程编排」。

---

## 3. 架构设计对比

### 3.1 Onyx（研究型编排架构）

Deep Research 在 Onyx 中不是 prompt 技巧，而是独立执行环：

1. 前端传 `deep_research` 标记（`learn_proj/onyx/web/src/app/app/services/lib.tsx:157`），且仅在搜索工具可用时展示开关（`learn_proj/onyx/web/src/sections/input/AppInputBar.tsx:399`）。
2. 后端请求模型包含 `deep_research: bool` 字段（`learn_proj/onyx/backend/onyx/server/query_and_chat/models.py:99`）。
3. 主流程在 `process_message` 分支到 `run_deep_research_llm_loop`（`learn_proj/onyx/backend/onyx/chat/process_message.py:874`）。

### 3.2 lex_mint（单轮编排 + 工具循环）

lex_mint 当前是单轮流式编排：

- `SingleChatFlowService.process_message_stream` 负责 prepare-context -> stream -> persist（`src/api/services/single_chat_flow_service.py:82`）。
- 工具循环由 `ToolLoopRunner` 驱动，默认最大 3 轮（`src/agents/tool_loop_runner.py:53`）。
- 工具集合当前偏轻量（全局工具 + 会话级 RAG 工具），未引入子代理分治与并行研究分支。

### 3.3 存储与回放差异

- Onyx 把 Deep Research 的计划/子研究/报告等阶段打成结构化 streaming packet，并支持会话重放（`learn_proj/onyx/backend/onyx/server/query_and_chat/streaming_models.py:49`, `learn_proj/onyx/backend/onyx/server/query_and_chat/session_loading.py:254`）。
- lex_mint 目前也有 SSE 事件，但偏内容流+工具事件，未形成「研究过程时间线对象模型」。

---

## 4. 功能模块逐项对比

### 4.1 对话与编排


| 功能      | Onyx            | lex_mint  | 结论          |
| ------- | --------------- | --------- | ----------- |
| 普通对话流   | 支持              | 支持        | 基本对齐        |
| 工具循环    | 支持并支持并发分支（研究模式） | 支持，默认 3 轮 | Onyx 编排深度更高 |
| 深度研究模式  | 内置独立模式          | 无         | 关键差距        |
| 研究过程可视化 | 计划/子任务/中间报告分段渲染 | 暂无对应时间线模型 | 关键差距        |


### 4.2 RAG 与检索


| 功能        | Onyx                                         | lex_mint                            | 结论             |
| --------- | -------------------------------------------- | ----------------------------------- | -------------- |
| Hybrid 检索 | 支持（hybrid_alpha、recency bias 等）              | 支持（hybrid + RRF 参数）                 | 双方均有           |
| 查询扩展与重排   | 多阶段（query expansion + selection + expansion） | 支持 query planner / CRAG / rerank 开关 | 思路接近，Onyx流程化更强 |
| ACL 过滤    | 默认纳入检索 filter                                | 当前主要是单用户本地知识库                       | Onyx更完整        |
| 联邦检索      | 支持 federated retrieval                       | 暂无                                  | 差距明显           |


### 4.3 多模态与执行


| 功能          | Onyx                     | lex_mint | 结论   |
| ----------- | ------------------------ | -------- | ---- |
| Python 代码执行 | 内置 PythonTool + 文件上传下载闭环 | 暂无       | 差距明显 |
| 图像生成        | 内置 `generate_image` 工具   | 暂无       | 差距明显 |
| MCP 工具生态    | 原生发现 + 调用 + 认证头合并策略      | 暂无       | 差距明显 |


### 4.4 KG 能力状态

- Onyx 的 KG 基础设施和配置模型较完整（`learn_proj/onyx/backend/onyx/kg/models.py:12`），但当前聊天工具入口仍未开放：
  - `KnowledgeGraphTool` 构造即 `NotImplementedError`（`learn_proj/onyx/backend/onyx/tools/tool_implementations/knowledge_graph/knowledge_graph_tool.py:27`）；
  - `process_kg_commands` 里明确写了“暂时无前端管理 UI”（`learn_proj/onyx/backend/onyx/chat/chat_utils.py:275`）。

**结论**：KG 在 Onyx 更像「在建中的高级能力底座」，不是已完成的通用用户功能。

---

## 5. Onyx 独特功能深挖

### 5.1 Deep Research：四阶段执行环（核心独特能力）

Onyx Deep Research 的关键是“显式状态机化”而不是“单次长回答”：

1. **Clarification 阶段（可选）**
  若未跳过，会先做澄清问题或直接进入计划；如果发出澄清问题，会标记该 assistant 消息为 clarification 并结束当前轮（`learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:236`, `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:288`, `learn_proj/onyx/backend/onyx/db/models.py:2554`）。
2. **Research Plan 阶段**
  用独立 prompt 生成编号计划（<=6 步），并通过专用 packet `deep_research_plan_`* 流式输出给前端（`learn_proj/onyx/backend/onyx/prompts/deep_research/orchestration_layer.py:34`, `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:330`, `learn_proj/onyx/backend/onyx/server/query_and_chat/streaming_models.py:49`）。
3. **Orchestrator + Research Agent 阶段**
  编排器循环调用 `research_agent`；允许并行分支（提示限制最多 3 个并行子任务），并在 UI 层通过 `TopLevelBranching` 预告并发结构（`learn_proj/onyx/backend/onyx/prompts/deep_research/orchestration_layer.py:87`, `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:661`）。
4. **Final Report 阶段**
  汇总研究历史生成长报告，强制带引用，且支持超时兜底（主流程 30 分钟强制收敛）（`learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:83`, `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:433`, `learn_proj/onyx/backend/onyx/prompts/deep_research/orchestration_layer.py:123`）。

**约束与保护机制**：

- 仅允许 search/web_search/open_url 进入 Deep Research 主执行（`learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:229`）。
- 要求底层模型 `max_input_tokens >= 50000`（`learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:215`）。
- Deep Research 与 project chat 明确互斥（`learn_proj/onyx/backend/onyx/chat/process_message.py:875`）。
- 子研究代理单任务超时保护（30 分钟）和中间报告强制收敛窗口（12 分钟）（`learn_proj/onyx/backend/onyx/tools/fake_tools/research_agent.py:77`, `learn_proj/onyx/backend/onyx/tools/fake_tools/research_agent.py:81`）。

### 5.2 KG/RAG：流程化检索 + 引用处理底座

#### 5.2.1 检索流程化（Onyx）

`SearchTool` 代码注释直接给出 5 步检索法：查询扩展 -> 结果重组(RRF) -> LLM 选择 -> 上下文扩展 -> prompt 构建（`learn_proj/onyx/backend/onyx/tools/tool_implementations/search/search_tool.py:1`）。  
检索 pipeline 中把 ACL / 文档集 / 时间过滤 / source 过滤统一进 `IndexFilters`（`learn_proj/onyx/backend/onyx/context/search/pipeline.py:39`）。

`search_runner` 还把 federated 检索与常规 hybrid 检索并行组合（`learn_proj/onyx/backend/onyx/context/search/retrieval/search_runner.py:100`）。

#### 5.2.2 引用体系（Onyx）

Onyx 的 `DynamicCitationProcessor` 支持三种模式（REMOVE / KEEP_MARKERS / HYPERLINK），并针对流式 token 做 citation 解析、去重、重编排（`learn_proj/onyx/backend/onyx/chat/citation_processor.py:27`）。

这让 Deep Research 的“中间报告引用保留 + 最终报告引用重整”成为可工程化流程，而不依赖模型偶然输出格式。

#### 5.2.3 KG 现状（Onyx）

KG 数据结构与配置已较完备，但用户面能力尚未 fully open（见 4.4）。

### 5.3 多模态与执行：Python / 图像 / MCP 三件套

#### 5.3.1 Python Tool

- `PythonTool` 通过外部 Code Interpreter 服务执行代码（`learn_proj/onyx/backend/onyx/tools/tool_implementations/python/python_tool.py:72`）。
- 支持上传会话文件到沙箱、执行、回收生成文件并回写到 Onyx 文件存储（`learn_proj/onyx/backend/onyx/tools/tool_implementations/python/python_tool.py:177`, `learn_proj/onyx/backend/onyx/tools/tool_implementations/python/python_tool.py:242`）。
- `CodeInterpreterClient` 支持 SSE 流式输出，且可自动回退 batch 接口（`learn_proj/onyx/backend/onyx/tools/tool_implementations/python/code_interpreter_client.py:128`, `learn_proj/onyx/backend/onyx/tools/tool_implementations/python/code_interpreter_client.py:152`）。

#### 5.3.2 图像生成 Tool

- 明确约束“用户明确请求时才调用”（`learn_proj/onyx/backend/onyx/tools/tool_implementations/images/image_generation_tool.py:53`）。
- 支持 reference image（编辑/变体上下文）与 provider 能力检测（`learn_proj/onyx/backend/onyx/tools/tool_implementations/images/image_generation_tool.py:254`）。
- 长耗时阶段发 heartbeat 保活，并可并行生成多图（`learn_proj/onyx/backend/onyx/tools/tool_implementations/images/image_generation_tool.py:420`, `learn_proj/onyx/backend/onyx/tools/tool_implementations/images/image_generation_tool.py:395`）。

#### 5.3.3 MCP 工具化

- MCP 客户端支持工具发现、资源发现、标准化结果处理（`learn_proj/onyx/backend/onyx/tools/tool_implementations/mcp/mcp_client.py:294`, `learn_proj/onyx/backend/onyx/tools/tool_implementations/mcp/mcp_client.py:316`）。
- MCPTool 有明确的 header 优先级与 denylist（防 Host Header 注入）（`learn_proj/onyx/backend/onyx/tools/tool_implementations/mcp/mcp_tool.py:21`, `learn_proj/onyx/backend/onyx/tools/tool_implementations/mcp/mcp_tool.py:116`）。

---

## 6. 对比总结表


| 能力域    | Onyx                  | lex_mint              | 评估                |
| ------ | --------------------- | --------------------- | ----------------- |
| 深度研究编排 | 完整四阶段 + 子代理并行 + 时间线回放 | 无独立研究模式               | Onyx 明显领先         |
| 检索工程化  | 多阶段检索流程 + ACL + 联邦检索  | 已有 Hybrid/RRF/CRAG 配置 | Onyx在流程编排和权限维度更成熟 |
| KG     | 有底座，入口未完全开放           | 暂无                    | Onyx中期潜力更大        |
| 代码执行   | 内置 PythonTool + 文件闭环  | 暂无                    | Onyx领先            |
| 图像生成   | 内置工具，支持参考图            | 暂无                    | Onyx领先            |
| MCP    | 原生工具接入与调用             | 暂无                    | Onyx领先            |
| 系统复杂度  | 高，模块多，执行链长            | 中等，架构更轻               | lex_mint维护成本更低    |


---

## 7. Onyx 值得借鉴的设计

1. **把“研究过程”做成一等对象，而不是大模型黑箱输出**
  计划、子任务、中间报告、最终报告都可追踪、可回放、可局部失败降级。
2. **统一 streaming packet 协议驱动前后端协同**
  前端 timeline renderer 直接消费 packet 类型，避免“靠字符串猜状态”。
3. **工具层分级：普通工具 vs 研究子代理工具**
  Deep Research 使用受限工具白名单，降低失控概率。
4. **长任务保护机制完善**
  主流程超时强制收敛、子代理超时回退、think-tool 约束、并行分支可视化。
5. **多模态工具是“流程内公民”**
  Python/图像/MCP 不是外挂页面，而是与会话上下文、文件系统、流式 UI 打通。

---

## 8. 功能引入优先级建议

### P0（2-4 周，优先做）

1. **Research Mode Lite（最小深度研究模式）**
  - 新增请求开关（类似 `deep_research`）；
  - 先做 3 阶段：计划 -> 2-3 次研究循环 -> 报告；
  - 限制可用工具为 `search_knowledge` + `web_search` + `read_webpage`；
  - 目标：先补“流程可解释性”。
2. **研究过程 packet 化 + 前端时间线渲染**
  - 新增最小 packet：`research_plan_start/delta`、`research_task_start`、`research_report_delta`、`section_end`；
  - 复用现有 SSE 通道；
  - 目标：先可视化，再优化质量。
3. **超时与收敛策略**
  - 增加总超时、单子任务超时、最终报告强制收敛；
  - 目标：避免长任务挂死。

### P1（4-8 周）

1. **会话重放一致性（研究流程重建）**
  - 把研究任务/子步骤持久化为结构化消息元数据；
  - 页面刷新后可重建时间线。
2. **引用处理升级**
  - 引入 citation 模式切换（保留标记/去除/链接化）；
  - 目标：中间报告与最终答案的引用一致性更强。
3. **工具分层编排**
  - 普通聊天仍走现有 ToolLoop；
  - Research Mode 使用独立 orchestrator，互不干扰。

### P2（中长期）

1. **MCP 接入层**
  - 先做最小 MCP tool discovery + call；
  - 后续补认证透传、header 策略、安全审计。
2. **代码执行工具（可选）**
  - 外置沙箱服务 + 文件回传；
  - 先内部灰度，不默认对所有模型开放。
3. **KG 能力（谨慎）**
  - 先从“检索增强特征”切入，不急于开放完整 KG 对话入口。

---

## 9. 实施路线图（面向 lex_mint）

### 阶段 1：流程骨架（1-2 周）

- 新增 `research_mode` 请求参数与后端分支；
- 定义研究流程 packet 协议；
- 前端新增最小时间线块（计划/任务/报告）。

### 阶段 2：可运行闭环（2-3 周）

- 编排器实现：计划生成 + 多轮检索任务 + 最终汇总；
- 接入现有 `search_knowledge`、`read_knowledge`、`search_service`、`webpage_service`；
- 增加总超时/单任务超时。

### 阶段 3：稳定性与体验（2-4 周）

- 会话重放还原研究过程；
- citation 与来源展示升级；
- 增加回归测试（超时、并行、中断恢复、刷新重放）。

### 阶段 4：高级扩展（按需）

- MCP PoC；
- Python 执行沙箱 PoC；
- KG 检索增强实验（非默认路径）。

---

## 10. 附录：关键证据索引

### Onyx 功能与定位

- `learn_proj/onyx/README.md:33`
- `learn_proj/onyx/README.md:47`
- `learn_proj/onyx/README.md:65`

### Onyx Deep Research 主链路

- `learn_proj/onyx/backend/onyx/server/query_and_chat/models.py:99`
- `learn_proj/onyx/backend/onyx/chat/process_message.py:874`
- `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:229`
- `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:243`
- `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:304`
- `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:426`
- `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:661`
- `learn_proj/onyx/backend/onyx/deep_research/dr_loop.py:765`
- `learn_proj/onyx/backend/onyx/prompts/deep_research/orchestration_layer.py:87`
- `learn_proj/onyx/backend/onyx/tools/fake_tools/research_agent.py:77`
- `learn_proj/onyx/backend/onyx/tools/fake_tools/research_agent.py:644`

### Onyx Deep Research 前端呈现

- `learn_proj/onyx/web/src/sections/input/AppInputBar.tsx:399`
- `learn_proj/onyx/web/src/app/app/services/lib.tsx:157`
- `learn_proj/onyx/web/src/app/app/message/messageComponents/renderMessageComponent.tsx:115`
- `learn_proj/onyx/web/src/app/app/message/messageComponents/timeline/renderers/deepresearch/DeepResearchPlanRenderer.tsx:20`
- `learn_proj/onyx/web/src/app/app/message/messageComponents/timeline/renderers/deepresearch/ResearchAgentRenderer.tsx:41`
- `learn_proj/onyx/backend/onyx/server/query_and_chat/session_loading.py:254`

### Onyx 检索与引用

- `learn_proj/onyx/backend/onyx/tools/tool_implementations/search/search_tool.py:1`
- `learn_proj/onyx/backend/onyx/context/search/pipeline.py:39`
- `learn_proj/onyx/backend/onyx/context/search/retrieval/search_runner.py:84`
- `learn_proj/onyx/backend/onyx/chat/citation_processor.py:27`

### Onyx KG / 多模态 / MCP

- `learn_proj/onyx/backend/onyx/tools/tool_implementations/knowledge_graph/knowledge_graph_tool.py:27`
- `learn_proj/onyx/backend/onyx/chat/chat_utils.py:272`
- `learn_proj/onyx/backend/onyx/tools/tool_implementations/python/python_tool.py:72`
- `learn_proj/onyx/backend/onyx/tools/tool_implementations/python/code_interpreter_client.py:128`
- `learn_proj/onyx/backend/onyx/tools/tool_implementations/images/image_generation_tool.py:52`
- `learn_proj/onyx/backend/onyx/tools/tool_implementations/mcp/mcp_client.py:294`
- `learn_proj/onyx/backend/onyx/tools/tool_implementations/mcp/mcp_tool.py:21`

### lex_mint 对照点

- `src/api/main.py:19`
- `src/api/services/conversation_storage.py:1`
- `src/api/services/single_chat_flow_service.py:82`
- `src/agents/tool_loop_runner.py:53`
- `src/api/routers/chat.py:29`
- `src/tools/registry.py:119`
- `src/api/services/rag_tool_service.py:47`
- `src/api/services/rag_config_service.py:43`
- `src/api/services/search_service.py:1`
- `src/api/services/webpage_service.py:1`
- `frontend/package.json:7`

---

## 11. 跨项目 Packet 设计结论与最佳方案

> 本节用于回答「learn_proj 里是否有类似 packet 化设计」以及「不直接照抄时，lex_mint 的最佳方案是什么」。

### 11.1 learn_proj 中的相似设计结论

#### A. LobeHub：最接近 Onyx 的“结构化事件流 + 历史回放”

- 定义了明确的流事件类型：`stream_start` / `stream_chunk` / `tool_start` / `tool_end` / `agent_runtime_end`（`learn_proj/lobehub/src/server/modules/AgentRuntime/StreamEventManager.ts:16`）。
- 事件被写入流并可按 operation 拉取历史（`learn_proj/lobehub/src/server/modules/AgentRuntime/StreamEventManager.ts:69`, `learn_proj/lobehub/src/server/modules/AgentRuntime/StreamEventManager.ts:268`）。
- SSE 路由支持 `lastEventId + includeHistory`，可先补历史再接实时流（`learn_proj/lobehub/src/app/(backend)/api/agent/stream/route.ts:20`, `learn_proj/lobehub/src/app/(backend)/api/agent/stream/route.ts:53`）。
- 统一 SSE writer 负责 `event/type/data/id` 标准化输出（`learn_proj/lobehub/packages/utils/src/server/sse.ts:52`）。

**判断**：在“可恢复、可重放、可类型化”的 packet 体系上，LobeHub 是除 Onyx 外最值得参考的实现。

#### B. LibreChat：事件体系成熟，且有流恢复工程能力

- 有稳定事件枚举：`on_run_step` / `on_run_step_delta` / `on_message_delta` / `on_reasoning_delta`（`learn_proj/LibreChat/packages/api/src/agents/openai/handlers.ts:163`）。
- 事件由统一回调层分发并聚合（`learn_proj/LibreChat/api/server/controllers/agents/callbacks.js:204`）。
- `GenerationJobManager` 提供早期事件缓冲、首订阅回放、chunk 持久化（`learn_proj/LibreChat/packages/api/src/stream/GenerationJobManager.ts:760`, `learn_proj/LibreChat/packages/api/src/stream/GenerationJobManager.ts:796`）。

**判断**：LibreChat 的强项在“连接鲁棒性与断线恢复”，适合借鉴到 lex_mint 的 SSE/重连层。

#### C. Cherry Studio：有事件块思想，但更偏 SDK 插件内部流

- 其工具链中有 `start-step` / `finish-step` / `tool-call` / `tool-result` 这类块（`learn_proj/cherry-studio/packages/aiCore/src/core/plugins/built-in/toolUsePlugin/StreamEventManager.ts:19`, `learn_proj/cherry-studio/packages/aiCore/src/core/plugins/built-in/toolUsePlugin/ToolExecutor.ts:49`）。
- 该体系更偏“插件执行流”而非“会话级统一事件总线 + 历史回放”。

**判断**：适合参考其工具事件语义，不适合作为完整 packet 架构模板。

#### D. Open WebUI：有类型事件，但偏中间层转换

- 存在 `chat:completion`、`source` 等事件化输出（`learn_proj/open-webui/backend/open_webui/utils/middleware.py:2785`, `learn_proj/open-webui/backend/open_webui/utils/middleware.py:2891`）。
- 更像对上游模型流的转换和增强，未形成独立“研究流程状态机 + 历史重放总线”。

**判断**：可借鉴其事件过滤/增强思路，但不建议作为主架构蓝本。

### 11.2 lex_mint 的最佳方案（不照抄，融合设计）

结论：**采用「Onyx 编排语义 + LobeHub 事件总线 + LibreChat 恢复机制」三层融合方案**。

#### 层 1：编排语义层（借鉴 Onyx）

- 将研究流程显式状态机化：`clarify -> plan -> orchestrate -> report`。
- 研究过程中的计划、子任务、分支、报告都必须是结构化事件，不再依赖文本猜状态。

#### 层 2：事件总线层（借鉴 LobeHub）

- 建立统一 packet schema（建议最小字段）：
  - `event_id`, `seq`, `ts`, `stream_id`, `conversation_id`, `turn_id`, `type`, `stage`, `payload`。
- 事件域分层：
  - transport: `connected/heartbeat/end/error`
  - content: `text_delta/reasoning_delta/citation_delta`
  - tool: `tool_start/tool_delta/tool_end`
  - research: `plan_* / task_* / branch_* / report_*`
- 采用 append-only 事件日志，支持 replay 与审计。

#### 层 3：连接与恢复层（借鉴 LibreChat）

- 支持 `last_event_id` 续连；
- 首订阅前的早到事件缓冲（避免 created/start 丢失）；
- 历史补发后切换到实时订阅；
- 对长任务增加超时、收敛、取消三类控制事件。

### 11.3 对 lex_mint 的落地原则

1. **先协议后 UI**：先定 packet 枚举和字段，再做前端时间线。
2. **先兼容后替换**：通过 adapter 将现有 SSE 文本事件映射为 packet，渐进迁移。
3. **先可重放后优化质量**：先保证“过程可回看、可恢复”，再优化答案质量和并行策略。
4. **先白名单后开放工具**：Research Mode 先限制为检索类工具，逐步开放高级工具。

### 11.4 一句话结论

lex_mint 的最优路径不是“照搬单一项目”，而是构建一个**统一 packet 协议驱动的研究执行总线**：  
上层用 Onyx 的研究状态机，中层用 LobeHub 的事件流/历史重放，下层用 LibreChat 的断线恢复与缓冲机制。
