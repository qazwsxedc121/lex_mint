"""Shared user-input preparation for chat, group, and compare flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .conversation_storage import ConversationStorage
from .file_service import FileService
from .service_contracts import SourcePayload


@dataclass(frozen=True)
class PreparedUserInput:
    """Normalized result of preparing one user turn for downstream processing."""

    raw_user_message: str
    full_message_content: str
    attachment_metadata: List[SourcePayload]
    user_message_id: Optional[str]


class ChatInputService:
    """Handles attachment expansion and optional user-message persistence."""

    def __init__(self, storage: ConversationStorage, file_service: FileService):
        self.storage = storage
        self.file_service = file_service

    async def prepare_user_input(
        self,
        *,
        session_id: str,
        raw_user_message: str,
        expanded_user_message: str,
        attachments: Optional[List[SourcePayload]],
        skip_user_append: bool,
        context_type: str,
        project_id: Optional[str],
    ) -> PreparedUserInput:
        """Resolve attachment contents and optionally append the user message."""
        attachment_metadata: List[SourcePayload] = []
        full_message_content = expanded_user_message

        if attachments:
            session = await self.storage.get_session(
                session_id,
                context_type=context_type,
                project_id=project_id,
            )
            message_index = len(session["state"]["messages"])

            for idx, att in enumerate(attachments):
                filename = att["filename"]
                temp_path = att["temp_path"]
                mime_type = att["mime_type"]
                is_image = mime_type.startswith("image/")

                attachment_metadata.append(
                    {
                        "filename": filename,
                        "size": att["size"],
                        "mime_type": mime_type,
                    }
                )

                if not is_image:
                    temp_file_path = self.file_service.attachments_dir / temp_path
                    content = await self.file_service.get_file_content(temp_file_path)
                    full_message_content += (
                        f"\n\n[File {idx + 1}: {filename}]\n{content}\n[End of file]"
                    )

                await self.file_service.move_to_permanent(
                    session_id,
                    message_index,
                    temp_path,
                    filename,
                )

        user_message_id: Optional[str] = None
        if not skip_user_append:
            user_message_id = await self.storage.append_message(
                session_id,
                "user",
                full_message_content,
                attachments=attachment_metadata if attachment_metadata else None,
                context_type=context_type,
                project_id=project_id,
            )

        return PreparedUserInput(
            raw_user_message=raw_user_message,
            full_message_content=full_message_content,
            attachment_metadata=attachment_metadata,
            user_message_id=user_message_id,
        )
