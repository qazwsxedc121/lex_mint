"""Tests for projects router endpoint wrappers."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.api.routers import projects as projects_router
from src.infrastructure.config.project_service import ProjectConflictError
from src.infrastructure.projects.project_document_tool_service import ProjectDocumentToolError


class _ProjectService:
    def __init__(self):
        self.fail_with: Exception | None = None
        self.project = {
            "id": "proj_123",
            "name": "Demo",
            "root_path": "/tmp/demo",
            "description": None,
            "settings": {},
        }

    def _maybe_raise(self):
        if self.fail_with:
            raise self.fail_with

    async def get_projects(self):
        self._maybe_raise()
        return [self.project]

    def list_browse_roots(self):
        self._maybe_raise()
        return [{"path": "/tmp", "name": "tmp", "is_directory": True}]

    def list_directories(self, path: str):
        self._maybe_raise()
        return [{"path": path, "name": "child", "is_directory": True}]

    def create_browse_directory(self, parent_path: str, name: str):
        self._maybe_raise()
        return {"path": f"{parent_path}/{name}", "name": name, "is_directory": True}

    async def add_project(self, project):
        self._maybe_raise()
        return project

    async def get_project(self, project_id: str):
        self._maybe_raise()
        return None if project_id == "missing" else self.project

    async def update_project(self, project_id: str, **kwargs):
        self._maybe_raise()
        return None if project_id == "missing" else {**self.project, **kwargs}

    async def delete_project(self, project_id: str):
        self._maybe_raise()
        return project_id != "missing"

    async def get_file_tree(self, project_id: str, path: str):
        self._maybe_raise()
        return {"name": path or ".", "path": path, "type": "directory", "children": []}

    async def read_file(self, project_id: str, path: str):
        self._maybe_raise()
        return {"path": path, "content": "hello", "encoding": "utf-8"}

    async def create_file(self, project_id: str, path: str, content: str, encoding: str | None):
        self._maybe_raise()
        return {"path": path, "content": content, "encoding": encoding or "utf-8"}

    async def create_directory(self, project_id: str, path: str):
        self._maybe_raise()
        return {"name": path, "path": path, "type": "directory", "children": []}

    async def write_file(
        self,
        project_id: str,
        path: str,
        content: str,
        encoding: str | None,
        expected_hash: str | None,
    ):
        self._maybe_raise()
        return {
            "path": path,
            "content": content,
            "encoding": encoding or "utf-8",
            "hash": expected_hash,
        }

    async def rename_path(self, project_id: str, source_path: str, target_path: str):
        self._maybe_raise()
        return {
            "source_path": source_path,
            "target_path": target_path,
            "updated_paths": [target_path],
        }

    async def delete_file(self, project_id: str, path: str):
        self._maybe_raise()

    async def delete_directory(self, project_id: str, path: str, recursive: bool):
        self._maybe_raise()

    async def search_files_with_proximity(self, **kwargs):
        self._maybe_raise()
        return [{"path": "src/app.py", "score": 0.9}]

    async def search_project_text(self, **kwargs):
        self._maybe_raise()
        return {"matches": [{"path": "src/app.py", "line": 1, "content": "match"}]}


class _WorkspaceService:
    async def get_workspace_state(self, project_id: str):
        return {"project_id": project_id, "recent_items": [], "open_tabs": []}

    async def upsert_recent_item(self, project_id: str, item):
        return {"project_id": project_id, "recent_items": [item.model_dump()], "open_tabs": []}


@pytest.mark.asyncio
async def test_projects_router_success_paths(monkeypatch, tmp_path):
    service = _ProjectService()
    workspace = _WorkspaceService()
    monkeypatch.setattr(projects_router, "get_project_service", lambda: service)
    monkeypatch.setattr(projects_router, "get_project_workspace_state_service", lambda: workspace)
    monkeypatch.setattr(
        projects_router.uuid, "uuid4", lambda: SimpleNamespace(hex="abcdef1234567890")
    )
    monkeypatch.setattr(
        projects_router,
        "confirm_pending_patch_apply",
        lambda **kwargs: _async_value(
            {
                "ok": True,
                "file_path": "src/app.py",
                "new_content_hash": "hash-1",
                "updated_at": 1,
                "content": "updated",
            }
        ),
    )

    projects = await projects_router.list_projects()
    assert projects[0]["id"] == "proj_123"
    assert (await projects_router.list_browse_roots())[0]["name"] == "tmp"
    assert (await projects_router.list_directories(path="/tmp"))[0]["path"] == "/tmp"
    assert (
        await projects_router.create_browse_directory(
            projects_router.BrowseDirectoryCreate(parent_path="/tmp", name="demo")
        )
    )["name"] == "demo"

    project_root = tmp_path / "demo_project"
    project_root.mkdir()
    created = await projects_router.create_project(
        projects_router.ProjectCreate(name="Demo", root_path=str(project_root))
    )
    assert created.id == "proj_abcdef123456"

    assert (await projects_router.get_project("proj_123"))["id"] == "proj_123"
    assert (
        await projects_router.update_project(
            "proj_123", projects_router.ProjectUpdate(name="Updated")
        )
    )["name"] == "Updated"
    await projects_router.delete_project("proj_123")

    workspace_state = await projects_router.get_workspace_state("proj_123")
    assert workspace_state["project_id"] == "proj_123"
    upserted = await projects_router.add_workspace_state_item(
        "proj_123",
        projects_router.ProjectWorkspaceItemUpsert(
            type="file",
            id="src/app.py",
            title="app.py",
            path="src/app.py",
        ),
    )
    assert upserted["recent_items"][0]["path"] == "src/app.py"

    tree = await projects_router.get_file_tree("proj_123", path="src")
    assert tree["path"] == "src"
    file_content = await projects_router.read_file("proj_123", path="src/app.py")
    assert file_content["content"] == "hello"
    created_file = await projects_router.create_file(
        "proj_123",
        projects_router.FileCreate(path="src/new.py", content="print('x')"),
    )
    assert created_file["path"] == "src/new.py"
    created_dir = await projects_router.create_directory(
        "proj_123",
        projects_router.DirectoryCreate(path="src/lib"),
    )
    assert created_dir["type"] == "directory"
    written = await projects_router.write_file(
        "proj_123",
        projects_router.FileWrite(
            path="src/app.py",
            content="updated",
            expected_hash="0123456789abcdef",
        ),
    )
    assert written["hash"] == "0123456789abcdef"

    applied = await projects_router.apply_chat_diff(
        "proj_123",
        projects_router.ConfirmPendingPatchArgs(session_id="s1", pending_patch_id="p1"),
    )
    assert applied.ok is True

    renamed = await projects_router.rename_path(
        "proj_123",
        projects_router.FileRename(source_path="src/app.py", target_path="src/main.py"),
    )
    assert renamed["target_path"] == "src/main.py"
    await projects_router.delete_file("proj_123", path="src/main.py")
    await projects_router.delete_directory("proj_123", path="src/lib", recursive=True)

    search_files = await projects_router.search_project_files(
        "proj_123", query="app", current_file=None, limit=10
    )
    assert search_files[0]["score"] == 0.9
    search_text = await projects_router.search_project_text("proj_123", query="match")
    assert search_text["matches"][0]["line"] == 1


@pytest.mark.asyncio
async def test_projects_router_error_mapping(monkeypatch):
    service = _ProjectService()
    monkeypatch.setattr(projects_router, "get_project_service", lambda: service)

    with pytest.raises(HTTPException) as exc_info:
        await projects_router.get_project("missing")
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await projects_router.update_project("missing", projects_router.ProjectUpdate(name="x"))
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await projects_router.delete_project("missing")
    assert exc_info.value.status_code == 404

    service.fail_with = ValueError("bad path")
    with pytest.raises(HTTPException) as exc_info:
        await projects_router.list_directories(path="/bad")
    assert exc_info.value.status_code == 400

    service.fail_with = ProjectConflictError("stale", "changed since last read", expected_hash="x")
    with pytest.raises(HTTPException) as exc_info:
        await projects_router.write_file(
            "proj_123",
            projects_router.FileWrite(
                path="src/app.py", content="x", expected_hash="0123456789abcdef"
            ),
        )
    assert exc_info.value.status_code == 409

    monkeypatch.setattr(
        projects_router,
        "confirm_pending_patch_apply",
        lambda **kwargs: _raise_project_tool_error(),
    )
    with pytest.raises(HTTPException) as exc_info:
        await projects_router.apply_chat_diff(
            "proj_123",
            projects_router.ConfirmPendingPatchArgs(session_id="s1", pending_patch_id="p1"),
        )
    assert exc_info.value.status_code == 400


async def _raise_project_tool_error():
    raise ProjectDocumentToolError("invalid_patch", "bad patch")


async def _async_value(value):
    return value
