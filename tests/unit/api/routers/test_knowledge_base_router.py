"""Unit tests for knowledge base upload persistence helpers."""

import asyncio
import sys
import shutil
import uuid
from pathlib import Path
from types import SimpleNamespace

import pytest

from fastapi import HTTPException

from src.api.routers import knowledge_base as kb_router
from src.api.routers.knowledge_base import _persist_upload_file
from src.domain.models.knowledge_base import KnowledgeBase, KnowledgeBaseDocument
from src.infrastructure.config import rag_config_service as rag_config_module


class _FakeUploadFile:
    def __init__(self, filename: str, chunks):
        self.filename = filename
        self._chunks = list(chunks)
        self.closed = False

    async def read(self, size=-1):
        _ = size
        if not self._chunks:
            return b""
        return self._chunks.pop(0)

    async def close(self):
        self.closed = True


def test_persist_upload_file_streams_to_disk():
    base_dir = Path("data") / "tmp_test_runtime" / f"kb_upload_{uuid.uuid4().hex[:8]}"
    storage_path = base_dir / "doc.bin"
    base_dir.mkdir(parents=True, exist_ok=True)
    upload = _FakeUploadFile("doc.bin", [b"abc", b"de"])

    try:
        size = asyncio.run(
            _persist_upload_file(
                upload,
                storage_path,
                chunk_size_bytes=2,
                max_size_bytes=10,
            )
        )
        assert size == 5
        assert storage_path.read_bytes() == b"abcde"
        assert upload.closed is True
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


def test_persist_upload_file_rejects_oversized_input():
    base_dir = Path("data") / "tmp_test_runtime" / f"kb_upload_{uuid.uuid4().hex[:8]}"
    storage_path = base_dir / "doc.bin"
    base_dir.mkdir(parents=True, exist_ok=True)
    upload = _FakeUploadFile("doc.bin", [b"abcdef", b"ghijkl"])

    try:
        with pytest.raises(HTTPException) as exc:
            asyncio.run(
                _persist_upload_file(
                    upload,
                    storage_path,
                    chunk_size_bytes=4,
                    max_size_bytes=10,
                )
            )
        assert exc.value.status_code == 413
        assert not storage_path.exists()
        assert upload.closed is True
    finally:
        shutil.rmtree(base_dir, ignore_errors=True)


class _FakeKnowledgeBaseService:
    def __init__(self, storage_dir: Path):
        self.storage_dir = storage_dir
        self.kb = KnowledgeBase(id="kb1", name="KB 1")
        self.doc = KnowledgeBaseDocument(
            id="doc1",
            kb_id="kb1",
            filename="doc.md",
            file_type=".md",
            file_size=12,
            status="ready",
        )
        self.fail_with: Exception | None = None
        self.added_doc: KnowledgeBaseDocument | None = None
        self.updated_status: tuple | None = None

    async def get_knowledge_bases(self):
        if self.fail_with:
            raise self.fail_with
        return [self.kb]

    async def add_knowledge_base(self, kb: KnowledgeBase):
        if self.fail_with:
            raise self.fail_with
        self.kb = kb

    async def get_knowledge_base(self, kb_id: str):
        return None if kb_id == "missing" else self.kb

    async def update_knowledge_base(self, kb_id: str, updates: dict):
        if self.fail_with:
            raise self.fail_with
        if kb_id == "missing":
            raise ValueError("missing kb")
        self.kb = self.kb.model_copy(update=updates)
        return self.kb

    async def delete_knowledge_base(self, kb_id: str):
        if self.fail_with:
            raise self.fail_with
        if kb_id == "missing":
            raise ValueError("missing kb")

    async def get_documents(self, kb_id: str):
        assert kb_id == "kb1"
        return [self.doc]

    def get_document_storage_path(self, kb_id: str, doc_id: str, filename: str) -> Path:
        doc_dir = self.storage_dir / kb_id / "documents"
        doc_dir.mkdir(parents=True, exist_ok=True)
        return doc_dir / f"{doc_id}_{filename}"

    async def add_document(self, doc: KnowledgeBaseDocument):
        self.added_doc = doc

    async def get_document(self, kb_id: str, doc_id: str):
        return None if doc_id == "missing" else self.doc

    async def delete_document(self, kb_id: str, doc_id: str):
        if self.fail_with:
            raise self.fail_with
        if doc_id == "missing":
            raise ValueError("missing doc")

    async def update_document_status(self, kb_id: str, doc_id: str, status: str, error_message=None):
        self.updated_status = (kb_id, doc_id, status, error_message)


