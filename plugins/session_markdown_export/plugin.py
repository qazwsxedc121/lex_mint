"""Session markdown export plugin example."""

from __future__ import annotations

import re
from typing import Any


def _format_thinking_block(content: str) -> str:
    think_pattern = re.compile(r"<think>(.*?)</think>", re.DOTALL)
    match = think_pattern.search(content)
    if not match:
        return content

    thinking_text = match.group(1).strip()
    main_content = think_pattern.sub("", content).strip()
    thinking_html = f"<details>\n<summary>Thinking</summary>\n\n{thinking_text}\n\n</details>\n"
    return f"{thinking_html}\n{main_content}"


def _build_export_markdown(session: dict[str, Any]) -> str:
    title = session.get("title", "Untitled")
    messages = session.get("state", {}).get("messages", [])

    lines = [f"# {title}\n"]
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")

        if role == "user":
            lines.append("---")
            lines.append("## User\n")
            lines.append(content)
            lines.append("")
        elif role == "assistant":
            lines.append("---")
            lines.append("## Assistant\n")
            lines.append(_format_thinking_block(content))
            lines.append("")
    return "\n".join(lines)


def register_session_export():
    return _build_export_markdown
