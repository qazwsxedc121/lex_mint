"""Unit tests for document processing vector store writes."""

import asyncio
import sys
import types
import uuid
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.api.services.document_processing_service import DocumentProcessingService


class _FakeCollection:
    def __init__(self):
        self.docs = {}
        self.delete_calls = []

    def delete(self, ids=None, where=None):
        self.delete_calls.append({"ids": ids, "where": where})
        if ids:
            for chunk_id in ids:
                self.docs.pop(chunk_id, None)
            return
        if where and "doc_id" in where:
            target_doc_id = where["doc_id"]
            stale = [
                chunk_id
                for chunk_id, payload in self.docs.items()
                if (payload.get("metadata") or {}).get("doc_id") == target_doc_id
            ]
            for chunk_id in stale:
                self.docs.pop(chunk_id, None)

    def get(self, where=None, include=None):
        _ = include
        if where and "doc_id" in where:
            target_doc_id = where["doc_id"]
            ids = [
                chunk_id
                for chunk_id, payload in self.docs.items()
                if (payload.get("metadata") or {}).get("doc_id") == target_doc_id
            ]
        else:
            ids = list(self.docs.keys())
        return {"ids": ids}


class _FakeChroma:
    collections = {}
    call_count = 0
    fail_on_call = None
    fail_calls = set()

    def __init__(self, collection_name, embedding_function, persist_directory, collection_metadata):
        _ = embedding_function, persist_directory, collection_metadata
        self._collection = self.collections.setdefault(collection_name, _FakeCollection())

    def add_texts(self, texts, ids, metadatas):
        _FakeChroma.call_count += 1
        if _FakeChroma.call_count in _FakeChroma.fail_calls:
            raise RuntimeError("forced batch failure")
        if _FakeChroma.fail_on_call == _FakeChroma.call_count:
            raise RuntimeError("forced batch failure")
        for text, chunk_id, metadata in zip(texts, ids, metadatas):
            self._collection.docs[chunk_id] = {"text": text, "metadata": metadata}


def _install_fake_vector_modules(monkeypatch):
    fake_langchain_chroma = types.ModuleType("langchain_chroma")
    fake_langchain_chroma.Chroma = _FakeChroma
    monkeypatch.setitem(sys.modules, "langchain_chroma", fake_langchain_chroma)

    fake_chromadb_errors = types.ModuleType("chromadb.errors")

    class _InvalidArgumentError(Exception):
        pass

    fake_chromadb_errors.InvalidArgumentError = _InvalidArgumentError
    monkeypatch.setitem(sys.modules, "chromadb.errors", fake_chromadb_errors)


def _build_service(tmp_path: Path, *, batch_max_retries: int = 1) -> DocumentProcessingService:
    service = DocumentProcessingService.__new__(DocumentProcessingService)
    service.rag_config_service = SimpleNamespace(
        config=SimpleNamespace(
            storage=SimpleNamespace(persist_directory=str(tmp_path / "chromadb")),
            embedding=SimpleNamespace(
                batch_size=2,
                batch_delay_seconds=0.0,
                batch_max_retries=batch_max_retries,
            ),
        )
    )
    service.embedding_service = None
    service.bm25_service = SimpleNamespace(upsert_document_chunks=lambda **kwargs: None)
    return service


def test_store_in_chromadb_rolls_back_partial_writes(monkeypatch):
    tmp_path = Path("data") / "tmp_test_runtime" / f"doc_proc_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    _install_fake_vector_modules(monkeypatch)
    _FakeChroma.collections = {}
    _FakeChroma.call_count = 0
    _FakeChroma.fail_on_call = None
    _FakeChroma.fail_calls = {2, 3}

    try:
        service = _build_service(tmp_path, batch_max_retries=1)
        collection = _FakeChroma.collections.setdefault("kb_kb1", _FakeCollection())
        collection.docs["old_chunk"] = {
            "text": "existing",
            "metadata": {"doc_id": "doc1", "chunk_index": 0},
        }

        with pytest.raises(RuntimeError, match="forced batch failure"):
            asyncio.run(
                service._store_in_chromadb(
                    kb_id="kb1",
                    doc_id="doc1",
                    filename="doc.md",
                    file_type=".md",
                    chunks=["a", "b", "c"],
                    embedding_fn=None,
                )
            )
        remaining_ids = set(collection.docs.keys())
        assert remaining_ids == {"old_chunk"}
        assert any(call["ids"] for call in collection.delete_calls)
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_store_in_chromadb_cleans_stale_doc_generation(monkeypatch):
    tmp_path = Path("data") / "tmp_test_runtime" / f"doc_proc_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    _install_fake_vector_modules(monkeypatch)
    _FakeChroma.collections = {}
    _FakeChroma.call_count = 0
    _FakeChroma.fail_on_call = None
    _FakeChroma.fail_calls = set()

    try:
        service = _build_service(tmp_path)
        collection = _FakeChroma.collections.setdefault("kb_kb1", _FakeCollection())
        collection.docs["legacy_doc1_chunk"] = {
            "text": "legacy",
            "metadata": {"doc_id": "doc1", "chunk_index": 0},
        }
        collection.docs["other_doc_chunk"] = {
            "text": "other",
            "metadata": {"doc_id": "doc2", "chunk_index": 0},
        }

        asyncio.run(
            service._store_in_chromadb(
                kb_id="kb1",
                doc_id="doc1",
                filename="doc.md",
                file_type=".md",
                chunks=["new-a", "new-b"],
                embedding_fn=None,
            )
        )
        doc1_ids = [
            chunk_id
            for chunk_id, payload in collection.docs.items()
            if payload["metadata"].get("doc_id") == "doc1"
        ]
        assert len(doc1_ids) == 2
        assert "legacy_doc1_chunk" not in collection.docs
        assert "other_doc_chunk" in collection.docs
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


