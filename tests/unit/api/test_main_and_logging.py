"""Coverage tests for API bootstrap, logging, and shared errors."""

from __future__ import annotations

import importlib
import io
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api import errors as api_errors
from src.api import logging_config
from src.core.errors import ExternalServiceError, ValidationError


def _reload_api_main(monkeypatch):
    monkeypatch.setattr("src.api.logging_config.setup_logging", lambda: None)
    import src.api.main as api_main

    return importlib.reload(api_main)


def test_register_exception_handlers_maps_app_errors():
    app = FastAPI()
    api_errors.register_exception_handlers(app)

    @app.get("/validation")
    async def validation_route():
        raise ValidationError("bad input", extra={"field": "name"})

    @app.get("/missing")
    async def missing_route():
        raise FileNotFoundError("lost file")

    @app.get("/external")
    async def external_route():
        raise ExternalServiceError("upstream failed")

    client = TestClient(app)

    validation_response = client.get("/validation")
    assert validation_response.status_code == 400
    assert validation_response.json() == {
        "error": {
            "code": "validation_error",
            "message": "bad input",
            "details": {"field": "name"},
        }
    }

    missing_response = client.get("/missing")
    assert missing_response.status_code == 404
    assert missing_response.json() == {
        "error": {
            "code": "not_found",
            "message": "lost file",
        }
    }

    external_response = client.get("/external")
    assert external_response.status_code == 502
    assert external_response.json()["error"]["code"] == "external_service_error"


def test_rotate_logs_renames_existing_backups(tmp_path: Path):
    current = tmp_path / "server.log"
    current.write_bytes(b"x" * (10 * 1024 * 1024 + 1))
    (tmp_path / "server.log.1").write_text("old-1", encoding="utf-8")
    (tmp_path / "server.log.2").write_text("old-2", encoding="utf-8")
    (tmp_path / "server.log.3").write_text("old-3", encoding="utf-8")

    logging_config.rotate_logs(tmp_path)

    assert not current.exists()
    assert (tmp_path / "server.log.1").exists()
    assert (tmp_path / "server.log.2").read_text(encoding="utf-8") == "old-1"
    assert (tmp_path / "server.log.3").read_text(encoding="utf-8") == "old-2"


def test_setup_logging_initializes_stdout_and_file(tmp_path: Path, monkeypatch):
    stdout = io.StringIO()
    stderr = io.StringIO()
    monkeypatch.setattr(logging_config, "_initialized", False)
    monkeypatch.setattr(logging_config, "logs_dir", lambda: tmp_path)
    monkeypatch.setattr(sys, "stdout", stdout)
    monkeypatch.setattr(sys, "stderr", stderr)

    logging_config.setup_logging()

    log_file = tmp_path / "server.log"
    assert log_file.exists()
    assert isinstance(sys.stdout, logging_config.TeeOutput)
    assert isinstance(sys.stderr, logging_config.TeeOutput)
    assert "Logging system initialized" in log_file.read_text(encoding="utf-8")

    sys.stdout.close()
    sys.stderr.close()


@pytest.mark.asyncio
async def test_api_main_root_and_packaged_routes(tmp_path: Path, monkeypatch):
    api_main = _reload_api_main(monkeypatch)
    dist_dir = tmp_path / "frontend" / "dist"
    dist_dir.mkdir(parents=True)
    (dist_dir / "index.html").write_text("<html>home</html>", encoding="utf-8")
    (dist_dir / "app.js").write_text("console.log('ok');", encoding="utf-8")

    monkeypatch.setattr(api_main, "_frontend_dist_dir", lambda: dist_dir)

    monkeypatch.setattr(api_main, "_packaged_frontend_enabled", lambda: False)
    root_payload = await api_main.root()
    assert root_payload["health"] == "/api/health"

    monkeypatch.setattr(api_main, "_packaged_frontend_enabled", lambda: True)
    response = api_main._frontend_file_response("app.js")
    assert Path(response.path).name == "app.js"

    index_response = await api_main.root()
    assert Path(index_response.path).name == "index.html"

    frontend_route = await api_main.packaged_frontend_routes("nested/route")
    assert Path(frontend_route.path).name == "index.html"

    with pytest.raises(api_main.HTTPException) as exc_info:
        await api_main.packaged_frontend_routes("api/health")
    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_api_main_startup_event_initializes_runtime(tmp_path: Path, monkeypatch):
    api_main = _reload_api_main(monkeypatch)
    monkeypatch.setattr(api_main.settings, "projects_config_path", tmp_path / "config" / "projects.yaml")
    monkeypatch.setattr(api_main.settings, "conversations_dir", tmp_path / "conversations")
    monkeypatch.setattr(api_main, "resolve_user_data_path", lambda path: tmp_path / Path(path))

    class _ModelConfigService:
        def __init__(self):
            self.created = True

    class _AssistantConfigService:
        def __init__(self):
            self.created = True

    class _PromptTemplateConfigService:
        def __init__(self):
            self.created = True

    class _FolderService:
        def __init__(self):
            self.created = True

    class _WorkflowConfigService:
        async def ensure_system_workflows(self):
            return None

    class _Storage:
        async def cleanup_temporary_sessions(self):
            return 2

    class _RagConfig:
        def __init__(self):
            self.config = type(
                "Config",
                (),
                {
                    "storage": type(
                        "Storage",
                        (),
                        {
                            "vector_store_backend": "chroma",
                            "persist_directory": "rag-store",
                        },
                    )()
                },
            )()

    import src.infrastructure.config.model_config_service as model_config_service
    import src.infrastructure.config.assistant_config_service as assistant_config_service
    import src.infrastructure.config.prompt_template_service as prompt_template_service
    import src.infrastructure.config.folder_service as folder_service
    import src.infrastructure.config.workflow_config_service as workflow_config_service
    import src.infrastructure.storage.migration_service as migration_service
    import src.infrastructure.storage.conversation_storage as conversation_storage
    import src.infrastructure.config.rag_config_service as rag_config_service

    monkeypatch.setattr(model_config_service, "ModelConfigService", _ModelConfigService)
    monkeypatch.setattr(assistant_config_service, "AssistantConfigService", _AssistantConfigService)
    monkeypatch.setattr(prompt_template_service, "PromptTemplateConfigService", _PromptTemplateConfigService)
    monkeypatch.setattr(folder_service, "FolderService", _FolderService)
    monkeypatch.setattr(workflow_config_service, "WorkflowConfigService", _WorkflowConfigService)
    monkeypatch.setattr(
        migration_service,
        "migrate_project_conversations",
        lambda _path: {"migrated": 1},
    )
    monkeypatch.setattr(
        conversation_storage,
        "create_storage_with_project_resolver",
        lambda _path: _Storage(),
    )
    monkeypatch.setattr(rag_config_service, "RagConfigService", _RagConfig)

    await api_main.startup_event()

    assert api_main.settings.projects_config_path.parent.exists()
    assert (tmp_path / "rag-store").exists()


def test_cli_main_runs_one_turn(monkeypatch, capsys):
    import src.main as cli_main

    monkeypatch.setattr(cli_main.uuid, "uuid4", lambda: "session-123")
    monkeypatch.setattr(cli_main, "call_llm", lambda messages, session_id: f"reply:{messages[-1]['content']}:{session_id}")
    answers = iter(["hello", "quit"])
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    cli_main.main()

    output = capsys.readouterr().out
    assert "Session ID: session-123" in output
    assert "Agent: reply:hello:session-123" in output
