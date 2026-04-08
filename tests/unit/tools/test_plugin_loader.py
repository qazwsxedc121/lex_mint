"""Unit tests for tool plugin loader."""

from __future__ import annotations

from pathlib import Path

from src.tools.plugins.loader import ToolPluginLoader


def _write_manifest(path: Path, *, body: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def test_loader_loads_valid_plugin(tmp_path, monkeypatch):
    pkg_dir = tmp_path / "testpkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "plugin.py").write_text(
        "\n".join(
            [
                "from src.tools.plugins.models import ToolPluginContribution",
                "from src.tools.plugins.web_tools_definitions import WEB_SEARCH_TOOL",
                "",
                "def register():",
                "    return ToolPluginContribution(definitions=[WEB_SEARCH_TOOL])",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    _write_manifest(
        tmp_path / "tool_plugins" / "demo" / "manifest.yaml",
        body="\n".join(
            [
                "schema_version: 1",
                "id: demo",
                "name: Demo",
                "version: 0.1.0",
                "enabled: true",
                "entrypoint: testpkg.plugin:register",
                "settings_schema_path: settings.schema.json",
                "settings_defaults_path: settings.defaults.yaml",
            ]
        ),
    )

    loaded, statuses = ToolPluginLoader(tmp_path / "tool_plugins").load()

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
        tmp_path / "tool_plugins" / "broken" / "manifest.yaml",
        body="schema_version: 1\nid: broken\nname: Broken\n",
    )

    loaded, statuses = ToolPluginLoader(tmp_path / "tool_plugins").load()

    assert loaded == []
    assert len(statuses) == 1
    assert statuses[0].loaded is False
    assert statuses[0].error is not None


def test_loader_reports_duplicate_plugin_id(tmp_path, monkeypatch):
    pkg_dir = tmp_path / "pkg"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    (pkg_dir / "__init__.py").write_text("", encoding="utf-8")
    (pkg_dir / "plug.py").write_text(
        "\n".join(
            [
                "from src.tools.plugins.models import ToolPluginContribution",
                "def register():",
                "    return ToolPluginContribution()",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))

    for folder in ("a", "b"):
        _write_manifest(
            tmp_path / "tool_plugins" / folder / "manifest.yaml",
            body="\n".join(
                [
                    "schema_version: 1",
                    "id: same_id",
                    f"name: {folder}",
                    "version: 0.1.0",
                    "enabled: true",
                    "entrypoint: pkg.plug:register",
                ]
            ),
        )

    loaded, statuses = ToolPluginLoader(tmp_path / "tool_plugins").load()

    assert len(loaded) == 1
    assert len(statuses) == 2
    assert sum(1 for item in statuses if item.loaded) == 1
    assert sum(1 for item in statuses if not item.loaded) == 1


def test_loader_reports_entrypoint_failure(tmp_path):
    _write_manifest(
        tmp_path / "tool_plugins" / "broken_entrypoint" / "manifest.yaml",
        body="\n".join(
            [
                "schema_version: 1",
                "id: broken_entrypoint",
                "name: Broken Entrypoint",
                "version: 0.1.0",
                "enabled: true",
                "entrypoint: not.exists.module:register",
            ]
        ),
    )

    loaded, statuses = ToolPluginLoader(tmp_path / "tool_plugins").load()

    assert loaded == []
    assert len(statuses) == 1
    assert statuses[0].loaded is False
    assert statuses[0].error is not None
