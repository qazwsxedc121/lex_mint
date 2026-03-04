# Novel Workflows V1

This document describes the built-in `project_pipeline` workflows for novel creation.

## Built-in workflows

- `wf_novel_charter_v1` -> writes `novel/00_charter.md`
- `wf_novel_world_build_v1` -> writes `novel/01_world.md`
- `wf_novel_character_build_v1` -> writes `novel/02_characters.md`
- `wf_novel_plot_design_v1` -> writes `novel/03_plot.md`
- `wf_novel_chapter_plan_v1` -> writes `novel/04_chapters/<chapter_id>_plan.md`
- `wf_novel_chapter_draft_v1` -> writes `novel/04_chapters/<chapter_id>_draft.md`
- `wf_novel_continuity_check_v1` -> writes `novel/05_qc/<chapter_id>_continuity.md`
- `wf_novel_style_polish_v1` -> writes `novel/05_qc/<chapter_id>_style.md`

All workflows generate markdown with YAML frontmatter and default `language=zh-CN`.

## How to run in Projects

1. Open a project and any file in the editor.
2. Click the new **Project Workflow** button in the editor toolbar.
3. Pick a `project_pipeline` workflow.
4. Fill required workflow inputs.
5. Optionally set:
   - `Artifact output path` to override the workflow default path.
   - `Write mode`:
     - `overwrite`
     - `create`
     - `none` (preview only, do not write files)
6. Run and inspect output + written artifact path.

## Event stream additions

Workflow stream now emits `workflow_artifact_written` when an artifact node runs.
Payload includes file path, write mode, whether the file was written, and content hash.

