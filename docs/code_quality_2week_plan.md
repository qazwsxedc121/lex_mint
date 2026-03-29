# Code Quality 2-Week Plan

This plan is tailored to the current repository state:

- Backend quality gates already exist: `ruff`, `mypy`, `pytest`, coverage report.
- Frontend quality gates already exist: `eslint`, `tsc -b`, `vite build`, Playwright e2e.
- Main gaps are frontend unit/component testing, loose TypeScript typing, and missing local pre-commit enforcement.

## Goals

By the end of 2 weeks, the project should achieve these outcomes:

- Reduce regression risk in `settings`, `projects`, and `shared/chat`.
- Tighten frontend and backend type safety without doing a repo-wide disruptive cleanup.
- Add fast local guardrails before code reaches CI.
- Add one lightweight CI smoke path that validates the core user journey.

## Current Baseline

- Backend CI runs `ruff check`, `ruff format --check`, `mypy src`, and `pytest`.
- Frontend CI runs `npm run lint` and `npm run build`.
- Pytest produces coverage output, but there is no coverage threshold gate.
- Frontend uses Playwright e2e, but CI does not currently run a Playwright smoke suite.
- Frontend has many `any` usages, especially in:
  - `frontend/src/modules/settings/config/`
  - `frontend/src/modules/settings/components/`
  - `frontend/src/services/api.ts`
  - `frontend/src/modules/projects/components/`
  - `frontend/src/shared/chat/components/`
- There is no root `.pre-commit-config.yaml`.

## Week 1

### 1. Add local pre-commit guardrails

Scope:

- Add `.pre-commit-config.yaml`.
- Add fast checks only. Do not put slow Playwright or full pytest in pre-commit.

Hooks:

- Backend:
  - `ruff check --fix` on changed Python files
  - `ruff format` on changed Python files
- Frontend:
  - `eslint --fix` on changed `ts` and `tsx` files
- Generic:
  - trailing whitespace
  - end-of-file newline
  - YAML validation

Success criteria:

- A normal commit catches formatting and obvious lint issues locally.
- Team members do not need to wait for CI to see basic failures.

### 2. Add frontend unit/component test stack

Scope:

- Add `vitest` and `@testing-library/react`.
- Add a minimal test setup file for jsdom and shared mocks.
- Add `npm` scripts:
  - `test`
  - `test:watch`
  - `test:coverage`

Target directories for first coverage wave:

- `frontend/src/shared/chat/components/`
- `frontend/src/modules/projects/`
- `frontend/src/modules/settings/`

First test targets:

- `ChatSidebar`
  - session list rendering
  - selection behavior
  - empty state
- `ProjectSearchView`
  - empty query
  - result rendering
  - error state
- `RAG` or settings preset logic
  - preset selection
  - field update mapping
  - save payload excludes UI-only fields

Success criteria:

- Frontend has a fast test layer below Playwright.
- New UI state bugs can be caught without running the full browser suite.

### 3. Start type-hardening on the frontend hot paths

Scope:

- Do not try to remove all `any` in one pass.
- Focus only on files that sit on data boundaries or shared config layers.

Priority files:

- `frontend/src/services/api.ts`
- `frontend/src/modules/settings/config/types.ts`
- `frontend/src/modules/settings/components/config/`
- `frontend/src/modules/projects/hooks/useProjectWorkspaceState.ts`
- `frontend/src/shared/chat/components/ChatInterface.tsx`

Execution strategy:

- Replace request/response `any` with explicit interfaces.
- Replace `catch (err: any)` with `unknown` plus a small error normalization helper.
- Replace generic form `Record<string, any>` where the shape is stable.
- Leave dynamic schema-driven cases for Week 2 if they need larger refactors.

Success criteria:

- New API changes cause type errors earlier.
- Shared settings/config code stops propagating `any` through the rest of the UI.

### 4. Add a lightweight CI smoke lane

Scope:

- Do not move the full Playwright suite into CI yet.
- Add one stable smoke spec or one smoke subset.

Suggested candidates:

- `frontend/tests/e2e/specs/projects-smoke.spec.ts`
- `frontend/tests/e2e/specs/group-chat.spec.ts` filtered to non-LLM tests
- one settings-related smoke test with mocked network responses

Implementation notes:

- Prefer deterministic mocked API responses over real LLM dependencies.
- Keep runtime short enough for pull requests.

Success criteria:

- Every PR validates at least one real browser path.
- Failures are actionable and not dependent on external providers.

## Week 2

### 5. Tighten backend type checks selectively

Scope:

- Keep repo-wide defaults unchanged if the blast radius is too large.
- Use per-module tightening first.

