"""Atomic tool: ChatGPT Custom GPT markdown export -> NormalizedRecords.

Format: files with 'You asked:' / 'ChatGPT Replied:' role markers
(as produced by ChatGPT Custom GPT conversation exports).

Example:
    You asked:
    ----------

    Prompt to Start New Chat: "We are continuing a custody..."

    ---

    ChatGPT Replied:
    ----------------

    NOTICE OF LEGAL DISCLAIMER...
    **SYNC & SUMMARY OF CASE STATUS**
Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from server.contracts.records import NormalizedRecord, RecordType
from server.tools.registry import register
from server.tools._common import records_out

_ROLE_RE = re.compile(r"^(You asked|ChatGPT Replied):$", re.IGNORECASE)
_SEPARATOR_RE = re.compile(r"^[-]{3,}$")


def _parse_custom_gpt_md(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Parse Custom GPT markdown into (title, [(role, content)])."""
    lines = text.split("\n")
    title = "untitled"
    messages: list[tuple[str, str]] = []
    current_role = None
    current_lines: list[str] = []

    for line in lines:
        stripped = line.strip()

        # Check for role marker
        m = _ROLE_RE.match(stripped)
        if m:
            # Flush previous message
            if current_role and current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    messages.append((current_role, content))
            role_raw = m.group(1).lower()
            current_role = "user" if "you" in role_raw else "assistant"
            current_lines = []
            continue

        # Skip separator lines right after role markers
        if current_role is not None and _SEPARATOR_RE.match(stripped) and not current_lines:
            continue

        # Accumulate content
        if current_role is not None:
            current_lines.append(line)

    # Flush last message
    if current_role and current_lines:
        content = "\n".join(current_lines).strip()
        if content:
            messages.append((current_role, content))

    # Extract title from first user message if it starts with "Prompt to Start New Chat:"
    if messages and messages[0][0] == "user":
        first = messages[0][1]
        m = re.match(r'(?:Prompt to Start New Chat:\s*)?["\u201c](.+?)["\u201d]', first, re.DOTALL)
        if m:
            title = m.group(1)[:120]

    return title, messages


@register(
    id="transcripts.chatgpt-custom-gpt-md",
    capability="parse.transcript",
    description="ChatGPT Custom GPT markdown export (You asked: / ChatGPT Replied:) -> normalized records",
    accept=lambda hint, size: hint.endswith((".md", ".txt")),
    provenance="new module (chat sample format detection)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    text = path.read_text(encoding="utf-8", errors="replace")

    # Quick rejection: must have role markers
    if not re.search(r"You asked:", text, re.IGNORECASE) or not re.search(r"ChatGPT Replied:", text, re.IGNORECASE):
        raise ValueError("not a ChatGPT Custom GPT markdown (no 'You asked:' / 'ChatGPT Replied:')")

    title, messages = _parse_custom_gpt_md(text)
    if not messages:
        raise ValueError("Custom GPT markdown parsed but found zero messages")

    conv_id = f"chatgpt-custom-gpt-{path.stem}"

    records: list[NormalizedRecord] = []
    for role, content in messages:
        records.append(
            NormalizedRecord(
                record_type=RecordType.message,
                source="chatgpt-custom-gpt-md",
                conversation_id=conv_id,
                role=role,
                content=content,
                attrs={"conversation_title": title},
            )
        )

    return records_out(records, conversation_count=1)
