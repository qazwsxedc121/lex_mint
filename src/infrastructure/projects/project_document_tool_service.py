"""Project-scoped document tools for project chat function calling."""

from __future__ import annotations

import fnmatch
import hashlib
import json
import logging
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional, Tuple

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, ValidationError
from src.tools.request_scoped import (
    APPLY_DIFF_CURRENT_DOCUMENT_TOOL,
    APPLY_DIFF_PROJECT_DOCUMENT_TOOL,
    READ_CURRENT_DOCUMENT_TOOL,
    READ_PROJECT_DOCUMENT_TOOL,
    SEARCH_PROJECT_TEXT_TOOL,
    ApplyDiffCurrentDocumentArgs,
    ApplyDiffProjectDocumentArgs,
    ReadCurrentDocumentArgs,
    ReadProjectDocumentArgs,
    SearchProjectTextArgs,
)

from src.api.config import settings
from src.infrastructure.config.project_service import ProjectService

logger = logging.getLogger(__name__)


class ProjectDocumentToolError(ValueError):
    """Structured error for project-document tool failures."""

    def __init__(self, code: str, message: str, **extra: Any):
        super().__init__(message)
        self.code = code
        self.message = message
        self.extra = extra


def compute_content_hash(content: str) -> str:
    """Compute stable content hash."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _normalize_rel_path(path: str) -> str:
    return str(path or "").replace("\\", "/").strip()


class ConfirmPendingPatchArgs(BaseModel):
    """Arguments for confirming a pending diff apply."""

    session_id: str = Field(..., min_length=1)
    pending_patch_id: str = Field(..., min_length=1)
    expected_hash: Optional[str] = Field(default=None, min_length=16, max_length=128)


@dataclass
class PendingPatch:
    """One pending dry-run patch waiting for user confirmation."""

    patch_id: str
    project_id: str
    session_id: str
    file_path: str
    base_hash: str
    patched_content: str
    created_at: float
    ttl_seconds: int

    def is_expired(self, now_ts: float) -> bool:
        return now_ts > (self.created_at + self.ttl_seconds)


class PendingPatchStore:
    """In-memory pending patch store."""

    def __init__(self) -> None:
        self._lock = Lock()
        self._patches: Dict[str, PendingPatch] = {}

    def _cleanup_locked(self, now_ts: float) -> None:
        expired_ids = [pid for pid, patch in self._patches.items() if patch.is_expired(now_ts)]
        for patch_id in expired_ids:
            self._patches.pop(patch_id, None)

    def put(self, patch: PendingPatch) -> None:
        now_ts = time.time()
        with self._lock:
            self._cleanup_locked(now_ts)
            self._patches[patch.patch_id] = patch

    def pop_valid(self, patch_id: str) -> Optional[PendingPatch]:
        now_ts = time.time()
        with self._lock:
            self._cleanup_locked(now_ts)
            patch = self._patches.get(patch_id)
            if patch is None:
                return None
            if patch.is_expired(now_ts):
                self._patches.pop(patch_id, None)
                return None
            self._patches.pop(patch_id, None)
            return patch

    def peek_valid(self, patch_id: str) -> Optional[PendingPatch]:
        now_ts = time.time()
        with self._lock:
            self._cleanup_locked(now_ts)
            patch = self._patches.get(patch_id)
            if patch is None or patch.is_expired(now_ts):
                return None
            return patch

    def peek_with_status(self, patch_id: str) -> Tuple[Optional[PendingPatch], str]:
        """Peek patch with status: valid, expired, or missing."""
        now_ts = time.time()
        with self._lock:
            patch = self._patches.get(patch_id)
            if patch is None:
                return None, "missing"
            if patch.is_expired(now_ts):
                self._patches.pop(patch_id, None)
                return patch, "expired"
            return patch, "valid"


_pending_patch_store = PendingPatchStore()
_SEARCH_MAX_FILES = 5000


_HUNK_HEADER_RE = re.compile(r"^@@\s+\-(\d+)(?:,(\d+))?\s+\+(\d+)(?:,(\d+))?\s+@@")
_SPECIAL_SPACE_RE = re.compile(r"[\u00A0\u2002-\u200A\u202F\u205F\u3000]")
_SMART_SINGLE_QUOTES_RE = re.compile(r"[\u2018\u2019\u201A\u201B]")
_SMART_DOUBLE_QUOTES_RE = re.compile(r"[\u201C\u201D\u201E\u201F]")
_DASH_RE = re.compile(r"[\u2010\u2011\u2012\u2013\u2014\u2015\u2212]")


@dataclass
class ParsedHunk:
    """Parsed unified diff hunk."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    lines: List[Tuple[str, str]]


