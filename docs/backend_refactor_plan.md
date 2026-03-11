# Backend Refactor Plan

## Purpose

This document converts the architecture guidance in
`docs/backend_module_responsibilities.md` into a staged refactor plan.

It is intentionally incremental.
The goal is to reduce structural risk while keeping the system runnable after each stage.


## Refactor Strategy

We will not do a one-shot repo-wide move.

We will refactor in small, testable stages with these rules:

- keep the main chat path runnable after each stage
- prefer compatibility shims over large break-the-world moves
- reduce layer confusion before renaming directories aggressively
- move ownership first, rename second
- each stage must end with a stable checkpoint that can be tested and committed


## Target Outcome

The backend should converge toward this conceptual flow:

`router -> application -> llm_runtime -> provider adapter`

And toward this ownership model:

- `src/api/`: transport
- application layer: use-case orchestration
- `src/agents/` or future `src/llm_runtime/`: LLM runtime
- `src/providers/`: provider integration
- infrastructure-oriented modules: storage, file, retrieval, config access


## Status Snapshot

- Stage 0 - done
- Stage 1 - done
- Stage 2 - partial
- Stage 3 - done
- Stage 4 - partial
- Stage 5 - partial
- Stage 6 - partial


## Stage 0 - Baseline and Safety Rails

### Goal

Create a stable baseline before larger refactors.

### Status

Done.

### Scope

- document target responsibilities
- document staged refactor plan
- keep compatibility shims where needed
- create a git checkpoint before structural migrations continue

### Exit Criteria

- architecture guidance doc exists
- refactor plan doc exists
- current tree is committed as a rollback point

### Current Result

- baseline architecture docs exist
- early refactor checkpoints have been committed
- staged rollback points already exist in git history


## Stage 1 - Stabilize the LLM Runtime Boundary

### Status

Done.

### Goal

Finish separating model-turn execution from application orchestration.

### Why first

This is the highest-value boundary because the chat path depends on it directly,
and it is the most reusable runtime layer across single chat, compare, workflow,
and group chat.

### Scope

- keep all model-call execution logic inside `src/agents/llm_runtime/`
- remove legacy runtime shim files once tests and callers migrate
- move any remaining pure runtime helpers out of application services if they are
  only about model invocation behavior
- make runtime entrypoints explicit and narrow

### Candidate cleanup items

- review whether more stream/tool helper logic should move from
  `src/api/services/*` into `src/agents/`
- reduce direct imports of legacy shim files in production code
- define a stable small API for runtime entrypoints:
  - sync model call
  - streaming model call
  - context shaping helpers if still needed externally

### Risks

- tests may still patch old import paths
- helper functions may still be shared in awkward ways

### Mitigation

- keep compatibility exports on the runtime package during transition
- migrate production imports before test imports

### Exit Criteria

- production code no longer depends on legacy runtime filenames
- legacy shim files are removed
- runtime-related tests remain green

### Current Result

- runtime implementation lives under `src/agents/llm_runtime/`
- legacy `simple_llm.py` shim has been removed
- production imports use `src.agents.llm_runtime`


## Stage 2 - Flatten the Single Chat Path

### Status

Partial.

### Goal

Reduce the number of thin layers in the normal single-chat chain.

### Current problem

A normal single chat currently passes through:

`router -> ChatApplicationService -> SingleChatFlowService -> SingleTurnOrchestrator -> llm_runtime`

This works, but some of these layers are too thin and their ownership is not sharp enough.

Current progress:

- production router dependencies now resolve `ChatApplicationService` directly
- `AgentService` has been removed from the production chat path
- `SingleChatFlowService` is now the clear single-chat application flow owner
- single-chat streaming now calls `llm_runtime.call_llm_stream` directly from
  `SingleChatFlowService` (no production `SingleTurnOrchestrator` hop)

### Scope

- decide the long-term owner of the single-chat use case
- make `SingleChatFlowService` the clear application owner for single chat,
  or merge it into a better-named application service
- keep orchestrators only where they add real value

### Preferred direction

For the single-chat path, the likely target should be:

`router -> chat application service -> llm_runtime`

with persistence/context/tool preparation remaining in the application service.

### Candidate cleanup items

- keep group chat and compare chat behind separate entry services
- evaluate whether `SingleTurnOrchestrator` should remain as a reusable abstraction
  or become an internal helper of the single-chat application layer

### Risks

- hidden coupling with compare/group/workflow paths
- event payload compatibility for frontend SSE consumers

