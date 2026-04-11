## Tools Stage 1

Stage 1 freezes the current tool architecture and onboarding rules. This stage does not add new runtime capabilities. It standardizes how tools are defined, exposed to the UI, and enabled in project settings.

### Source of Truth

- `ToolDefinition` is the single metadata source for every tool.
- The tool catalog API is the single source for frontend tool lists and grouping.
- Project default `tool_enabled_map` must be derived from shared tool definitions, not handwritten maps.

### Builtin Tools

Core builtin tools under `src/tools/builtin/` are reserved for runtime-coupled capabilities.

Current core builtin tools:

- `execute_python`
- `execute_javascript`

Pure utility-style tools should be implemented as tool plugins under `plugins/<plugin_id>/` and loaded through the plugin loader.

### Request-scoped Tools

Stage 1 keeps request-scoped execution inside services, but shared schema and metadata must live in `src/tools/request_scoped.py`.

Use this flow:

1. Add the args schema and `ToolDefinition` to `src/tools/request_scoped.py`.
2. Add the definition to `REQUEST_SCOPED_TOOL_DEFINITIONS`.
3. Build the LangChain tool from that definition inside the owning service.
4. Add the execution branch to the service `execute_tool()` method.
5. Add matching i18n keys.

### Frontend Contract

- Frontend tool UIs must consume `/api/tools/catalog`.
- Frontend must not hardcode tool lists or default enabled maps.
- Frontend should render labels via returned i18n keys, not by rebuilding keys from tool names.

### Guardrails

Do not:

- Handwrite tool description/schema metadata in multiple places.
- Add tool defaults directly to `project_config.py` unless they are derived from shared definitions.
- Reintroduce hardcoded tool lists in the frontend.
- Skip tests when adding a tool.

### Minimum Tests For A New Tool

- Registry or service exposes the tool.
- Catalog includes the tool with correct group and metadata.
- Project default enablement map includes the tool.
- Execution path works for at least one happy-path call.
