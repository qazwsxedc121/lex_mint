# Lex Mint

面向开发者的 AI Agent 工作台，基于 FastAPI、React 和 LangGraph。

[English README](README.md) | [当前功能总结](docs/current_features_summary.md)

## 项目亮点

- 对话可读可控：会话以 Markdown 存储，便于备份、同步和版本管理。
- 日常体验完整：消息编辑、会话分支、文件夹分组、全文搜索、导入导出。
- 模型能力实用：会话级参数覆盖、推理深度控制、费用追踪、多模型对比。
- 知识能力闭环：知识库 RAG + 记忆系统 + 来源注入。
- 开发者场景友好：项目文件浏览与聊天同屏协作。

## 已支持能力

- 流式聊天（SSE）、附件上传/下载、重新生成、消息原地编辑
- 会话分支、复制/移动、文件夹拖拽整理
- Markdown 导出；ChatGPT（`.json/.zip`）与 Markdown 导入
- 会话全文搜索、上下文压缩、自动标题、后续问题建议
- 知识库 CRUD、文档处理与向量检索（TXT/MD/PDF/DOCX/HTML）
- 全局/助手级记忆（自动提取 + 检索注入）
- 对话内翻译、TTS 语音播放
- i18n（`en` / `zh-CN`）、命令面板（`Ctrl/Cmd + K`）

## 快速开始

### Windows 脚本方式（推荐）

1. 复制 `.env.example` 为 `.env`
2. 在 `$HOME/.lex_mint/keys_config.yaml` 中配置 API Key（见 `docs/worktree_bootstrap.md`）
3. 运行 `install.bat`
4. 运行 `start.bat`

### 手动启动

后端（请始终使用 venv 可执行文件）：

```powershell
./venv/Scripts/pip install -r requirements.txt
./venv/Scripts/uvicorn src.api.main:app --reload --port 8988
```

前端：

```powershell
cd frontend
npm install
npm run dev
```

访问地址：

- 前端：`http://localhost:5173`
- API 文档：`http://localhost:8988/docs`

### Docker Compose 启动

1. 复制 `.env.example` 为 `.env`
2. 在 `$HOME/.lex_mint/keys_config.yaml` 中配置 API Key（或启动后在设置页配置）
3. 启动服务：

```powershell
docker compose up --build
```

4. 停止服务：

```powershell
docker compose down
```

## 目录结构

```text
src/                    FastAPI 后端（API/服务/Agent/Provider）
frontend/               React + Vite 前端
tests/                  Pytest 测试
config/                 defaults/local 配置
conversations/          Markdown 对话存储
data/state/             运行态配置与状态
docs/                   架构与分析文档
```

## 后续方向

- 多用户认证与权限体系
- MCP 客户端支持
- STT 语音输入
- RAG 质量增强（混合检索、重排序、评估）
