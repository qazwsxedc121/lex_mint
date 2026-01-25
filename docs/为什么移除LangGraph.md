# 为什么移除了 LangGraph？

## 问题

原来的 `simple_agent.py` 使用 LangGraph，有一个循环逻辑：

```python
def should_continue(state: SimpleAgentState) -> str:
    if state["current_step"] >= 10:
        return "end"
    return "continue"  # ← 循环回 chat_node
```

**结果**：每次用户发一条消息，会调用 **10 次** DeepSeek API！

- ❌ 浪费钱
- ❌ 浪费时间
- ❌ 完全没必要

## 简化后的架构

对于简单的一问一答场景：

**之前（使用 LangGraph）**：
```
用户消息 → LangGraph Graph → chat_node → should_continue →
循环 10 次 → 最后返回
```

**现在（直接调用）**：
```
用户消息 → 调用 LLM 一次 → 返回回复
```

## 文件说明

### 新增文件（简化版）

1. **src/agents/simple_llm.py** - 直接调用 LLM 的函数
   - `call_llm()` - 接收消息列表，调用 DeepSeek，返回回复
   - 只调用一次！

2. **src/api/services/agent_service_simple.py** - 简化版 AgentService
   - 不依赖 LangGraph
   - 直接调用 `call_llm()`

### 保留的旧文件（如果想用 LangGraph）

- `src/agents/simple_agent.py` - 原来的 LangGraph 实现（仍然有循环问题）
- `src/api/services/agent_service.py` - 原来的 AgentService

## 当前使用的版本

**chat.py** 现在导入：
```python
from ..services.agent_service_simple import AgentService  # 简化版
```

## 何时需要 LangGraph？

LangGraph 适合：
- ✅ 多步骤工作流（搜索 → 分析 → 总结）
- ✅ 需要工具调用（calculator, web search, database）
- ✅ 复杂的路由逻辑
- ✅ 需要人工审核的节点

**当前场景不需要**：
- ❌ 只是简单的一问一答
- ❌ 没有工具调用
- ❌ 没有多步骤流程

## 性能对比

### 之前（LangGraph，10 次循环）
- API 调用: 10 次
- 时间: ~30-50 秒
- 成本: 10x

### 现在（直接调用）
- API 调用: 1 次
- 时间: ~3-5 秒
- 成本: 1x

## 如果想恢复 LangGraph

修改 `src/api/routers/chat.py`:

```python
# 从这个
from ..services.agent_service_simple import AgentService

# 改成这个
from ..services.agent_service import AgentService
```

然后修复 `simple_agent.py` 的循环问题：

```python
def should_continue(state: SimpleAgentState) -> str:
    # 直接结束，不循环
    return "end"
```