Priority backend areas:

- `src/application/`
- `src/domain/`
- `src/infrastructure/config/`
- `src/infrastructure/projects/`

Suggested changes:

- Turn on stricter checks for selected modules first.
- Reduce `ignore_missing_imports` only where libraries already have type hints.
- Add return types to service boundaries and helper functions that feed API responses.

Success criteria:

- Core orchestration and config code has stronger type guarantees.
- CI catches interface drift earlier in business logic.

### 6. Add coverage gates for new code

Scope:

- Do not start with an aggressive global threshold.
- Prefer a practical threshold that the current suite can satisfy.

Recommended starting gates:

- Backend total coverage threshold: `70%`
- Frontend unit test coverage threshold for touched files or changed modules

Implementation notes:

- Add `--cov-fail-under=70` only after checking current backend baseline.
- If global frontend coverage is noisy at first, use changed-file reporting in CI comments or a separate `test:coverage` job without failing the whole build for week 2.

Success criteria:

- New code does not lower the quality floor silently.
- Coverage becomes an enforcement tool, not just an HTML artifact.

### 7. Introduce API contract hardening

Scope:

- Reduce drift between FastAPI responses and frontend request handling.

Options:

- Preferred: generate typed frontend models from backend OpenAPI schema.
- Acceptable interim step: centralize request and response interfaces in `frontend/src/services/api.ts` and shared type files.

First endpoints to harden:

- chat session create and list
- project workspace read/search
- settings CRUD endpoints
- workflow run and resume endpoints

Success criteria:

- Backend field changes fail at compile time or in contract tests instead of at runtime.

### 8. Add architecture and regression-focused tests

Scope:

- Add a small set of tests that protect the repository from structural erosion.

Recommended additions:

- import boundary test for backend layers
- frontend import boundary rule or lint-based restriction
- property-style tests for path normalization and workspace root safety
- regression tests for config serialization and migration logic

Success criteria:

- The codebase is protected against accidental cross-layer coupling.
- High-risk file and config logic gets stronger regression coverage.

## Concrete Deliverables

At the end of the 2-week plan, the repo should contain:

- `.pre-commit-config.yaml`
- frontend unit/component test setup and scripts
- 8 to 15 new frontend tests focused on `settings`, `projects`, and `shared/chat`
- reduced `any` count in high-risk frontend files
- one CI smoke Playwright job
- tightened type checking in selected backend modules
- initial coverage threshold enforcement
- at least one contract hardening step for frontend API use

## Suggested Task Breakdown

### Day 1 to Day 2

- add pre-commit
- add frontend test stack
- add first 3 to 5 frontend tests

### Day 3 to Day 5

- harden `frontend/src/services/api.ts`
- harden `frontend/src/modules/settings/config/types.ts`
- replace high-value `any` cases in settings and projects

### Day 6 to Day 7

- add CI smoke Playwright lane
- stabilize mocked responses
- document local run commands

### Day 8 to Day 10

- tighten backend typing in `application`, `domain`, and config services
- add regression tests for path and config logic

### Day 11 to Day 14

- enable coverage threshold
- add API contract hardening
- clean up flaky tests and update docs

## Metrics To Track

Track these metrics at the start and end of the plan:

- frontend explicit `any` count in `frontend/src/`
- number of frontend unit/component tests
- CI total runtime
- backend coverage percentage
- count of flaky Playwright failures across a week
- number of PR failures caught by pre-commit or CI before merge

## Recommended Order If Time Is Limited

If only 3 items can be done now, do them in this order:

1. Add frontend unit/component tests.
2. Harden frontend types in `api.ts` and `settings/config`.
3. Add pre-commit plus one CI smoke Playwright path.

## Commands To Standardize

Backend:

```powershell
./venv/Scripts/python -m ruff check .
./venv/Scripts/python -m ruff format --check .
./venv/Scripts/python -m mypy src
./venv/Scripts/pytest tests
```

Frontend:

```powershell
cd frontend
npm run lint
npm run build
npm run test
npm run test:coverage
npx playwright test tests/e2e/specs/projects-smoke.spec.ts --project=chromium --workers=1
```

## Risks

- Tightening types too broadly in one pass will create a long-lived branch and slow feature work.
- Running unstable or provider-dependent e2e in CI will reduce trust in the pipeline.
- Enabling coverage gates before stabilizing the baseline will cause noisy failures.

## Notes

- Favor incremental gating over repo-wide strictness flips.
- For this codebase, the best return is in the frontend middle layer: API typing, settings config, and component-level tests.
- Keep real LLM flows outside the default PR gate unless they are isolated and deterministic.
