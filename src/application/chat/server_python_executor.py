"""Execute Python code on the backend host when explicitly enabled."""

from __future__ import annotations

import asyncio
import base64
import json
import sys

_RUNNER_SCRIPT = r"""
import ast
import base64
import contextlib
import io
import json
import sys
import traceback

def _main() -> int:
    if len(sys.argv) < 2:
        print(json.dumps({"ok": False, "error": "missing code payload"}, ensure_ascii=False))
        return 1

    code = base64.b64decode(sys.argv[1].encode("ascii")).decode("utf-8", errors="replace")
    stdout = io.StringIO()
    stderr = io.StringIO()
    value = None
    ok = True
    error = None

    try:
        tree = ast.parse(code, filename="<execute_python>", mode="exec")
        globals_ns = {"__name__": "__main__"}

        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            if tree.body and isinstance(tree.body[-1], ast.Expr):
                prefix = ast.Module(body=tree.body[:-1], type_ignores=[])
                expr = ast.Expression(body=tree.body[-1].value)
                exec(compile(prefix, "<execute_python>", "exec"), globals_ns, globals_ns)
                value = eval(compile(expr, "<execute_python>", "eval"), globals_ns, globals_ns)
            else:
                exec(compile(tree, "<execute_python>", "exec"), globals_ns, globals_ns)
    except Exception as exc:
        ok = False
        error = f"{type(exc).__name__}: {exc}"
        traceback.print_exc(file=stderr)

    payload = {
        "ok": ok,
        "stdout": stdout.getvalue(),
        "stderr": stderr.getvalue(),
        "value": "" if value is None else repr(value),
    }
    if error:
        payload["error"] = error
    print(json.dumps(payload, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(_main())
""".strip()


async def execute_python_server_side(*, code: str, timeout_ms: int) -> str:
    """Run Python code with a subprocess and return JSON payload as text."""
    normalized_timeout_ms = max(1000, min(int(timeout_ms), 120000))
    encoded = base64.b64encode(code.encode("utf-8")).decode("ascii")

    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-c",
        _RUNNER_SCRIPT,
        encoded,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout_raw, stderr_raw = await asyncio.wait_for(
            process.communicate(),
            timeout=normalized_timeout_ms / 1000.0,
        )
    except asyncio.TimeoutError:
        process.kill()
        await process.communicate()
        return json.dumps(
            {
                "ok": False,
                "error": f"Server-side Python execution timed out after {normalized_timeout_ms}ms",
            }
        )

    stdout_text = stdout_raw.decode("utf-8", errors="replace").strip()
    stderr_text = stderr_raw.decode("utf-8", errors="replace").strip()

    if stdout_text:
        try:
            payload = json.loads(stdout_text)
            if isinstance(payload, dict):
                if stderr_text and not payload.get("stderr"):
                    payload["stderr"] = stderr_text
                return json.dumps(payload, ensure_ascii=False)
        except Exception:
            pass

    fallback_payload = {
        "ok": False,
        "error": "Server-side Python execution produced invalid payload",
        "stdout": stdout_text,
        "stderr": stderr_text,
    }
    return json.dumps(fallback_payload, ensure_ascii=False)
