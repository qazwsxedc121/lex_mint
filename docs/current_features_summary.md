# Lex Mint 当前功能概览（2026-03-13）

> 本文是产品能力快照，和实现细节以代码/接口文档为准。

## 1) 对话与流式能力

- 支持普通聊天、SSE 流式聊天、断线续传（resume）。
- 支持消息编辑、删除、重新生成、分支、复制、移动、导入导出。
- 支持单助手聊天、多人 Group Chat（`round_robin` / `committee`）和多模型 Compare。
- FlowEvent 协议已收口为 canonical 语义：未知事件 fail-fast（`stream_error` + 终止）。

## 2) 会话目标与配置语义

- 会话目标统一为 `target_type + assistant_id/model_id`。
- 已移除 legacy 兼容层（不再使用 `__legacy_model_*`、legacy event、legacy config fallback）。
- 配置体系统一为 `config/defaults + config/local`。

## 3) 模型、助手与工具能力

- 提供商/模型支持完整 CRUD、连通性测试、模型拉取、能力探测。
- 内置 provider 由 `config/defaults/provider_config.yaml` 驱动（当前默认 17 个）。
- 助手支持 CRUD、默认助手设置、会话级参数覆盖。
- 工具目录接口：`/api/tools/catalog`。

## 4) 知识库、记忆与检索

- 知识库支持 CRUD、文档上传、重处理、chunk 查看。
- 记忆支持 settings + CRUD + 检索。
- RAG 配置支持统一读写，后端支持 `sqlite_vec` / `chroma`。

## 5) 项目工作区

- 项目 CRUD、文件树/文件内容读写、目录操作、文本检索。
- Project Chat 与普通 Chat 分上下文管理。
- 支持 `apply-diff` 工作流接口用于项目改动落地。

## 6) 前端组织与设置

- 会话侧边栏支持文件夹、拖拽移动会话、拖拽排序文件夹。
- 多配置模块可在设置页独立管理（RAG、Search、Webpage、Compression、Translation、TTS 等）。

## 7) 仍待持续推进（非阻塞）

- 认证/多用户协作能力。
- 更完整的生产化部署与可观测性规范。
- RAG/记忆评测闭环与自动化基准。
