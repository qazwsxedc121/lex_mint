"""Minimal GAIA-style web research evaluation harness.

This module drives the public chat HTTP API so the evaluation path matches
real product usage. It focuses on public-web research tasks that primarily
exercise ``web_search`` and ``read_webpage``.
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

DEFAULT_CASES_PATH = Path("scripts/eval_cases/gaia_level1_web_cases.json")
DEFAULT_REPORTS_DIR = Path("docs/eval")
_ANSWER_ONLY_PROMPT = (
    "You are being evaluated on answer accuracy. Research using the available tools, "
    "then return only the final answer. Do not include explanation, reasoning, citations, "
    "or extra words beyond the answer itself."
)


@dataclass
class EvalCase:
    """One benchmark case."""

    id: str
    source_question_id: str
    title: str
    question: str
    source_url: str
    expected_answer: str | None = None
    match_type: str = "exact_ci"
    notes: str = ""
    tags: list[str] | None = None


@dataclass
class ToolCallRecord:
    """A tool call announced by the backend stream."""

    name: str
    call_id: str = ""
    args: dict[str, Any] | None = None


@dataclass
class ToolResultRecord:
    """A tool result emitted by the backend stream."""

    name: str
    ok: bool | None
    status_code: int | None
    error_code: str = ""
    error_message: str = ""
    preview: str = ""
    raw_result: str = ""


@dataclass
class EvalResult:
    """Result for a single evaluation case."""

    case_id: str
    source_question_id: str
    session_id: str
    final_answer: str
    passed: bool | None
    expected_answer: str | None
    match_type: str
    tool_rounds: int
    tool_call_count: int
    tool_result_count: int
    web_search_calls: int
    read_webpage_calls: int
    read_webpage_failures: int
    stream_error: str = ""
    usage: dict[str, Any] | None = None
    tool_calls: list[ToolCallRecord] | None = None
    tool_results: list[ToolResultRecord] | None = None


def load_cases(path: Path) -> list[EvalCase]:
    """Load evaluation cases from JSON."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return [EvalCase(**item) for item in payload]


def select_cases(
    cases: Sequence[EvalCase],
    *,
    case_ids: Sequence[str] | None = None,
    limit: int | None = None,
    scored_only: bool = False,
) -> list[EvalCase]:
    """Filter the full case catalog to the requested subset."""

    selected = list(cases)
    if case_ids:
        wanted = {value.strip() for value in case_ids if value.strip()}
        selected = [case for case in selected if case.id in wanted]
    if scored_only:
        selected = [case for case in selected if case.expected_answer is not None]
    if limit is not None:
        selected = selected[: max(0, limit)]
    return selected


def normalize_answer(value: str) -> str:
    """Normalize answer text for lightweight matching."""

    return " ".join((value or "").strip().split())


