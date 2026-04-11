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
    registration_body: str = (
        "return {\n"
        "    'formats': [\n"
        "        {\n"
        "            'id': 'markdown',\n"
        "            'display_name': 'Markdown',\n"
        "            'media_type': 'text/markdown; charset=utf-8',\n"
        "            'extension': 'md',\n"
        "        }\n"
        "    ],\n"
        "    'handlers': {'markdown': lambda session: '# plugin export\\n'},\n"
        "}\n"
    ),
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
    plugin_lines = ["def register_session_export():"] + [
        f"    {line}" for line in registration_body.rstrip().splitlines()
    ]
    plugin_dir.joinpath("plugin.py").write_text(
        "\n".join(plugin_lines),
        encoding="utf-8",
    )


def test_session_export_loader_loads_feature_plugin(tmp_path: Path):
    _write_plugin(tmp_path)
    loaded = export_plugins.SessionExportPluginLoader(tmp_path).load()
    assert len(loaded) == 1
    assert loaded[0].plugin_id == "demo_export"
    assert loaded[0].contribution.handlers["markdown"]({"title": "x"}) == "# plugin export\n"


def test_session_export_loader_reports_disabled_plugin_status(tmp_path: Path):
    _write_plugin(tmp_path, plugin_enabled=False)
    loaded, statuses = export_plugins.SessionExportPluginLoader(tmp_path).load_with_statuses()
    assert loaded == []
    assert len(statuses) == 1
    assert statuses[0].id == "demo_export"
    assert statuses[0].enabled is False
    assert statuses[0].loaded is False


def test_session_export_core_default_formats_work_without_plugin(monkeypatch):
    loader_cls = export_plugins.SessionExportPluginLoader
    monkeypatch.setattr(export_plugins, "_runtime_registry", None)
    monkeypatch.setattr(
        export_plugins,
        "SessionExportPluginLoader",
        lambda: loader_cls(Path("__missing_plugins__")),
    )
    formats = export_plugins.list_session_export_formats()
    format_ids = [item.id for item in formats]
    assert "markdown" in format_ids
    assert "json" in format_ids

    artifact = export_plugins.export_session_artifact(
        session={"title": "Demo", "state": {"messages": [{"role": "user", "content": "hi"}]}},
        export_format="json",
    )
    assert artifact.filename.endswith(".json")
    assert '"role": "user"' in artifact.content_bytes.decode("utf-8")


def test_session_export_plugin_override_falls_back_to_core_on_error(tmp_path: Path, monkeypatch):
    _write_plugin(
        tmp_path,
        registration_body=(
            "return {\n"
            "    'formats': [\n"
            "        {\n"
            "            'id': 'markdown',\n"
            "            'display_name': 'Markdown',\n"
            "            'media_type': 'text/markdown; charset=utf-8',\n"
            "            'extension': 'md',\n"
            "        }\n"
            "    ],\n"
            "    'handlers': {'markdown': lambda session: (_ for _ in ()).throw(RuntimeError('boom'))},\n"
            "}\n"
        ),
    )
    loader_cls = export_plugins.SessionExportPluginLoader
    monkeypatch.setattr(export_plugins, "_runtime_registry", None)
    monkeypatch.setattr(
        export_plugins,
        "SessionExportPluginLoader",
        lambda: loader_cls(tmp_path),
    )
    artifact = export_plugins.export_session_artifact(
        session={
            "title": "Demo",
            "state": {"messages": [{"role": "assistant", "content": "<think>x</think>done"}]},
        },
        export_format="markdown",
    )
    text = artifact.content_bytes.decode("utf-8")
    assert "<details>" in text
    assert "done" in text


def test_session_export_raises_for_unknown_format(monkeypatch):
    loader_cls = export_plugins.SessionExportPluginLoader
    monkeypatch.setattr(export_plugins, "_runtime_registry", None)
    monkeypatch.setattr(
        export_plugins,
        "SessionExportPluginLoader",
        lambda: loader_cls(Path("__missing_plugins__")),
    )
    with pytest.raises(export_plugins.SessionExportUnsupportedFormatError) as exc_info:
        export_plugins.export_session_artifact(
            session={"title": "Demo", "state": {"messages": []}},
            export_format="xml",
        )
    assert "markdown" in exc_info.value.available_formats
