"""Unit tests for knowledge base upload persistence helpers."""

import asyncio
import shutil
import uuid
from pathlib import Path

import pytest

from fastapi import HTTPException

from src.api.routers.knowledge_base import _persist_upload_file


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
