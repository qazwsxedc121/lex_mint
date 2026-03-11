"""Project-local workspace state persisted under .lex_mint/state/."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Optional

import aiofiles
import yaml

from src.api.models.project_config import (
    ProjectWorkspaceItemUpsert,
    ProjectWorkspaceRecentItem,
    ProjectWorkspaceState,
)
from src.infrastructure.config.project_service import ProjectService


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _normalize_relative_path(value: str) -> str:
    normalized = (value or "").replace("\\", "/").strip()
    if not normalized:
        raise ValueError("Path is required")
    pure = PurePosixPath(normalized)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError("Path must be a safe relative path")
    return str(pure)


class ProjectWorkspaceStateService:
    """Read/write project-local workspace state inside project_root/.lex_mint/."""

    _locks: dict[str, asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    def __init__(self, project_service: Optional[ProjectService] = None, max_recent_items: int = 20):
        self.project_service = project_service or ProjectService()
        self.max_recent_items = max(1, int(max_recent_items))

    async def _get_project_root(self, project_id: str) -> Path:
        project = await self.project_service.get_project(project_id)
        if project is None:
            raise ValueError(f"Project not found: {project_id}")
        return Path(project.root_path)

    def _state_path(self, project_root: Path) -> Path:
        return project_root / ".lex_mint" / "state" / "project_workspace_state.yaml"

    def _default_state(self, project_id: str) -> ProjectWorkspaceState:
        return ProjectWorkspaceState(project_id=project_id, updated_at=None, recent_items=[], extra={})

    async def _get_lock(self, project_root: Path) -> asyncio.Lock:
        key = str(self._state_path(project_root).resolve())
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def _read_state(self, project_id: str, project_root: Path) -> ProjectWorkspaceState:
        path = self._state_path(project_root)
        if not path.exists():
            return self._default_state(project_id)

        async with aiofiles.open(path, "r", encoding="utf-8") as f:
            content = await f.read()

        if not content.strip():
            return self._default_state(project_id)

        data = yaml.safe_load(content) or {}
        if not isinstance(data, dict):
            return self._default_state(project_id)
        data.setdefault("project_id", project_id)
        data.setdefault("recent_items", [])
        data.setdefault("extra", {})
        data.setdefault("version", 1)
        return ProjectWorkspaceState(**data)

    async def _write_state(self, project_root: Path, state: ProjectWorkspaceState) -> None:
        path = self._state_path(project_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = path.with_suffix(".yaml.tmp")
        payload = state.model_dump(mode="json")
        async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
            await f.write(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False))
        temp_path.replace(path)

    def _build_recent_item(self, item: ProjectWorkspaceItemUpsert) -> ProjectWorkspaceRecentItem:
        updated_at = (item.updated_at or "").strip() or _now_iso()
        normalized_title = item.title.strip() or item.id.strip()

        if item.type == "file":
            normalized_path = _normalize_relative_path(item.path or item.id)
            return ProjectWorkspaceRecentItem(
                type=item.type,
                id=normalized_path,
                title=normalized_title or Path(normalized_path).name,
                path=normalized_path,
                updated_at=updated_at,
                meta=dict(item.meta or {}),
            )

        return ProjectWorkspaceRecentItem(
            type=item.type,
            id=item.id.strip(),
            title=normalized_title,
            path=None,
            updated_at=updated_at,
            meta=dict(item.meta or {}),
        )

    def _merge_item(self, state: ProjectWorkspaceState, item: ProjectWorkspaceRecentItem) -> ProjectWorkspaceState:
        filtered = [
            existing
            for existing in state.recent_items
            if not (existing.type == item.type and existing.id == item.id)
        ]
        merged = [item, *filtered]
        merged.sort(key=lambda entry: entry.updated_at, reverse=True)
        state.recent_items = merged[: self.max_recent_items]
        state.updated_at = item.updated_at
        return state

    async def get_workspace_state(self, project_id: str) -> ProjectWorkspaceState:
        project_root = await self._get_project_root(project_id)
        return await self._read_state(project_id, project_root)

    async def upsert_recent_item(self, project_id: str, item: ProjectWorkspaceItemUpsert) -> ProjectWorkspaceState:
        project_root = await self._get_project_root(project_id)
        lock = await self._get_lock(project_root)
        async with lock:
            state = await self._read_state(project_id, project_root)
            recent_item = self._build_recent_item(item)
            state = self._merge_item(state, recent_item)
            await self._write_state(project_root, state)
            return state
