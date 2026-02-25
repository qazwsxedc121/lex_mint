from src.api.services.bm25_service import Bm25Service


def test_bm25_search_filters_by_term_coverage(tmp_path):
    db_path = tmp_path / "bm25.sqlite3"
    service = Bm25Service(db_path=str(db_path))
    service.upsert_document_chunks(
        kb_id="kb_a",
        doc_id="doc_1",
        filename="doc_1.md",
        chunks=[
            {
                "chunk_id": "c1",
                "chunk_index": 0,
                "content": "hari seldon psychohistory trantor empire",
            },
            {
                "chunk_id": "c2",
                "chunk_index": 1,
                "content": "seldon heard rumors in the streets",
            },
        ],
    )

    loose_rows = service.search(
        kb_id="kb_a",
        query="hari seldon psychohistory",
        top_k=5,
        min_term_coverage=0.0,
    )
    assert {row["chunk_id"] for row in loose_rows} == {"c1", "c2"}

    strict_rows = service.search(
        kb_id="kb_a",
        query="hari seldon psychohistory",
        top_k=5,
        min_term_coverage=0.6,
    )
    assert [row["chunk_id"] for row in strict_rows] == ["c1"]
    assert strict_rows[0]["term_coverage"] == 1.0


def test_significant_terms_fallback_keeps_short_tokens():
    assert Bm25Service._significant_query_terms("a b") == ["a", "b"]


def test_upsert_document_chunks_refreshes_fts_without_duplicates(tmp_path):
    db_path = tmp_path / "bm25.sqlite3"
    service = Bm25Service(db_path=str(db_path))

    service.upsert_document_chunks(
        kb_id="kb_a",
        doc_id="doc_1",
        filename="doc_1.md",
        chunks=[
            {
                "chunk_id": "c1",
                "chunk_index": 0,
                "content": "alpha beta gamma",
            }
        ],
    )
    service.upsert_document_chunks(
        kb_id="kb_a",
        doc_id="doc_1",
        filename="doc_1.md",
        chunks=[
            {
                "chunk_id": "c1",
                "chunk_index": 0,
                "content": "alpha beta gamma delta",
            }
        ],
    )

    rows = service.search(
        kb_id="kb_a",
        query="alpha",
        top_k=10,
        min_term_coverage=0.0,
    )
    assert [row["chunk_id"] for row in rows] == ["c1"]
