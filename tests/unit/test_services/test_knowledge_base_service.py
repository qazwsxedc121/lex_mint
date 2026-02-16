"""Unit tests for knowledge base deletion behavior."""

import asyncio
import sys
import types
import uuid
import shutil
from pathlib import Path
from types import SimpleNamespace

from src.api.models.knowledge_base import (
    KnowledgeBase,
    KnowledgeBaseDocument,
    KnowledgeBasesConfig,
)
from src.api.services.knowledge_base_service import KnowledgeBaseService


class _FakeCollection:
    def __init__(self):
        self.delete_calls = []

    def delete(self, ids=None, where=None):
        self.delete_calls.append({"ids": ids, "where": where})


class _FakeClient:
    def __init__(self, collection):
        self._collection = collection

    def get_collection(self, name):
        _ = name
        return self._collection


def test_delete_document_uses_doc_id_where_filter(monkeypatch):
    tmp_path = Path("data") / "tmp_test_runtime" / f"kb_svc_{uuid.uuid4().hex[:8]}"
    tmp_path.mkdir(parents=True, exist_ok=True)
    service = KnowledgeBaseService.__new__(KnowledgeBaseService)
    service.storage_dir = tmp_path

    config = KnowledgeBasesConfig(
        knowledge_bases=[KnowledgeBase(id="kb1", name="KB 1", document_count=1)],
        documents=[
            KnowledgeBaseDocument(
                id="doc1",
                kb_id="kb1",
                filename="doc.md",
                file_type=".md",
                file_size=10,
                status="ready",
                chunk_count=99,
            )
        ],
    )

    async def _load_config():
        return config

    saved = {}

    async def _save_config(new_config):
        saved["config"] = new_config

    service.load_config = _load_config
    service.save_config = _save_config

    try:
        doc_dir = tmp_path / "kb1" / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        (doc_dir / "doc1_doc.md").write_text("content", encoding="utf-8")

        class _FakeRagConfigService:
            def __init__(self):
                self.config = SimpleNamespace(
                    storage=SimpleNamespace(persist_directory=str(tmp_path / "chromadb"))
                )

        monkeypatch.setattr(
            "src.api.services.rag_config_service.RagConfigService",
            _FakeRagConfigService,
        )
        monkeypatch.setattr(
            "src.api.services.bm25_service.Bm25Service",
            lambda: SimpleNamespace(delete_document_chunks=lambda **kwargs: None),
        )

        fake_collection = _FakeCollection()
        fake_chromadb = types.ModuleType("chromadb")
        fake_chromadb.PersistentClient = lambda path: _FakeClient(fake_collection)
        monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)

        asyncio.run(service.delete_document("kb1", "doc1"))

        assert fake_collection.delete_calls
        assert fake_collection.delete_calls[0]["where"] == {"doc_id": "doc1"}
        assert fake_collection.delete_calls[0]["ids"] is None
        assert saved["config"].documents == []
        assert saved["config"].knowledge_bases[0].document_count == 0
    finally:
        shutil.rmtree(tmp_path, ignore_errors=True)
