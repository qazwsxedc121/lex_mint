# 群聊专题讨论（Lex Mint）

更新时间：2026-02-18

## 1. 文档目标

本文件用于沉淀群聊（Multi-Agent Group Chat）能力的专项讨论，作为后续增强的统一基线文档。

- 对比对象：`learn_proj/lobehub`
- 目标方向：从“多助手顺序回复”升级为“可编排的多 Agent 协作系统”
- 使用方式：需求评审、技术设计、迭代排期、验收回归

---

## 2. 现状基线

### 2.1 我们（Lex Mint）已具备能力

1) 群聊会话创建与成员保存
- 前端建群弹窗与最少 2 个助手校验：`frontend/src/shared/chat/components/GroupChatCreateModal.tsx:83`
- 后端 session 创建/更新 `group_assistants` 校验：`src/api/routers/sessions.py:80`, `src/api/routers/sessions.py:445`
- 存储层持久化 `group_assistants`：`src/api/services/conversation_storage.py:120`, `src/api/services/conversation_storage.py:1314`

2) 群聊流式事件与前端渲染
- 后端根据 `group_assistants` 进入群聊流式处理：`src/api/routers/chat.py:248`
- 群聊主流程（assistant_start/chunk/done/message_id）：`src/api/services/agent_service_simple.py:1084`
- 前端事件消费与多助手消息拼装：`frontend/src/shared/chat/hooks/useChat.ts:517`
- API 层支持 group 事件分发：`frontend/src/services/api.ts:812`

3) 执行模型
- 当前是**按成员顺序轮询（round-robin）**，每个助手可看到前面助手的输出：`src/api/services/agent_service_simple.py:1100`, `src/api/services/agent_service_simple.py:1183`


### 2.2 LobeHub 具备而我们当前缺失的关键能力

1) 编排内核（Supervisor + Runtime + Executor）
- 状态机决策：`learn_proj/lobehub/packages/agent-runtime/src/groupOrchestration/GroupOrchestrationSupervisor.ts:27`
- 运行时闭环：`learn_proj/lobehub/packages/agent-runtime/src/groupOrchestration/GroupOrchestrationRuntime.ts:12`
- 指令与结果类型系统：`learn_proj/lobehub/packages/agent-runtime/src/groupOrchestration/types.ts:120`

2) 群聊动作语义
- `speak`、`broadcast`、`delegate`、`execute_task(s)` 等：`learn_proj/lobehub/packages/builtin-tool-group-management/src/executor.ts:30`
- 工具清单与参数定义：`learn_proj/lobehub/packages/builtin-tool-group-management/src/manifest.ts:11`

3) 任务/线程生命周期
- `execSubAgentTask`、`getSubAgentTaskStatus`、`interruptTask`：`learn_proj/lobehub/src/server/routers/lambda/aiAgent.ts:684`, `learn_proj/lobehub/src/server/routers/lambda/aiAgent.ts:767`, `learn_proj/lobehub/src/server/routers/lambda/aiAgent.ts:1002`
- 线程状态与元数据回写：`learn_proj/lobehub/src/server/services/aiAgent/index.ts:557`

4) 数据模型深度
- group + 成员角色：`learn_proj/lobehub/packages/database/src/schemas/chatGroup.ts:67`
- topic/thread（含 groupId）：`learn_proj/lobehub/packages/database/src/schemas/topic.ts:65`
- message 上 groupId/threadId/messageGroupId：`learn_proj/lobehub/packages/database/src/schemas/message.ts:124`

5) 群聊 UI 交互
- 群上下文与 supervisor 视角：`learn_proj/lobehub/src/app/[variants]/(main)/group/features/Conversation/useGroupContext.ts:15`
- 群输入 mention 与成员聚合：`learn_proj/lobehub/src/app/[variants]/(main)/group/features/Conversation/MainChatInput/GroupChat.tsx:47`
- thread hydration 与 thread 入口：`learn_proj/lobehub/src/app/[variants]/(main)/group/features/Conversation/ThreadHydration.tsx:33`, `learn_proj/lobehub/src/app/[variants]/(main)/group/features/Conversation/ChatItem/Thread.tsx:34`

