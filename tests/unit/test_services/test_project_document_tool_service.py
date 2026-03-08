"""Unit tests for project document chat tools."""

from __future__ import annotations

import json
import time

import pytest

from src.api.models.project_config import Project
from src.api.services.project_document_tool_service import (
    PendingPatch,
    PendingPatchStore,
    ProjectDocumentToolError,
    ProjectDocumentToolService,
    confirm_pending_patch_apply,
)
from src.api.services.project_service import ProjectService


@pytest.fixture
def project_service(tmp_path):
    config_path = tmp_path / "projects_config.yaml"
    service = ProjectService(config_path=config_path)
    return service


async def _prepare_project(tmp_path, project_service: ProjectService) -> Project:
    root = tmp_path / "project_root"
    root.mkdir()
    (root / "notes.txt").write_text("line1\nline2\n", encoding="utf-8")
    project = Project(
        id="proj_tools_1",
        name="Project Tools",
        root_path=str(root),
    )
    await project_service.add_project(project)
    return project


@pytest.mark.asyncio
async def test_read_current_document_returns_hash(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    store = PendingPatchStore()
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-1",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=store,
    )

    raw = await service.read_current_document()
    payload = json.loads(raw)

    assert payload["ok"] is True
    assert payload["file_path"] == "notes.txt"
    assert payload["line_count"] == 2
    assert "content_hash" in payload
    assert payload["content"] == "line1\nline2"


@pytest.mark.asyncio
async def test_apply_diff_dry_run_then_confirm(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    store = PendingPatchStore()
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-1",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=store,
    )

    read_payload = json.loads(await service.read_current_document())
    base_hash = read_payload["content_hash"]
    diff_text = (
        "--- a/notes.txt\n"
        "+++ b/notes.txt\n"
        "@@ -1,2 +1,2 @@\n"
        " line1\n"
        "-line2\n"
        "+line-two\n"
    )
    dry_run_payload = json.loads(
        await service.apply_diff_current_document(
            unified_diff=diff_text,
            base_hash=base_hash,
            dry_run=True,
        )
    )

    assert dry_run_payload["ok"] is True
    assert dry_run_payload["mode"] == "dry_run"
    assert dry_run_payload["preview"]["additions"] == 1
    assert dry_run_payload["preview"]["deletions"] == 1

    confirm_payload = await confirm_pending_patch_apply(
        project_id=prepared_project.id,
        session_id="session-1",
        pending_patch_id=dry_run_payload["pending_patch_id"],
        expected_hash=base_hash,
        project_service=project_service,
        pending_store=store,
    )
    assert confirm_payload["ok"] is True

    after = await project_service.read_file(prepared_project.id, "notes.txt")
    assert after.content == "line1\nline-two\n"