class _FakeSqliteVecService:
    def __init__(self, *, had_existing=False):
        self.upsert_calls = []
        self.delete_by_ids_calls = []
        self.delete_stale_calls = []
        self.had_existing = had_existing

    def upsert_chunks(self, **kwargs):
        self.upsert_calls.append(kwargs)
        return self.had_existing

    def delete_chunks_by_ids(self, **kwargs):
        self.delete_by_ids_calls.append(kwargs)

    def delete_stale_document_chunks(self, **kwargs):
        self.delete_stale_calls.append(kwargs)
        return 1


class _FakeEmbeddingFn:
    def embed_documents(self, texts):
        vectors = []
        for text in texts:
            size = max(1, len(text))
            vectors.append([float(size), 1.0])
        return vectors


def test_store_in_sqlite_vec_rolls_back_on_bm25_failure(monkeypatch):
    tmp_path = Path("data") / "tmp_test_runtime" / f"doc_proc_sqlite_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)

    try:
        service = _build_service(tmp_path, batch_max_retries=1)
        fake_sqlite = _FakeSqliteVecService()
        monkeypatch.setattr(
            "src.api.services.sqlite_vec_service.SqliteVecService",
            lambda: fake_sqlite,
        )

        def _raise_bm25(**kwargs):
            _ = kwargs
            raise RuntimeError("bm25 write failed")

        service.bm25_service = SimpleNamespace(upsert_document_chunks=_raise_bm25)

        with pytest.raises(RuntimeError, match="bm25 write failed"):
            asyncio.run(
                service._store_in_sqlite_vec(
                    kb_id="kb1",
                    doc_id="doc1",
                    filename="doc.md",
                    file_type=".md",
                    chunks=["a", "bb", "ccc"],
                    embedding_fn=_FakeEmbeddingFn(),
                )
            )

        assert len(fake_sqlite.upsert_calls) == 1
        assert len(fake_sqlite.delete_by_ids_calls) == 1
        assert len(fake_sqlite.delete_stale_calls) == 0
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_store_in_sqlite_vec_skips_stale_cleanup_for_new_doc(monkeypatch):
    tmp_path = Path("data") / "tmp_test_runtime" / f"doc_proc_sqlite_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)

    try:
        service = _build_service(tmp_path, batch_max_retries=1)
        fake_sqlite = _FakeSqliteVecService(had_existing=False)
        monkeypatch.setattr(
            "src.api.services.sqlite_vec_service.SqliteVecService",
            lambda: fake_sqlite,
        )
        service.bm25_service = SimpleNamespace(upsert_document_chunks=lambda **kwargs: None)

        asyncio.run(
            service._store_in_sqlite_vec(
                kb_id="kb1",
                doc_id="doc1",
                filename="doc.md",
                file_type=".md",
                chunks=["a", "bb"],
                embedding_fn=_FakeEmbeddingFn(),
            )
        )

        assert len(fake_sqlite.upsert_calls) == 1
        assert len(fake_sqlite.delete_stale_calls) == 0
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)


def test_store_in_sqlite_vec_runs_stale_cleanup_for_existing_doc(monkeypatch):
    tmp_path = Path("data") / "tmp_test_runtime" / f"doc_proc_sqlite_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)

    try:
        service = _build_service(tmp_path, batch_max_retries=1)
        fake_sqlite = _FakeSqliteVecService(had_existing=True)
        monkeypatch.setattr(
            "src.api.services.sqlite_vec_service.SqliteVecService",
            lambda: fake_sqlite,
        )
        service.bm25_service = SimpleNamespace(upsert_document_chunks=lambda **kwargs: None)

        asyncio.run(
            service._store_in_sqlite_vec(
                kb_id="kb1",
                doc_id="doc1",
                filename="doc.md",
                file_type=".md",
                chunks=["a", "bb"],
                embedding_fn=_FakeEmbeddingFn(),
            )
        )

        assert len(fake_sqlite.upsert_calls) == 1
        assert len(fake_sqlite.delete_stale_calls) == 1
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
