"""Unit tests for API dependency providers."""

from types import SimpleNamespace

from src.api import dependencies


def test_get_chat_application_service_builds_directly(monkeypatch):
    sentinel_storage = object()
    sentinel_file_service = object()
    sentinel_chat_application_service = object()
    calls = []

    monkeypatch.setattr(dependencies, "_chat_application_service", None)
    monkeypatch.setattr(dependencies, "get_storage", lambda: sentinel_storage)
    monkeypatch.setattr(dependencies, "get_file_service", lambda: sentinel_file_service)
    monkeypatch.setattr(
        dependencies,
        "build_default_chat_application_service",
        lambda **kwargs: calls.append(kwargs) or sentinel_chat_application_service,
    )
    result = dependencies.get_chat_application_service()

    assert result is sentinel_chat_application_service
    assert calls == [
        {
            "storage": sentinel_storage,
            "file_service": sentinel_file_service,
        }
    ]


def test_dependency_getters_cache_instances(monkeypatch):
    model_calls = []
    assistant_calls = []
    project_calls = []
    workspace_calls = []
    storage_calls = []
    file_calls = []
    session_calls = []

    monkeypatch.setattr(dependencies, "_model_service", None)
    monkeypatch.setattr(dependencies, "_assistant_service", None)
    monkeypatch.setattr(dependencies, "_project_service", None)
    monkeypatch.setattr(dependencies, "_project_workspace_state_service", None)
    monkeypatch.setattr(dependencies, "_storage", None)
    monkeypatch.setattr(dependencies, "_file_service", None)
    monkeypatch.setattr(dependencies, "_session_application_service", None)
    monkeypatch.setattr(dependencies, "_chat_application_service", None)
    monkeypatch.setattr(
        dependencies,
        "settings",
        SimpleNamespace(
            conversations_dir="/tmp/conversations",
            attachments_dir="/tmp/attachments",
            max_file_size_mb=16,
        ),
    )
    monkeypatch.setattr(
        dependencies, "ModelConfigService", lambda: model_calls.append("model") or "model-service"
    )
    monkeypatch.setattr(
        dependencies,
        "AssistantConfigService",
        lambda **kwargs: assistant_calls.append(kwargs) or {"assistant": kwargs},
    )
    monkeypatch.setattr(
        dependencies, "ProjectService", lambda: project_calls.append("project") or "project-service"
    )
    monkeypatch.setattr(
        dependencies,
        "ProjectWorkspaceStateService",
        lambda project_service: (
            workspace_calls.append(project_service) or {"workspace": project_service}
        ),
    )
    monkeypatch.setattr(
        dependencies,
        "create_storage_with_project_resolver",
        lambda conversations_dir, **kwargs: (
            storage_calls.append((conversations_dir, kwargs)) or {"storage": kwargs}
        ),
    )
    monkeypatch.setattr(
        dependencies,
        "FileService",
        lambda attachments_dir, max_size: (
            file_calls.append((attachments_dir, max_size)) or {"file": (attachments_dir, max_size)}
        ),
    )
    monkeypatch.setattr(dependencies, "SessionApplicationDeps", lambda **kwargs: kwargs)
    monkeypatch.setattr(
        dependencies,
        "SessionApplicationService",
        lambda deps: session_calls.append(deps) or {"session": deps},
    )

    assert dependencies.get_model_service() == "model-service"
    assert dependencies.get_model_service() == "model-service"
    assert model_calls == ["model"]

    assistant_service = dependencies.get_assistant_service()
    assert assistant_service["assistant"]["model_service"] == "model-service"
    assert dependencies.get_assistant_service() is assistant_service
    assert len(assistant_calls) == 1

    assert dependencies.get_project_service() == "project-service"
    assert dependencies.get_project_service() == "project-service"
    assert project_calls == ["project"]

    workspace_service = dependencies.get_project_workspace_state_service()
    assert workspace_service["workspace"] == "project-service"
    assert dependencies.get_project_workspace_state_service() is workspace_service
    assert workspace_calls == ["project-service"]

    storage = dependencies.get_storage()
    assert storage["storage"]["project_service"] == "project-service"
    assert storage["storage"]["assistant_service"] is assistant_service
    assert storage["storage"]["model_service"] == "model-service"
    assert dependencies.get_storage() is storage
    assert storage_calls == [
        (
            "/tmp/conversations",
            {
                "project_service": "project-service",
                "assistant_service": assistant_service,
                "model_service": "model-service",
            },
        )
    ]

    file_service = dependencies.get_file_service()
    assert file_service["file"] == ("/tmp/attachments", 16)
    assert dependencies.get_file_service() is file_service
    assert file_calls == [("/tmp/attachments", 16)]

    session_service = dependencies.get_session_application_service()
    assert session_service["session"]["storage"] is storage
    assert session_service["session"]["assistant_service"] is assistant_service
    assert session_service["session"]["model_service"] == "model-service"
    assert session_service["session"]["file_service"] is file_service
    assert dependencies.get_session_application_service() is session_service
    assert len(session_calls) == 1
