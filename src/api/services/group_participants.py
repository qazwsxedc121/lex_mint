"""Compatibility re-export for group participant parsing."""

from src.application.chat.group_participants import (
    ASSISTANT_PREFIX,
    MODEL_PREFIX,
    GroupParticipant,
    parse_group_participant,
)

__all__ = [
    "ASSISTANT_PREFIX",
    "MODEL_PREFIX",
    "GroupParticipant",
    "parse_group_participant",
]
