# 模型ID设计修复说明

## 问题背景

**原始问题**：不同提供商可能提供相同的模型ID

例如：
- OpenRouter 提供商 → `deepseek-chat-v3.2`
- DeepSeek 官方提供商 → `deepseek-chat-v3.2`

**原设计缺陷**：
```python
# 旧代码：全局检查唯一性
if any(m.id == model.id for m in config.models):
    raise ValueError(f"Model with id '{model.id}' already exists")
```
这会直接**阻止添加**第二个相同ID的模型！

## 修复方案

### 核心改进：使用复合主键

**模型唯一性** = `(provider_id, model_id)` 组合

### 1. 后端验证逻辑

```python
# 新代码：按提供商检查唯一性
if any(m.id == model.id and m.provider_id == model.provider_id
       for m in config.models):
    raise ValueError(
        f"Model '{model.id}' already exists for provider '{model.provider_id}'"
    )
```

✅ **现在允许**：
- DeepSeek 提供商 → `deepseek-chat-v3.2`
- OpenRouter 提供商 → `deepseek-chat-v3.2`

### 2. 会话存储格式

**新格式**：复合ID `provider_id:model_id`

```yaml
---
session_id: uuid
model_id: deepseek:deepseek-chat-v3.2  # 复合ID
---
```

**向后兼容**：
```yaml
model_id: deepseek-chat  # 简单ID（旧格式）
```
系统会自动转换为 `deepseek:deepseek-chat`

### 3. LLM 实例化

支持两种ID格式：

```python
# 复合ID（推荐）
get_llm_instance("deepseek:deepseek-chat-v3.2")

# 简单ID（向后兼容）
get_llm_instance("deepseek-chat")  # 查找第一个匹配的
```

### 4. 前端处理

**ModelSelector 组件**：
```typescript
// 构造复合ID
const compositeId = `${model.provider_id}:${model.id}`;

// 发送到后端
await updateSessionModel(sessionId, compositeId);
```

**显示逻辑**：
```typescript
// 支持两种格式的匹配
const isSelected =
  compositeId === currentModelId ||  // 新格式
  model.id === currentModelId;        // 旧格式
```

## 配置文件示例

```yaml
providers:
  - id: deepseek
    name: DeepSeek Official
    base_url: https://api.deepseek.com

  - id: openrouter
    name: OpenRouter
    base_url: https://openrouter.ai/api/v1

models:
  # DeepSeek 官方
  - id: deepseek-chat-v3.2
    name: DeepSeek Chat v3.2 (Official)
    provider_id: deepseek

  # OpenRouter 代理
  - id: deepseek-chat-v3.2
    name: DeepSeek Chat v3.2 (OpenRouter)
    provider_id: openrouter

  # 两者可以共存！✅
```

## 实际使用场景

### 场景 1：添加相同模型ID

```python
# 添加 DeepSeek 官方的模型
await service.add_model(Model(
    id="deepseek-chat-v3.2",
    provider_id="deepseek",
    name="DeepSeek Chat v3.2 (Official)"
))
# ✅ 成功

# 添加 OpenRouter 的相同模型
await service.add_model(Model(
    id="deepseek-chat-v3.2",
    provider_id="openrouter",
    name="DeepSeek Chat v3.2 (OpenRouter)"
))
# ✅ 成功！现在可以添加了
```

### 场景 2：创建会话时指定模型

```bash
# API 调用（使用复合ID）
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"model_id": "openrouter:deepseek-chat-v3.2"}'
```

会话文件：
```markdown
---
model_id: openrouter:deepseek-chat-v3.2
---
```

### 场景 3：前端模型选择

用户在 UI 中看到：
```
对话模型
  ├─ DeepSeek Chat v3.2 (Official)
  │  deepseek-chat-v3.2
  └─ DeepSeek Chat v3.2 (OpenRouter)
     deepseek-chat-v3.2
```

点击 "OpenRouter" 版本 → 发送 `openrouter:deepseek-chat-v3.2`

## 向后兼容性

### 旧会话文件
```yaml
model_id: deepseek-chat  # 简单ID
```

**自动处理**：
1. 系统查找 `deepseek-chat` 模型
2. 找到提供商 ID（如 `deepseek`）
3. 转换为 `deepseek:deepseek-chat`
4. 正常工作 ✅

### 旧 API 调用
```bash
# 仍然支持简单ID
curl -X POST http://localhost:8000/api/sessions \
  -H "Content-Type: application/json" \
  -d '{"model_id": "deepseek-chat"}'
```

系统会自动转换为复合ID。

## 关键修改文件

### 后端（5 个修改）

1. `src/api/services/model_config_service.py`
   - ✅ `add_model()` - 复合主键验证
   - ✅ `get_model()` - 支持复合ID查询
   - ✅ `delete_model()` - 支持复合ID删除
   - ✅ `get_llm_instance()` - 支持复合ID实例化

2. `src/api/services/conversation_storage.py`
   - ✅ `create_session()` - 存储复合ID
   - ✅ `get_session()` - 返回复合ID

### 前端（1 个修改）

3. `frontend/src/components/ModelSelector.tsx`
   - ✅ `handleSelectModel()` - 发送复合ID
   - ✅ 匹配逻辑 - 支持两种格式

## 测试验证

### 测试用例 1：添加重复ID

```python
# 添加第一个
service.add_model(Model(
    id="gpt-4",
    provider_id="openai",
    name="GPT-4 (OpenAI)"
))

# 添加第二个（不同提供商）
service.add_model(Model(
    id="gpt-4",
    provider_id="azure",
    name="GPT-4 (Azure)"
))
# ✅ 应该成功

# 添加第三个（相同提供商）
service.add_model(Model(
    id="gpt-4",
    provider_id="openai",
    name="GPT-4 Duplicate"
))
# ❌ 应该失败：Model 'gpt-4' already exists for provider 'openai'
```

### 测试用例 2：会话使用正确的模型

```python
# 创建使用 Azure GPT-4 的会话
session_id = await storage.create_session(model_id="azure:gpt-4")

# 加载会话
session = await storage.get_session(session_id)
assert session["model_id"] == "azure:gpt-4"

# LLM 调用应该使用 Azure 的配置
llm = service.get_llm_instance("azure:gpt-4")
assert llm.base_url == "https://azure.openai.com/..."
```

## 优势总结

✅ **支持相同模型ID** - 不同提供商可以有相同的模型名称
✅ **明确的模型来源** - 复合ID清晰标识提供商
✅ **向后兼容** - 旧格式自动转换
✅ **用户友好** - UI 显示清晰，选择方便
✅ **数据一致性** - 会话永远知道使用的是哪个提供商的模型

## 总结

现在系统**完全支持** OpenRouter 这种聚合提供商的场景：

- ✅ OpenRouter 可以提供 `deepseek-chat-v3.2`
- ✅ DeepSeek 官方也可以提供 `deepseek-chat-v3.2`
- ✅ 两者可以同时存在，互不冲突
- ✅ 用户可以清楚地选择使用哪个提供商的版本
- ✅ 会话会记住精确的模型来源
