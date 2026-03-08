"""Unit tests for the GAIA web evaluation helpers."""

from __future__ import annotations

import json
from pathlib import Path

from src.evals.gaia_web_eval import (
    EvalCase,
    _parse_tool_result,
    extract_final_answer,
    evaluate_answer,
    load_cases,
    render_markdown_report,
    select_cases,
    summarize_case_result,
)


def test_load_cases_and_select_scored(tmp_path: Path) -> None:
    payload = [
        {
            "id": "c1",
            "source_question_id": "q1",
            "title": "Case 1",
            "question": "Question 1",
            "source_url": "https://example.com",
            "expected_answer": "A",
        },
        {
            "id": "c2",
            "source_question_id": "q2",
            "title": "Case 2",
            "question": "Question 2",
            "source_url": "https://example.com",
            "expected_answer": None,
        },
    ]
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    cases = load_cases(path)
    assert [case.id for case in cases] == ["c1", "c2"]
    assert [case.id for case in select_cases(cases, scored_only=True)] == ["c1"]


def test_evaluate_answer_supports_exact_and_numeric() -> None:
    assert evaluate_answer(" wojciech ", "Wojciech", "exact_ci") is True
    assert evaluate_answer("Answer: Wojciech", "Wojciech", "exact_ci") is True
    assert evaluate_answer("**Answer: CUB**", "CUB", "exact_ci") is True
    assert evaluate_answer("6", "6", "numeric") is True
    assert evaluate_answer("5", "6", "numeric") is False
    assert evaluate_answer("any", None, "exact_ci") is None


def test_extract_final_answer_prefers_answer_span_or_last_line() -> None:
    assert extract_final_answer("Some explanation\n\nAnswer: CUB") == "CUB"
    assert extract_final_answer("Some explanation\n\n**Wojciech**") == "Wojciech"


def test_parse_tool_result_extracts_error_metadata() -> None:
    raw = json.dumps(
        {
            "ok": False,
            "status_code": 403,
            "error": {"code": "READ_WEBPAGE_FAILED", "message": "HTTP 403"},
        }
    )

    result = _parse_tool_result(raw, "read_webpage")
    assert result.name == "read_webpage"
    assert result.ok is False
    assert result.status_code == 403
    assert result.error_code == "READ_WEBPAGE_FAILED"


def test_summarize_case_result_counts_web_tools() -> None:
    case = EvalCase(
        id="case-1",
        source_question_id="q1",
        title="Title",
        question="Question",
        source_url="https://example.com",
        expected_answer="CUB",
    )
    run_payload = {
        "final_answer": "CUB",
        "tool_calls": [
            type("ToolCall", (), {"name": "web_search"})(),
            type("ToolCall", (), {"name": "read_webpage"})(),
        ],
        "tool_results": [
            _parse_tool_result(json.dumps({"ok": True, "preview": "ok"}), "web_search"),
            _parse_tool_result(
                json.dumps({"ok": False, "error": {"code": "READ_WEBPAGE_FAILED", "message": "HTTP 403"}}),
                "read_webpage",
            ),
        ],
        "usage": {"total_tokens": 10},
        "stream_error": "",
    }

    result = summarize_case_result(case, "session-1", run_payload)
    assert result.passed is True
    assert result.web_search_calls == 1
    assert result.read_webpage_calls == 1
    assert result.read_webpage_failures == 1


def test_render_markdown_report_includes_summary() -> None:
    report = {
        "generated_at": "2026-03-08T12:00:00",
        "base_url": "http://127.0.0.1:8988",
        "model_id": "provider:model",
        "context_type": "chat",
        "project_id": None,
        "summary": {
            "case_count": 1,
            "scored_case_count": 1,
            "passed_case_count": 1,
            "pass_rate": 1.0,
        },
        "cases": [
            {
                "id": "case-1",
                "source_question_id": "q1",
                "title": "Title",
                "question": "Question",
                "source_url": "https://example.com",
                "expected_answer": "CUB",
                "match_type": "exact_ci",
                "notes": "",
                "tags": ["scored"],
                "result": {
                    "case_id": "case-1",
                    "source_question_id": "q1",
                    "session_id": "session-1",
                    "final_answer": "CUB",
                    "passed": True,
                    "expected_answer": "CUB",
                    "match_type": "exact_ci",
                    "tool_rounds": 2,
                    "tool_call_count": 2,
                    "tool_result_count": 2,
                    "web_search_calls": 1,
                    "read_webpage_calls": 1,
                    "read_webpage_failures": 0,
                    "stream_error": "",
                    "usage": {"total_tokens": 10},
                    "tool_calls": [],
                    "tool_results": [],
                },
            }
        ],
    }

    markdown = render_markdown_report(report)
    assert "# GAIA Web Eval" in markdown
    assert "Pass rate: 100%" in markdown
    assert "Final answer: `CUB`" in markdown
