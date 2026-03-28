"""Message conversion helpers for LLM runtime calls."""

from __future__ import annotations

import logging
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage

from src.infrastructure.files.file_service import FileService

logger = logging.getLogger(__name__)


async def convert_to_langchain_messages(
    messages: list[dict[str, Any]],
    session_id: str,
    file_service: FileService,
) -> list[BaseMessage]:
    """Convert stored chat messages to LangChain messages, including images."""
    langchain_messages: list[BaseMessage] = []

    for index, msg in enumerate(messages):
        role = msg.get("role")
        if role == "user":
            attachments = msg.get("attachments", [])
            has_images = any(att.get("mime_type", "").startswith("image/") for att in attachments)

            if not has_images:
                langchain_messages.append(HumanMessage(content=msg["content"]))
                continue

            content_list: list[str | dict[str, Any]] = []
            if msg["content"].strip():
                content_list.append(
                    {
                        "type": "text",
                        "text": msg["content"],
                    }
                )

            for attachment in attachments:
                if not attachment.get("mime_type", "").startswith("image/"):
                    continue
                image_path = file_service.get_file_path(
                    session_id,
                    index,
                    attachment["filename"],
                )
                if not image_path:
                    continue
                try:
                    base64_data = await file_service.get_file_as_base64(image_path)
                    content_list.append(
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": (f"data:{attachment['mime_type']};base64,{base64_data}")
                            },
                        }
                    )
                    logger.info("Added image to message: %s", attachment["filename"])
                except Exception as exc:
                    logger.error("Failed to read image %s: %s", attachment["filename"], exc)

            langchain_messages.append(HumanMessage(content=content_list))
            continue

        if role == "assistant":
            langchain_messages.append(AIMessage(content=msg["content"]))

    return langchain_messages
