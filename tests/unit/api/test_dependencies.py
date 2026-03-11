"""Unit tests for API dependency providers."""

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
