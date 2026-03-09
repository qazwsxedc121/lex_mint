"""Compatibility re-export for chat application factories."""

from src.application.chat.factory import (
    build_chat_application_service,
    build_compare_flow_service,
    build_single_chat_flow_service,
)

__all__ = [
    "build_chat_application_service",
    "build_compare_flow_service",
    "build_single_chat_flow_service",
]
