"""Atomic tool: claude.ai data-export conversations.json -> NormalizedRecords.

One format, one module, swappable. Format: list of conversations with
`chat_messages`; each message has sender (human/assistant), text or
content blocks, created_at ISO timestamps.
Provenance: new (format documented; no prior extracted parser existed).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from server.evidence.normalize import NormalizedRecord, RecordType
from .registry import register
from ._common import parse_timestamp, records_out


@register(
    id="transcripts.claude-ai-export",
    capability="parse.transcript",
    description="claude.ai data-export conversations.json -> normalized message records",
    accept=lambda hint, size: hint.endswith(".json"),
    provenance="new module (no prior extracted parser)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(Path(payload["path"]).read_text(encoding="utf-8", errors="replace"))
    convs = data if isinstance(data, list) else [data]
    if not (convs and isinstance(convs[0], dict) and "chat_messages" in convs[0]):
        raise ValueError("not a claude.ai export (no `chat_messages`)")

    records: list[NormalizedRecord] = []
    for conv in convs:
        conv_id = conv.get("uuid") or ""
        title = conv.get("name") or "untitled"
        for msg in conv.get("chat_messages") or []:
            text = msg.get("text") or ""
            if not text:
                blocks = msg.get("content") or []
                text = "\n".join(
                    b.get("text", "") for b in blocks if isinstance(b, dict) and b.get("type") == "text"
                ).strip()
            if not text:
                continue
            sender = msg.get("sender") or ""
            records.append(
                NormalizedRecord(
                    record_type=RecordType.message,
                    source="claude-ai-export",
                    conversation_id=conv_id,
                    role="user" if sender == "human" else "assistant",
                    participants=["owner", "claude"],
                    content=text,
                    occurred_at=parse_timestamp(msg.get("created_at")),
                    attrs={"conversation_title": title},
                )
            )
    return records_out(records, conversation_count=len(convs))
