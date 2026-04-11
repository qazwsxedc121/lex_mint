"""Unit tests for provider plugin loader."""

import sys

from src.providers.plugins.loader import ProviderPluginLoader


def test_loader_loads_valid_provider_plugin(tmp_path):
    plugin_dir = tmp_path / "plugins" / "demo"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "plugin.py").write_text(
        "\n".join(
            [
                "from src.providers.plugins.models import ProviderPluginContribution",
                "",
                "class DemoAdapter:",
                "    pass",
                "",
                "def register_provider():",
                "    return ProviderPluginContribution(adapters={'demo': DemoAdapter})",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (plugin_dir / "manifest.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "id: demo",
                "name: Demo Provider",
                "version: 0.1.0",
                "enabled: true",
                "provider:",
                "  entrypoint: plugin.py:register_provider",
                "",
            ]
        ),
        encoding="utf-8",
    )

    sys.path.insert(0, str(tmp_path))
    try:
        loaded, statuses = ProviderPluginLoader(tmp_path / "plugins").load()
    finally:
        sys.path.remove(str(tmp_path))

    assert len(loaded) == 1
    assert loaded[0][0].id == "demo"
    assert "demo" in loaded[0][1].adapters
    assert len(statuses) == 1
    assert statuses[0].id == "demo"
    assert statuses[0].loaded is True


def test_loader_reports_invalid_manifest(tmp_path):
    plugin_dir = tmp_path / "plugins" / "broken"
    plugin_dir.mkdir(parents=True)
    (plugin_dir / "manifest.yaml").write_text(
        "\n".join(
            [
                "schema_version: 1",
                "id: broken",
                "name: Broken Provider",
                "provider:",
                "  entrypoint: plugin.py:register_provider",
            ]
        ),
        encoding="utf-8",
    )

    loaded, statuses = ProviderPluginLoader(tmp_path / "plugins").load()

    assert loaded == []
    assert len(statuses) == 1
    assert statuses[0].id == "broken"
    assert statuses[0].loaded is False
    assert "invalid manifest" in str(statuses[0].error)
