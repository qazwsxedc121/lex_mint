"""Tests for file upload management service."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from src.infrastructure.files.file_service import FileService


class _FakeUploadFile:
    def __init__(self, filename: str, content: bytes, content_type: str):
        self.filename = filename
        self.content_type = content_type
        self._buffer = BytesIO(content)

    async def read(self) -> bytes:
        return self._buffer.read()

    async def seek(self, position: int) -> None:
        self._buffer.seek(position)


@pytest.mark.asyncio
async def test_file_service_validates_and_persists_files(tmp_path: Path):
    service = FileService(tmp_path, max_size_mb=1)

    text_file = _FakeUploadFile("notes.txt", b"hello world", "application/octet-stream")
    await service.validate_file(text_file)

    image_file = _FakeUploadFile("photo.png", b"\x89PNG\r\n", "image/png")
    metadata = await service.save_temp_file("session-1", image_file)
    assert metadata["mime_type"] == "image/png"

    permanent_path = await service.move_to_permanent(
        session_id="session-1",
        message_index=2,
        temp_path=metadata["temp_path"],
        filename=metadata["filename"],
    )
    assert permanent_path.exists()
    assert service.get_file_path("session-1", 2, "photo.png") == permanent_path


@pytest.mark.asyncio
async def test_file_service_reads_content_and_rejects_invalid_files(tmp_path: Path):
    service = FileService(tmp_path, max_size_mb=1)

    binary_file = _FakeUploadFile("data.bin", b"\xff\xfe\xfd\xfc", "application/octet-stream")
    with pytest.raises(ValueError):
        await service.validate_file(binary_file)

    huge_file = _FakeUploadFile("big.txt", b"a" * (service.max_size_bytes + 1), "text/plain")
    with pytest.raises(ValueError):
        await service.validate_file(huge_file)

    text_path = tmp_path / "latin1.txt"
    text_path.write_bytes("hello".encode("utf-8"))
    assert await service.get_file_content(text_path) == "hello"

    encoded = await service.get_file_as_base64(text_path)
    assert encoded == "aGVsbG8="