6) 集成测试成熟度
- 群执行集成测试：`learn_proj/lobehub/src/server/routers/lambda/__tests__/integration/aiAgent/execGroupAgent.integration.test.ts:96`
- 任务全生命周期集成测试：`learn_proj/lobehub/src/server/routers/lambda/__tests__/integration/aiAgent.task.integration.test.ts:120`

---

## 3. 差距清单（按优先级）

### P0（先补）

- 缺少 Supervisor 编排层（决策与执行分离）
- 缺少任务线程实体（thread/task status/中断/轮询）
- 缺少群聊动作语义（speak/broadcast/execute_task）
- 缺少群聊全链路状态观测（每轮/每任务）

### P1（次级）

- 缺少成员角色体系（主持人/成员）与角色管理
- 缺少群聊 thread 视图与任务进度 UI
- 缺少群聊专项回归测试矩阵（后端 + 前端）

### P2（增强）

- delegate、投票、总结等高级机制
- 并行任务负载策略与成本策略

---

## 4. 建议升级路线图

### 阶段 A：打底（数据与接口）

目标：先把“群聊动作与任务状态”抽象出来。

- 新增 `group_sessions` / `group_threads` / `group_tasks`（或复用现有会话结构，先从 metadata 子结构起步）
- 新增 API（建议）：
  - `POST /api/group/{session_id}/orchestrate`（触发一次编排）
  - `POST /api/group/{session_id}/tasks`（创建任务）
  - `GET /api/group/tasks/{task_id}`（查询状态）
  - `POST /api/group/tasks/{task_id}/interrupt`（中断）

### 阶段 B：编排 MVP（先不做复杂工具）

目标：实现最小可用编排闭环。

- 引入 `GroupSupervisor`（决策）
- 引入 `GroupRuntime`（循环执行）
- 支持三种动作：
  - `speak(agent_id, instruction?)`
  - `broadcast(agent_ids, instruction?)`
  - `execute_task(agent_id, instruction, timeout?)`

### 阶段 C：UI 与可观测性

目标：让群聊“可看、可控、可回放”。

- 群聊消息中展示：动作来源、任务状态、耗时、token/cost
- 增加 thread/task 面板
- 支持任务中断按钮和状态轮询

### 阶段 D：高级能力

- delegate / 批量任务 / 投票 / 总结压缩
- 策略化并发（并行上限、超时与重试）

---

## 5. 第一阶段（近期）建议交付范围

建议先做“能跑通、可验证”的最小闭环：

1) 后端
- 在现有 `process_group_message_stream` 前增加 orchestrator 分支
- 先支持 `speak` 和 `execute_task` 两个动作
- 提供 task status 查询与中断

2) 前端
- 群聊消息体可渲染“任务卡片”（processing/completed/failed/cancel）
- 保持现有群聊展示兼容，不破坏单聊逻辑

3) 测试
- 后端：最小 3 个集成用例（成功、失败、中断）
- 前端：最小 2 个 e2e 用例（任务创建、状态更新）

---

## 6. 验收标准（MVP）

- 可以在群聊里由“主持逻辑”选择指定成员发言（speak）
- 可以发起子任务并看到状态变化（processing -> completed/failed/cancel）
- 任务可中断，且前端状态与后端一致
- 保证现有群聊顺序轮询模式可回退（开关控制）

---

## 7. 备注

- LobeHub 部分群管理能力也存在未完全实现项（如 summarize/createWorkflow/vote 等仍有占位实现），可作为“参考但不照搬”的依据：
  - `learn_proj/lobehub/packages/builtin-tool-group-management/src/executor.ts:232`
  - `learn_proj/lobehub/packages/builtin-tool-group-management/src/executor.ts:257`