@pytest.mark.asyncio
async def test_knowledge_base_crud_and_document_routes(monkeypatch, tmp_path):
    service = _FakeKnowledgeBaseService(tmp_path)

    listed = await kb_router.list_knowledge_bases(service=service)  # type: ignore[arg-type]
    assert listed[0].id == "kb1"

    created = await kb_router.create_knowledge_base(
        kb_router.KnowledgeBaseCreate(id="kb2", name="KB 2"),
        service=service,  # type: ignore[arg-type]
    )
    assert created.id == "kb2"

    got = await kb_router.get_knowledge_base("kb1", service=service)  # type: ignore[arg-type]
    assert got.id == "kb2"

    updated = await kb_router.update_knowledge_base(
        "kb1",
        kb_router.KnowledgeBaseUpdate(name="Updated KB"),
        service=service,  # type: ignore[arg-type]
    )
    assert updated.name == "Updated KB"

    deleted = await kb_router.delete_knowledge_base("kb1", service=service)  # type: ignore[arg-type]
    assert "deleted successfully" in deleted["message"]

    documents = await kb_router.list_documents("kb1", service=service)  # type: ignore[arg-type]
    assert documents[0].id == "doc1"

    monkeypatch.setattr(kb_router.uuid, "uuid4", lambda: "docuuid12")
    monkeypatch.setattr(kb_router, "_persist_upload_file", lambda *args, **kwargs: asyncio.sleep(0, result=12))
    queued: list[object] = []

    def _capture_task(coro):
        queued.append(coro)
        coro.close()
        return SimpleNamespace()

    monkeypatch.setattr(kb_router.asyncio, "create_task", _capture_task)

    uploaded = await kb_router.upload_document(
        "kb1",
        file=_FakeUploadFile("doc.md", [b"abc"]),  # type: ignore[arg-type]
        service=service,  # type: ignore[arg-type]
    )
    assert uploaded.status == "pending"
    assert service.added_doc is not None
    assert queued

    deleted_doc = await kb_router.delete_document("kb1", "doc1", service=service)  # type: ignore[arg-type]
    assert "deleted successfully" in deleted_doc["message"]

    doc_path = service.get_document_storage_path("kb1", "doc1", "doc.md")
    doc_path.write_text("content", encoding="utf-8")
    reprocessed = await kb_router.reprocess_document("kb1", "doc1", service=service)  # type: ignore[arg-type]
    assert "queued for reprocessing" in reprocessed["message"]
    assert service.updated_status == ("kb1", "doc1", "pending", None)


@pytest.mark.asyncio
async def test_knowledge_base_router_error_mapping_and_chunk_listing(monkeypatch, tmp_path):
    service = _FakeKnowledgeBaseService(tmp_path)

    with pytest.raises(HTTPException) as exc_info:
        await kb_router.get_knowledge_base("missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await kb_router.update_knowledge_base(
            "kb1",
            kb_router.KnowledgeBaseUpdate(),
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    service.fail_with = RuntimeError("boom")
    with pytest.raises(HTTPException) as exc_info:
        await kb_router.list_knowledge_bases(service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 500

    service.fail_with = None
    with pytest.raises(HTTPException) as exc_info:
        await kb_router.upload_document(
            "missing",
            file=_FakeUploadFile("doc.md", [b"abc"]),  # type: ignore[arg-type]
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await kb_router.upload_document(
            "kb1",
            file=_FakeUploadFile("doc.exe", [b"abc"]),  # type: ignore[arg-type]
            service=service,  # type: ignore[arg-type]
        )
    assert exc_info.value.status_code == 400

    with pytest.raises(HTTPException) as exc_info:
        await kb_router.delete_document("kb1", "missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    with pytest.raises(HTTPException) as exc_info:
        await kb_router.reprocess_document("kb1", "missing", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    empty_doc_dir = tmp_path / "kb1" / "documents"
    empty_doc_dir.mkdir(parents=True, exist_ok=True)
    with pytest.raises(HTTPException) as exc_info:
        await kb_router.reprocess_document("kb1", "doc1", service=service)  # type: ignore[arg-type]
    assert exc_info.value.status_code == 404

    monkeypatch.setattr(
        rag_config_module,
        "RagConfigService",
        lambda: SimpleNamespace(config=SimpleNamespace(storage=SimpleNamespace(vector_store_backend="sqlite_vec", persist_directory="."))),
    )
    monkeypatch.setitem(
        sys.modules,
        "src.infrastructure.retrieval.sqlite_vec_service",
        SimpleNamespace(
            SqliteVecService=lambda: SimpleNamespace(
                list_chunks=lambda **kwargs: [
                    {"id": "c1", "kb_id": "kb1", "doc_id": "doc1", "filename": "doc.md", "chunk_index": 1, "content": "chunk"}
                ]
            )
        ),
    )
    chunks = await kb_router.list_chunks("kb1", doc_id=None, limit=200, service=service)  # type: ignore[arg-type]
    assert chunks[0].content == "chunk"

    monkeypatch.setitem(
        sys.modules,
        "chromadb",
        SimpleNamespace(
            PersistentClient=lambda path: SimpleNamespace(
                get_collection=lambda _name: SimpleNamespace(
                    get=lambda **kwargs: {
                        "documents": ["doc content"],
                        "metadatas": [{"doc_id": "doc1", "filename": "doc.md", "chunk_index": "2"}],
                        "ids": ["chunk-2"],
                    }
                )
            )
        ),
    )
    monkeypatch.setattr(
        rag_config_module,
        "RagConfigService",
        lambda: SimpleNamespace(config=SimpleNamespace(storage=SimpleNamespace(vector_store_backend="chroma", persist_directory=str(tmp_path)))),
    )
    chunks = await kb_router.list_chunks("kb1", doc_id="doc1", limit=200, service=service)  # type: ignore[arg-type]
    assert chunks[0].chunk_index == 2


@pytest.mark.asyncio
async def test_process_document_async_updates_status_on_failure(monkeypatch):
    class _Processor:
        async def process_document(self, *args, **kwargs):
            raise RuntimeError("process failed")

    status_updates = []

    class _StatusService:
        async def update_document_status(self, *args, **kwargs):
            status_updates.append((args, kwargs))

    monkeypatch.setitem(
        sys.modules,
        "src.infrastructure.knowledge.document_processing_service",
        SimpleNamespace(DocumentProcessingService=lambda: _Processor()),
    )
    monkeypatch.setattr(kb_router, "KnowledgeBaseService", lambda: _StatusService(), raising=False)

    await kb_router._process_document_async("kb1", "doc1", "doc.md", ".md", "/tmp/doc.md")
    assert status_updates[0][0][:3] == ("kb1", "doc1", "error")
