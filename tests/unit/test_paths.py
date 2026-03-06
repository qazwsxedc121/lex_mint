from pathlib import Path

from src.api.config import Settings
from src.api import paths


def test_user_data_root_defaults_to_repo_root_in_source_mode(monkeypatch):
    monkeypatch.delenv("LEX_MINT_PACKAGED", raising=False)
    monkeypatch.delenv("LEX_MINT_USER_DATA_ROOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    paths.user_data_root.cache_clear()

    assert paths.user_data_root() == paths.repo_root()
    assert paths.config_local_dir() == paths.repo_root() / "config" / "local"
    assert paths.data_state_dir() == paths.repo_root() / "data" / "state"


def test_packaged_mode_uses_localappdata_for_runtime_writes(monkeypatch):
    local_appdata = Path("D:/tmp/lexmint-localappdata")
    monkeypatch.setenv("LEX_MINT_PACKAGED", "1")
    monkeypatch.delenv("LEX_MINT_USER_DATA_ROOT", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setenv("API_PORT", "18000")
    paths.user_data_root.cache_clear()

    expected_root = local_appdata / "LexMint"

    assert paths.user_data_root() == expected_root
    assert paths.conversations_dir() == expected_root / "conversations"
    assert paths.attachments_dir() == expected_root / "attachments"
    assert paths.logs_dir() == expected_root / "logs"
    assert paths.resolve_user_data_path("data/chromadb") == expected_root / "data" / "chromadb"

    settings = Settings()
    assert settings.conversations_dir == expected_root / "conversations"
    assert settings.attachments_dir == expected_root / "attachments"
    assert settings.projects_config_path == expected_root / "data" / "state" / "projects_config.yaml"
