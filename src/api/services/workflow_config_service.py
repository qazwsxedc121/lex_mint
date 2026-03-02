"""Workflow configuration management service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import aiofiles
import yaml

from ..models.workflow import EndNode, LlmNode, StartNode, Workflow, WorkflowInputDef, WorkflowsConfig
from ..paths import data_state_dir, legacy_config_dir, ensure_local_file


class WorkflowConfigService:
    """CRUD helpers for persisted workflow definitions."""

    INLINE_REWRITE_WORKFLOW_ID = "wf_inline_rewrite_default"
    INLINE_REWRITE_TEMPLATE_VERSION = 2

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

    def _build_system_workflows(self, now: datetime) -> List[Workflow]:
        inline_rewrite_prompt = (
            "Task: Rewrite only the selected text using the instruction and surrounding context.\n"
            "Instruction: {{inputs.instruction}}\n"
            "File: {{inputs._file_path}}\n"
            "Language: {{inputs._language}}\n\n"
            "<context_before>\n{{inputs._context_before}}\n</context_before>\n\n"
            "<selected_text>\n{{inputs._selected_text}}\n</selected_text>\n\n"
            "<context_after>\n{{inputs._context_after}}\n</context_after>\n\n"
            "Return only the rewritten selected text.\n"
            "Do not output explanations, markdown fences, headings, or commentary."
        )
        return [
            Workflow(
                id=self.INLINE_REWRITE_WORKFLOW_ID,
                name="Inline Rewrite (Default)",
                description="Default inline rewrite workflow for project editor selection.",
                enabled=True,
                scenario="editor_rewrite",
                is_system=True,
                template_version=self.INLINE_REWRITE_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(key="_selected_text", type="string", required=True),
                    WorkflowInputDef(
                        key="instruction",
                        type="string",
                        required=False,
                        default="Improve clarity while preserving meaning and style.",
                    ),
                    WorkflowInputDef(key="_context_before", type="string", required=False, default=""),
                    WorkflowInputDef(key="_context_after", type="string", required=False, default=""),
                    WorkflowInputDef(key="_file_path", type="string", required=False, default="(unknown)"),
                    WorkflowInputDef(key="_language", type="string", required=False, default="(unknown)"),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        prompt_template=inline_rewrite_prompt,
                        output_key="rewritten_text",
                        next_id="end_1",
                    ),
                    EndNode(id="end_1", type="end", result_template="{{ctx.rewritten_text}}"),
                ],
                created_at=now,
                updated_at=now,
            )
        ]

    def _upsert_system_workflows(self, config: WorkflowsConfig) -> bool:
        changed = False
        now = datetime.now(timezone.utc)
        builtin_workflows = self._build_system_workflows(now)
        index_by_id = {workflow.id: idx for idx, workflow in enumerate(config.workflows)}

        for builtin in builtin_workflows:
            index = index_by_id.get(builtin.id)
            if index is None:
                config.workflows.append(builtin)
                changed = True
                continue

            existing = config.workflows[index]
            if not existing.is_system:
                continue

            existing_version = existing.template_version or 0
            target_version = builtin.template_version or 1
            if existing_version >= target_version:
                continue

            config.workflows[index] = builtin.model_copy(
                update={
                    "created_at": existing.created_at,
                    "updated_at": now,
                }
            )
            changed = True

        return changed

    async def ensure_system_workflows(self) -> None:
        """Ensure built-in workflows exist and upgrade system templates when needed."""
        lock = await self._get_lock()
        async with lock:
            config = await self.load_config()
            if self._upsert_system_workflows(config):
                await self.save_config(config)

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
        await self.ensure_system_workflows()
        config = await self.load_config()
        return config.workflows

    async def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        await self.ensure_system_workflows()
        config = await self.load_config()
        for workflow in config.workflows:
            if workflow.id == workflow_id:
                return workflow
        return None

    async def add_workflow(self, workflow: Workflow) -> None:
        await self.ensure_system_workflows()
        lock = await self._get_lock()
        async with lock:
            config = await self.load_config()
            if any(item.id == workflow.id for item in config.workflows):
                raise ValueError(f"Workflow with id '{workflow.id}' already exists")
            config.workflows.append(workflow)
            await self.save_config(config)

    async def update_workflow(self, workflow_id: str, updated: Workflow) -> None:
        await self.ensure_system_workflows()
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
        await self.ensure_system_workflows()
        lock = await self._get_lock()
        async with lock:
            config = await self.load_config()
            original_count = len(config.workflows)
            config.workflows = [item for item in config.workflows if item.id != workflow_id]
            if len(config.workflows) == original_count:
                raise ValueError(f"Workflow with id '{workflow_id}' not found")
            await self.save_config(config)
