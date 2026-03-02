# 内联改写工作流参数规范

本文定义 `projects` 模块内联改写面板与 `workflow.input_schema` 的参数约定。

## 目标

- 工作流参数由 `input_schema` 驱动，避免固定 UI 参数。
- 保留上下文自动注入能力（选区、文件、会话信息）。
- 在 UI 层明确“自动注入参数不展示、用户参数可编辑”。

## 命名约定

- **自动注入参数**：以 `_` 开头（推荐）。
  - 示例：`_selected_text`、`_context_before`、`_file_path`
- **用户输入参数**：不以下划线开头。
  - 示例：`instruction`、`tone`、`target_language`

## 面板行为

- `input_schema` 中，凡是自动注入参数（`_` 开头）：
  - 不在内联改写面板显示
  - 在请求发起时自动填入 `inputs`
- 其他参数：
  - 在面板中动态渲染输入控件
  - 按 `type`（`string` / `number` / `boolean`）渲染
  - 按 `required` 做前端校验

## 当前自动注入参数

内联改写运行时会注入以下值（同时提供无下划线与下划线别名）：

- 选区正文：
  - `input` / `_input`
  - `text` / `_text`
  - `selected_text` / `_selected_text`
- 选区上下文：
  - `context_before` / `_context_before`
  - `context_after` / `_context_after`
- 文件上下文：
  - `file_path` / `_file_path`
  - `language` / `_language`
- 运行上下文：
  - `project_id` / `_project_id`
  - `session_id` / `_session_id`
  - `selection_start` / `_selection_start`
  - `selection_end` / `_selection_end`

## 推荐写法

新建内联改写工作流时，优先使用下划线参数，示例：

```text
Rewrite only the selected text.
Instruction: {{inputs.instruction}}
File: {{inputs._file_path}}

<before>
{{inputs._context_before}}
</before>

<selected>
{{inputs._selected_text}}
</selected>

<after>
{{inputs._context_after}}
</after>
```

## 兼容性说明

- 历史工作流若仍使用 `selected_text` / `file_path`（无下划线），仍可运行。
- 新工作流建议统一迁移到 `_` 前缀自动注入参数。
