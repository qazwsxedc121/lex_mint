"""Unit tests for SQLite vector store service."""

import math
import struct
import uuid
import shutil
import sys
import types
from pathlib import Path

from src.api.services.sqlite_vec_service import SqliteVecService


def test_sqlite_vec_upsert_search_and_cleanup():
    tmp_path = Path("data") / "tmp_test_runtime" / f"sqlite_vec_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)

    try:
        service = SqliteVecService(db_path=str(tmp_path / "rag_vec.sqlite3"))
        had_existing = service.upsert_chunks(
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
        assert had_existing is False

        had_existing = service.upsert_chunks(
            kb_id="kb1",
            doc_id="doc1",
            filename="doc.md",
            file_type=".md",
            ingest_id="ingest_b",
            chunk_rows=[
                {
                    "chunk_id": "doc1_chunk_0",
                    "chunk_index": 0,
                    "content": "alpha",
                    "embedding": [1.0, 0.0],
                }
            ],
        )
        assert had_existing is True

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


def test_sqlite_vec_search_backfills_legacy_blob_columns():
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
            ],
        )

        # Simulate a legacy row that predates embedding_blob / embedding_dim.
        with service._connect() as conn:
            conn.execute(
                """
                UPDATE rag_vec_chunks
                SET embedding_blob = NULL, embedding_dim = NULL
                WHERE chunk_id = 'doc1_chunk_0'
                """
            )
            conn.commit()

        results = service.search(kb_id="kb1", query_embedding=[1.0, 0.0], top_k=1)
        assert len(results) == 1
        assert results[0]["chunk_id"] == "doc1_chunk_0"

        with service._connect() as conn:
            row = conn.execute(
                """
                SELECT embedding_blob, embedding_dim
                FROM rag_vec_chunks
                WHERE chunk_id = 'doc1_chunk_0'
                """
            ).fetchone()
        assert row["embedding_blob"] is not None
        assert int(row["embedding_dim"]) == 2
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_sqlite_vec_search_uses_extension_distance(monkeypatch):
    tmp_path = Path("data") / "tmp_test_runtime" / f"sqlite_vec_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)

    def _blob_to_vector(blob):
        if not blob:
            return []
        count = len(blob) // 4
        return list(struct.unpack(f"<{count}f", blob))

    def _cosine_distance(blob_a, blob_b):
        a = _blob_to_vector(blob_a)
        b = _blob_to_vector(blob_b)
        if not a or not b or len(a) != len(b):
            return 1.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a <= 0 or norm_b <= 0:
            return 1.0
        cosine = dot / (norm_a * norm_b)
        return 1.0 - cosine

    fake_module = types.SimpleNamespace()

    def _load(conn):
        conn.create_function("vec_distance_cosine", 2, _cosine_distance)

    fake_module.load = _load
    monkeypatch.setitem(sys.modules, "sqlite_vec", fake_module)

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

        results = service.search(kb_id="kb1", query_embedding=[1.0, 0.0], top_k=2)
        assert len(results) == 2
        assert results[0]["chunk_id"] == "doc1_chunk_0"
        assert float(results[0]["score"]) > float(results[1]["score"])
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
