"""Unit tests for SQLite vector store service."""

import uuid
import shutil
from pathlib import Path

from src.api.services.sqlite_vec_service import SqliteVecService


def test_sqlite_vec_upsert_search_and_cleanup():
    tmp_path = Path("data") / "tmp_test_runtime" / f"sqlite_vec_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)

    try:
        service = SqliteVecService(db_path=str(tmp_path / "rag_vec.sqlite3"))
        service.upsert_chunks(
            kb_id="kb1",
            doc_id="doc1",
            filename="doc.md",
            file_type=".md",
            ingest_id="ingest_a",
            chunk_rows=[
                {
                    "chunk_id": "doc1_chunk_0",
                    "chunk_index": 0,
                    "content": "alpha",
                    "embedding": [1.0, 0.0],
                },
                {
                    "chunk_id": "doc1_chunk_1",
                    "chunk_index": 1,
                    "content": "beta",
                    "embedding": [0.0, 1.0],
                },
            ],
        )

        search_results = service.search(kb_id="kb1", query_embedding=[1.0, 0.0], top_k=2)
        assert len(search_results) == 2
        assert search_results[0]["chunk_id"] == "doc1_chunk_0"
        assert float(search_results[0]["score"]) > float(search_results[1]["score"])

        deleted = service.delete_stale_document_chunks(
            kb_id="kb1",
            doc_id="doc1",
            keep_chunk_ids=["doc1_chunk_0"],
        )
        assert deleted == 1

        chunks = service.list_chunks(kb_id="kb1", doc_id="doc1", limit=10)
        assert len(chunks) == 1
        assert chunks[0]["id"] == "doc1_chunk_0"

        deleted_doc = service.delete_document_chunks(kb_id="kb1", doc_id="doc1")
        assert deleted_doc == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
