# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL Development Rules

**IMPORTANT**: These rules must be followed at all times:

1. **Always Use Virtual Environment**
   - NEVER run Python commands without using venv
   - **Correct way**: Directly call venv's python executable
   - Example: `./venv/Scripts/python your_script.py`
   - Example: `./venv/Scripts/pip install package_name`
   - **WRONG**: `python your_script.py` (uses system Python)
   - **WRONG**: `venv\Scripts\activate && python ...` (doesn't work in bash)

2. **Windows Terminal Encoding**
   - Windows terminal uses GBK encoding by default (NOT UTF-8)
   - **NEVER use Chinese characters in print() or console output**
   - **NEVER use emoji (✅❌⚠️) in console output**
   - Use only ASCII characters in terminal output
   - Example: Use "OK" instead of "✅", "FAIL" instead of "❌"

3. **Code Files vs Terminal Output**
   - Code files (.py, .md, etc.): Can use UTF-8, Chinese, emoji
   - Terminal/console output: Only ASCII characters allowed

4. **Windows Path Handling**
   - **Key Discovery**: Git Bash and Windows use different path formats for the SAME directory
   - Project root is mapped to TWO different paths:
     - Git Bash: `/d/work/pythonProjects/agent_dev`
     - Windows: `D:\work\pythonProjects\agent_dev`

   **Rules by Tool Type**:

   **Bash Tool (Git Bash environment)**:
   - ALWAYS use relative paths with forward slashes: `logs/server.log`
   - Can use backslashes too: `logs\server.log` (but forward slash preferred)
   - Absolute paths must be Unix-style: `/d/work/pythonProjects/agent_dev/logs/server.log`
   - Windows absolute paths DON'T WORK: ~~`C:/Users/.../logs/server.log`~~ ✗

   **Read/Edit/Write/Glob Tools**:
   - MUST use Windows absolute paths: `D:\work\pythonProjects\agent_dev\logs\server.log`
   - Forward slashes also work: `C:/Users/lisareese1674/projects/agents-f17830c7de/logs/server.log`

   **Grep Tool**:
   - Can use relative paths: `logs/server.log`
   - Works with both slash types

   **Best Practice**:
   - Use **relative paths** whenever possible (works across all tools)
   - Example: `logs/server.log`, `src/api/main.py`, `frontend/src/App.tsx`
   - Only use absolute paths when necessary (and use tool-appropriate format)

## Frontend Development Rules

**IMPORTANT**: Follow these rules when developing frontend components:

1. **Always Use Tailwind CSS**
   - **NEVER use inline styles** (e.g., `style={{ color: '#666' }}`)
   - **ALWAYS use Tailwind CSS classes** for styling
   - Example: Use `className="p-5 text-gray-500 dark:text-gray-400"` instead of `style={{ padding: '20px', color: '#666' }}`

2. **Dark Mode Support**
   - **ALWAYS include dark mode variants** for all styles using the `dark:` prefix
   - Example: `text-gray-900 dark:text-white`, `bg-white dark:bg-gray-800`

3. **Reference Existing Components**
   - **ALWAYS check existing settings pages** for style reference:
     - `frontend/src/modules/settings/components/AssistantList.tsx`
     - `frontend/src/modules/settings/components/ModelList.tsx`
     - `frontend/src/modules/settings/TitleGenerationSettings.tsx`
   - Copy and adapt existing Tailwind patterns for consistency
   - Maintain visual consistency across all pages

4. **Component Debugging**
   - **ALWAYS add `data-name` attribute** to container divs for easier debugging
   - Use descriptive names: `data-name="chat-view-root"`, `data-name="file-tree-panel"`
   - Helps identify elements in Chrome DevTools during layout debugging

## Project Overview

LangGraph-based AI agent system with web interface using FastAPI backend and React frontend. The system uses DeepSeek as the LLM provider and stores conversations in Markdown format for easy cross-device synchronization.

### Key Features
- **Backend**: FastAPI REST API for agent interactions
- **Frontend**: React + TypeScript web interface
- **Storage**: Markdown files with YAML frontmatter (text-based, sync-friendly)
- **LLM**: DeepSeek chat model via LangChain

## Development Environment

**Primary Platform**: Windows

All commands and examples in this document are provided for Windows unless otherwise noted. When providing commands, always default to Windows syntax (e.g., `venv\Scripts\activate` for virtual environment activation).

## Development Commands

### Setup
```bash
# Install backend dependencies (use venv's pip)
./venv/Scripts/pip install -r requirements.txt

# Install frontend dependencies
cd frontend
npm install
```

### Running

**Backend API** (Terminal 1):
```bash
# Use venv's uvicorn directly (port configured in .env, default: 8888)
./venv/Scripts/uvicorn src.api.main:app --reload --port 8888
```

**Frontend** (Terminal 2):
```bash
cd frontend
npm run dev
```

Access the web interface at http://localhost:5173

**CLI Mode** (original):
```bash
# Use venv's python directly
./venv/Scripts/python -m src.main
```

### Testing
```bash
# Run all tests
./venv/Scripts/pytest

# Run single test file
./venv/Scripts/pytest tests/unit/test_simple_agent.py

# Run single test function
./venv/Scripts/pytest tests/unit/test_simple_agent.py::test_chat_node

# Run with coverage
./venv/Scripts/pytest --cov=src --cov-report=html
```

### Logging
- Backend logs: Check `logs/server.log`
- All backend API and agent logs are written to this single file

## Architecture

For detailed documentation, see `docs/`:
- `docs/file_structure.md` - Complete project file structure and organization
- `docs/api_endpoints.md` - API endpoint specifications and usage
- `docs/llm_logging.md` - LLM logging system documentation
- `docs/port_configuration.md` - Backend port configuration guide

### Key Concepts
- **Backend**: FastAPI REST API (`src/api/`)
- **Frontend**: React + TypeScript (`frontend/`)
- **Storage**: Markdown files with YAML frontmatter in `conversations/` (no database)
- **Agent**: LangGraph state-based architecture (`src/agents/`)
- **LLM Providers**: Configurable via `config/models_config.yaml`

## Environment Variables

Required `.env` file:
```
DEEPSEEK_API_KEY=your_key_here
```

Optional for API configuration:
```
API_HOST=0.0.0.0
API_PORT=8888          # Backend port (default: 8888, change if port conflicts)
CORS_ORIGINS=http://localhost:5173
CONVERSATIONS_DIR=conversations
LOG_LEVEL=INFO
```

Optional for LangSmith tracing:
```
LANGCHAIN_API_KEY=your_key_here
LANGCHAIN_TRACING_V2=true
```

Frontend `.env` (optional):
```
VITE_API_URL=http://localhost:8888  # Must match backend API_PORT
```
