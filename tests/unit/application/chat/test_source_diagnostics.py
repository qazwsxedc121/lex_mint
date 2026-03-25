from src.application.chat.source_diagnostics import (
    merge_source_groups,
    merge_tool_diagnostics_into_sources,
)


def test_merge_source_groups_ignores_empty_groups():
    merged = merge_source_groups(
        [{"type": "memory"}],
        [],
        None,
        [{"type": "search"}, {"type": "rag"}],
    )

    assert merged == [
        {"type": "memory"},
        {"type": "search"},
        {"type": "rag"},
    ]


def test_merge_tool_diagnostics_updates_existing_rag_source():
    sources = [
        {"type": "memory"},
        {"type": "rag_diagnostics", "snippet": "retrieved context | tool s:1 u:1 d:0 r:1 f:read"},
    ]

    merged = merge_tool_diagnostics_into_sources(
        sources,
        {
            "type": "tool_diagnostics",
            "tool_search_count": 2,
            "tool_search_unique_count": 2,
            "tool_search_duplicate_count": 0,
            "tool_read_count": 1,
            "tool_finalize_reason": "normal_with_tools",
        },
    )

    assert merged[1]["tool_search_count"] == 2
    assert merged[1]["tool_finalize_reason"] == "normal_with_tools"
    assert merged[1]["snippet"] == (
        "retrieved context | tool s:2 u:2 d:0 r:1 f:normal_with_tools"
    )
