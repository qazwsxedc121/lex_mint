# Server Log System

## Overview

Server logs are automatically saved to files with rotation (keeps latest 3 files).

## Log Files Location

```
logs/
├── server.log           # Current log file
├── server.log.1         # Previous log (1st rotation)
├── server.log.2         # Previous log (2nd rotation)
└── server.log.3         # Previous log (3rd rotation)
```

## File Rotation

- **Max file size**: 10MB per file
- **Backup count**: 3 files (4 files total including current)
- When `server.log` reaches 10MB:
  - `server.log.3` is deleted
  - `server.log.2` → `server.log.3`
  - `server.log.1` → `server.log.2`
  - `server.log` → `server.log.1`
  - New `server.log` is created

## Viewing Logs

### Method 1: Quick View (Last 50 lines)

```bash
./venv/Scripts/python view_server_logs.py
```

### Method 2: View Last N Lines

```bash
# View last 100 lines
./venv/Scripts/python view_server_logs.py 100

# View last 200 lines
./venv/Scripts/python view_server_logs.py 200
```

### Method 3: View All Logs

```bash
./venv/Scripts/python view_server_logs.py 0
```

### Method 4: Use Text Editor

Open `logs/server.log` in any text editor:
- VS Code
- Notepad++
- Notepad

### Method 5: Tail in Real-time (Windows PowerShell)

```powershell
Get-Content logs/server.log -Wait -Tail 50
```

### Method 6: Tail in Real-time (Git Bash/WSL)

```bash
tail -f logs/server.log
```

## Log Format

### Console Output
```
[2026-01-31 12:34:56] [INFO] src.api.main - Server started
```

### File Output (with line numbers)
```
[2026-01-31 12:34:56] [INFO] [src.api.main:45] - Server started
```

## Configuration

Logs are configured in `src/api/logging_config.py`:

```python
# Console: INFO level
# File: INFO level, 10MB max, keep 3 backups
```

## Excluding from Git

The `logs/` directory is excluded from version control (in `.gitignore`).

## Troubleshooting

### No log file exists

If `logs/server.log` doesn't exist, the server hasn't been started yet. Run:

```bash
./start_backend.bat
```

### Permission denied

If you can't read the log file, it may be locked by the server. Try:
1. Close the log file in your editor
2. Stop the server
3. Try again

### Logs not appearing in file

Make sure `setup_logging()` is called in `run_server_debug.py`:

```python
from src.api.logging_config import setup_logging
setup_logging()
```

## Log Levels

- **INFO**: Normal operation (default)
- **WARNING**: Something unexpected but not critical
- **ERROR**: Operation failed but server continues
- **CRITICAL**: Server failure

To change log level, edit `src/api/logging_config.py`:

```python
# Change from INFO to DEBUG for more verbose output
console_handler.setLevel(logging.DEBUG)
file_handler.setLevel(logging.DEBUG)
```