### Mitigation

- preserve external event contract while changing internal structure
- refactor single chat first without touching compare/group entry behavior

### Exit Criteria

- there is one obvious owner for the single-chat application flow
- normal chat call chain is shorter and easier to explain

### Remaining Work

- decide whether `SingleTurnOrchestrator` should remain only for compatibility/tests
- decide whether `SingleChatFlowService` should stay public or be folded into a narrower application package structure
- reduce residual composition code still living under `src/api/services/`


## Stage 3 - Split `src/api/services/` by Real Ownership

### Status

Partial.

### Goal

Stop treating `src/api/services/` as a permanent catch-all directory.

### Scope

Classify existing services into three buckets:

- application orchestration
- infrastructure-oriented support
- legacy/transitional wrappers

### Preferred direction

Introduce target-state package boundaries gradually, for example:

- `src/application/chat/`
- `src/application/workflows/`
- `src/application/context/`
- `src/infrastructure/storage/`
- `src/infrastructure/files/`
- `src/infrastructure/config/`

This does not require moving everything in one PR.

### Candidate moves

Application-oriented:

- `single_chat_flow_service.py`
- `compare_flow_service.py`
- `context_assembly_service.py`
- `workflow_execution_service.py`
- `post_turn_service.py`

Infrastructure-oriented:

- `conversation_storage.py`
- `file_service.py`
- `project_service.py`
- `webpage_service.py`
- `model_config_service.py`

### Risks

- import churn across many files
- merge conflicts if too many files move at once

### Mitigation

- move by slice, not by directory sweep
- leave temporary re-export shims where needed

### Exit Criteria

- new code has a clear placement rule
- fewer unrelated modules are added to `src/api/services/`
- at least one application package and one infrastructure package exist

### Current Progress

- `src/application/chat/` has been introduced as the new application package
- `src/application/workflows/` has been introduced for workflow execution ownership
- production API entrypoints now import chat application composition and types from
  `src.application.chat`
- production workflow entrypoints now import workflow execution from
  `src.application.workflows`
- compatibility re-export modules under `src/api/services/` have been fully
  retired; the `src/api/services/` package has been removed
- note: some bullets below mention earlier "compatibility re-export kept"
  milestones for historical traceability
- `single_chat_flow_service.py` and `compare_flow_service.py` now physically live under
  `src/application/chat/`
- `context_assembly_service.py` and `post_turn_service.py` now physically live under
  `src/application/chat/`
- `chat_input_service.py` and `service_contracts.py` now physically live under
  `src/application/chat/` (with compatibility re-exports kept under
  `src/api/services/`)
- `group_participants.py` now physically lives under `src/application/chat/`
  (with a compatibility re-export kept under `src/api/services/`)
- `file_reference_context_builder.py`, `source_context_service.py`, and
  `rag_context_builder_service.py` now physically live under
  `src/application/chat/` (with compatibility re-exports kept under
  `src/api/services/`)
- `rag_tool_service.py` now physically lives under `src/application/chat/`
  (with a compatibility re-export kept under `src/api/services/`)
- `title_generation_service.py` and `followup_service.py` now physically
  live under `src/application/chat/` (with compatibility re-exports kept
  under `src/api/services/`)
- `chatgpt_import_service.py` and `markdown_import_service.py` now physically
  live under `src/application/chat/` (with compatibility re-exports kept
  under `src/api/services/`)
- `translation_service.py` now physically lives under
  `src/application/translation/` (with a compatibility re-export kept under
  `src/api/services/`)
- `tool_catalog_service.py` now physically lives under
  `src/application/tools/` (with a compatibility re-export kept under
  `src/api/services/`)
- `flow_event_types.py`, `flow_events.py`, `flow_event_mapper.py`,
  `flow_event_emitter.py`, `flow_stream_runtime.py`,
  `flow_stream_runtime_provider.py`, `workflow_flow_event_mapper.py`,
  `async_run_service.py`, and `async_run_provider.py` now physically live
  under `src/application/flow/` (their `src/api/services/` compatibility
  re-exports have now been removed)
- `workflow_execution_service.py` now physically lives under
  `src/application/workflows/`
- `workflow_run_history_service.py` now physically lives under
  `src/application/workflows/` (with a compatibility re-export kept under
  `src/api/services/`)
- `src/infrastructure/storage/` has been introduced, and the following modules now
  physically live there (with compatibility re-exports kept under `src/api/services/`):
  - `conversation_storage.py`
  - `conversation_storage_paths.py`
  - `conversation_target_resolver.py`
  - `comparison_storage.py`
  - `migration_service.py`
  - `async_run_store_service.py`
