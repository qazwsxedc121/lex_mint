"""Simple static server for packaged frontend dist (SPA fallback)."""

from __future__ import annotations

from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv


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


class SpaRequestHandler(SimpleHTTPRequestHandler):
    """Serve built assets and fallback to index.html for route paths."""

    def do_GET(self) -> None:  # noqa: N802 - stdlib handler signature
        parsed = urlparse(self.path)
        path = unquote(parsed.path or "/").lstrip("/")
        if not path:
            self.path = "/index.html"
            super().do_GET()
            return

        requested = Path(self.directory, path)  # type: ignore[arg-type]
        try:
            requested_resolved = requested.resolve()
            root_resolved = Path(self.directory).resolve()  # type: ignore[arg-type]
            within_root = requested_resolved == root_resolved or root_resolved in requested_resolved.parents
        except OSError:
            within_root = False

        if within_root and requested.exists() and requested.is_file():
            super().do_GET()
            return

        self.path = "/index.html"
        super().do_GET()

    def log_message(self, format: str, *args: object) -> None:
        message = format % args
        print(f"[frontend] {message}")


def main() -> None:
    runtime_root = _runtime_root()
    os.environ.setdefault("LEX_MINT_RUNTIME_ROOT", str(runtime_root))
    os.chdir(runtime_root)
    load_dotenv(runtime_root / ".env", override=False)

    frontend_port = _read_port("FRONTEND_PORT", 18001)
    host = os.getenv("FRONTEND_HOST", "127.0.0.1").strip() or "127.0.0.1"
    dist_dir = runtime_root / "frontend" / "dist"
    if not dist_dir.exists():
        raise FileNotFoundError(f"frontend dist not found: {dist_dir}")

    handler = partial(SpaRequestHandler, directory=str(dist_dir))
    server = ThreadingHTTPServer((host, frontend_port), handler)
    print(f"[lex_mint] frontend: http://{host}:{frontend_port}")
    print(f"[lex_mint] serving static files from: {dist_dir}")
    server.serve_forever()


if __name__ == "__main__":
    main()
