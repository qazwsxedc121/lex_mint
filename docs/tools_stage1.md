## Tools Stage 1

Stage 1 freezes the current tool architecture and onboarding rules. This stage does not add new runtime capabilities. It standardizes how tools are defined, exposed to the UI, and enabled in project settings.

### Source of Truth

- `ToolDefinition` is the single metadata source for every tool.
- The tool catalog API is the single source for frontend tool lists and grouping.
- Project default `tool_enabled_map` must be derived from shared tool definitions, not handwritten maps.

### Builtin Tools

Builtin tools use a one-file-per-tool plugin structure under `src/tools/builtin/`.

Each builtin tool file must contain exactly these parts:

- A Pydantic args schema
- A module-level `TOOL = ToolDefinition(...)`
- An `execute(...)` function
- A `build_tool()` function that returns `TOOL.build_tool(...)`

Example shape:

```python
from pydantic import BaseModel, Field

from ..definitions import ToolDefinition


class MyToolArgs(BaseModel):
    text: str = Field(..., min_length=1, description="Text to process.")


TOOL = ToolDefinition(
    name="my_tool",
    description="Do something deterministic with text.",
    args_schema=MyToolArgs,
    group="builtin",
    source="builtin",
    enabled_by_default=False,
)


def execute(*, text: str) -> str:
    return text.upper()


def build_tool():
    return TOOL.build_tool(func=execute)
```

To register a builtin tool:

1. Add the tool module under `src/tools/builtin/`.
2. Export its `TOOL`, `execute`, and `build_tool()` from `src/tools/builtin/__init__.py`.
3. Add the definition to `BUILTIN_TOOL_DEFINITIONS`.
4. Add the builder to `_BUILTIN_TOOL_BUILDERS`.
5. Add the handler to `_BUILTIN_TOOL_HANDLERS`.
6. Add i18n keys for title and description in both locale files.

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
