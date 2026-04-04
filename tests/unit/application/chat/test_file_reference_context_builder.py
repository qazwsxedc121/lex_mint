"""Tests for file reference prompt context building."""

from __future__ import annotations

import pytest

from src.application.chat.file_reference_context_builder import FileReferenceContextBuilder
from src.domain.models.project_config import FileContent
from src.infrastructure.config.file_reference_config_service import FileReferenceConfig


class _ConfigService:
    def __init__(self, *, fail: bool = False):
        self.fail = fail
        self.config = FileReferenceConfig(
            ui_preview_max_chars=100,
            ui_preview_max_lines=10,
            injection_preview_max_chars=30,
            injection_preview_max_lines=3,
            chunk_size=20,
            max_chunks=3,
            total_budget_chars=450,
        )

    def reload_config(self) -> None:
        if self.fail:
            raise RuntimeError("reload failed")


class _ProjectService:
    def __init__(self, content: str, *, fail: bool = False):
        self.content = content
        self.fail = fail

    async def read_file(self, project_id: str, relative_path: str) -> FileContent:
        if self.fail:
            raise RuntimeError("cannot read")
        return FileContent(path=relative_path, content=self.content, size=len(self.content))


def test_select_chunk_indexes_and_abbreviate():
    indexes = FileReferenceContextBuilder._select_chunk_indexes(total_chunks=8, max_chunks=4)
    assert indexes[0] == 0
    assert indexes[-1] == 7

    preview = FileReferenceContextBuilder._abbreviate_chunk_text(
        "line1\nline2\nline3\nline4\nline5",
        max_chars=12,
        max_lines=3,
    )
    assert "..." in preview


@pytest.mark.asyncio
async def test_build_context_block_reads_files_and_enforces_budget():
    builder = FileReferenceContextBuilder(
        file_reference_config_service=_ConfigService(),
        project_service=_ProjectService("abcdefghijklmnopqrstuvwxyz" * 5),
    )

    result = await builder.build_context_block(
        [
            {"project_id": "p1", "path": "src/a.py"},
            {"project_id": "p1", "path": "src/b.py"},
            {"project_id": "p1", "path": "src/c.py"},
        ]
    )

    assert "[Block: File Reference: src/a.py]" in result
    assert "[Chunk" in result
    assert "File Reference Budget" in result


@pytest.mark.asyncio
async def test_build_context_block_handles_defaults_empty_and_errors():
    default_builder = FileReferenceContextBuilder(
        file_reference_config_service=_ConfigService(fail=True),
        project_service=_ProjectService(""),
    )
    empty_result = await default_builder.build_context_block(
        [{"project_id": "p1", "path": "empty.txt"}]
    )
    assert "empty file" in empty_result

    error_builder = FileReferenceContextBuilder(
        file_reference_config_service=_ConfigService(),
        project_service=_ProjectService("x", fail=True),
    )
    error_result = await error_builder.build_context_block(
        [{"project_id": "p1", "path": "bad.txt"}]
    )
    assert "Could not read file" in error_result

    assert await error_builder.build_context_block(None) == ""