@dataclass
class ParsedUnifiedDiff:
    """Parsed single-file unified diff."""

    old_path: Optional[str]
    new_path: Optional[str]
    hunks: List[ParsedHunk]
    additions: int
    deletions: int


def _parse_unified_diff(unified_diff: str) -> ParsedUnifiedDiff:
    lines = unified_diff.splitlines()
    old_path: Optional[str] = None
    new_path: Optional[str] = None
    hunks: List[ParsedHunk] = []
    additions = 0
    deletions = 0
    idx = 0

    while idx < len(lines):
        line = lines[idx]
        if line.startswith("--- "):
            old_path = line[4:].strip()
            idx += 1
            continue
        if line.startswith("+++ "):
            new_path = line[4:].strip()
            idx += 1
            continue
        if line.startswith("@@"):
            match = _HUNK_HEADER_RE.match(line)
            if not match:
                raise ProjectDocumentToolError(
                    "INVALID_DIFF_FORMAT",
                    f"Invalid hunk header: {line}",
                )
            old_start = int(match.group(1))
            old_count = int(match.group(2) or "1")
            new_start = int(match.group(3))
            new_count = int(match.group(4) or "1")
            idx += 1

            hunk_lines: List[Tuple[str, str]] = []
            while idx < len(lines):
                hline = lines[idx]
                if hline.startswith("@@"):
                    break
                if hline.startswith("\\ No newline at end of file"):
                    idx += 1
                    continue
                if not hline:
                    # In unified diff, empty content line still has a prefix char.
                    raise ProjectDocumentToolError(
                        "INVALID_DIFF_FORMAT",
                        "Malformed diff line in hunk",
                    )
                prefix = hline[0]
                text = hline[1:]
                if prefix not in (" ", "+", "-"):
                    raise ProjectDocumentToolError(
                        "INVALID_DIFF_FORMAT",
                        f"Unsupported hunk line prefix: {prefix}",
                    )
                if prefix == "+":
                    additions += 1
                elif prefix == "-":
                    deletions += 1
                hunk_lines.append((prefix, text))
                idx += 1

            old_line_total = sum(1 for prefix, _ in hunk_lines if prefix in (" ", "-"))
            new_line_total = sum(1 for prefix, _ in hunk_lines if prefix in (" ", "+"))
            if old_line_total != old_count or new_line_total != new_count:
                raise ProjectDocumentToolError(
                    "INVALID_DIFF_FORMAT",
                    (
                        "Hunk line counts do not match header: "
                        f"expected -{old_count}/+{new_count}, got -{old_line_total}/+{new_line_total}."
                    ),
                )

            hunks.append(
                ParsedHunk(
                    old_start=old_start,
                    old_count=old_count,
                    new_start=new_start,
                    new_count=new_count,
                    lines=hunk_lines,
                )
            )
            continue
        idx += 1

    if not hunks:
        raise ProjectDocumentToolError("INVALID_DIFF_FORMAT", "No diff hunks found")

    return ParsedUnifiedDiff(
        old_path=old_path,
        new_path=new_path,
        hunks=hunks,
        additions=additions,
        deletions=deletions,
    )


def _strip_diff_path(path: str) -> str:
    value = _normalize_rel_path(path)
    if "\t" in value:
        value = value.split("\t", 1)[0]
    if value.startswith('"') and value.endswith('"') and len(value) >= 2:
        value = value[1:-1]
    if value.startswith("a/") or value.startswith("b/"):
        return value[2:]
    return value


def _normalize_for_fuzzy_match(text: str) -> str:
    normalized = text.rstrip()
    normalized = _SMART_SINGLE_QUOTES_RE.sub("'", normalized)
    normalized = _SMART_DOUBLE_QUOTES_RE.sub('"', normalized)
    normalized = _DASH_RE.sub("-", normalized)
    normalized = _SPECIAL_SPACE_RE.sub(" ", normalized)
    return normalized


def _same_line_text(source_line: str, diff_line: str) -> bool:
    source_text = source_line.rstrip("\r\n")
    if source_text == diff_line:
        return True
    return _normalize_for_fuzzy_match(source_text) == _normalize_for_fuzzy_match(diff_line)


