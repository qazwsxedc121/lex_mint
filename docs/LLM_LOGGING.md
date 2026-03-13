# LLM Interaction Logging

Last updated: 2026-03-13

This project writes per-call LLM debug logs for request/response inspection.

## Log Files

- Directory: `logs/`
- File pattern: `logs/llm_interactions_YYYYMMDD.log`

Example:
- `logs/llm_interactions_20260313.log`

## What Is Logged

Each interaction entry includes:
- timestamp
- session id
- model id
- request messages (type/role/content)
- response payload (type/role/content)
- optional extra params
- error entry when call fails

Implementation:
- `src/utils/llm_logger.py`

## Quick Inspection

### 1) View latest lines

```bash
tail -n 120 logs/llm_interactions_$(date +%Y%m%d).log
```

### 2) Filter one session

```bash
rg "550e8400-e29b-41d4-a716-446655440000" logs/llm_interactions_*.log
```

### 3) Pretty-print one file with Python

```bash
./venv/Scripts/python - <<'PY'
import json
from pathlib import Path
p = Path('logs/llm_interactions_20260313.log')
text = p.read_text(encoding='utf-8')
for block in text.split('\\n' + '=' * 80 + '\\n'):
    block = block.strip()
    if not block or not block.startswith('{'):
        continue
    data = json.loads(block)
    print(data['timestamp'], data.get('session_id'), data.get('model'))
PY
```

## Runtime Console Summary

Backend process also prints summary lines similar to:

```text
[INFO] LLM Call | Session: 550e8400... | Sent: 2 msgs | Received: 157 chars
```

## Adjust Verbosity

`LLMLogger` currently uses DEBUG for file detail logs.
To reduce volume, update logger level in `src/utils/llm_logger.py`.

## Notes

- There is no standalone `view_llm_logs.py` utility in current codebase.
- For API-level request tracing, also check `logs/server.log`.
