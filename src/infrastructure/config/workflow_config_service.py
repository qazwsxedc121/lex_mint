"""Workflow configuration management service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
import yaml

from src.core.paths import data_state_dir, ensure_local_file
from src.domain.models.workflow import (
    ArtifactNode,
    EndNode,
    LlmNode,
    StartNode,
    Workflow,
    WorkflowInputDef,
    WorkflowsConfig,
)


class WorkflowConfigService:
    """CRUD helpers for persisted workflow definitions."""

    INLINE_REWRITE_WORKFLOW_ID = "wf_inline_rewrite_default"
    INLINE_REWRITE_TEMPLATE_VERSION = 2
    NOVEL_TEMPLATE_VERSION = 2
    CHAPTER_ID_PATTERN = r'^[^\\/:*?"<>|\r\n]{1,64}$'

    _locks: dict[str, asyncio.Lock] = {}
    _locks_guard = asyncio.Lock()

    def __init__(self, config_path: Path | None = None):
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
        async with aiofiles.open(self.config_path, encoding="utf-8") as f:
            content = await f.read()
        data = yaml.safe_load(content) or {}
        if "workflows" not in data:
            data["workflows"] = []
        return WorkflowsConfig(**data)

    def _build_novel_prompt(
        self,
        *,
        artifact_type: str,
        chapter_expr: str,
        upstream_lines: list[str],
        objective: str,
        context_lines: list[str],
        section_lines: list[str],
        quality_gate_note: str,
    ) -> str:
        upstream_block = "\n".join([f"- {line}" for line in upstream_lines]) or "-"
        context_block = "\n".join([f"- {line}" for line in context_lines])
        section_block = "\n".join([f"- {line}" for line in section_lines])
        return (
            "You are a professional fiction writing assistant.\n"
            f"Objective: {objective}\n"
            "Return ONLY one markdown document with YAML frontmatter and body.\n"
            "Do not include explanations outside the document.\n\n"
            "Frontmatter template:\n"
            "---\n"
            f"artifact_type: {artifact_type}\n"
            "workflow_id: {{ctx.workflow_id}}\n"
            "run_id: {{ctx.run_id}}\n"
            "project_id: {{ctx.project_id}}\n"
            f"chapter_id: {chapter_expr}\n"
            "language: {{inputs.language}}\n"
            "created_at: {{ctx.started_at}}\n"
            "upstream:\n"
            f"{upstream_block}\n"
            "risk_flags:\n"
            "-\n"
            "quality_gate:\n"
            "  status: pass\n"
            f"  summary: {quality_gate_note}\n"
            "---\n\n"
            "Context to follow:\n"
            f"{context_block}\n\n"
            "Body requirements (use markdown headings):\n"
            f"{section_block}\n"
        )

    def _build_novel_system_workflows(self, now: datetime) -> list[Workflow]:
        workflows: list[Workflow] = []

        workflows.append(
            Workflow(
                id="wf_novel_charter_v1",
                name="Novel Charter",
                description="Create novel charter with scope, tone, and quality constraints.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(key="idea", type="string", required=True),
                    WorkflowInputDef(key="genre", type="string", required=False, default="fantasy"),
                    WorkflowInputDef(
                        key="target_audience",
                        type="string",
                        required=False,
                        default="general readers",
                    ),
                    WorkflowInputDef(
                        key="tone",
                        type="string",
                        required=False,
                        default="dramatic and immersive",
                    ),
                    WorkflowInputDef(
                        key="length_target",
                        type="string",
                        required=False,
                        default="60000-80000 words",
                    ),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="charter_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="charter",
                            chapter_expr='""',
                            upstream_lines=["idea_input"],
                            objective="Define the creative charter for a full-length novel project.",
                            context_lines=[
                                "idea={{inputs.idea}}",
                                "genre={{inputs.genre}}",
                                "target_audience={{inputs.target_audience}}",
                                "tone={{inputs.tone}}",
                                "length_target={{inputs.length_target}}",
                            ],
                            section_lines=[
                                "# Project Charter",
                                "## Premise",
                                "## Narrative Promise",
                                "## Scope and Boundaries",
                                "## Character Intent",
                                "## Conflict Design",
                                "## Writing Rules",
                                "## Quality Checklist",
                            ],
                            quality_gate_note="Charter baseline generated.",
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/00_charter.md",
                        content_template="{{ctx.charter_doc}}",
                        write_mode="overwrite",
                        output_key="charter_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        workflows.append(
            Workflow(
                id="wf_novel_world_build_v1",
                name="Novel World Build",
                description="Build world bible from charter content.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(key="charter_text", type="string", required=True),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="world_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="world",
                            chapter_expr='""',
                            upstream_lines=["novel/00_charter.md"],
                            objective="Generate a coherent world bible for the novel.",
                            context_lines=["charter_text={{inputs.charter_text}}"],
                            section_lines=[
                                "# World Bible",
                                "## Core Rules",
                                "## Factions and Power Structure",
                                "## Timeline Anchors",
                                "## Geography and Locations",
                                "## Terminology",
                                "## Forbidden Contradictions",
                            ],
                            quality_gate_note="World baseline generated.",
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/01_world.md",
                        content_template="{{ctx.world_doc}}",
                        write_mode="overwrite",
                        output_key="world_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        workflows.append(
            Workflow(
                id="wf_novel_character_build_v1",
                name="Novel Character Build",
                description="Create character bible with arcs and relationships.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(key="charter_text", type="string", required=True),
                    WorkflowInputDef(key="world_text", type="string", required=True),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="characters_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="characters",
                            chapter_expr='""',
                            upstream_lines=["novel/00_charter.md", "novel/01_world.md"],
                            objective="Create character bible and relationship map.",
                            context_lines=[
                                "charter_text={{inputs.charter_text}}",
                                "world_text={{inputs.world_text}}",
                            ],
                            section_lines=[
                                "# Character Bible",
                                "## Protagonist Profile",
                                "## Major Supporting Characters",
                                "## Antagonist and Opposition",
                                "## Relationship Map",
                                "## Arc by Story Phase",
                                "## Invariant Traits",
                            ],
                            quality_gate_note="Character baseline generated.",
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/02_characters.md",
                        content_template="{{ctx.characters_doc}}",
                        write_mode="overwrite",
                        output_key="characters_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        workflows.append(
            Workflow(
                id="wf_novel_plot_design_v1",
                name="Novel Plot Design",
                description="Create master plot and chapter-level arc map.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(key="charter_text", type="string", required=True),
                    WorkflowInputDef(key="world_text", type="string", required=True),
                    WorkflowInputDef(key="characters_text", type="string", required=True),
                    WorkflowInputDef(
                        key="chapter_count", type="number", required=False, default=24
                    ),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="plot_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="plot",
                            chapter_expr='""',
                            upstream_lines=[
                                "novel/00_charter.md",
                                "novel/01_world.md",
                                "novel/02_characters.md",
                            ],
                            objective="Design the story spine and chapter-level progression.",
                            context_lines=[
                                "charter_text={{inputs.charter_text}}",
                                "world_text={{inputs.world_text}}",
                                "characters_text={{inputs.characters_text}}",
                                "chapter_count={{inputs.chapter_count}}",
                            ],
                            section_lines=[
                                "# Plot Masterplan",
                                "## Three-Act Skeleton",
                                "## Mainline and Subplots",
                                "## Chapter Progression Table",
                                "## Foreshadowing and Payoff Plan",
                                "## Escalation Strategy",
                            ],
                            quality_gate_note="Plot baseline generated.",
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/03_plot.md",
                        content_template="{{ctx.plot_doc}}",
                        write_mode="overwrite",
                        output_key="plot_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        workflows.append(
            Workflow(
                id="wf_novel_chapter_plan_v1",
                name="Novel Chapter Plan",
                description="Generate a detailed chapter card for one chapter.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(
                        key="chapter_id",
                        type="string",
                        required=True,
                        allow_file_insert=False,
                        max_length=64,
                        pattern=self.CHAPTER_ID_PATTERN,
                        description="Short chapter identifier, for example: ch01",
                    ),
                    WorkflowInputDef(key="plot_text", type="string", required=True),
                    WorkflowInputDef(key="characters_text", type="string", required=True),
                    WorkflowInputDef(key="world_text", type="string", required=True),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="chapter_plan_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="chapter_plan",
                            chapter_expr="{{inputs.chapter_id}}",
                            upstream_lines=[
                                "novel/03_plot.md",
                                "novel/02_characters.md",
                                "novel/01_world.md",
                            ],
                            objective="Create one chapter planning card.",
                            context_lines=[
                                "chapter_id={{inputs.chapter_id}}",
                                "plot_text={{inputs.plot_text}}",
                                "characters_text={{inputs.characters_text}}",
                                "world_text={{inputs.world_text}}",
                            ],
                            section_lines=[
                                "# Chapter Plan {{inputs.chapter_id}}",
                                "## Chapter Goal",
                                "## Scene List",
                                "## Character Beats",
                                "## Conflict and Turn",
                                "## Foreshadowing / Callback",
                                "## Exit Hook",
                            ],
                            quality_gate_note="Chapter planning baseline generated.",
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/04_chapters/{{inputs.chapter_id}}_plan.md",
                        content_template="{{ctx.chapter_plan_doc}}",
                        write_mode="overwrite",
                        output_key="chapter_plan_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        workflows.append(
            Workflow(
                id="wf_novel_chapter_draft_v1",
                name="Novel Chapter Draft",
                description="Draft one chapter from chapter plan.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(
                        key="chapter_id",
                        type="string",
                        required=True,
                        allow_file_insert=False,
                        max_length=64,
                        pattern=self.CHAPTER_ID_PATTERN,
                        description="Short chapter identifier, for example: ch01",
                    ),
                    WorkflowInputDef(key="chapter_plan_text", type="string", required=True),
                    WorkflowInputDef(
                        key="style_guide",
                        type="string",
                        required=False,
                        default="Keep narrative vivid and character-consistent.",
                    ),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="chapter_draft_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="chapter_draft",
                            chapter_expr="{{inputs.chapter_id}}",
                            upstream_lines=["novel/04_chapters/{{inputs.chapter_id}}_plan.md"],
                            objective="Produce a complete prose draft for a single chapter.",
                            context_lines=[
                                "chapter_id={{inputs.chapter_id}}",
                                "chapter_plan_text={{inputs.chapter_plan_text}}",
                                "style_guide={{inputs.style_guide}}",
                            ],
                            section_lines=[
                                "# Chapter Draft {{inputs.chapter_id}}",
                                "## Draft Text",
                                "## Self-Check Notes",
                            ],
                            quality_gate_note="Chapter draft generated.",
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/04_chapters/{{inputs.chapter_id}}_draft.md",
                        content_template="{{ctx.chapter_draft_doc}}",
                        write_mode="overwrite",
                        output_key="chapter_draft_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        workflows.append(
            Workflow(
                id="wf_novel_continuity_check_v1",
                name="Novel Continuity Check",
                description="Run soft-gate continuity checks after each chapter draft.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(
                        key="chapter_id",
                        type="string",
                        required=True,
                        allow_file_insert=False,
                        max_length=64,
                        pattern=self.CHAPTER_ID_PATTERN,
                        description="Short chapter identifier, for example: ch01",
                    ),
                    WorkflowInputDef(key="chapter_draft_text", type="string", required=True),
                    WorkflowInputDef(key="world_text", type="string", required=True),
                    WorkflowInputDef(key="characters_text", type="string", required=True),
                    WorkflowInputDef(key="plot_text", type="string", required=True),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="continuity_report_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="qc_continuity",
                            chapter_expr="{{inputs.chapter_id}}",
                            upstream_lines=[
                                "novel/04_chapters/{{inputs.chapter_id}}_draft.md",
                                "novel/01_world.md",
                                "novel/02_characters.md",
                                "novel/03_plot.md",
                            ],
                            objective="Generate soft-gate continuity report and concrete fixes.",
                            context_lines=[
                                "chapter_id={{inputs.chapter_id}}",
                                "chapter_draft_text={{inputs.chapter_draft_text}}",
                                "world_text={{inputs.world_text}}",
                                "characters_text={{inputs.characters_text}}",
                                "plot_text={{inputs.plot_text}}",
                            ],
                            section_lines=[
                                "# Continuity Report {{inputs.chapter_id}}",
                                "## Gate Verdict (pass or warn)",
                                "## Issues Table (severity, category, evidence, fix)",
                                "## Character Consistency Findings",
                                "## World Rule Findings",
                                "## Timeline Findings",
                                "## Suggested Rewrite Actions",
                            ],
                            quality_gate_note=(
                                "Soft gate: use pass when no major contradiction, warn otherwise."
                            ),
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/05_qc/{{inputs.chapter_id}}_continuity.md",
                        content_template="{{ctx.continuity_report_doc}}",
                        write_mode="overwrite",
                        output_key="continuity_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        workflows.append(
            Workflow(
                id="wf_novel_style_polish_v1",
                name="Novel Style Polish",
                description="Run style pass and produce chapter-level polish report.",
                enabled=True,
                scenario="project_pipeline",
                is_system=True,
                template_version=self.NOVEL_TEMPLATE_VERSION,
                input_schema=[
                    WorkflowInputDef(
                        key="chapter_id",
                        type="string",
                        required=True,
                        allow_file_insert=False,
                        max_length=64,
                        pattern=self.CHAPTER_ID_PATTERN,
                        description="Short chapter identifier, for example: ch01",
                    ),
                    WorkflowInputDef(key="chapter_draft_text", type="string", required=True),
                    WorkflowInputDef(
                        key="style_profile",
                        type="string",
                        required=False,
                        default="Maintain coherent tone, concise prose, and natural dialogue.",
                    ),
                    WorkflowInputDef(
                        key="continuity_report_text",
                        type="string",
                        required=False,
                        default="",
                    ),
                    WorkflowInputDef(
                        key="language", type="string", required=False, default="zh-CN"
                    ),
                ],
                entry_node_id="start_1",
                nodes=[
                    StartNode(id="start_1", type="start", next_id="llm_1"),
                    LlmNode(
                        id="llm_1",
                        type="llm",
                        output_key="style_report_doc",
                        prompt_template=self._build_novel_prompt(
                            artifact_type="qc_style",
                            chapter_expr="{{inputs.chapter_id}}",
                            upstream_lines=[
                                "novel/04_chapters/{{inputs.chapter_id}}_draft.md",
                                "novel/05_qc/{{inputs.chapter_id}}_continuity.md",
                            ],
                            objective="Produce style polish guidance and revised sample passages.",
                            context_lines=[
                                "chapter_id={{inputs.chapter_id}}",
                                "chapter_draft_text={{inputs.chapter_draft_text}}",
                                "style_profile={{inputs.style_profile}}",
                                "continuity_report_text={{inputs.continuity_report_text}}",
                            ],
                            section_lines=[
                                "# Style Report {{inputs.chapter_id}}",
                                "## Gate Verdict (pass or warn)",
                                "## Tone and Rhythm Notes",
                                "## Dialogue Quality Notes",
                                "## Rewrite Suggestions",
                                "## Polished Sample Paragraphs",
                            ],
                            quality_gate_note="Soft gate: warn if style consistency is weak.",
                        ),
                        next_id="artifact_1",
                    ),
                    ArtifactNode(
                        id="artifact_1",
                        type="artifact",
                        file_path_template="novel/05_qc/{{inputs.chapter_id}}_style.md",
                        content_template="{{ctx.style_report_doc}}",
                        write_mode="overwrite",
                        output_key="style_artifact",
                        next_id="end_1",
                    ),
                    EndNode(
                        id="end_1",
                        type="end",
                        result_template="Wrote {{ctx.last_artifact.file_path}}",
                    ),
                ],
                created_at=now,
                updated_at=now,
            )
        )

        return workflows

    def _build_system_workflows(self, now: datetime) -> list[Workflow]:
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
        workflows = [
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
                    WorkflowInputDef(
                        key="_context_before", type="string", required=False, default=""
                    ),
                    WorkflowInputDef(
                        key="_context_after", type="string", required=False, default=""
                    ),
                    WorkflowInputDef(
                        key="_file_path", type="string", required=False, default="(unknown)"
                    ),
                    WorkflowInputDef(
                        key="_language", type="string", required=False, default="(unknown)"
                    ),
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
        workflows.extend(self._build_novel_system_workflows(now))
        return workflows

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

    async def get_workflows(self) -> list[Workflow]:
        await self.ensure_system_workflows()
        config = await self.load_config()
        return config.workflows

    async def get_workflow(self, workflow_id: str) -> Workflow | None:
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