def _detect_newline_style(content: str) -> str:
    if "\r\n" in content:
        return "\r\n"
    return "\n"


def _hunk_matches_at(source_lines: List[str], start: int, hunk: ParsedHunk) -> bool:
    cursor = start
    for prefix, text in hunk.lines:
        if prefix == "+":
            continue
        if cursor >= len(source_lines) or not _same_line_text(source_lines[cursor], text):
            return False
        cursor += 1
    return True


def _resolve_hunk_start(source_lines: List[str], cursor: int, expected_start: int, hunk: ParsedHunk) -> int:
    if expected_start < cursor:
        raise ProjectDocumentToolError(
            "PATCH_APPLY_FAILED",
            "Overlapping hunks are not supported",
        )

    if _hunk_matches_at(source_lines, expected_start, hunk):
        return expected_start

    pattern_len = sum(1 for prefix, _ in hunk.lines if prefix != "+")
    if pattern_len == 0:
        return expected_start

    max_start = len(source_lines) - pattern_len
    if max_start < cursor:
        raise ProjectDocumentToolError(
            "PATCH_APPLY_FAILED",
            f"Context mismatch near line {expected_start + 1}",
        )

    matches: List[int] = []
    for candidate in range(cursor, max_start + 1):
        if _hunk_matches_at(source_lines, candidate, hunk):
            matches.append(candidate)
            if len(matches) > 1:
                break

    if not matches:
        raise ProjectDocumentToolError(
            "PATCH_APPLY_FAILED",
            f"Context mismatch near line {expected_start + 1}",
        )
    if len(matches) > 1:
        raise ProjectDocumentToolError(
            "PATCH_APPLY_FAILED",
            (
                "Patch hunk location is ambiguous; multiple candidate regions match. "
                "Regenerate the diff with more surrounding context."
            ),
        )
    return matches[0]


def _apply_parsed_diff(content: str, parsed: ParsedUnifiedDiff) -> str:
    source_lines = content.splitlines(keepends=True)
    newline = _detect_newline_style(content)
    result: List[str] = []
    cursor = 0

    for hunk in parsed.hunks:
        hunk_start = max(0, hunk.old_start - 1)
        hunk_start = _resolve_hunk_start(source_lines, cursor, hunk_start, hunk)

        result.extend(source_lines[cursor:hunk_start])
        cursor = hunk_start

        for prefix, text in hunk.lines:
            if prefix == " ":
                if cursor >= len(source_lines) or not _same_line_text(source_lines[cursor], text):
                    raise ProjectDocumentToolError(
                        "PATCH_APPLY_FAILED",
                        f"Context mismatch near line {cursor + 1}",
                    )
                result.append(source_lines[cursor])
                cursor += 1
                continue

            if prefix == "-":
                if cursor >= len(source_lines) or not _same_line_text(source_lines[cursor], text):
                    raise ProjectDocumentToolError(
                        "PATCH_APPLY_FAILED",
                        f"Delete mismatch near line {cursor + 1}",
                    )
                cursor += 1
                continue

            # prefix == "+"
            result.append(f"{text}{newline}")

    result.extend(source_lines[cursor:])
    return "".join(result)