@pytest.mark.asyncio
async def test_apply_diff_hash_mismatch_returns_error(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    store = PendingPatchStore()
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-1",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=store,
    )

    diff_text = (
        "--- a/notes.txt\n"
        "+++ b/notes.txt\n"
        "@@ -1,2 +1,2 @@\n"
        " line1\n"
        "-line2\n"
        "+line-two\n"
    )
    payload = json.loads(
        await service.execute_tool(
            "apply_diff_current_document",
            {
                "unified_diff": diff_text,
                "base_hash": "invalid_hash_value_123456",
                "dry_run": True,
            },
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "HASH_MISMATCH"


@pytest.mark.asyncio
async def test_read_current_document_empty_file_ok(tmp_path, project_service: ProjectService):
    root = tmp_path / "project_root_empty"
    root.mkdir()
    (root / "empty.txt").write_text("", encoding="utf-8")
    project = Project(
        id="proj_tools_empty",
        name="Project Empty",
        root_path=str(root),
    )
    await project_service.add_project(project)

    service = ProjectDocumentToolService(
        project_id=project.id,
        session_id="session-empty",
        active_file_path="empty.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )
    payload = json.loads(await service.read_current_document())

    assert payload["ok"] is True
    assert payload["line_count"] == 0
    assert payload["content"] == ""


@pytest.mark.asyncio
async def test_confirm_pending_patch_expired_error_contains_expiry(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    store = PendingPatchStore()
    patch_id = "expired-patch-1"
    created_at = time.time() - 120
    store.put(
        PendingPatch(
            patch_id=patch_id,
            project_id=prepared_project.id,
            session_id="session-1",
            file_path="notes.txt",
            base_hash="x" * 64,
            patched_content="line1\nline-two\n",
            created_at=created_at,
            ttl_seconds=1,
        )
    )

    with pytest.raises(ProjectDocumentToolError) as exc:
        await confirm_pending_patch_apply(
            project_id=prepared_project.id,
            session_id="session-1",
            pending_patch_id=patch_id,
            expected_hash=None,
            project_service=project_service,
            pending_store=store,
        )

    assert exc.value.code == "PATCH_EXPIRED"
    assert "expires_at" in exc.value.extra


@pytest.mark.asyncio
async def test_apply_diff_accepts_paths_with_spaces(tmp_path, project_service: ProjectService):
    root = tmp_path / "project_root_spaces"
    root.mkdir()
    (root / "notes file.txt").write_text("line1\nline2\n", encoding="utf-8")
    project = Project(
        id="proj_tools_spaces",
        name="Project Spaces",
        root_path=str(root),
    )
    await project_service.add_project(project)

    service = ProjectDocumentToolService(
        project_id=project.id,
        session_id="session-spaces",
        active_file_path="notes file.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )
    read_payload = json.loads(await service.read_current_document())
    base_hash = read_payload["content_hash"]

    diff_text = (
        "--- a/notes file.txt\n"
        "+++ b/notes file.txt\n"
        "@@ -1,2 +1,2 @@\n"
        " line1\n"
        "-line2\n"
        "+line-two\n"
    )
    dry_run_payload = json.loads(
        await service.apply_diff_current_document(
            unified_diff=diff_text,
            base_hash=base_hash,
            dry_run=True,
        )
    )

    assert dry_run_payload["ok"] is True
    assert dry_run_payload["preview"]["additions"] == 1
    assert dry_run_payload["preview"]["deletions"] == 1


@pytest.mark.asyncio
async def test_apply_diff_fallbacks_when_hunk_line_number_is_wrong(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    store = PendingPatchStore()
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-1",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=store,
    )

    read_payload = json.loads(await service.read_current_document())
    base_hash = read_payload["content_hash"]
    diff_text = (
        "--- a/notes.txt\n"
        "+++ b/notes.txt\n"
        "@@ -1,1 +1,1 @@\n"
        "-line2\n"
        "+line-two\n"
    )
    dry_run_payload = json.loads(
        await service.apply_diff_current_document(
            unified_diff=diff_text,
            base_hash=base_hash,
            dry_run=True,
        )
    )

    assert dry_run_payload["ok"] is True
    confirm_payload = await confirm_pending_patch_apply(
        project_id=prepared_project.id,
        session_id="session-1",
        pending_patch_id=dry_run_payload["pending_patch_id"],
        expected_hash=base_hash,
        project_service=project_service,
        pending_store=store,
    )
    assert confirm_payload["ok"] is True
    after = await project_service.read_file(prepared_project.id, "notes.txt")
    assert after.content == "line1\nline-two\n"


@pytest.mark.asyncio
async def test_apply_diff_rejects_ambiguous_hunk_fallback(tmp_path, project_service: ProjectService):
    root = tmp_path / "project_root_ambiguous"
    root.mkdir()
    (root / "notes.txt").write_text("dup\ndup\n", encoding="utf-8")
    project = Project(
        id="proj_tools_ambiguous",
        name="Project Ambiguous",
        root_path=str(root),
    )
    await project_service.add_project(project)
    service = ProjectDocumentToolService(
        project_id=project.id,
        session_id="session-ambiguous",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    read_payload = json.loads(await service.read_current_document())
    base_hash = read_payload["content_hash"]
    diff_text = (
        "--- a/notes.txt\n"
        "+++ b/notes.txt\n"
        "@@ -99,1 +99,1 @@\n"
        "-dup\n"
        "+updated\n"
    )
    payload = json.loads(
        await service.execute_tool(
            "apply_diff_current_document",
            {
                "unified_diff": diff_text,
                "base_hash": base_hash,
                "dry_run": True,
            },
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "PATCH_APPLY_FAILED"
    assert "ambiguous" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_apply_diff_rejects_invalid_hunk_counts(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-1",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    read_payload = json.loads(await service.read_current_document())
    base_hash = read_payload["content_hash"]
    diff_text = (
        "--- a/notes.txt\n"
        "+++ b/notes.txt\n"
        "@@ -1,2 +1,2 @@\n"
        "-line2\n"
        "+line-two\n"
    )
    payload = json.loads(
        await service.execute_tool(
            "apply_diff_current_document",
            {
                "unified_diff": diff_text,
                "base_hash": base_hash,
                "dry_run": True,
            },
        )
    )

    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_DIFF_FORMAT"
    assert "line counts" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_search_project_text_basic_match(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    root = tmp_path / "project_root"
    (root / "src").mkdir()
    (root / "src" / "main.py").write_text("print('hello')\n", encoding="utf-8")

    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-search",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    payload = json.loads(await service.search_project_text(query="line2"))
    assert payload["ok"] is True
    assert payload["results_count"] == 1
    assert payload["results"][0]["file_path"] == "notes.txt"
    assert payload["results"][0]["line_number"] == 2


@pytest.mark.asyncio
async def test_search_project_text_include_glob_filters_files(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    root = tmp_path / "project_root"
    (root / "script.py").write_text("needle = 1\n", encoding="utf-8")
    (root / "README.md").write_text("needle in markdown\n", encoding="utf-8")

    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-search",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    payload = json.loads(
        await service.search_project_text(
            query="needle",
            include_glob="*.py",
        )
    )
    assert payload["ok"] is True
    assert payload["results_count"] == 1
    assert payload["results"][0]["file_path"] == "script.py"


@pytest.mark.asyncio
async def test_search_project_text_invalid_regex_returns_error(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-search",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    payload = json.loads(
        await service.execute_tool(
            "search_project_text",
            {
                "query": "(",
                "use_regex": True,
            },
        )
    )
    assert payload["ok"] is False
    assert payload["error"]["code"] == "INVALID_ARGUMENT"
    assert "regex" in payload["error"]["message"].lower()


@pytest.mark.asyncio
async def test_search_project_text_honors_max_results(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    root = tmp_path / "project_root"
    (root / "many.txt").write_text("hit one\nhit two\nhit three\n", encoding="utf-8")

    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-search",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    payload = json.loads(
        await service.search_project_text(
            query="hit",
            max_results=2,
        )
    )
    assert payload["ok"] is True
    assert payload["results_count"] == 2
    assert payload["truncated"] is True


@pytest.mark.asyncio
async def test_read_project_document_without_active_file(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-project-read",
        active_file_path=None,
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    payload = json.loads(
        await service.read_project_document(
            file_path="notes.txt",
            start_line=2,
            end_line=2,
        )
    )
    assert payload["ok"] is True
    assert payload["file_path"] == "notes.txt"
    assert payload["content"] == "line2"
    assert payload["line_count"] == 2
    assert payload["client_hash"] is None


@pytest.mark.asyncio
async def test_apply_diff_project_document_without_active_file(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-project-apply",
        active_file_path=None,
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )
    read_payload = json.loads(await service.read_project_document(file_path="notes.txt"))
    base_hash = read_payload["content_hash"]
    diff_text = (
        "--- a/notes.txt\n"
        "+++ b/notes.txt\n"
        "@@ -1,2 +1,2 @@\n"
        " line1\n"
        "-line2\n"
        "+line-two\n"
    )
    dry_run_payload = json.loads(
        await service.apply_diff_project_document(
            file_path="notes.txt",
            unified_diff=diff_text,
            base_hash=base_hash,
            dry_run=True,
        )
    )
    assert dry_run_payload["ok"] is True
    assert dry_run_payload["file_path"] == "notes.txt"

    confirm_payload = await confirm_pending_patch_apply(
        project_id=prepared_project.id,
        session_id="session-project-apply",
        pending_patch_id=dry_run_payload["pending_patch_id"],
        expected_hash=base_hash,
        project_service=project_service,
        pending_store=service.pending_store,
    )
    assert confirm_payload["ok"] is True
    after = await project_service.read_file(prepared_project.id, "notes.txt")
    assert after.content == "line1\nline-two\n"


@pytest.mark.asyncio
async def test_read_current_document_without_active_file_returns_error(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-no-active",
        active_file_path=None,
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    payload = json.loads(await service.execute_tool("read_current_document", {}))
    assert payload["ok"] is False
    assert payload["error"]["code"] == "NO_ACTIVE_FILE"


@pytest.mark.asyncio
async def test_get_tools_includes_shared_metadata(tmp_path, project_service: ProjectService):
    prepared_project = await _prepare_project(tmp_path, project_service)
    service = ProjectDocumentToolService(
        project_id=prepared_project.id,
        session_id="session-meta",
        active_file_path="notes.txt",
        project_service=project_service,
        pending_store=PendingPatchStore(),
    )

    tools = service.get_tools()
    metadata_by_name = {tool.name: tool.metadata for tool in tools}

    assert metadata_by_name["read_project_document"] == {
        "group": "projectDocuments",
        "source": "project_document",
        "enabled_by_default": True,
        "requires_project_knowledge": False,
    }
    assert metadata_by_name["apply_diff_project_document"] == {
        "group": "projectDocuments",
        "source": "project_document",
        "enabled_by_default": False,
        "requires_project_knowledge": False,
    }
    assert metadata_by_name["read_current_document"] == {
        "group": "projectDocuments",
        "source": "project_document",
        "enabled_by_default": True,
        "requires_project_knowledge": False,
    }
    assert metadata_by_name["apply_diff_current_document"] == {
        "group": "projectDocuments",
        "source": "project_document",
        "enabled_by_default": False,
        "requires_project_knowledge": False,
    }
    assert metadata_by_name["search_project_text"] == {
        "group": "projectDocuments",
        "source": "project_document",
        "enabled_by_default": True,
        "requires_project_knowledge": False,
    }
