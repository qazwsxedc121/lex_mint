from __future__ import annotations

from pathlib import Path

import pytest

from src.application.chat import session_export_plugins as export_plugins


def _write_plugin(
    root: Path,
    *,
    plugin_id: str = "demo_export",
    plugin_enabled: bool = True,
    export_enabled: bool = True,
    body: str = "def formatter(session):\n    return '# plugin export\\n'\n",
) -> None:
    plugin_dir = root / plugin_id
    plugin_dir.mkdir(parents=True, exist_ok=True)
    plugin_dir.joinpath("manifest.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                f"id: {plugin_id}",
                "name: Demo Export",
                "version: 0.1.0",
                f"enabled: {'true' if plugin_enabled else 'false'}",
                "feature:",
                "  session_export:",
                f"    enabled: {'true' if export_enabled else 'false'}",
                "    entrypoint: plugin.py:register_session_export",
            ]
        ),
        encoding="utf-8",
    )
    plugin_dir.joinpath("plugin.py").write_text(
        "\n".join(
            [
                body.rstrip(),
                "",
                "def register_session_export():",
                "    return formatter",
            ]
        ),
        encoding="utf-8",
    )


def test_session_export_loader_loads_feature_plugin(tmp_path: Path):
    _write_plugin(tmp_path)
    loaded = export_plugins.SessionExportPluginLoader(tmp_path).load()
    assert len(loaded) == 1
    assert loaded[0].plugin_id == "demo_export"
    assert loaded[0].formatter({"title": "x"}) == "# plugin export\n"


def test_session_export_loader_reports_disabled_plugin_status(tmp_path: Path):
    _write_plugin(tmp_path, plugin_enabled=False)
    loaded, statuses = export_plugins.SessionExportPluginLoader(tmp_path).load_with_statuses()
    assert loaded == []
    assert len(statuses) == 1
    assert statuses[0].id == "demo_export"
    assert statuses[0].enabled is False
    assert statuses[0].loaded is False


def test_session_export_builder_raises_when_plugin_raises(tmp_path: Path, monkeypatch):
    _write_plugin(
        tmp_path,
        body="def formatter(session):\n    raise RuntimeError('boom')\n",
    )
    loader_cls = export_plugins.SessionExportPluginLoader
    monkeypatch.setattr(export_plugins, "_plugins_initialized", False)
    monkeypatch.setattr(export_plugins, "_loaded_plugin", None)
    monkeypatch.setattr(
        export_plugins,
        "SessionExportPluginLoader",
        lambda: loader_cls(tmp_path),
    )

    with pytest.raises(RuntimeError):
        export_plugins.build_session_export_markdown(session={"title": "t"})


def test_session_export_builder_raises_when_plugin_missing(monkeypatch):
    monkeypatch.setattr(export_plugins, "_plugins_initialized", True)
    monkeypatch.setattr(export_plugins, "_loaded_plugin", None)

    with pytest.raises(export_plugins.SessionExportPluginUnavailable):
        export_plugins.build_session_export_markdown(session={"title": "t"})