class ProjectDocumentToolService:
    """Project chat tools for active-file and cross-file editing."""

    def __init__(
        self,
        *,
        project_id: str,
        session_id: str,
        active_file_path: Optional[str] = None,
        active_file_hash: Optional[str] = None,
        project_service: Optional[ProjectService] = None,
        pending_store: Optional[PendingPatchStore] = None,
        pending_ttl_seconds: Optional[int] = None,
    ) -> None:
        self.project_id = project_id
        self.session_id = session_id
        self.active_file_path = _normalize_rel_path(active_file_path) or None
        self.active_file_hash = (active_file_hash or "").strip() or None
        self.project_service = project_service or ProjectService()
        self.pending_store = pending_store or _pending_patch_store
        configured_ttl = pending_ttl_seconds
        if configured_ttl is None:
            configured_ttl = int(getattr(settings, "project_chat_pending_patch_ttl_seconds", 3600))
        self.pending_ttl_seconds = max(60, int(configured_ttl))

    @staticmethod
    def _json(data: Dict[str, Any]) -> str:
        return json.dumps(data, ensure_ascii=False)

    def _error(self, code: str, message: str, **extra: Any) -> str:
        payload: Dict[str, Any] = {
            "ok": False,
            "error": {
                "code": code,
                "message": message,
            },
        }
        payload.update(extra)
        return self._json(payload)

    def get_tools(self) -> List[BaseTool]:
        """Build project-document tools for LLM function calling."""
        tools: List[BaseTool] = [
            READ_PROJECT_DOCUMENT_TOOL.build_tool(coroutine=self.read_project_document),
            APPLY_DIFF_PROJECT_DOCUMENT_TOOL.build_tool(coroutine=self.apply_diff_project_document),
        ]

        if self.active_file_path:
            tools.extend([
                READ_CURRENT_DOCUMENT_TOOL.build_tool(coroutine=self.read_current_document),
                APPLY_DIFF_CURRENT_DOCUMENT_TOOL.build_tool(coroutine=self.apply_diff_current_document),
            ])

        tools.append(SEARCH_PROJECT_TEXT_TOOL.build_tool(coroutine=self.search_project_text))
        return tools

    async def execute_tool(self, name: str, args: Dict[str, Any]) -> Optional[str]:
        """Request-scoped executor contract used by tool loop."""
        try:
            if name == "read_project_document":
                parsed = ReadProjectDocumentArgs.model_validate(args or {})
                return await self.read_project_document(
                    file_path=parsed.file_path,
                    start_line=parsed.start_line,
                    end_line=parsed.end_line,
                    max_chars=parsed.max_chars,
                )

            if name == "apply_diff_project_document":
                parsed = ApplyDiffProjectDocumentArgs.model_validate(args or {})
                return await self.apply_diff_project_document(
                    file_path=parsed.file_path,
                    unified_diff=parsed.unified_diff,
                    base_hash=parsed.base_hash,
                    dry_run=parsed.dry_run,
                )

            if name == "read_current_document":
                parsed = ReadCurrentDocumentArgs.model_validate(args or {})
                return await self.read_current_document(
                    start_line=parsed.start_line,
                    end_line=parsed.end_line,
                    max_chars=parsed.max_chars,
                )

            if name == "apply_diff_current_document":
                parsed = ApplyDiffCurrentDocumentArgs.model_validate(args or {})
                return await self.apply_diff_current_document(
                    unified_diff=parsed.unified_diff,
                    base_hash=parsed.base_hash,
                    dry_run=parsed.dry_run,
                )

            if name == "search_project_text":
                parsed = SearchProjectTextArgs.model_validate(args or {})
                return await self.search_project_text(
                    query=parsed.query,
                    case_sensitive=parsed.case_sensitive,
                    use_regex=parsed.use_regex,
                    include_glob=parsed.include_glob,
                    exclude_glob=parsed.exclude_glob,
                    max_results=parsed.max_results,
                    context_lines=parsed.context_lines,
                    max_chars_per_line=parsed.max_chars_per_line,
                )

            return None
        except ValidationError as e:
            return self._error("INVALID_ARGUMENT", "Tool arguments are invalid", details=str(e))
        except ProjectDocumentToolError as e:
            return self._error(e.code, e.message, **e.extra)
        except Exception as e:
            logger.exception("Project document tool execution failed: %s", e)
            return self._error("TOOL_EXECUTION_FAILED", f"Tool execution failed: {e}")

    def _require_active_file_path(self) -> str:
        if self.active_file_path:
            return self.active_file_path
        raise ProjectDocumentToolError(
            "NO_ACTIVE_FILE",
            "No active file selected. Use read_project_document/apply_diff_project_document with file_path.",
        )

    @staticmethod
    def _normalize_required_file_path(file_path: str) -> str:
        normalized = _normalize_rel_path(file_path)
        if not normalized:
            raise ProjectDocumentToolError("INVALID_ARGUMENT", "file_path is required")
        return normalized

    async def _read_project_file(self, file_path: str) -> Tuple[str, str]:
        normalized_file_path = self._normalize_required_file_path(file_path)
        file_data = await self.project_service.read_file(self.project_id, normalized_file_path)
        return file_data.content or "", file_data.encoding

    async def _read_active_file(self) -> Tuple[str, str]:
        active_file_path = self._require_active_file_path()
        file_data = await self.project_service.read_file(self.project_id, active_file_path)
        return file_data.content or "", file_data.encoding

    def _build_read_payload(
        self,
        *,
        file_path: str,
        content: str,
        start_line: Optional[int],
        end_line: Optional[int],
        max_chars: int,
        client_hash: Optional[str],
    ) -> Dict[str, Any]:
        all_lines = content.splitlines()
        line_count = len(all_lines)

        if line_count == 0:
            return {
                "ok": True,
                "file_path": file_path,
                "line_count": 0,
                "content_hash": compute_content_hash(content),
                "client_hash": client_hash,
                "range": {
                    "start_line": 1,
                    "end_line": 0,
                },
                "truncated": False,
                "content": "",
            }

        if start_line is None:
            start_line = 1
        if end_line is None:
            end_line = line_count
        if end_line < start_line:
            raise ProjectDocumentToolError(
                "INVALID_ARGUMENT",
                "end_line must be greater than or equal to start_line",
            )

        start_idx = max(0, start_line - 1)
        end_idx = min(line_count, end_line)
        selected_lines = all_lines[start_idx:end_idx]
        selected_content = "\n".join(selected_lines)
        truncated = False
        if len(selected_content) > max_chars:
            selected_content = selected_content[:max_chars]
            truncated = True

        return {
            "ok": True,
            "file_path": file_path,
            "line_count": line_count,
            "content_hash": compute_content_hash(content),
            "client_hash": client_hash,
            "range": {
                "start_line": start_line,
                "end_line": min(end_line, line_count),
            },
            "truncated": truncated,
            "content": selected_content,
        }

    async def read_current_document(
        self,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        max_chars: int = 12000,
    ) -> str:
        """Read current active file content (optionally by line range)."""
        active_file_path = self._require_active_file_path()
        content, _ = await self._read_active_file()
        payload = self._build_read_payload(
            file_path=active_file_path,
            content=content,
            start_line=start_line,
            end_line=end_line,
            max_chars=max_chars,
            client_hash=self.active_file_hash,
        )
        return self._json(payload)

    async def apply_diff_current_document(
        self,
        unified_diff: str,
        base_hash: str,
        dry_run: bool = True,
    ) -> str:
        """Validate and dry-run apply unified diff for active file."""
        active_file_path = self._require_active_file_path()
        payload = await self._apply_diff_for_file(
            file_path=active_file_path,
            unified_diff=unified_diff,
            base_hash=base_hash,
            dry_run=dry_run,
            mode="dry_run",
            hash_mismatch_message="Document changed since read; call read_current_document again.",
            target_mismatch_message=(
                f"Diff target does not match active file '{active_file_path}'."
            ),
        )
        return self._json(payload)

    async def read_project_document(
        self,
        *,
        file_path: str,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
        max_chars: int = 12000,
    ) -> str:
        """Read any project file content by file path."""
        normalized_file_path = self._normalize_required_file_path(file_path)
        content, _ = await self._read_project_file(normalized_file_path)
        payload = self._build_read_payload(
            file_path=normalized_file_path,
            content=content,
            start_line=start_line,
            end_line=end_line,
            max_chars=max_chars,
            client_hash=None,
        )
        return self._json(payload)

    async def apply_diff_project_document(
        self,
        *,
        file_path: str,
        unified_diff: str,
        base_hash: str,
        dry_run: bool = True,
    ) -> str:
        """Validate and dry-run apply unified diff for a specific project file."""
        normalized_file_path = self._normalize_required_file_path(file_path)
        payload = await self._apply_diff_for_file(
            file_path=normalized_file_path,
            unified_diff=unified_diff,
            base_hash=base_hash,
            dry_run=dry_run,
            mode="dry_run",
            hash_mismatch_message="Document changed since read; call read_project_document again.",
            target_mismatch_message=(
                f"Diff target does not match file_path '{normalized_file_path}'."
            ),
        )
        return self._json(payload)

    async def _apply_diff_for_file(
        self,
        *,
        file_path: str,
        unified_diff: str,
        base_hash: str,
        dry_run: bool,
        mode: str,
        hash_mismatch_message: str,
        target_mismatch_message: str,
    ) -> Dict[str, Any]:
        if not dry_run:
            raise ProjectDocumentToolError(
                "CONFIRMATION_REQUIRED",
                "apply_diff tools only support dry_run=true. Confirm via API to apply.",
            )

        current_content, _ = await self._read_project_file(file_path)
        current_hash = compute_content_hash(current_content)
        if current_hash != base_hash:
            raise ProjectDocumentToolError(
                "HASH_MISMATCH",
                hash_mismatch_message,
                current_hash=current_hash,
                expected_hash=base_hash,
            )

        parsed = _parse_unified_diff(unified_diff)
        for diff_path in (parsed.old_path, parsed.new_path):
            if not diff_path:
                continue
            normalized_diff_path = _strip_diff_path(diff_path)
            if normalized_diff_path in ("/dev/null", "dev/null"):
                raise ProjectDocumentToolError(
                    "TARGET_FILE_NOT_ALLOWED",
                    "Creating or deleting files is not allowed in project chat patch mode.",
                )
            if _normalize_rel_path(normalized_diff_path) != file_path:
                raise ProjectDocumentToolError(
                    "TARGET_FILE_NOT_ALLOWED",
                    target_mismatch_message,
                    diff_target=normalized_diff_path,
                    file_path=file_path,
                )

        patched_content = _apply_parsed_diff(current_content, parsed)
        new_hash = compute_content_hash(patched_content)
        pending_patch_id = uuid.uuid4().hex
        created_at = time.time()
        expires_at = created_at + self.pending_ttl_seconds
        self.pending_store.put(
            PendingPatch(
                patch_id=pending_patch_id,
                project_id=self.project_id,
                session_id=self.session_id,
                file_path=file_path,
                base_hash=base_hash,
                patched_content=patched_content,
                created_at=created_at,
                ttl_seconds=self.pending_ttl_seconds,
            )
        )

        return {
            "ok": True,
            "mode": mode,
            "applied": False,
            "file_path": file_path,
            "base_hash": base_hash,
            "new_content_hash": new_hash,
            "pending_patch_id": pending_patch_id,
            "pending_patch_ttl_seconds": self.pending_ttl_seconds,
            "pending_patch_expires_at": int(expires_at * 1000),
            "preview": {
                "additions": parsed.additions,
                "deletions": parsed.deletions,
                "hunks": len(parsed.hunks),
            },
        }

    @staticmethod
    def _trim_line(text: str, max_chars_per_line: int) -> str:
        if len(text) <= max_chars_per_line:
            return text
        return text[: max_chars_per_line - 1] + "…"

    @staticmethod
    def _line_matches(
        line: str,
        *,
        query: str,
        use_regex: bool,
        case_sensitive: bool,
        regex: Optional[re.Pattern[str]],
    ) -> bool:
        if use_regex:
            assert regex is not None
            return bool(regex.search(line))
        if case_sensitive:
            return query in line
        return query.lower() in line.lower()

    async def search_project_text(
        self,
        query: str,
        case_sensitive: bool = False,
        use_regex: bool = False,
        include_glob: Optional[str] = None,
        exclude_glob: Optional[str] = None,
        max_results: int = 30,
        context_lines: int = 0,
        max_chars_per_line: int = 300,
    ) -> str:
        """Search text in project files and return compact structured matches."""
        project = await self.project_service.get_project(self.project_id)
        if project is None:
            raise ProjectDocumentToolError("PROJECT_NOT_FOUND", f"Project not found: {self.project_id}")

        root_path = Path(project.root_path)
        if not root_path.exists() or not root_path.is_dir():
            raise ProjectDocumentToolError(
                "PROJECT_ROOT_INVALID",
                f"Project root is not a directory: {project.root_path}",
            )

        regex: Optional[re.Pattern[str]] = None
        if use_regex:
            flags = 0 if case_sensitive else re.IGNORECASE
            try:
                regex = re.compile(query, flags)
            except re.error as e:
                raise ProjectDocumentToolError("INVALID_ARGUMENT", f"Invalid regex pattern: {e}")

        max_file_bytes = settings.max_file_read_size_mb * 1024 * 1024
        results: List[Dict[str, Any]] = []
        scanned_files = 0
        skipped_binary_files = 0
        skipped_large_files = 0
        skipped_hidden_files = 0
        scan_limit_hit = False
        truncated = False

        for abs_path in root_path.rglob("*"):
            if not abs_path.is_file():
                continue

            if scanned_files >= _SEARCH_MAX_FILES:
                scan_limit_hit = True
                break
            scanned_files += 1

            rel_path = str(abs_path.relative_to(root_path)).replace("\\", "/")
            path_parts = Path(rel_path).parts
            if any(part.startswith(".") for part in path_parts):
                skipped_hidden_files += 1
                continue

            if include_glob and not fnmatch.fnmatch(rel_path, include_glob):
                continue
            if exclude_glob and fnmatch.fnmatch(rel_path, exclude_glob):
                continue

            try:
                file_size = abs_path.stat().st_size
                if file_size > max_file_bytes:
                    skipped_large_files += 1
                    continue

                raw = abs_path.read_bytes()
                if b"\x00" in raw[:4096]:
                    skipped_binary_files += 1
                    continue
                text = raw.decode("utf-8", errors="replace")
            except OSError:
                continue

            lines = text.splitlines()
            for idx, line in enumerate(lines):
                if not self._line_matches(
                    line,
                    query=query,
                    use_regex=use_regex,
                    case_sensitive=case_sensitive,
                    regex=regex,
                ):
                    continue

                start = max(0, idx - context_lines)
                end = min(len(lines), idx + context_lines + 1)
                results.append(
                    {
                        "file_path": rel_path,
                        "line_number": idx + 1,
                        "line_text": self._trim_line(line, max_chars_per_line),
                        "context_before": [
                            self._trim_line(lines[i], max_chars_per_line)
                            for i in range(start, idx)
                        ],
                        "context_after": [
                            self._trim_line(lines[i], max_chars_per_line)
                            for i in range(idx + 1, end)
                        ],
                    }
                )
                if len(results) >= max_results:
                    truncated = True
                    break

            if truncated:
                break

        payload = {
            "ok": True,
            "query": query,
            "case_sensitive": case_sensitive,
            "use_regex": use_regex,
            "include_glob": include_glob,
            "exclude_glob": exclude_glob,
            "max_results": max_results,
            "results_count": len(results),
            "truncated": truncated,
            "scan_limit_hit": scan_limit_hit,
            "scanned_files": scanned_files,
            "skipped_hidden_files": skipped_hidden_files,
            "skipped_binary_files": skipped_binary_files,
            "skipped_large_files": skipped_large_files,
            "results": results,
        }
        return self._json(payload)


