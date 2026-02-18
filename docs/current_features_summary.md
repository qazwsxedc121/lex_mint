# Lex Mint 当前功能独立总结（2026-02-18）

## 1. 当前定位

- 形态：`FastAPI + React 19` 的开发者导向 AI 工作台。
- 存储：对话主存储为 `Markdown + YAML frontmatter`，RAG 为 `sqlite-vec/chroma + BM25` 混合检索层。
- 协议：聊天主链路使用 `SSE` 流式返回。

## 2. 已落地核心能力

### 2.1 对话与会话管理

- 流式聊天、附件上传/下载、消息删除、消息原地编辑、重新生成。
- 会话能力：新建/删除/重命名、临时会话、模型切换、助手切换、参数覆盖。
- 会话组织：文件夹分组、拖拽排序、会话移动/复制/重复。
- 会话分支：支持从指定消息分叉为新会话（Branch）。
- 会话迁移与检索：全文搜索、Markdown 导出、ChatGPT(`.json/.zip`) 与 Markdown 导入。
- 对话增强：自动标题、后续问题建议、上下文压缩、`@file` 文件引用注入、可选 Web 搜索注入。
- 多助手/多模型：支持 Group Chat（同会话多助手）与 Compare（同输入多模型并行流式对比）。

### 2.2 模型与助手体系

- 提供商与模型 CRUD、连通性测试、动态拉取模型列表（按 provider 能力）。
- 内置提供商定义已扩展为 10 个：DeepSeek、Zhipu、Gemini、Volcengine、OpenAI、OpenRouter、Anthropic、Ollama、xAI、Together。
- 统一适配器注册表（8 个适配器实现），支持 OpenAI/Anthropic/Gemini/Ollama 等协议路由。
- 助手 CRUD（提示词、图标、默认模型、参数、知识库绑定、记忆开关）。
- 会话级参数覆盖（temperature/top_p/max_tokens/reasoning_effort 等）与费用追踪。

### 2.3 RAG 知识库

- 知识库 CRUD、文档上传/删除/重处理、Chunk 列表查看。
- 文档处理链路：解析 -> 语义优先分块 -> 嵌入 -> 向量写入 + BM25 索引。
- 已支持文档类型：`TXT/MD/PDF/DOCX/HTML`。
- 检索模式：`vector / bm25 / hybrid`，支持 RRF 融合、重排（rerank）、长上下文重排策略。
- 查询增强：Query Transform（重写）、Rewrite Guard、CRAG 质量门控回退。
- 向量后端可切换：`sqlite_vec`（默认）或 `chroma`；嵌入支持 `api / local / local_gguf`。

### 2.4 记忆系统

- 全局记忆 + 助手级记忆，支持 `fact/instruction` 分层。
- 自动记忆提取（对话后后台写入）与可配置注入策略。
- 记忆 CRUD、语义搜索、上下文注入、置顶/激活状态管理。

### 2.5 翻译与语音

- 对话内流式翻译，支持自动语言检测与双向语言路由。
- 翻译支持模型配置与本地 `GGUF` 模式。
- TTS 文本转语音（edge-tts），支持语音、语速、音量、语音列表与中英自动语音选择。

### 2.6 项目工作区（Project）

- 项目 CRUD、服务端目录选择与可控根目录浏览。
- 文件树浏览、文件读写、重命名/移动、目录创建删除、文件搜索。
- 项目上下文聊天：支持 `context_type=project`，项目会话与通用会话隔离管理。

### 2.7 前端、设置与开发者工具

- 模块化前端：`chat / projects / settings / developer`。
- i18n：`en / zh-CN`。
- 全局命令面板：`Ctrl/Cmd + K`。
- 设置页覆盖：模型、提供商、助手、知识库、Prompt 模板、记忆、RAG、搜索、网页、标题、后续问题、压缩、文件引用、翻译、TTS、开发者模式。
- 开发者工具：Chunk Inspector（按知识库/文档查看切分结果与诊断）。

### 2.8 部署与运行

- 本地脚本：`install.bat` / `start.bat` / `stop.bat`。
- 容器化基础：`Dockerfile.backend`、`Dockerfile.frontend`、`docker-compose.yml` 已可用。
- 健康检查：`/api/health`；日志落地到 `logs/`。

## 3. 主要缺口（当前阶段）

- 多用户能力：认证、权限、租户/团队协作尚未落地。
- MCP 客户端与插件生态尚未接入。
- 语音输入（STT）、图像生成仍未上线。
- 会话分支目前是“分叉新会话”，尚未形成完整树状分支 UI。
- 生产化运维能力仍需强化（反向代理、分环境配置、可观测性深化）。

## 4. 阶段判断

- 项目已从“可用聊天工具”进入“功能完整的开发者 AI 工作台”阶段。
- 下一阶段重点建议从“继续补功能”转向“平台化与质量治理”（认证/MCP/部署治理/RAG 与记忆评估闭环）。