- `src/infrastructure/files/` has been introduced, and `file_service.py` now
  physically lives there (with a compatibility re-export kept under `src/api/services/`).
- `src/infrastructure/config/` has been introduced, and `project_service.py` now
  physically lives there (with a compatibility re-export kept under `src/api/services/`).
- `model_config_service.py` (plus `model_config_repository.py` / `model_runtime_service.py`)
  now physically live under `src/infrastructure/config/` (with compatibility re-exports kept
  under `src/api/services/`).
- `pricing_service.py` now physically lives under
  `src/infrastructure/config/` (with a compatibility re-export kept under
  `src/api/services/`).
- `assistant_config_service.py`, `file_reference_config_service.py`,
  `memory_config_service.py`, `rag_config_service.py`,
  `translation_config_service.py`, `tts_config_service.py`, and
  `workflow_config_service.py` now physically live under
  `src/infrastructure/config/` (with compatibility re-exports kept under
  `src/api/services/`).
- `prompt_template_service.py` and `folder_service.py` now physically live
  under `src/infrastructure/config/` (with compatibility re-exports kept
  under `src/api/services/`).
- `provider_probe_service.py` now physically lives under
  `src/infrastructure/config/` (with a compatibility re-export kept under
  `src/api/services/`).
- shared `yaml_config_utils.py` now physically lives under
  `src/infrastructure/config/` (with a compatibility re-export kept under
  `src/api/services/`).
- `src/infrastructure/web/` has been introduced, and `webpage_service.py` now physically
  lives there (with a compatibility re-export kept under `src/api/services/`).
- `search_service.py` and `web_tool_service.py` now physically live under
  `src/infrastructure/web/` (with compatibility re-exports kept under `src/api/services/`).
- `src/infrastructure/compression/` has been introduced, and
  `compression_config_service.py` plus `compression_service.py` now physically
  live there (with compatibility re-exports kept under `src/api/services/`).
- `src/infrastructure/llm/` has been introduced, and
  `language_detection_service.py` plus `local_llama_cpp_service.py` now
  physically live there (with compatibility re-exports kept under
  `src/api/services/`).
- `src/infrastructure/memory/` has been introduced, and
  `memory_service.py` now physically lives there (with a compatibility
  re-export kept under `src/api/services/`).
- `src/infrastructure/projects/` has been introduced, and
  `project_document_tool_service.py`, `project_knowledge_base_resolver.py`, and
  `project_tool_policy_resolver.py`, and `project_workspace_state_service.py`
  now physically live there (with compatibility
  re-exports kept under `src/api/services/`).
- `src/infrastructure/retrieval/` has been introduced, and
  `rag_service.py`, `rag_backend_search.py`, `rag_post_processor.py`,
  `embedding_service.py`, `bm25_service.py`, `sqlite_vec_service.py`,
  `rerank_service.py`, `query_transform_service.py`, and
  `retrieval_query_planner_service.py` now physically live there (their
  `src/api/services/` compatibility re-exports have now been removed).
- `src/infrastructure/knowledge/` has been introduced, and
  `knowledge_base_service.py` plus `document_processing_service.py` now
  physically live there (with compatibility re-exports kept under
  `src/api/services/`).
- `src/infrastructure/audio/` has been introduced, and `tts_service.py` now
  physically lives there (with a compatibility re-export kept under
  `src/api/services/`).
- production API transport modules now import owned modules directly from
  `src/application/*` and `src/infrastructure/*`; there are no remaining
  `from ..services ...` imports under `src/api/`

### Remaining Work

- review whether workflow support modules need their own package split beyond
  the execution entrypoint


## Stage 4 - Reorganize Group, Compare, and Workflow Flows

### Status

Partial.

### Goal

Bring non-single-chat flows under the same structural vocabulary.

### Scope

- give group chat a clear application owner
- give compare flow a clear application owner
- align workflow execution with the same runtime boundary used by chat
- reduce duplicated model-call preparation paths

### Candidate cleanup items

- isolate committee/round-robin orchestration behind clearly named application modules
- ensure compare and workflow flows share runtime invocation contracts instead of custom wrappers

### Risks

- these paths are more coupled to legacy code than single chat
- streaming and persistence side effects may differ subtly

### Mitigation

- refactor only after Stage 2 is stable
- use contract tests on emitted events and persistence side effects

