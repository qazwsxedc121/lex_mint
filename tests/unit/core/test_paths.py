from pathlib import Path

from src.core import paths
from src.core.config import Settings
from src.infrastructure.llm.local_llama_cpp_service import discover_local_gguf_models


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

    settings = Settings(api_port=18000)
    assert settings.conversations_dir == expected_root / "conversations"
    assert settings.attachments_dir == expected_root / "attachments"
    assert (
        settings.projects_config_path == expected_root / "data" / "state" / "projects_config.yaml"
    )


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


def test_discover_local_gguf_models_scans_priority_roots(monkeypatch, tmp_path):
    explicit_root = tmp_path / "custom_models"
    local_appdata = tmp_path / "localappdata"
    install_root = tmp_path / "install_root"

    monkeypatch.setenv("LEX_MINT_MODELS_ROOT", str(explicit_root))
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setenv("LEX_MINT_RUNTIME_ROOT", str(install_root))
    paths.repo_root.cache_clear()
    paths.user_data_root.cache_clear()

    explicit_model = explicit_root / "llm" / "alpha.gguf"
    duplicate_appdata_model = local_appdata / "LexMint" / "models" / "llm" / "alpha.gguf"
    appdata_model = local_appdata / "LexMint" / "models" / "llm" / "nested" / "beta.gguf"
    install_model = install_root / "models" / "llm" / "gamma.gguf"

    explicit_model.parent.mkdir(parents=True, exist_ok=True)
    duplicate_appdata_model.parent.mkdir(parents=True, exist_ok=True)
    appdata_model.parent.mkdir(parents=True, exist_ok=True)
    install_model.parent.mkdir(parents=True, exist_ok=True)

    explicit_model.write_text("explicit", encoding="utf-8")
    duplicate_appdata_model.write_text("appdata-duplicate", encoding="utf-8")
    appdata_model.write_text("appdata", encoding="utf-8")
    install_model.write_text("install", encoding="utf-8")

    discovered = discover_local_gguf_models()

    assert [item["id"] for item in discovered] == [
        "llm/alpha.gguf",
        "llm/nested/beta.gguf",
        "llm/gamma.gguf",
    ]
    assert [item["name"] for item in discovered] == ["alpha", "beta", "gamma"]
    assert all(item["capabilities"]["streaming"] is True for item in discovered)


def test_discover_local_gguf_models_infers_qwen3_reasoning_controls(monkeypatch, tmp_path):
    local_appdata = tmp_path / "localappdata"

    monkeypatch.delenv("LEX_MINT_MODELS_ROOT", raising=False)
    monkeypatch.delenv("LEX_MINT_PACKAGED", raising=False)
    monkeypatch.setenv("LOCALAPPDATA", str(local_appdata))
    monkeypatch.setenv("LEX_MINT_RUNTIME_ROOT", str(tmp_path / "install_root"))
    paths.repo_root.cache_clear()
    paths.user_data_root.cache_clear()

    model_path = local_appdata / "LexMint" / "models" / "llm" / "Qwen3-0.6B-Q8_0.gguf"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    model_path.write_text("qwen3", encoding="utf-8")

    discovered = discover_local_gguf_models()

    assert len(discovered) == 1
    assert discovered[0]["capabilities"]["reasoning"] is True
    assert discovered[0]["capabilities"]["function_calling"] is True
    assert discovered[0]["capabilities"]["reasoning_controls"]["disable_supported"] is True
