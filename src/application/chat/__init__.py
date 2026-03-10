"""Chat application layer public exports."""

from .service import ChatApplicationDeps, ChatApplicationService


def build_default_chat_application_service(*args, **kwargs):
    from .bootstrap import build_default_chat_application_service as _builder

    return _builder(*args, **kwargs)


__all__ = [
    "build_default_chat_application_service",
    "ChatApplicationDeps",
    "ChatApplicationService",
]
