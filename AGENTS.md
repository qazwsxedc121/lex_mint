# Repository Guidelines

## Project Structure and Module Organization
This repo has a FastAPI backend and a React frontend.
- `src/`: backend application code (API in `src/api/`, agents in `src/agents/`)
- `frontend/`: Vite + React + TypeScript UI (`frontend/src/modules/` for feature modules)
- `tests/`: pytest tests for backend
- `docs/`: architecture and API docs
- `config/`: model and runtime config (for example `config/models_config.yaml`)
- `conversations/`: markdown storage for chats
- `logs/`: runtime logs (`logs/server.log`)
- `attachments/`: uploaded files

## Build, Test, and Development Commands
Backend (always use venv scripts, do not use system python):
```
./venv/Scripts/pip install -r requirements.txt
./venv/Scripts/uvicorn src.api.main:app --reload --port <API_PORT>
./venv/Scripts/python -m src.main
```
UI runs at `http://localhost:<FRONTEND_PORT>` after `npm run dev`.
Frontend:
```
cd frontend
npm install
npm run dev
npm run build
npm run lint
```

## Coding Style and Naming Conventions
- Python: 4 spaces, PEP8 style; keep modules in `src/` and tests in `tests/`.
- TypeScript/TSX: 2 spaces; follow ESLint rules in `frontend/eslint.config.js`.
- Frontend styling: Tailwind only, no inline styles; include `dark:` variants; add `data-name` on container divs for debugging.
- UI consistency: reference existing settings components (`frontend/src/modules/settings/components/AssistantList.tsx`, `ModelList.tsx`, `frontend/src/modules/settings/TitleGenerationSettings.tsx`).
- Names: files and components follow feature folder structure (`frontend/src/modules/<feature>/...`).

## Testing Guidelines
- Framework: pytest. Naming: `tests/**/test_*.py` and `test_*` functions.
- Run all tests: `./venv/Scripts/pytest`
- Run one test: `./venv/Scripts/pytest tests/unit/test_file.py::test_case`
- Frontend tests are not configured yet; rely on `npm run lint` and manual UI checks.

## Commit and Pull Request Guidelines
- Commit history uses short, lowercase summaries, often imperative and sometimes comma-separated (example: "fix switch project bug, change some ui bug").
- PRs should describe what and why, note config changes, and include screenshots or a short clip for UI changes.

## Security and Configuration Tips
- Do not commit secrets; use `.env` and `.env.example`.
- API keys are stored in `$HOME/.lex_mint/keys_config.yaml`. Optional env config: `API_PORT`, `CORS_ORIGINS`.
- Conversations and logs may contain user data; handle with care.

## Platform and Tooling Notes
- Primary platform is Windows; prefer Windows command syntax in docs and scripts.
- Always call venv executables directly (do not rely on activation).
- Terminal output should be ASCII only when running commands or scripts.
- Path differences: Git Bash uses `/d/work/pythonProjects/lex_mint`, Windows uses `D:\work\pythonProjects\lex_mint`.
