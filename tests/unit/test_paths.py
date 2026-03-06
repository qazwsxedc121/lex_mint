from pathlib import Path

from src.api.config import Settings
from src.api import paths


def test_user_data_root_defaults_to_repo_root_in_source_mode(monkeypatch):
    monkeypatch.delenv("LEX_MINT_PACKAGED", raising=False)
    monkeypatch.delenv("LEX_MINT_USER_DATA_ROOT", raising=False)
    monkeypatch.delenv("LOCALAPPDATA", raising=False)
    monkeypatch.delenv("LEX_MINT_MODELS_ROOT", raising=False)
    paths.user_data_root.cache_clear()

    assert paths.user_data_root() == paths.repo_root()
    assert paths.config_local_dir() == paths.repo_root() / "config" / "local"
    assert paths.data_state_dir() == paths.repo_root() / "data" / "state"


def test_packaged_mode_uses_localappdata_for_runtime_writes(monkeypatch):
    local_appdata = Path("D:/tmp/lexmint-localappdata")
    monkeypatch.setenv("LEX_MINT_PACKAGED", "1")
    monkeypatch.delenv("LEX_MINT_USER_DATA_ROOT", raising=False)
    monkeypatch.delenv("LEX_MINT_MODELS_ROOT", raising=False)
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


def test_resolve_model_path_prefers_explicit_models_root(monkeypatch, tmp_path):
    monkeypatch.delenv("LEX_MINT_PACKAGED", raising=False)
    monkeypatch.setenv("LEX_MINT_MODELS_ROOT", str(tmp_path / "custom_models"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    paths.user_data_root.cache_clear()

    explicit_model = tmp_path / "custom_models" / "llm" / "picked.gguf"
    explicit_model.parent.mkdir(parents=True, exist_ok=True)
    explicit_model.write_text("x", encoding="utf-8")

    appdata_model = tmp_path / "localappdata" / "LexMint" / "models" / "llm" / "picked.gguf"
    appdata_model.parent.mkdir(parents=True, exist_ok=True)
    appdata_model.write_text("y", encoding="utf-8")

    assert paths.resolve_model_path("models/llm/picked.gguf") == explicit_model
    assert paths.resolve_model_path("llm/picked.gguf") == explicit_model


def test_resolve_model_path_falls_back_to_appdata_then_install(monkeypatch, tmp_path):
    monkeypatch.delenv("LEX_MINT_MODELS_ROOT", raising=False)
    monkeypatch.delenv("LEX_MINT_PACKAGED", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "localappdata"))
    monkeypatch.setenv("LEX_MINT_RUNTIME_ROOT", str(tmp_path / "install_root"))
    paths.user_data_root.cache_clear()
    paths.repo_root.cache_clear()

    appdata_model = tmp_path / "localappdata" / "LexMint" / "models" / "llm" / "fallback.gguf"
    appdata_model.parent.mkdir(parents=True, exist_ok=True)
    appdata_model.write_text("a", encoding="utf-8")

    install_model = tmp_path / "install_root" / "models" / "llm" / "fallback.gguf"
    install_model.parent.mkdir(parents=True, exist_ok=True)
    install_model.write_text("b", encoding="utf-8")

    assert paths.resolve_model_path("models/llm/fallback.gguf") == appdata_model

    appdata_model.unlink()
    assert paths.resolve_model_path("models/llm/fallback.gguf") == install_model


def test_resolve_model_path_returns_absolute_path_unchanged(monkeypatch, tmp_path):
    monkeypatch.delenv("LEX_MINT_MODELS_ROOT", raising=False)
    absolute_model = (tmp_path / "external" / "manual.gguf").resolve()
    absolute_model.parent.mkdir(parents=True, exist_ok=True)
    absolute_model.write_text("z", encoding="utf-8")

    assert paths.resolve_model_path(str(absolute_model)) == absolute_model
