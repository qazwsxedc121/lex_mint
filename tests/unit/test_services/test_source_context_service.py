"""Unit tests for structured source context rendering."""

from src.api.services.source_context_service import SourceContextService


def test_build_source_tags_includes_core_attributes_and_content():
    service = SourceContextService()
    tags = service.build_source_tags(
        query="what is rag",
        sources=[
            {
                "type": "rag",
                "kb_id": "kb_a",
                "doc_id": "doc_1",
                "filename": "intro.md",
                "chunk_index": 3,
                "content": "RAG combines retrieval and generation.",
            }
        ],
    )

    assert '<source id="1" type="rag"' in tags
    assert 'kb_id="kb_a"' in tags
    assert 'doc_id="doc_1"' in tags
    assert 'chunk_index="3"' in tags
    assert "RAG combines retrieval and generation." in tags


def test_build_source_tags_escapes_markup_like_text():
    service = SourceContextService()
    tags = service.build_source_tags(
        query="q",
        sources=[
            {
                "type": "search",
                "title": "doc <A>",
                "snippet": "2 < 3 and 5 > 1",
            }
        ],
    )

    assert 'title="doc &lt;A&gt;"' in tags
    assert "2 &lt; 3 and 5 &gt; 1" in tags


def test_build_source_tags_formats_rag_diagnostics_body():
    service = SourceContextService()
    tags = service.build_source_tags(
        query="q",
        sources=[
            {
                "type": "rag_diagnostics",
                "snippet": "raw 10 -> selected 3",
                "retrieval_mode": "hybrid",
                "raw_count": 10,
                "selected_count": 3,
                "retrieval_query_count": 2,
            }
        ],
    )

    assert "summary: raw 10 -&gt; selected 3" in tags
    assert "retrieval_mode=hybrid" in tags
    assert "raw_count=10" in tags
    assert "selected_count=3" in tags
    assert "retrieval_query_count=2" in tags


def test_apply_template_replaces_query_and_context():
    service = SourceContextService()
    output = service.apply_template(
        query="what is rag",
        source_context='<source id="1">x</source>',
    )

    assert "<query>what is rag</query>" in output
    assert "<sources>" in output
    assert '<source id="1">x</source>' in output
