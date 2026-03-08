"""Unit tests for ContextPlanner."""

from src.api.services.context_planner import ContextPlanner


def test_context_planner_keeps_all_segments_when_budget_is_large():
    planner = ContextPlanner()

    plan = planner.plan(
        context_budget_tokens=2000,
        base_system_prompt="SYSTEM",
        compressed_history_summary="SUMMARY",
        recent_messages=[{"role": "user", "content": "hello"}],
        memory_context="MEMORY",
        webpage_context="WEBPAGE",
        search_context="SEARCH",
        rag_context="RAG",
        structured_source_context="SOURCES",
    )

    included_names = [segment.name for segment in plan.system_segments]
    assert included_names == ["system", "summary", "memory", "rag", "webpage", "search", "sources"]
    assert plan.usage_summary.context_budget == 2000
    assert plan.usage_summary.estimated_prompt_tokens > 0


def test_context_planner_drops_low_priority_sources_first_when_budget_is_tight():
    planner = ContextPlanner()
    large_text = "x" * 2000

    plan = planner.plan(
        context_budget_tokens=260,
        base_system_prompt="SYSTEM",
        compressed_history_summary="SUMMARY",
        recent_messages=[{"role": "user", "content": "hello"}],
        memory_context=large_text,
        webpage_context=large_text,
        search_context=large_text,
        rag_context=large_text,
        structured_source_context=large_text,
    )

    reports = {segment.name: segment for segment in plan.segment_reports}
    assert reports["memory"].included is True
    assert reports["rag"].included is True
    assert reports["sources"].included is False
    assert reports["sources"].drop_reason == "budget_exhausted"


def test_context_planner_applies_max_rounds_before_budgeting_history():
    planner = ContextPlanner()

    plan = planner.plan(
        context_budget_tokens=1000,
        base_system_prompt="SYSTEM",
        compressed_history_summary=None,
        recent_messages=[
            {"role": "user", "content": "u1"},
            {"role": "assistant", "content": "a1"},
            {"role": "user", "content": "u2"},
            {"role": "assistant", "content": "a2"},
            {"role": "user", "content": "u3"},
        ],
        max_rounds=1,
    )

    assert [msg["content"] for msg in plan.chat_messages] == ["u3"]
    history_report = next(segment for segment in plan.segment_reports if segment.name == "history")
    assert history_report.truncated is True
