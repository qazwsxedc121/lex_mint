"""Build bounded prompt context from referenced project files."""

from __future__ import annotations

import logging
from typing import Protocol

from src.domain.models.project_config import FileContent
from src.infrastructure.config.file_reference_config_service import (
    FileReferenceConfig,
    FileReferenceConfigService,
)

logger = logging.getLogger(__name__)


class ProjectFileReader(Protocol):
    async def read_file(self, project_id: str, relative_path: str) -> FileContent: ...


class FileReferenceContextBuilder:
    """Render file references into bounded prompt-safe context blocks."""

    def __init__(
        self,
        file_reference_config_service: FileReferenceConfigService,
        project_service: ProjectFileReader,
    ):
        self.file_reference_config_service = file_reference_config_service
        self.project_service = project_service

    def _get_file_reference_config(self) -> FileReferenceConfig:
        """Load latest runtime limits; fall back to hardcoded defaults on error."""
        try:
            self.file_reference_config_service.reload_config()
            return self.file_reference_config_service.config
        except Exception as exc:
            logger.warning("Failed to refresh file reference config, using defaults: %s", exc)
            return FileReferenceConfig(
                ui_preview_max_chars=1200,
                ui_preview_max_lines=28,
                injection_preview_max_chars=600,
                injection_preview_max_lines=40,
                chunk_size=2500,
                max_chunks=6,
                total_budget_chars=18000,
            )

    @staticmethod
    def _format_file_reference_block(title: str, body: str) -> str:
        """Wrap file reference context in the same block format used by frontend blocks."""
        return f"[Block: {title}]\n```text\n{body}\n```"

    @staticmethod
    def _abbreviate_chunk_text(text: str, max_chars: int, max_lines: int) -> str:
        """Return a compact preview bounded by lines and chars."""
        safe_max_chars = max(1, max_chars)
        safe_max_lines = max(1, max_lines)
        lines = text.splitlines()
        if len(lines) > safe_max_lines:
            text = "\n".join(lines[:safe_max_lines])

        if len(text) <= safe_max_chars:
            return text
        head = int(safe_max_chars * 0.65)
        tail = safe_max_chars - head
        return f"{text[:head]}\n...\n{text[-tail:]}"

    @staticmethod
    def _select_chunk_indexes(total_chunks: int, max_chunks: int) -> list[int]:
        """Select representative chunk indexes across the whole file."""
        if total_chunks <= max_chunks:
            return list(range(total_chunks))
        if max_chunks <= 1:
            return [0]

        selected = {0, total_chunks - 1}
        middle_slots = max_chunks - 2
        if middle_slots > 0:
            for index in range(1, middle_slots + 1):
                chunk_index = round(index * (total_chunks - 1) / (middle_slots + 1))
                selected.add(chunk_index)

        ordered = sorted(selected)
        while len(ordered) > max_chunks:
            ordered.pop(len(ordered) // 2)
        return ordered

    async def _read_file_reference(
        self,
        project_id: str,
        file_path: str,
        cfg: FileReferenceConfig,
    ) -> str:
        """Read file and return chunked, abbreviated context safe for large files."""
        try:
            file_content = await self.project_service.read_file(project_id, file_path)
            content = file_content.content or ""

            if not content:
                return self._format_file_reference_block(
                    f"File Reference: {file_path}",
                    "[Content Summary] empty file",
                )

            chunk_size = max(1, cfg.chunk_size)
            max_chunks = max(1, cfg.max_chunks)
            preview_max_chars = max(1, cfg.injection_preview_max_chars)
            preview_max_lines = max(1, cfg.injection_preview_max_lines)

            chunks = [content[i : i + chunk_size] for i in range(0, len(content), chunk_size)]
            total_chunks = len(chunks)
            selected_indexes = self._select_chunk_indexes(total_chunks, max_chunks)

            chunk_blocks: list[str] = []
            for index in selected_indexes:
                chunk = chunks[index]
                start_char = index * chunk_size + 1
                end_char = min((index + 1) * chunk_size, len(content))
                preview = self._abbreviate_chunk_text(
                    chunk,
                    preview_max_chars,
                    preview_max_lines,
                )
                chunk_blocks.append(
                    f"[Chunk {index + 1}/{total_chunks} | chars {start_char}-{end_char}]\n{preview}"
                )

            block_body = (
                f"[Content Summary] {len(content)} chars, {total_chunks} chunks; "
                f"showing {len(selected_indexes)} abbreviated chunks "
                f"(<= {preview_max_lines} lines and <= {preview_max_chars} chars each).\n\n"
                f"{chr(10).join(chunk_blocks)}\n\n"
                "[Hint] Ask for a specific chunk number or keyword range if you need more detail."
            )
            return self._format_file_reference_block(f"File Reference: {file_path}", block_body)
        except Exception as exc:
            logger.warning("Failed to read file %s from project %s: %s", file_path, project_id, exc)
            return self._format_file_reference_block(
                f"File Reference: {file_path}",
                "[Error] Could not read file",
            )

    async def build_context_block(
        self,
        file_references: list[dict[str, str]] | None,
    ) -> str:
        """Build bounded context from referenced files to avoid context explosion."""
        if not file_references:
            return ""

        cfg = self._get_file_reference_config()
        total_budget_chars = max(1, cfg.total_budget_chars)
        parts: list[str] = []
        used_chars = 0

        for index, ref in enumerate(file_references):
            ref_project_id = ref.get("project_id")
            ref_path = ref.get("path")
            if not ref_project_id or not ref_path:
                continue

            file_context = await self._read_file_reference(
                ref_project_id,
                ref_path,
                cfg,
            )

            if used_chars + len(file_context) > total_budget_chars:
                skipped = len(file_references) - index
                parts.append(
                    self._format_file_reference_block(
                        "File Reference Budget",
                        f"[File Context Truncated] budget reached; skipped {skipped} remaining file reference(s).",
                    )
                )
                break

            parts.append(file_context)
            used_chars += len(file_context)

        return "\n\n".join(parts)