### Exit Criteria

- group/compare/workflow flows follow the same high-level layering model
- no legacy facade remains as the main coordination hub for everything

### Current Progress

- group flow has dedicated services and orchestration support
- compare flow has a dedicated application service
- group and compare no longer route through a legacy compatibility facade
- workflow execution now has a dedicated application package entrypoint
- `group_runtime_support_service.py` and `group_orchestration_support_service.py`
  now physically live under `src/application/chat/` with compatibility re-exports
  retained under `src/api/services/`
- orchestration modules now physically live under
  `src/application/chat/orchestration/` with compatibility re-exports retained
  under `src/api/services/orchestration/`
- think-tag stream filtering helpers now physically live under
  `src/agents/llm_runtime/` with a compatibility re-export retained under
  `src/api/services/`
- context planner now physically lives under `src/agents/llm_runtime/`
  with a compatibility re-export retained under `src/api/services/`

### Remaining Work

- compare modules still have transitional package dependencies
- supporting workflow modules still mostly live under transitional package locations


## Stage 5 - Naming Cleanup

### Status

Partial.

### Goal

Rename transitional and misleading modules once ownership is already stable.

### Important rule

Renaming is not the first step.
Renaming should happen after boundaries are already real.

### Candidate renames

- `src/agents/` -> `src/llm_runtime/` if runtime ownership fully dominates
- compatibility shims removed after callers migrate

### Risks

- high merge churn with low architectural value if done too early

### Mitigation

- only rename once imports are already narrowed
- batch renames after functional refactors are stable

### Exit Criteria

- directory and module names describe real ownership
- no major compatibility shim remains for historical names

### Current Progress

- `AgentService` has been removed
- `simple_llm.py` has been removed
- production API code no longer imports compatibility shims from
  `src/api/services/`
- compatibility shim modules under `src/api/services/` are now removed

### Remaining Work

- decide whether `src/agents/` should be renamed to `src/llm_runtime/`
- rename outdated test/module names that still reflect deleted structures


## Stage 6 - Test Structure Alignment

### Status

Partial.

### Goal

Make tests mirror the new ownership model.

### Scope

- runtime tests follow runtime modules
- application flow tests follow application packages
- infrastructure tests follow storage/config/file modules
- legacy-path tests removed once migration shims are retired

### Candidate actions

- split old `test_simple_llm.py` into runtime-focused test modules over time
- add contract tests for single-chat event flow
- add regression tests around tool loop behavior and persistence boundaries

### Exit Criteria

- tests reinforce architecture instead of hiding legacy structure

### Current Progress

- legacy committee tests were moved to orchestration-focused tests
- runtime tests already target `src.agents.llm_runtime`
- tests no longer import `src.api.services.*`; they now target owned
  `src/application/*`, `src/infrastructure/*`, and `src/agents/*` modules directly

### Remaining Work

- split legacy-named runtime test files such as `test_simple_llm.py`
- continue reorganizing test folders to mirror application/runtime/infrastructure ownership


## Delivery Order

Recommended order:

1. Stage 0
2. Stage 1
3. Stage 2
4. Stage 3
5. Stage 4
6. Stage 5
7. Stage 6

Reason:

- first stabilize runtime
- then simplify the hottest path
- then move packages by ownership
- then clean up names
- finally align tests to target structure


## Rules for Each Refactor PR

Every structural PR should follow these rules:

- one primary architectural move per PR
- keep public behavior stable unless intentionally changed
- update docs when boundaries change
- prefer re-export shims over mass breakage
- add or update tests for the moved ownership boundary
- leave the tree in a runnable state


## Suggested First Execution Slice

After the current baseline commit, the first real refactor slice should be:

1. finish Stage 1 runtime cleanup
2. decide the final owner of single-chat orchestration
3. continue reducing transitional application bootstrapping code

This is the smallest high-leverage slice because it improves the most important path
without requiring immediate repo-wide directory moves.


## Rollback Strategy

Because this refactor is staged, rollback is straightforward:

- each stage ends in a standalone commit
- compatibility shims reduce migration blast radius
- structural moves should be separated from behavior changes where possible

If a stage proves unstable, revert only that stage and keep the previous checkpoint.


## Definition of Success

The refactor is successful if:

- a normal chat path can be explained in one sentence
- new backend files have an obvious home
- `src/api/services/` no longer grows as a catch-all
- runtime behavior is isolated from application orchestration
- naming reflects actual ownership rather than history
