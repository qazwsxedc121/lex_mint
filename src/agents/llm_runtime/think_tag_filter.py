"""Utilities to hide <think>...</think> blocks from streamed text."""

from __future__ import annotations

import re


_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.IGNORECASE | re.DOTALL)


def strip_think_blocks(text: str) -> str:
    """Remove complete <think>...</think> blocks from text."""
    if not text:
        return ""
    return _THINK_BLOCK_RE.sub("", text)


class ThinkTagStreamFilter:
    """Incremental filter for streamed text containing <think> tags."""

    _open_tag = "<think>"
    _close_tag = "</think>"

    def __init__(self):
        self._in_think = False
        self._pending = ""

    def feed(self, chunk: str) -> str:
        if not chunk:
            return ""

        self._pending += chunk
        out_parts: list[str] = []

        while self._pending:
            lower_pending = self._pending.lower()

            if self._in_think:
                close_idx = lower_pending.find(self._close_tag)
                if close_idx < 0:
                    keep = len(self._close_tag) - 1
                    if len(self._pending) > keep:
                        self._pending = self._pending[-keep:]
                    break
                self._pending = self._pending[close_idx + len(self._close_tag):]
                self._in_think = False
                continue

            open_idx = lower_pending.find(self._open_tag)
            if open_idx < 0:
                keep = len(self._open_tag) - 1
                if len(self._pending) > keep:
                    out_parts.append(self._pending[:-keep])
                    self._pending = self._pending[-keep:]
                break

            if open_idx > 0:
                out_parts.append(self._pending[:open_idx])
            self._pending = self._pending[open_idx + len(self._open_tag):]
            self._in_think = True

        return "".join(out_parts)

    def flush(self) -> str:
        if self._in_think:
            self._pending = ""
            return ""

        leftover = self._pending
        self._pending = ""

        lower_leftover = leftover.lower()
        if self._open_tag.startswith(lower_leftover):
            return ""
        return leftover
