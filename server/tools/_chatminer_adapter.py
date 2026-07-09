"""ChatMiner -> NormalizedRecord bridge (not a tool module itself —
underscore prefix excludes it from auto-discovery).

Maps the vendored chatminer types (ParsedMessage / ParsedConversation /
ParseResult) onto the one canonical evidence shape, and provides the shared
run helper every chatminer-backed @register wrapper delegates to. Forensic
contract: content is verbatim, the per-message SHA-256 hash and every
source-specific extra ride along in `attrs`.

Mesh behavior: `run_chatminer_parser` HARD-FAILS (raises ValueError) when the
parser's own detector isn't confident or when parsing yields zero messages —
never a silent-empty success — so the workflow substitution loop moves on to
the next same-capability candidate.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from server.vendored.chatminer.core.base import BaseParser
from server.vendored.chatminer.core.types import ParsedConversation, ParsedMessage, ParseResult
from server.evidence.normalize import NormalizedRecord, RecordType
from ._common import records_out

# chatminer's own auto-detection threshold (parsers/__init__.get_parser_for_file).
DEFAULT_MIN_CONFIDENCE = 0.5


def message_to_record(
    msg: ParsedMessage,
    conv: ParsedConversation,
    participants: list[str] | None = None,
) -> NormalizedRecord:
    """One ParsedMessage -> one NormalizedRecord (verbatim content, full attrs)."""
    attrs: dict[str, Any] = {
        "message_id": msg.message_id,
        "message_hash": msg.compute_hash(),
        "content_type": msg.content_type.value,
        "sender": msg.sender,
        "source_file": msg.source_file or conv.source_file,
        "source_format": msg.source_format or conv.source_format,
        "source_index": msg.source_index,
        "confidence": msg.confidence,
    }
    if msg.language:
        attrs["language"] = msg.language
    if msg.metadata:
        attrs["message_metadata"] = msg.metadata
    if conv.title:
        attrs["conversation_title"] = conv.title
    if conv.metadata:
        attrs["conversation_metadata"] = conv.metadata

    source_format = msg.source_format or conv.source_format or "chatminer"
    return NormalizedRecord(
        record_type=RecordType.message,
        source=source_format.replace("_", "-"),
        # Prefer the ORIGINAL export conversation id (deterministic across
        # re-ingests) over chatminer's per-parse uuid4.
        conversation_id=str(conv.metadata.get("conversation_id") or conv.conversation_id),
        role=msg.sender_role.value,
        participants=participants if participants is not None else _participants(conv),
        content=msg.content,
        occurred_at=msg.timestamp,
        attrs=attrs,
    )


def conversation_to_records(conv: ParsedConversation) -> list[NormalizedRecord]:
    participants = _participants(conv)
    return [message_to_record(m, conv, participants) for m in conv.messages]


def to_normalized_records(result: ParseResult) -> list[NormalizedRecord]:
    """Flatten a chatminer ParseResult into NormalizedRecords."""
    records: list[NormalizedRecord] = []
    for conv in result.conversations:
        records.extend(conversation_to_records(conv))
    return records


def run_chatminer_parser(
    parser_cls: type[BaseParser],
    payload: dict[str, Any],
    min_confidence: float = DEFAULT_MIN_CONFIDENCE,
) -> dict[str, Any]:
    """Shared wrapper body: detect-gate -> parse -> adapt -> records_out."""
    parser = parser_cls()
    path = Path(payload["path"])
    content = parser.read_file(path)  # encoding-fallback read
    score = parser.can_parse(content, str(path))
    if score < min_confidence:
        raise ValueError(
            f"{parser_cls.SOURCE_NAME}: detection confidence {score:.2f} < {min_confidence} — not this format"
        )
    result = parser.parse_file(path)
    if result.errors and not result.conversations:
        raise ValueError(f"{parser_cls.SOURCE_NAME}: parse failed: {result.errors}")
    records = to_normalized_records(result)
    if not records:
        raise ValueError(f"{parser_cls.SOURCE_NAME}: parsed 0 messages — hard-fail, no silent-empty")
    return records_out(records, conversation_count=len(result.conversations), detection_confidence=round(score, 4))


def _participants(conv: ParsedConversation) -> list[str]:
    """Unique sender display names in first-appearance order."""
    seen: list[str] = []
    for m in conv.messages:
        if m.sender and m.sender not in seen:
            seen.append(m.sender)
    return seen
