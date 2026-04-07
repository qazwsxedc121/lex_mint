"""Execute Python code on the backend host when explicitly enabled."""

from __future__ import annotations

import asyncio
import base64
import json
import queue
import sys
import time
from typing import Any

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
    """Run Python code with a configured backend and return JSON payload as text."""
    return await execute_python_server_side_with_backend(
        code=code,
        timeout_ms=timeout_ms,
        backend="subprocess",
        jupyter_kernel_name="python3",
    )


async def execute_python_server_side_with_backend(
    *,
    code: str,
    timeout_ms: int,
    backend: str = "subprocess",
    jupyter_kernel_name: str = "python3",
) -> str:
    """Run Python code with backend selector and return JSON payload as text."""
    normalized_backend = str(backend or "subprocess").strip().lower()
    if normalized_backend == "subprocess":
        return await _execute_python_with_subprocess(code=code, timeout_ms=timeout_ms)
    if normalized_backend == "jupyter":
        return await _execute_python_with_jupyter(
            code=code,
            timeout_ms=timeout_ms,
            kernel_name=jupyter_kernel_name,
        )
    return json.dumps(
        {
            "ok": False,
            "error": (
                f"Unknown server-side execution backend '{normalized_backend}', "
                "expected one of: subprocess, jupyter"
            ),
        }
    )


async def _execute_python_with_subprocess(*, code: str, timeout_ms: int) -> str:
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


async def _execute_python_with_jupyter(*, code: str, timeout_ms: int, kernel_name: str) -> str:
    """Run Python code via a fresh Jupyter kernel and return JSON payload as text."""
    normalized_timeout_ms = max(1000, min(int(timeout_ms), 120000))
    return await asyncio.to_thread(
        _execute_python_with_jupyter_sync,
        code,
        normalized_timeout_ms,
        str(kernel_name or "python3").strip() or "python3",
    )


def _execute_python_with_jupyter_sync(code: str, timeout_ms: int, kernel_name: str) -> str:
    """Blocking Jupyter execution helper used through asyncio.to_thread."""
    try:
        from jupyter_client import KernelManager
    except Exception:
        return json.dumps(
            {
                "ok": False,
                "error": (
                    "Jupyter backend unavailable: missing dependency 'jupyter_client' "
                    "(and a usable Python kernel such as 'ipykernel')."
                ),
            }
        )

    km = None
    kc = None
    deadline = time.monotonic() + (timeout_ms / 1000.0)
    stdout_chunks: list[str] = []
    stderr_chunks: list[str] = []
    last_value = ""
    ok = True
    error_text: str | None = None

    try:
        km = KernelManager(kernel_name=kernel_name)
        km.start_kernel()
        kc = km.client()
        kc.start_channels()
        wait_timeout = max(1.0, deadline - time.monotonic())
        kc.wait_for_ready(timeout=wait_timeout)

        msg_id = kc.execute(
            code=code,
            store_history=False,
            allow_stdin=False,
            stop_on_error=True,
        )

        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"Jupyter execution timed out after {timeout_ms}ms")
            try:
                message: Any = kc.get_iopub_msg(timeout=min(1.0, remaining))
            except queue.Empty:
                continue

            parent_id = message.get("parent_header", {}).get("msg_id")
            if parent_id != msg_id:
                continue

            msg_type = message.get("msg_type")
            content = message.get("content", {}) or {}
            if msg_type == "stream":
                stream_name = str(content.get("name") or "")
                stream_text = str(content.get("text") or "")
                if stream_name == "stderr":
                    stderr_chunks.append(stream_text)
                else:
                    stdout_chunks.append(stream_text)
                continue
            if msg_type in {"execute_result", "display_data"}:
                data = content.get("data") or {}
                if isinstance(data, dict):
                    value_candidate = data.get("text/plain")
                    if value_candidate is not None:
                        last_value = str(value_candidate)
                continue
            if msg_type == "error":
                ok = False
                ename = str(content.get("ename") or "ExecutionError")
                evalue = str(content.get("evalue") or "")
                error_text = f"{ename}: {evalue}".strip()
                traceback_lines = content.get("traceback") or []
                if isinstance(traceback_lines, list) and traceback_lines:
                    stderr_chunks.append("\n".join(str(line) for line in traceback_lines))
                continue
            if msg_type == "status" and str(content.get("execution_state")) == "idle":
                break

        payload = {
            "ok": ok,
            "stdout": "".join(stdout_chunks),
            "stderr": "".join(stderr_chunks),
            "value": last_value,
        }
        if error_text:
            payload["error"] = error_text
        return json.dumps(payload, ensure_ascii=False)
    except Exception as exc:
        return json.dumps(
            {
                "ok": False,
                "error": str(exc),
                "stdout": "".join(stdout_chunks),
                "stderr": "".join(stderr_chunks),
            },
            ensure_ascii=False,
        )
    finally:
        try:
            if kc is not None:
                kc.stop_channels()
        except Exception:
            pass
        try:
            if km is not None:
                km.shutdown_kernel(now=True)
        except Exception:
            pass
