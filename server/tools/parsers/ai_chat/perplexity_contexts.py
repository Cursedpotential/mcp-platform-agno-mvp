"""Atomic tool: Perplexity data-export conversations.json -> NormalizedRecords.

One format, one module, swappable. This is the Perplexity "contexts" export
variant (distinct from the existing perplexity_gdpr / perplexity_md /
perplexity_plugin parsers): a top-level object

    {"conversations": [
        {"context_uuid", "context_title", "created_at", "updated_at",
         "mode" (e.g. "COPILOT"), "collection_uuid",
         "entries": [{"entry_uuid", "query", "answer", "created_at",
                      "label", "query_status"}]}
    ]}

Each entry is one Q/A turn -> TWO records: a `user` record (the query) and an
`assistant` record (the answer), sharing the entry's timestamp so they stay
adjacent and chronological. Provenance: new (real export
`user_data_export_2025-12-15.zip`, format documented 2026-08-12).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from server.contracts.records import NormalizedRecord, RecordType
from server.tools._common import parse_timestamp, records_out
from server.tools.registry import register


def _looks_like_perplexity_contexts(data: Any) -> bool:
    if not isinstance(data, dict):
        return False
    convs = data.get("conversations")
    if not (isinstance(convs, list) and convs and isinstance(convs[0], dict)):
        return False
    c0 = convs[0]
    # signature: context_uuid + entries[] where an entry has query/answer
    if "context_uuid" not in c0 or not isinstance(c0.get("entries"), list):
        return False
    entries = c0["entries"]
    return bool(entries) and isinstance(entries[0], dict) and "query" in entries[0] and "answer" in entries[0]


@register(
    id="transcripts.perplexity-contexts",
    capability="parse.transcript",
    description="Perplexity contexts data-export (conversations[].entries[].query/answer) -> normalized records",
    accept=lambda hint, size: hint.endswith(".json"),
    provenance="new module (real user_data_export_2025-12-15.zip, 2026-08-12)",
)
def parse(payload: dict[str, Any]) -> dict[str, Any]:
    data = json.loads(Path(payload["path"]).read_text(encoding="utf-8", errors="replace"))
    if not _looks_like_perplexity_contexts(data):
        raise ValueError("not a Perplexity contexts export (no conversations[].context_uuid/entries[].query/answer)")

    convs = data["conversations"]
    records: list[NormalizedRecord] = []
    for conv in convs:
        conv_id = conv.get("context_uuid") or ""
        title = conv.get("context_title") or "untitled"
        mode = conv.get("mode")
        collection = conv.get("collection_uuid")
        for entry in conv.get("entries") or []:
            occurred = parse_timestamp(entry.get("created_at"))
            base_attrs = {
                "conversation_title": title,
                "entry_uuid": entry.get("entry_uuid"),
                "label": entry.get("label"),
                "query_status": entry.get("query_status"),
                "mode": mode,
                "collection_uuid": collection,
            }
            query = (entry.get("query") or "").strip()
            answer = (entry.get("answer") or "").strip()
            if query:
                records.append(
                    NormalizedRecord(
                        record_type=RecordType.message,
                        source="perplexity-contexts",
                        conversation_id=conv_id,
                        role="user",
                        participants=["owner", "perplexity"],
                        content=query,
                        occurred_at=occurred,
                        attrs={**base_attrs, "turn": "query"},
                    )
                )
            if answer:
                records.append(
                    NormalizedRecord(
                        record_type=RecordType.message,
                        source="perplexity-contexts",
                        conversation_id=conv_id,
                        role="assistant",
                        participants=["owner", "perplexity"],
                        content=answer,
                        occurred_at=occurred,
                        attrs={**base_attrs, "turn": "answer"},
                    )
                )
    return records_out(records, conversation_count=len(convs))