def extract_final_answer(value: str) -> str:
    """Extract the most likely final answer span from a verbose completion."""

    text = str(value or "").strip()
    if not text:
        return ""

    lines = [line.strip() for line in text.splitlines() if line.strip()]
    patterns = (
        r"(?:final answer|answer)\s*[:：]\s*(.+)$",
        r"^therefore[, ]+the answer is\s+(.+)$",
        r"^therefore[, ]+(.+)$",
    )
    for line in reversed(lines):
        cleaned_line = line.strip().strip("`*")
        for pattern in patterns:
            match = re.search(pattern, cleaned_line, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip().strip("`* .")

    last_line = lines[-1].strip().strip("`*") if lines else text
    return last_line.strip().strip(". ")


def evaluate_answer(actual: str, expected: str | None, match_type: str) -> bool | None:
    """Evaluate a model answer against a reference answer."""

    if expected is None:
        return None

    actual_norm = normalize_answer(extract_final_answer(actual))
    expected_norm = normalize_answer(expected)

    if match_type == "exact":
        return actual_norm == expected_norm
    if match_type == "exact_ci":
        return actual_norm.casefold() == expected_norm.casefold()
    if match_type == "contains_ci":
        return expected_norm.casefold() in actual_norm.casefold()
    if match_type == "numeric":
        try:
            return float(actual_norm) == float(expected_norm)
        except ValueError:
            return False
    raise ValueError(f"Unsupported match_type: {match_type}")


def _truncate(value: str, *, limit: int = 200) -> str:
    text = normalize_answer(value)
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _parse_tool_result(raw_result: str, tool_name: str) -> ToolResultRecord:
    ok: bool | None = None
    status_code: int | None = None
    error_code = ""
    error_message = ""
    preview = _truncate(raw_result)

    try:
        payload = json.loads(raw_result)
    except Exception:
        return ToolResultRecord(
            name=tool_name,
            ok=ok,
            status_code=status_code,
            preview=preview,
            raw_result=raw_result,
        )

    if isinstance(payload, dict):
        if isinstance(payload.get("ok"), bool):
            ok = bool(payload.get("ok"))
        status_code_value = payload.get("status_code")
        if isinstance(status_code_value, int):
            status_code = int(status_code_value)
        error = payload.get("error")
        if isinstance(error, dict):
            error_code = str(error.get("code") or "")
            error_message = str(error.get("message") or "")
        preview = _truncate(
            str(payload.get("preview") or error_message or payload.get("title") or raw_result)
        )

    return ToolResultRecord(
        name=tool_name,
        ok=ok,
        status_code=status_code,
        error_code=error_code,
        error_message=error_message,
        preview=preview,
        raw_result=raw_result,
    )


async def iter_sse_flow_events(response: httpx.Response) -> AsyncIterator[dict[str, Any]]:
    """Yield flow_event payloads from an SSE response."""

    async for line in response.aiter_lines():
        if not line or not line.startswith("data: "):
            continue
        payload = json.loads(line[6:])
        flow_event = payload.get("flow_event")
        if isinstance(flow_event, dict):
            yield flow_event


class LexMintEvalClient:
    """Small HTTP client for the product APIs used by the eval harness."""

    def __init__(self, *, base_url: str, timeout_seconds: float = 180.0) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout_seconds

    async def get_default_model_id(self) -> str:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.get("/api/models/default")
            response.raise_for_status()
            payload = response.json()
        provider = str(payload.get("provider") or "").strip()
        model = str(payload.get("model") or "").strip()
        if not provider or not model:
            raise RuntimeError("No default model configured")
        return f"{provider}:{model}"

    async def create_session(
        self,
        *,
        model_id: str,
        context_type: str,
        project_id: str | None,
    ) -> str:
        params: dict[str, Any] = {"context_type": context_type}
        if project_id:
            params["project_id"] = project_id
        request = {"target_type": "model", "model_id": model_id}
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.post("/api/sessions", params=params, json=request)
            response.raise_for_status()
            payload = response.json()
        session_id = str(payload.get("session_id") or "").strip()
        if not session_id:
            raise RuntimeError("Session creation returned an empty session_id")
        return session_id

    async def delete_session(
        self,
        *,
        session_id: str,
        context_type: str,
        project_id: str | None,
    ) -> None:
        params: dict[str, Any] = {"context_type": context_type}
        if project_id:
            params["project_id"] = project_id
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.delete(f"/api/sessions/{session_id}", params=params)
            response.raise_for_status()

    async def ensure_project_web_tools_enabled(self, project_id: str) -> None:
        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            response = await client.get(f"/api/projects/{project_id}")
            response.raise_for_status()
            project = response.json()

            settings = dict(project.get("settings") or {})
            tool_settings = dict(settings.get("tools") or {})
            enabled_map = dict(tool_settings.get("tool_enabled_map") or {})
            enabled_map["web_search"] = True
            enabled_map["read_webpage"] = True
            tool_settings["tool_enabled_map"] = enabled_map
            settings["tools"] = tool_settings

            update_response = await client.put(
                f"/api/projects/{project_id}",
                json={"settings": settings},
            )
            update_response.raise_for_status()

    async def run_case(
        self,
        *,
        session_id: str,
        question: str,
        context_type: str,
        project_id: str | None,
        context_capabilities: list[str] | None = None,
        context_capability_args: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        wrapped_question = f"{_ANSWER_ONLY_PROMPT}\n\nQuestion:\n{question}"
        request: dict[str, Any] = {
            "session_id": session_id,
            "message": wrapped_question,
            "context_type": context_type,
            "project_id": project_id,
            "context_capabilities": list(context_capabilities or []),
            "context_capability_args": dict(context_capability_args or {}),
        }

        final_chunks: list[str] = []
        tool_calls: list[ToolCallRecord] = []
        tool_results: list[ToolResultRecord] = []
        usage: dict[str, Any] | None = None
        stream_error = ""

        async with httpx.AsyncClient(base_url=self.base_url, timeout=self.timeout) as client:
            async with client.stream("POST", "/api/chat/stream", json=request) as response:
                response.raise_for_status()
                async for event in iter_sse_flow_events(response):
                    event_type = str(event.get("event_type") or "")
                    payload = event.get("payload") or {}

                    if event_type == "text_delta":
                        final_chunks.append(str(payload.get("text") or ""))
                        continue

                    if event_type == "tool_call_started":
                        for item in payload.get("calls") or []:
                            tool_calls.append(
                                ToolCallRecord(
                                    name=str(item.get("name") or ""),
                                    call_id=str(item.get("id") or ""),
                                    args=item.get("args")
                                    if isinstance(item.get("args"), dict)
                                    else {},
                                )
                            )
                        continue

                    if event_type == "tool_call_finished":
                        for item in payload.get("results") or []:
                            tool_results.append(
                                _parse_tool_result(
                                    str(item.get("result") or ""),
                                    str(item.get("name") or ""),
                                )
                            )
                        continue

                    if event_type == "usage_reported" and isinstance(payload.get("usage"), dict):
                        usage = dict(payload.get("usage") or {})
                        continue

                    if event_type == "stream_error":
                        stream_error = str(payload.get("error") or "")

        return {
            "final_answer": "".join(final_chunks).strip(),
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "usage": usage,
            "stream_error": stream_error,
        }


def summarize_case_result(
    case: EvalCase, session_id: str, run_payload: dict[str, Any]
) -> EvalResult:
    """Convert a raw run payload into the persisted result model."""

    tool_calls = list(run_payload.get("tool_calls") or [])
    tool_results = list(run_payload.get("tool_results") or [])
    final_answer = str(run_payload.get("final_answer") or "")
    passed = evaluate_answer(final_answer, case.expected_answer, case.match_type)

    read_webpage_failures = sum(
        1 for item in tool_results if item.name == "read_webpage" and item.ok is False
    )

    return EvalResult(
        case_id=case.id,
        source_question_id=case.source_question_id,
        session_id=session_id,
        final_answer=final_answer,
        passed=passed,
        expected_answer=case.expected_answer,
        match_type=case.match_type,
        tool_rounds=len(tool_calls),
        tool_call_count=len(tool_calls),
        tool_result_count=len(tool_results),
        web_search_calls=sum(1 for item in tool_calls if item.name == "web_search"),
        read_webpage_calls=sum(1 for item in tool_calls if item.name == "read_webpage"),
        read_webpage_failures=read_webpage_failures,
        stream_error=str(run_payload.get("stream_error") or ""),
        usage=run_payload.get("usage"),
        tool_calls=tool_calls,
        tool_results=tool_results,
    )


def build_report_payload(
    *,
    cases: Sequence[EvalCase],
    results: Sequence[EvalResult],
    base_url: str,
    model_id: str,
    context_type: str,
    project_id: str | None,
) -> dict[str, Any]:
    """Build the report JSON payload."""

    result_map = {result.case_id: result for result in results}
    scored_results = [result for result in results if result.passed is not None]
    passed_count = sum(1 for result in scored_results if result.passed is True)

    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "base_url": base_url,
        "model_id": model_id,
        "context_type": context_type,
        "project_id": project_id,
        "summary": {
            "case_count": len(cases),
            "scored_case_count": len(scored_results),
            "passed_case_count": passed_count,
            "pass_rate": (passed_count / len(scored_results)) if scored_results else None,
        },
        "cases": [
            {
                **asdict(case),
                "result": asdict(result_map[case.id]) if case.id in result_map else None,
            }
            for case in cases
        ],
    }


def render_markdown_report(report: dict[str, Any]) -> str:
    """Render a concise markdown report."""

    summary = report["summary"]
    lines = [
        "# GAIA Web Eval",
        "",
        f"- Generated: {report['generated_at']}",
        f"- Base URL: `{report['base_url']}`",
        f"- Model: `{report['model_id']}`",
        f"- Context: `{report['context_type']}`",
        f"- Project: `{report['project_id'] or '-'}`",
        f"- Cases: {summary['case_count']}",
        f"- Scored: {summary['scored_case_count']}",
        f"- Passed: {summary['passed_case_count']}",
    ]
    if summary["pass_rate"] is None:
        lines.append("- Pass rate: n/a")
    else:
        lines.append(f"- Pass rate: {summary['pass_rate']:.0%}")

    lines.extend(["", "## Case Results", ""])

    for case_payload in report["cases"]:
        case = EvalCase(**{key: case_payload[key] for key in EvalCase.__dataclass_fields__.keys()})
        result = case_payload.get("result")
        lines.append(f"### {case.id} - {case.title}")
        lines.append("")
        lines.append(f"- Source question ID: `{case.source_question_id}`")
        lines.append(f"- Expected: `{case.expected_answer or 'manual review'}`")
        if result is None:
            lines.append("- Result: not run")
            lines.append("")
            continue

        status = "manual"
        if result["passed"] is True:
            status = "pass"
        elif result["passed"] is False:
            status = "fail"
        lines.append(f"- Status: {status}")
        lines.append(f"- Final answer: `{normalize_answer(result['final_answer']) or '-'}`")
        lines.append(
            "- Tool usage: "
            f"web_search={result['web_search_calls']}, "
            f"read_webpage={result['read_webpage_calls']}, "
            f"read_webpage_failures={result['read_webpage_failures']}"
        )
        if result.get("stream_error"):
            lines.append(f"- Stream error: `{result['stream_error']}`")
        lines.append("")

    return "\n".join(lines) + "\n"


def write_report_files(
    report: dict[str, Any], *, output_dir: Path, run_name: str
) -> dict[str, Path]:
    """Write JSON and markdown reports."""

    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{run_name}.json"
    md_path = output_dir / f"{run_name}.md"

    json_path.write_text(json.dumps(report, ensure_ascii=True, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown_report(report), encoding="utf-8")
    return {"json": json_path, "markdown": md_path}


async def run_eval(
    *,
    base_url: str,
    model_id: str | None,
    context_type: str,
    project_id: str | None,
    cases: Sequence[EvalCase],
    cleanup_sessions: bool,
    ensure_project_web_tools: bool,
) -> dict[str, Any]:
    """Run the selected evaluation cases end to end."""

    client = LexMintEvalClient(base_url=base_url)
    resolved_model_id = model_id or await client.get_default_model_id()

    if context_type == "project" and project_id and ensure_project_web_tools:
        await client.ensure_project_web_tools_enabled(project_id)

    results: list[EvalResult] = []
    for case in cases:
        session_id = await client.create_session(
            model_id=resolved_model_id,
            context_type=context_type,
            project_id=project_id,
        )
        try:
            raw_result = await client.run_case(
                session_id=session_id,
                question=case.question,
                context_type=context_type,
                project_id=project_id,
                context_capabilities=["web.search_context"],
            )
            results.append(summarize_case_result(case, session_id, raw_result))
        finally:
            if cleanup_sessions:
                await client.delete_session(
                    session_id=session_id,
                    context_type=context_type,
                    project_id=project_id,
                )

    return build_report_payload(
        cases=cases,
        results=results,
        base_url=base_url,
        model_id=resolved_model_id,
        context_type=context_type,
        project_id=project_id,
    )