async def confirm_pending_patch_apply(
    *,
    project_id: str,
    session_id: str,
    pending_patch_id: str,
    expected_hash: Optional[str] = None,
    project_service: Optional[ProjectService] = None,
    pending_store: Optional[PendingPatchStore] = None,
) -> Dict[str, Any]:
    """Apply one pending patch after explicit user confirmation."""
    store = pending_store or _pending_patch_store
    service = project_service or ProjectService()

    pending, pending_status = store.peek_with_status(pending_patch_id)
    if pending_status == "expired":
        expires_at = None
        if pending is not None:
            expires_at = int((pending.created_at + pending.ttl_seconds) * 1000)
        raise ProjectDocumentToolError(
            "PATCH_EXPIRED",
            "Pending patch expired. Ask the model to generate a new diff.",
            expires_at=expires_at,
        )
    if pending_status == "missing" or pending is None:
        raise ProjectDocumentToolError(
            "PATCH_EXPIRED",
            "Pending patch not found (it may have been cleared by restart). Ask the model to generate a new diff.",
            reason="not_found_or_restarted",
        )

    if pending.project_id != project_id or pending.session_id != session_id:
        raise ProjectDocumentToolError(
            "PATCH_NOT_FOUND",
            "Pending patch does not belong to this project session.",
        )

    file_data = await service.read_file(project_id, pending.file_path)
    current_content = file_data.content or ""
    current_hash = compute_content_hash(current_content)
    if expected_hash and expected_hash != current_hash:
        raise ProjectDocumentToolError(
            "HASH_MISMATCH",
            "Document changed; confirmation rejected.",
            current_hash=current_hash,
            expected_hash=expected_hash,
        )
    if pending.base_hash != current_hash:
        raise ProjectDocumentToolError(
            "HASH_MISMATCH",
            "Document changed since dry-run preview; regenerate diff first.",
            current_hash=current_hash,
            expected_hash=pending.base_hash,
        )

    # Consume pending patch atomically before write to avoid double-apply.
    consumed = store.pop_valid(pending_patch_id)
    if consumed is None:
        raise ProjectDocumentToolError(
            "PATCH_EXPIRED",
            "Pending patch not found or expired. Ask the model to generate a new diff.",
        )

    updated = await service.write_file(
        project_id,
        consumed.file_path,
        consumed.patched_content,
        file_data.encoding,
    )
    new_hash = compute_content_hash(updated.content or "")

    return {
        "ok": True,
        "file_path": consumed.file_path,
        "new_content_hash": new_hash,
        "updated_at": int(time.time() * 1000),
        "content": updated.content,
    }
