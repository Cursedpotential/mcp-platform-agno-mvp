"""Atomic tool: Claude Code session .jsonl -> NormalizedRecords.

One format, one module, swappable. Format: one JSON event per line;
user/assistant events carry message.content (string or typed blocks),
ISO timestamp, sessionId. Only text blocks become records (tool-call noise
is deliberately dropped — knowledge value lives in the prose).
Provenance: rewrite of extracted-code/parsers/chat-exports/ClaudeCodeJSONLParser.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from server.evidence.normalize import NormalizedRecord, RecordType
from .registry import register
from ._common import parse_timestamp, records_out


def _event_text(message: Any) -> str:
    if isinstance(message, str):
        return message.strip()
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text").strip()
    return ""


@register(
    id="transcripts.claude-code-jsonl",
    capability="parse.transcript",
    description="Claude Code session .jsonl -> normalized message records (text blocks only)",
    accept=lambda hint, size: hint.endswith(".jsonl"),
    provenance="rewrite of extracted-code/parsers/chat-exports/ClaudeCodeJSONLParser",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    path = Path(payload["path"])
    records: list[NormalizedRecord] = []
    line_count = 0
    with path.open(encoding="utf-8", errors="replace") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            line_count += 1
            try:
                evt = json.loads(line)
            except json.JSONDecodeError:
                continue
            if evt.get("type") not in ("user", "assistant"):
                continue
            text = _event_text(evt.get("message"))
            if not text:
                continue
            records.append(
                NormalizedRecord(
                    record_type=RecordType.message,
                    source="claude-code-jsonl",
                    conversation_id=evt.get("sessionId") or path.stem,
                    role=evt.get("type"),
                    participants=["owner", "claude-code"],
                    content=text,
                    occurred_at=parse_timestamp(evt.get("timestamp")),
                    attrs={"event_uuid": evt.get("uuid", "")},
                )
            )
    if line_count == 0:
        raise ValueError("empty file — nothing to parse")
    if not records:
        raise ValueError("no user/assistant text events — not a Claude Code session (hard-fail, no silent-empty)")
    return records_out(records, line_count=line_count)
