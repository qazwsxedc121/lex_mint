"""Workflow configuration management service."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List, Optional

import aiofiles
import yaml

from ..models.workflow import Workflow, WorkflowsConfig
from ..paths import data_state_dir, legacy_config_dir, ensure_local_file


class WorkflowConfigService:
    """CRUD helpers for persisted workflow definitions."""

    _locks: dict[str, asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    def __init__(self, config_path: Optional[Path] = None):
        if config_path is None:
            config_path = data_state_dir() / "workflows_config.yaml"
        self.config_path = Path(config_path)
        self._ensure_config_exists()

    def _ensure_config_exists(self) -> None:
        """Ensure workflow config exists with a valid initial schema."""
        if self.config_path.exists():
            return
        initial_text = yaml.safe_dump({"workflows": []}, allow_unicode=True, sort_keys=False)
        ensure_local_file(
            local_path=self.config_path,
            defaults_path=None,
            legacy_paths=[legacy_config_dir() / "workflows_config.yaml"],
            initial_text=initial_text,
        )

    async def _get_lock(self) -> asyncio.Lock:
        key = str(self.config_path.resolve())
        async with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[key] = lock
            return lock

    async def load_config(self) -> WorkflowsConfig:
        """Load workflow config from YAML file."""
        async with aiofiles.open(self.config_path, "r", encoding="utf-8") as f:
            content = await f.read()
        data = yaml.safe_load(content) or {}
        if "workflows" not in data:
            data["workflows"] = []
        return WorkflowsConfig(**data)

    async def save_config(self, config: WorkflowsConfig) -> None:
        """Persist workflow config atomically."""
        temp_path = self.config_path.with_suffix(".yaml.tmp")
        async with aiofiles.open(temp_path, "w", encoding="utf-8") as f:
            content = yaml.safe_dump(
                config.model_dump(mode="json"),
                allow_unicode=True,
                sort_keys=False,
            )
            await f.write(content)
        temp_path.replace(self.config_path)

    async def get_workflows(self) -> List[Workflow]:
        config = await self.load_config()
        return config.workflows

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        config = await self.load_config()
        for workflow in config.workflows:
            if workflow.id == workflow_id:
                return workflow
        return None

    async def add_workflow(self, workflow: Workflow) -> None:
        lock = await self._get_lock()
        async with lock:
            config = await self.load_config()
            if any(item.id == workflow.id for item in config.workflows):
                raise ValueError(f"Workflow with id '{workflow.id}' already exists")
            config.workflows.append(workflow)
            await self.save_config(config)

    async def update_workflow(self, workflow_id: str, updated: Workflow) -> None:
        lock = await self._get_lock()
        async with lock:
            config = await self.load_config()
            for index, workflow in enumerate(config.workflows):
                if workflow.id == workflow_id:
                    config.workflows[index] = updated
                    await self.save_config(config)
                    return
            raise ValueError(f"Workflow with id '{workflow_id}' not found")

    async def delete_workflow(self, workflow_id: str) -> None:
        lock = await self._get_lock()
        async with lock:
            config = await self.load_config()
            original_count = len(config.workflows)
            config.workflows = [item for item in config.workflows if item.id != workflow_id]
            if len(config.workflows) == original_count:
                raise ValueError(f"Workflow with id '{workflow_id}' not found")
            await self.save_config(config)
