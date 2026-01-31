"""File upload and management service."""

import os
import mimetypes
import shutil
import base64
from pathlib import Path
from typing import Dict, Optional
from fastapi import UploadFile
import aiofiles
import logging

logger = logging.getLogger(__name__)


class FileService:
    """Service for handling file uploads and storage."""

    ALLOWED_MIME_PREFIXES = [
        # Text files
        'text/',
        'application/json',
        'application/xml',
        'application/javascript',
        'application/x-yaml',
        # Image files
        'image/jpeg',
        'image/png',
        'image/gif',
        'image/webp',
    ]

    def __init__(self, attachments_dir: Path, max_size_mb: int = 10):
        """Initialize file service.

        Args:
            attachments_dir: Base directory for storing attachments
            max_size_mb: Maximum file size in megabytes
        """
        self.attachments_dir = Path(attachments_dir)
        self.max_size_mb = max_size_mb
        self.max_size_bytes = max_size_mb * 1024 * 1024

    def is_image_file(self, mime_type: str) -> bool:
        """Check if file is an image.

        Args:
            mime_type: MIME type to check

        Returns:
            True if image, False otherwise
        """
        return mime_type.startswith('image/')

    async def validate_file(self, file: UploadFile) -> None:
        """Validate file is text or image and under size limit.

        Args:
            file: Uploaded file to validate

        Raises:
            ValueError: If file is invalid (too large or not allowed type)
        """
        # Read file content for validation
        content = await file.read()
        await file.seek(0)  # Reset for later reading

        # Check size
        if len(content) > self.max_size_bytes:
            raise ValueError(f"File exceeds {self.max_size_mb}MB limit")

        # Detect MIME type
        mime_type = file.content_type or 'application/octet-stream'

        # Fallback to extension-based detection
        if mime_type == 'application/octet-stream' and file.filename:
            guessed = mimetypes.guess_type(file.filename)[0]
            if guessed:
                mime_type = guessed

        # Check if allowed MIME type
        allowed = any(
            mime_type.startswith(prefix)
            for prefix in self.ALLOWED_MIME_PREFIXES
        )

        if not allowed:
            # For non-image files, try to decode as text
            if not self.is_image_file(mime_type):
                try:
                    content[:1024].decode('utf-8')
                    # If decodable, treat as text
                    logger.info(f"File {file.filename} validated as text (MIME: {mime_type})")
                    return
                except UnicodeDecodeError:
                    raise ValueError(
                        f"File type '{mime_type}' not supported. "
                        "Only text files and images are allowed."
                    )
            else:
                raise ValueError(
                    f"File type '{mime_type}' not supported. "
                    "Only text files and images (JPEG, PNG, GIF, WebP) are allowed."
                )

        logger.info(f"File {file.filename} validated successfully (MIME: {mime_type}, size: {len(content)} bytes)")

    async def save_temp_file(
        self,
        session_id: str,
        file: UploadFile
    ) -> Dict[str, any]:
        """Save uploaded file to temporary location.

        Args:
            session_id: Session identifier
            file: Uploaded file

        Returns:
            Dict containing file metadata:
                - filename: Original filename
                - size: File size in bytes
                - mime_type: Detected MIME type
                - temp_path: Path to temporary file (relative to attachments_dir)
        """
        # Create temp directory
        temp_dir = self.attachments_dir / session_id / "temp"
        temp_dir.mkdir(parents=True, exist_ok=True)

        # Read file content
        content = await file.read()

        # Detect MIME type
        mime_type = file.content_type or 'application/octet-stream'
        if mime_type == 'application/octet-stream' and file.filename:
            guessed = mimetypes.guess_type(file.filename)[0]
            if guessed:
                mime_type = guessed

        # Save to temp location
        temp_path = temp_dir / file.filename
        async with aiofiles.open(temp_path, 'wb') as f:
            await f.write(content)

        logger.info(f"Saved temp file: {temp_path}")

        return {
            "filename": file.filename,
            "size": len(content),
            "mime_type": mime_type,
            "temp_path": str(temp_path.relative_to(self.attachments_dir)),
        }

    async def move_to_permanent(
        self,
        session_id: str,
        message_index: int,
        temp_path: str,
        filename: str
    ) -> Path:
        """Move file from temp to permanent location.

        Args:
            session_id: Session identifier
            message_index: Index of the message this file belongs to
            temp_path: Relative path to temp file
            filename: Original filename

        Returns:
            Path to permanent file location
        """
        # Construct paths
        temp_file = self.attachments_dir / temp_path
        permanent_dir = self.attachments_dir / session_id / str(message_index)
        permanent_dir.mkdir(parents=True, exist_ok=True)
        permanent_file = permanent_dir / filename

        # Move file
        shutil.move(str(temp_file), str(permanent_file))

        logger.info(f"Moved file to permanent location: {permanent_file}")

        return permanent_file

    async def get_file_content(self, filepath: Path) -> str:
        """Read text file content with encoding detection.

        Args:
            filepath: Path to file

        Returns:
            File content as string
        """
        # Try UTF-8 first
        try:
            async with aiofiles.open(filepath, 'r', encoding='utf-8') as f:
                return await f.read()
        except UnicodeDecodeError:
            # Fallback: try with chardet or just read as binary and decode with errors='replace'
            async with aiofiles.open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return await f.read()

    async def get_file_as_base64(self, filepath: Path) -> str:
        """Read file and return Base64 encoded content.

        Args:
            filepath: Path to file

        Returns:
            Base64 encoded file content
        """
        async with aiofiles.open(filepath, 'rb') as f:
            content = await f.read()
            return base64.b64encode(content).decode('utf-8')

    def get_file_path(
        self,
        session_id: str,
        message_index: int,
        filename: str
    ) -> Optional[Path]:
        """Get path to a file attachment.

        Args:
            session_id: Session identifier
            message_index: Message index
            filename: Filename

        Returns:
            Path to file if it exists, None otherwise
        """
        filepath = self.attachments_dir / session_id / str(message_index) / filename
        if filepath.exists():
            return filepath
        return None
