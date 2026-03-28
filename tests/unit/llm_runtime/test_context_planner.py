"""Unit tests for ContextPlanner."""

from src.llm_runtime.context_planner import ContextPlanner, ContextPlannerPolicy


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


def test_context_planner_keeps_required_summary_by_truncating():
    planner = ContextPlanner()

    plan = planner.plan(
        context_budget_tokens=80,
        base_system_prompt="SYSTEM",
        compressed_history_summary="x" * 4000,
        recent_messages=[],
    )

    summary_report = next(segment for segment in plan.segment_reports if segment.name == "summary")

    assert summary_report.included is True
    assert summary_report.truncated is True
    assert summary_report.estimated_tokens_after > 0


def test_context_planner_policy_can_raise_sources_minimum_budget():
    large_sources = "x" * 4000

    default_plan = ContextPlanner().plan(
        context_budget_tokens=500,
        base_system_prompt=None,
        compressed_history_summary=None,
        recent_messages=[],
        structured_source_context=large_sources,
    )
    strict_plan = ContextPlanner(
        policy=ContextPlannerPolicy(min_segment_tokens_by_name={"sources": 64})
    ).plan(
        context_budget_tokens=500,
        base_system_prompt=None,
        compressed_history_summary=None,
        recent_messages=[],
        structured_source_context=large_sources,
    )

    default_sources = next(
        segment for segment in default_plan.segment_reports if segment.name == "sources"
    )
    strict_sources = next(
        segment for segment in strict_plan.segment_reports if segment.name == "sources"
    )

    assert default_sources.included is True
    assert strict_sources.included is False
    assert strict_sources.drop_reason == "budget_exhausted"
