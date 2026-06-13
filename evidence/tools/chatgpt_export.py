"""Atomic tool: ChatGPT data-export conversations.json -> NormalizedRecords.

One format, one module, swappable (owner architecture: parsers are separate
atomic units). Format: list of conversations, each with a `mapping` node tree;
messages carry author.role, create_time, content.parts.
Provenance: rewrite of extracted-code/parsers/chat-exports/chatgpt_parser.py
(the extracted version was a skeleton; format handling completed here).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from evidence.normalize import NormalizedRecord, RecordType
from evidence.registry import register
from evidence.tools._common import parse_timestamp, records_out


def _message_text(message: dict) -> str:
    content = message.get("content") or {}
    parts = content.get("parts") or []
    chunks: list[str] = []
    for p in parts:
        if isinstance(p, str):
            chunks.append(p)
        elif isinstance(p, dict) and p.get("text"):
            chunks.append(str(p["text"]))
    return "\n".join(c for c in chunks if c).strip()


@register(
    id="transcripts.chatgpt-export",
    capability="parse.transcript",
    description="ChatGPT data-export conversations.json -> normalized message records",
    accept=lambda hint, size: hint.endswith(".json"),
    provenance="rewrite of extracted-code/parsers/chat-exports/chatgpt_parser.py",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(Path(payload["path"]).read_text(encoding="utf-8", errors="replace"))
    conversations = data if isinstance(data, list) else [data]
    if not (conversations and isinstance(conversations[0], dict) and "mapping" in conversations[0]):
        raise ValueError("not a ChatGPT export (no `mapping` tree)")

    records: list[NormalizedRecord] = []
    for conv in conversations:
        conv_id = conv.get("conversation_id") or conv.get("id") or ""
        title = conv.get("title") or "untitled"
        messages = []
        for node in (conv.get("mapping") or {}).values():
            msg = (node or {}).get("message")
            if not msg:
                continue
            role = ((msg.get("author") or {}).get("role")) or ""
            text = _message_text(msg)
            if not text or role == "system":
                continue
            messages.append((msg.get("create_time") or 0, role, text))
        messages.sort(key=lambda m: m[0])
        for create_time, role, text in messages:
            records.append(
                NormalizedRecord(
                    record_type=RecordType.message,
                    source="chatgpt-export",
                    conversation_id=conv_id,
                    role=role,
                    participants=["owner", "chatgpt"],
                    content=text,
                    occurred_at=parse_timestamp(create_time),
                    attrs={"conversation_title": title},
                )
            )
    return records_out(records, conversation_count=len(conversations))
