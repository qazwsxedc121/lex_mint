"""Packaged backend entrypoint for Windows builds."""

from __future__ import annotations

import os
from pathlib import Path
import sys

from dotenv import load_dotenv
import uvicorn


def _runtime_root() -> Path:
    env_root = os.getenv("LEX_MINT_RUNTIME_ROOT", "").strip()
    if env_root:
        return Path(env_root).expanduser().resolve()
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[3]


def _read_port(name: str, default: int) -> int:
    value = os.getenv(name, "").strip()
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        return default


def main() -> None:
    runtime_root = _runtime_root()
    os.environ.setdefault("LEX_MINT_RUNTIME_ROOT", str(runtime_root))
    os.environ.setdefault("LEX_MINT_SERVE_FRONTEND", "1")
    os.chdir(runtime_root)

    load_dotenv(runtime_root / ".env", override=False)

    api_host = os.getenv("API_HOST", "127.0.0.1").strip() or "127.0.0.1"
    api_port = _read_port("API_PORT", 18000)
    log_level = os.getenv("UVICORN_LOG_LEVEL", "info").strip() or "info"

    print(f"[lex_mint] runtime root: {runtime_root}")
    print(f"[lex_mint] backend: http://{api_host}:{api_port}")
    print(f"[lex_mint] frontend served by backend: {runtime_root / 'frontend' / 'dist'}")
    uvicorn.run(
        "src.api.main:app",
        host=api_host,
        port=api_port,
        log_level=log_level,
        reload=False,
        access_log=True,
    )


if __name__ == "__main__":
    main()
