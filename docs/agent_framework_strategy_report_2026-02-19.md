# Agent Framework 路线考察与对比报告（2026-02-19）

## 1) 结论先行

- 不建议把 lex_mint 全量迁移为 LangGraph-first。你们当前的核心路径已经是自研 runtime，LangGraph 实际使用很少。
- 建议采用 **Hybrid 路线**：`自研编排与产品层 + Durable 执行内核（Temporal）+ 可替换的模型适配层`。
- 短期不建议直接删除 LangChain 适配层；因为当前多 provider 接入仍明显依赖 LangChain 生态。
- 目标是“面向未来的框架化”，不是“框架名称统一”：先把执行契约、状态模型、可恢复能力做实，再决定是否进一步去 LangChain 化。

## 2) 当前仓库现状（与“是否会变劣化版 LangGraph”直接相关）

基于代码扫描（2026-02-19）：

- `src/api/routers/chat.py` 明确走 `AgentService` 简化路径（注释写明不使用 LangGraph）。
- `langgraph` import 在业务代码里几乎只出现在 `src/agents/simple_agent.py`。
- `langchain*` 在 provider / embeddings / tool / message 适配上使用广泛（多处 import）。
- 你们刚完成的 group chat 重构已经把 committee 逻辑改为“可配置解析 + runtime 注入”，方向正确。

这说明：你们现在更像“**自研 Agent 应用内核 + LangChain 作为适配层**”，而不是 LangGraph 应用。

## 3) 你未来三类需求对应的“图执行需求”

### A. Deep Research（类似 DeerFlow）
- 典型需求：长任务、并行检索、多轮反思、中断恢复、人审插入、失败重试、可追踪执行树。
- 核心痛点不是 prompt，而是 **durability + orchestration + traceability**。

### B. 自定义 Agent 工作流（类似 Dify / n8n）
- 典型需求：可视化节点编排、条件分支、工具节点、人工审批、版本管理、发布与回滚。
- 本质是 **workflow product + runtime contract**，不只是“能跑图”。

### C. 通用 Agent（类似 Claude Code/Cowork）
- 典型需求：工具调用稳定性、权限边界、上下文工程、任务分解与执行反馈。
- 本质是 **工具执行闭环 + 安全策略 + 交互体验**。

## 4) 框架与路线对比（面向你们场景）

## 4.1 LangGraph
- 优点：图式状态机、循环/分支、Agent 工作流表达能力强；生态与 LangChain/LangSmith 协同。
- 代价：状态与执行模型会影响你们现有服务边界；复杂场景下调试/演进成本并不低。
- 结论：适合“以图为核心产品”的团队；你们目前不必全量切入。

## 4.2 纯自研（保持现状并继续抽象）
- 优点：产品可控性最高，最贴合你们要做的“多形态 agent 平台”。
- 代价：长任务恢复、重放、队列与调度、幂等与可观测都要自己补齐。
- 结论：可行，但建议补上 durable 执行底座，否则 deep research 会反复踩坑。

## 4.3 Dify / n8n（对标产品）
- 优点：工作流能力成熟、交付快、可视化友好。
- 代价：作为你们主产品内核会受其模型与边界约束；二次开发深度受限。
- 结论：更适合作为“参考样本”或“内部自动化平台”，不建议直接替代 lex_mint 核心运行时。

## 4.4 Temporal（建议引入的底座）
- 优点：天然支持 long-running、重试、持久化、消息交互（Signal/Update）、恢复能力成熟。
- 代价：引入新基础设施与工程复杂度，需要 workflow 设计 discipline。
- 结论：非常适合承载 deep research / 长流程 agent，且能与现有 FastAPI + 自研编排并存。

## 4.5 OpenAI Agents SDK / PydanticAI / AG2(AutoGen) / CrewAI
- 价值：可作为“任务层编排器/实验层”快速验证某类 agent 模式。
- 局限：若当作平台内核，仍会遇到你们的长期需求（版本化流程、租户治理、持久执行）缺口。
- 结论：适合作为可插拔执行器，不建议直接成为平台唯一内核。

