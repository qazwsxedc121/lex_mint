# Unified Plugin Spec (`plugins/`)

This project now uses one unified plugin root:

- `plugins/<plugin_id>/`

You can manage plugins with Git directly (copy/clone into `plugins/`), then restart backend to load.

## Directory Rules

Each plugin lives fully inside its own directory:

- `plugins/<plugin_id>/manifest.yaml` (required)
- `plugins/<plugin_id>/plugin.py` (recommended entry file)
- Optional assets in the same directory (for example `settings.schema.json`, `settings.defaults.yaml`, adapters, helpers, etc.)

Plugin code must not depend on files outside its own plugin directory for entrypoint file resolution.

## `manifest.yaml` Format

Top-level fields:

- `schema_version`: currently `1`
- `id`, `name`, `version`
- `enabled`: global switch for this plugin
- `description`: optional
- `tool`: optional tool-plugin section
- `provider`: optional provider-plugin section
- `feature`: optional feature-plugin section (experimental)

One plugin directory can expose:

- only `tool`
- only `provider`
- both `tool` and `provider`
- `feature` only, or mixed with `tool` / `provider`

### Tool Section

```yaml
tool:
  enabled: true
  entrypoint: plugin.py:register_tool
  settings_schema_path: settings.schema.json        # optional
  settings_defaults_path: settings.defaults.yaml    # optional
  chat_capabilities:                                # optional
    - id: web.search_context
      title_i18n_key: workspace.settings.tools.web_search.title
      description_i18n_key: workspace.settings.tools.web_search.description
      tool_group: web
      prefer_tool_execution: true
      context_keys: [search_context]
      source_types: [search]
      icon: MagnifyingGlassIcon
      order: 10
      default_enabled: false
      visible_in_input: true
```

Entrypoint callable must return `ToolPluginContribution`.

### Provider Section

```yaml
provider:
  enabled: true
  entrypoint: plugin.py:register_provider
```

Entrypoint callable must return `ProviderPluginContribution`.

### Feature Section (Experimental)

```yaml
feature:
  session_export:
    enabled: true
    entrypoint: plugin.py:register_session_export
```

Current experimental capability:

- `session_export`: entrypoint callable returns a formatter callable.
- Formatter callable receives `session` data and returns markdown text.
- This capability is plugin-owned: if no enabled `session_export` plugin is present, session export API is unavailable.

## Entrypoint Rule

Entrypoint format is unified:

- `<relative_file.py>:<callable_name>`
- example: `plugin.py:register_tool`

The path is resolved relative to the plugin directory and must stay inside that directory.

## Minimal Examples

### Tool-only plugin

```yaml
schema_version: 1
id: demo_tool
name: Demo Tool
version: 0.1.0
enabled: true
tool:
  entrypoint: plugin.py:register_tool
```

### Provider-only plugin

```yaml
schema_version: 1
id: demo_provider
name: Demo Provider
version: 0.1.0
enabled: true
provider:
  entrypoint: plugin.py:register_provider
```

## Operational Notes

- Plugin loading is startup-time; after adding/updating/removing plugins, restart backend.
- Plugin status APIs:
  - Tool plugins: `GET /api/tools/plugins`
  - Provider plugins: `GET /api/models/providers/plugins`
  - Feature plugins (session export): `GET /api/features/plugins`

## Static Isolation Check Rule

Use static checker:

- `./venv/Scripts/python scripts/check_plugin_isolation.py`

Advisory mode (default):

- Always prints score/issues.
- Does not fail exit code unless script itself crashes.

Strict mode (for CI):

- `./venv/Scripts/python scripts/check_plugin_isolation.py --strict --min-score 60 --max-core-src-imports 0 --forbid-thin-wrapper`

Rule meaning:

- `score`: rough self-contained score (0-100).
- `core_src_imports`: imports from `src.*` outside allowed plugin API prefixes.
- `thin_wrapper`: entrypoint likely only forwards core implementation.

You can extend allowed plugin API imports with:

- `--allow-src-prefix src.some.stable.api`

## Hard Rule: No Thin-Wrapper Plugins

Plugins must not be thin wrappers that only forward core implementation.

Not allowed:

- `plugin.py` only imports `src.*` business modules and returns contributions directly.
- creating plugin directories whose purpose is only re-exporting existing core definitions.

Required direction:

- either keep that capability in core (non-plugin path),
- or move a real optional implementation into the plugin directory and make it independently replaceable.
