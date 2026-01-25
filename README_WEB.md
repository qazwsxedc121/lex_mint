# LangGraph Agent Web Interface

LangGraph-based AI agent system with FastAPI backend and React frontend.

## Quick Start

### First Time Setup

1. Double-click `install.bat` to install dependencies
2. Edit `.env` file and add your `DEEPSEEK_API_KEY`
3. Double-click `start.bat` to start services
4. Browser will automatically open at http://localhost:5173

### Daily Usage

- **Start**: Double-click `start.bat`
- **Stop**: Double-click `stop.bat`
- **Menu**: Double-click `menu.bat` (Recommended!)
- **Status**: Double-click `status.bat`

## Batch Scripts

| Script | Function | Description |
|--------|----------|-------------|
| `menu.bat` | Main Menu | Centralized operation menu |
| `install.bat` | Installation | Install Python and Node.js dependencies |
| `start.bat` | Start Services | Launch backend and frontend |
| `stop.bat` | Stop Services | Shutdown all running services |
| `status.bat` | Status Check | Check service status |

## Green Software Package

The project is ready for packaging as portable software:

### Package Contents
```
Project Root/
├── venv/              # Python virtual environment
├── frontend/          # Frontend code
│   └── node_modules/  # Frontend dependencies
├── src/               # Source code
├── conversations/     # Chat storage (optional)
├── *.bat              # Batch scripts
└── .env              # Configuration (remove API key)
```

### Packaging Options

**Option 1: Simple ZIP Package**
```
1. Run install.bat to complete all installations
2. Remove API key from .env file
3. Compress entire project folder to .zip
4. Users only need to configure .env after extraction
```

**Option 2: Installer (Inno Setup/NSIS)**
```
- Create professional Windows installer
- Auto-create desktop shortcuts
- Guide users through configuration
- Support uninstallation
```

**Option 3: Electron Standalone App**
```
- Fully independent desktop application
- No need for users to install Python/Node.js
- Cross-platform support
- ~200MB package size
```

## Access URLs

- 🌐 **Web Interface**: http://localhost:5173
- 🔧 **API Backend**: http://localhost:8000
- 📖 **API Docs**: http://localhost:8000/docs

## File Structure

- `conversations/` - Chat history storage (Markdown format)
- `.env` - Environment variables (API key)
- `requirements.txt` - Python dependencies
- `frontend/package.json` - Frontend dependencies

## Tech Stack

- **Backend**: FastAPI + LangGraph + DeepSeek
- **Frontend**: React + TypeScript + TailwindCSS + Vite
- **Storage**: Markdown files + YAML Frontmatter

## CLI Mode (Optional)

To use the original CLI mode:
```bash
venv\Scripts\activate
python -m src.main
```

## Testing

```bash
venv\Scripts\activate
pytest
pytest --cov=src --cov-report=html
```

## Documentation

See `CLAUDE.md` for complete developer documentation.