## 5) 推荐技术路线（可落地）

### Phase 1（现在 - 2 周）
- 固化统一执行事件模型：`task_started/task_progress/tool_call/tool_result/human_gate/task_done/task_failed`。
- 将 group chat committee 的配置模型扩展为通用 `workflow_settings` 契约（版本化 schema）。

### Phase 2（2 - 6 周）
- 引入 Temporal 作为“长任务执行层”，先落地一个 deep research 模板流（检索 -> 证据聚合 -> 反思 -> 输出）。
- 现有 chat/committee 保持在轻量 runtime，避免一次性迁移风险。

### Phase 3（4 - 8 周）
- 上层建设 Workflow DSL + 可视化编排（你们自己的 product surface）。
- 增加 HITL 断点、回放、重跑、审计日志。

### Phase 4（8 周后）
- 评估 LangChain 去耦：先抽象 provider adapter interface，再逐步替换 LangChain 依赖。
- 仅在确有收益时保留 LangChain 组件（如特定 provider 的成熟实现）。

## 6) 对你核心问题的直接回答

### “我们会不会做成劣化版 LangGraph？”
- **不会自动变成**。只要你们坚持“产品层目标优先 + 执行层契约清晰”，就不是在复制 LangGraph，而是在构建面向自身业务的 agent platform。

### “要不要上 LangGraph？”
- 建议：**不上全量，不做核心依赖**。可在局部复杂图场景试点，但核心路线仍是自研产品层 + durable 执行底座。

### “LangChain adapter 要不要去掉？”
- 现在不建议立刻去掉。建议先做 provider interface 抽象，等覆盖能力与测试完善后再逐步替换。

## 7) 参考资料（官方优先，访问时间：2026-02-19）

- LangGraph 文档（核心能力/快速开始）  
  https://langchain-ai.github.io/langgraph/
- LangChain 文档（框架定位与生态）  
  https://docs.langchain.com/oss/python/langchain/overview
- DeerFlow（开源 deep research 项目，README）  
  https://github.com/bytedance/deer-flow
- Dify 文档（工作流/Agent 能力）  
  https://docs.dify.ai/
- Dify 仓库（开源与许可证说明）  
  https://github.com/langgenius/dify
- n8n 文档（AI 与工作流自动化）  
  https://docs.n8n.io/
- n8n 仓库（源码与许可）  
  https://github.com/n8n-io/n8n
- Claude Code 文档（终端 agent 形态）  
  https://docs.anthropic.com/en/docs/claude-code/overview
- OpenAI Agents SDK 文档（agents/tool/handoff）  
  https://openai.github.io/openai-agents-python/
- PydanticAI 文档（typed agent framework）  
  https://ai.pydantic.dev/
- AutoGen（AG2）仓库  
  https://github.com/microsoft/autogen
- CrewAI 仓库  
  https://github.com/crewAIInc/crewAI
- Temporal 文档（durable execution / workflows）  
  https://docs.temporal.io/workflows
- Temporal Python SDK 文档（Signals/Updates 等消息交互）  
  https://docs.temporal.io/develop/python/message-passing

## 8) 备注与假设

- 你提到的 “NovelForge” 未检索到明确、权威且稳定的官方技术文档入口；本报告在“工作流产品对标”上主要采用 Dify / n8n 作为可验证样本。
- 如果你确认了 NovelForge 的官方链接，可在下一版把它纳入同一评估矩阵。

## 9) 补充调研结论（PocketFlow / DSPy / PydanticAI / Agno）

以下为补充调研后的结论汇总（访问时间：2026-02-19）：

### 9.1 PocketFlow
- 定位是“轻量、极简的 Agent/Workflow 框架”，学习曲线低，适合快速原型。
- 当前版本迭代与生态成熟度相对早期（参考 PyPI 版本节奏）。
- 结论：适合做小规模 PoC/教学，不建议作为 lex_mint 的主干执行内核。

