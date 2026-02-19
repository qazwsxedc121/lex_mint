"""Helpers for mixed group chat participants (assistant/model)."""

from dataclasses import dataclass
from typing import Literal


ASSISTANT_PREFIX = "assistant::"
MODEL_PREFIX = "model::"


@dataclass(frozen=True)
class GroupParticipant:
    """Normalized group participant descriptor."""
    raw: str
    kind: Literal["assistant", "model"]
    value: str

    @property
    def token(self) -> str:
        """Stable persisted token value."""
        if self.kind == "model":
            return f"{MODEL_PREFIX}{self.value}"
        return self.value


def parse_group_participant(raw_value: str) -> GroupParticipant:
    """Parse one participant token from API/session payloads."""
    cleaned = (raw_value or "").strip()
    if not cleaned:
        raise ValueError("Group participant token cannot be empty")

    if cleaned.startswith(MODEL_PREFIX):
        model_id = cleaned[len(MODEL_PREFIX):].strip()
        if not model_id:
            raise ValueError("Model participant token is missing model id")
        return GroupParticipant(raw=cleaned, kind="model", value=model_id)

    if cleaned.startswith(ASSISTANT_PREFIX):
        assistant_id = cleaned[len(ASSISTANT_PREFIX):].strip()
        if not assistant_id:
            raise ValueError("Assistant participant token is missing assistant id")
        return GroupParticipant(raw=cleaned, kind="assistant", value=assistant_id)

    # Backward compatibility: plain assistant id.
    return GroupParticipant(raw=cleaned, kind="assistant", value=cleaned)
