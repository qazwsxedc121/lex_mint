# 消息编辑和重新生成功能测试指南

## 实施完成总结

已成功实现以下功能：
1. ✅ 消息编辑 - 编辑已发送的用户消息并自动重新生成
2. ✅ 重新生成 - 重新生成助手的回复
3. ✅ 停止生成 - 中止正在进行的流式生成

## 启动应用

### 后端 (Terminal 1)
```bash
# 激活虚拟环境
venv\Scripts\activate

# 启动 FastAPI 服务器
uvicorn src.api.main:app --reload --port 8000
```

### 前端 (Terminal 2)
```bash
cd frontend
npm run dev
```

访问 http://localhost:5173

## 测试场景

### 1. 编辑用户消息（最后一条）

**步骤：**
1. 发送一条消息："什么是 Python？"
2. 等待 AI 回复完成
3. 将鼠标悬停在用户消息气泡上
4. 点击"✏️"编辑按钮
5. 修改内容为："什么是 JavaScript？"
6. 点击"保存并重新生成"或按 Ctrl+Enter

**预期结果：**
- 编辑模式正常显示 textarea
- 点击保存后自动重新生成 AI 回复
- Markdown 文件中内容正确更新
- 新回复基于修改后的问题

### 2. 编辑中间消息

**步骤：**
1. 发送 3 条消息，获得 3 个 AI 回复（共 6 条消息）
2. 悬停在第一条用户消息上
3. 点击"✏️"编辑
4. 修改内容
5. 点击保存

**预期结果：**
- 弹出确认对话框："编辑此消息将删除后续所有消息。是否继续？"
- 确认后删除第 2-6 条消息
- 重新生成新的回复

### 3. 重新生成最后一条回复

**步骤：**
1. 发送消息并获得回复
2. 悬停在 AI 回复气泡上
3. 点击"🔄"重新生成按钮

**预期结果：**
- 删除旧的 AI 回复
- 生成新的回复（可能内容不同）
- 用户消息保持不变

### 4. 流式生成时停止

**步骤：**
1. 发送一条需要较长回复的消息（如"详细解释量子计算"）
2. 在 AI 回复生成过程中点击"停止"按钮

**预期结果：**
- 流式生成立即停止
- 已生成的部分内容保留在界面和 Markdown 文件中
- 输入框恢复可用状态
- "停止"按钮变回"发送"按钮

### 5. 并发操作防护

**步骤：**
1. 发送消息
2. 在流式生成时尝试编辑其他消息

**预期结果：**
- 编辑/重新生成按钮在流式生成时不可用
- 防止并发操作

### 6. 错误处理和回滚

**步骤：**
1. 断开网络连接
2. 尝试编辑消息或重新生成

**预期结果：**
- 显示错误信息
- 消息列表回滚到操作前的状态
- 不丢失数据

### 7. 键盘快捷键

**步骤：**
1. 编辑消息时：
   - 按 Ctrl+Enter 保存
   - 按 Escape 取消

**预期结果：**
- 快捷键正常工作
- 提示文本正确显示

### 8. Markdown 文件验证

**步骤：**
1. 执行编辑操作
2. 打开 `conversations/` 目录下的对应 .md 文件
3. 检查内容

**预期结果：**
- YAML frontmatter 中 `current_step` 正确更新
- 消息内容和时间戳正确
- 文件格式符合规范

## 验证清单

- [ ] 编辑最后一条消息正常工作
- [ ] 编辑中间消息显示确认对话框
- [ ] 重新生成助手回复正常工作
- [ ] 停止生成功能正常
- [ ] 已生成的部分内容被保存
- [ ] 错误时状态正确回滚
- [ ] 操作按钮悬停正常显示
- [ ] Markdown 文件正确更新
- [ ] `current_step` 元数据正确
- [ ] 暗色模式样式正确
- [ ] 键盘快捷键工作正常
- [ ] 并发操作被正确阻止

## 后端 API 测试（可选）

使用 curl 测试截断功能：

```bash
# 发送带截断的消息
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "message": "新消息",
    "truncate_after_index": 2,
    "skip_user_message": false
  }'

# 重新生成（跳过用户消息）
curl -X POST http://localhost:8000/api/chat/stream \
  -H "Content-Type: application/json" \
  -d '{
    "session_id": "your-session-id",
    "message": "原消息",
    "truncate_after_index": 3,
    "skip_user_message": true
  }'
```

## 已知限制

1. 时间戳重建：截断后重建消息时，时间戳会更新为当前时间（可接受的权衡）
2. 仅支持单用户：没有多用户并发控制
3. Emoji 图标：使用 emoji 而不是图标库（可以后续升级到 @heroicons/react）

## 故障排查

### 前端报错
- 检查 TypeScript 编译：`cd frontend && npx tsc --noEmit`
- 检查依赖：`cd frontend && npm install`

### 后端报错
- 确保虚拟环境已激活：`venv\Scripts\activate`
- 检查依赖：`pip install -r requirements.txt`
- 检查 DeepSeek API key：`.env` 文件中的 `DEEPSEEK_API_KEY`

### 操作按钮不显示
- 确认鼠标悬停在消息气泡上
- 检查 `isStreaming` 状态（生成时按钮隐藏）
- 检查浏览器控制台是否有 React 错误

### 停止按钮不工作
- 检查浏览器控制台网络请求是否被 abort
- 确认后端收到 `asyncio.CancelledError` 异常