### 9.2 DSPy
- 强项在“把提示工程程序化并可优化”，适合离线优化路由/提示/策略。
- 对你们价值更像“效果优化层”，而非平台级 runtime（durable、治理、多租户、审计并非其主定位）。
- 结论：建议作为优化工具链接入，不作为唯一编排内核。

### 9.3 PydanticAI
- 强类型契约、工具调用与结构化输出能力对工程化落地友好。
- 官方能力覆盖 graph、多 agent、MCP、durable execution（可对接 Temporal）。
- 结论：在你们当前 Python/FastAPI 架构下，作为执行层候选非常合适。

### 9.4 Agno
- 提供 SDK + AgentOS runtime + 控制平面的一体化方案，含 HITL、追踪、RBAC、远程执行等能力。
- 工程交付速度可能快于纯自研同等能力堆叠，但版本演进较快，需关注升级成本与 provider 兼容细节。
- 结论：值得做 PoC，不建议当前阶段直接全量替换现有主干。

## 10) 更新后的最终建议（面向你们路线）

- **主路线不变**：`自研产品编排层 + Durable 执行底座（Temporal）`。
- **框架策略**：
  - `PydanticAI`：优先作为执行层候选（typed contract + 工程友好）。
  - `DSPy`：作为“优化层”增强 deep research 与路由/提示质量。
  - `Agno`：做专项 PoC（如 deep research 一条链路）后再决定是否扩大。
  - `PocketFlow`：仅用于快速原型，不进入核心架构。
- **LangGraph/LangChain 策略**：
  - 不做 LangGraph 全量迁移。
  - LangChain 先“接口抽象后渐进去耦”，而不是一次性移除。

## 11) 新增参考资料（补充调研来源，访问时间：2026-02-19）

- PocketFlow 文档  
  https://the-pocket.github.io/PocketFlow/
- PocketFlow 仓库  
  https://github.com/The-Pocket/PocketFlow
- PocketFlow PyPI  
  https://pypi.org/project/pocketflow/
- DSPy 文档  
  https://dspy.ai/
- DSPy 生产化文档  
  https://dspy.ai/production/
- DSPy 优化器文档  
  https://dspy.ai/learn/optimization/overview/
- DSPy 仓库  
  https://github.com/stanfordnlp/dspy
- DSPy 论文（原始）  
  https://arxiv.org/abs/2310.03714
- GEPA 论文（DSPy 新优化方法）  
  https://arxiv.org/abs/2507.19457
- PydanticAI 文档  
  https://ai.pydantic.dev/
- PydanticAI Graph 文档  
  https://ai.pydantic.dev/graph/
- PydanticAI Multi-agent 文档  
  https://ai.pydantic.dev/multi-agent-applications/
- PydanticAI Durable Execution（Temporal）  
  https://ai.pydantic.dev/durable_execution/temporal/
- PydanticAI PyPI  
  https://pypi.org/project/pydantic-ai/
- Agno 文档入口  
  https://docs.agno.com/
- Agno AgentOS 介绍  
  https://docs.agno.com/agent-os/introduction
- Agno Workflow Patterns  
  https://docs.agno.com/workflows/workflow-patterns/overview
- Agno HITL（User Confirmation）  
  https://docs.agno.com/hitl/user-confirmation
- Agno 评测文档  
  https://docs.agno.com/evals/overview
- Agno Provider Model Index  
  https://docs.agno.com/models/providers/model-index
- Agno FAQ（provider 切换）  
  https://docs.agno.com/faq/switching-models
- Agno v2 迁移文档  
  https://docs.agno.com/other/v2-migration
- Agno RBAC  
  https://docs.agno.com/agent-os/security/rbac
- Agno 远程执行  
  https://docs.agno.com/agent-os/remote-execution/overview
- Agno PyPI  
  https://pypi.org/project/agno/
