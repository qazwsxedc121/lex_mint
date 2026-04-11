"""Unit tests for tool plugin loader."""

from __future__ import annotations

from pathlib import Path

from src.tools.plugins.loader import ToolPluginLoader


def _write_manifest(path: Path, *, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_loader_loads_valid_plugin(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "defs.py").write_text(
        "\n".join(
            [
                "from src.tools.definitions import ToolDefinition",
                "from src.tools.plugins.models import ToolPluginContribution",
                "",
                "DEMO_TOOL = ToolDefinition(",
                "    name='demo_search',",
                "    description='demo',",
                "    args_schema=None,",
                "    group='web',",
                "    source='web',",
                ")",
                "",
                "def make_contribution():",
                "    return ToolPluginContribution(definitions=[DEMO_TOOL])",
            ]
        ),
        encoding="utf-8",
    )
    (plugin_dir / "plugin.py").write_text(
        "\n".join(
            [
                "from src.tools.plugins.models import ToolPluginContribution",
                "from .defs import make_contribution",
                "",
                "def register_tool():",
                "    return make_contribution()",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    _write_manifest(
        plugin_dir / "manifest.yaml",
        body="\n".join(
            [
                "schema_version: 1",
                "id: demo",
                "name: Demo",
                "version: 0.1.0",
                "enabled: true",
                "tool:",
                "  entrypoint: plugin.py:register_tool",
                "  settings_schema_path: settings.schema.json",
                "  settings_defaults_path: settings.defaults.yaml",
            ]
        ),
    )

    loaded, statuses = ToolPluginLoader(tmp_path / "plugins").load()

    assert len(loaded) == 1
    assert loaded[0][0].id == "demo"
    assert len(loaded[0][1].definitions) == 1
    assert len(statuses) == 1
    assert statuses[0].loaded is True
    assert statuses[0].has_settings_schema is True
    assert statuses[0].settings_schema_path == "settings.schema.json"
    assert statuses[0].settings_defaults_path == "settings.defaults.yaml"


def test_loader_reports_invalid_manifest(tmp_path):
    _write_manifest(
        tmp_path / "plugins" / "broken" / "manifest.yaml",
        body="\n".join(
            [
                "schema_version: 1",
                "id: broken",
                "name: Broken",
                "version: 0.1.0",
                "tool:",
                "  entrypoint: plugin.py:register_tool",
            ]
        ),
    )

    loaded, statuses = ToolPluginLoader(tmp_path / "plugins").load()

    assert loaded == []
    assert len(statuses) == 1
    assert statuses[0].loaded is False
    assert statuses[0].error is not None


def test_loader_reports_duplicate_plugin_id(tmp_path, monkeypatch):
    plugin_file_body = "\n".join(
        [
            "from src.tools.plugins.models import ToolPluginContribution",
            "def register_tool():",
            "    return ToolPluginContribution()",
        ]
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    for folder in ("a", "b"):
        plugin_dir = tmp_path / "plugins" / folder
        plugin_dir.mkdir(parents=True, exist_ok=True)
        (plugin_dir / "plugin.py").write_text(plugin_file_body, encoding="utf-8")
        _write_manifest(
            plugin_dir / "manifest.yaml",
            body="\n".join(
                [
                    "schema_version: 1",
                    "id: same_id",
                    f"name: {folder}",
                    "version: 0.1.0",
                    "enabled: true",
                    "tool:",
                    "  entrypoint: plugin.py:register_tool",
                ]
            ),
        )

    loaded, statuses = ToolPluginLoader(tmp_path / "plugins").load()

    assert len(loaded) == 1
    assert len(statuses) == 2
    assert sum(1 for item in statuses if item.loaded) == 1
    assert sum(1 for item in statuses if not item.loaded) == 1


def test_loader_reports_entrypoint_failure(tmp_path):
    _write_manifest(
        tmp_path / "plugins" / "broken_entrypoint" / "manifest.yaml",
        body="\n".join(
            [
                "schema_version: 1",
                "id: broken_entrypoint",
                "name: Broken Entrypoint",
                "version: 0.1.0",
                "enabled: true",
                "tool:",
                "  entrypoint: plugin.py:register_tool",
            ]
        ),
    )

    loaded, statuses = ToolPluginLoader(tmp_path / "plugins").load()

    assert loaded == []
    assert len(statuses) == 1
    assert statuses[0].loaded is False
    assert statuses[0].error is not None


def test_loader_parses_select_chat_capability(tmp_path, monkeypatch):
    plugin_dir = tmp_path / "plugins" / "select_demo"
    plugin_dir.mkdir(parents=True, exist_ok=True)
    (plugin_dir / "plugin.py").write_text(
        "\n".join(
            [
                "from src.tools.plugins.models import ToolPluginContribution",
                "def register_tool():",
                "    return ToolPluginContribution()",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    _write_manifest(
        plugin_dir / "manifest.yaml",
        body="\n".join(
            [
                "schema_version: 1",
                "id: select_demo",
                "name: Select Demo",
                "version: 0.1.0",
                "enabled: true",
                "tool:",
                "  entrypoint: plugin.py:register_tool",
                "  chat_capabilities:",
                "    - id: select.mode",
                "      title_i18n_key: workspace.settings.tools.select_mode.title",
                "      description_i18n_key: workspace.settings.tools.select_mode.description",
                "      control_type: select",
                "      arg_key: mode",
                "      default_value: balanced",
                "      options:",
                "        - value: fast",
                "          label_i18n_key: workspace.settings.tools.select_mode.fast",
                "        - value: balanced",
                "          label_i18n_key: workspace.settings.tools.select_mode.balanced",
            ]
        ),
    )

    loaded, statuses = ToolPluginLoader(tmp_path / "plugins").load()

    assert len(loaded) == 1
    assert len(statuses) == 1
    assert statuses[0].loaded is True
    manifest = loaded[0][0]
    assert len(manifest.chat_capabilities) == 1
    capability = manifest.chat_capabilities[0]
    assert capability.control_type == "select"
    assert capability.arg_key == "mode"
    assert capability.default_value == "balanced"
    assert [option.value for option in capability.options] == ["fast", "balanced"]
