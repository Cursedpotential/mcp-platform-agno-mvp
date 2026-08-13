"""Normalize parser output into ChatConversation + ChatMessage models.

Thin adapter: converts list[NormalizedRecord] (from existing parsers) →
ChatConversation + list[ChatMessage]. Parsers already produce NormalizedRecord;
we just map fields and assign message ordering.

Byline: Codex · GPT-5 · 2026-08-13 (normalize provider/fallback roles at the chat-schema boundary)
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any

from server.contracts.records import ChatConversation, ChatMessage, NormalizedRecord

logger = logging.getLogger(__name__)

_CHAT_ROLES = frozenset({"user", "assistant", "system", "tool", "unknown"})


def normalize_chat_role(role: str | None) -> str:
    """Return the finite role vocabulary accepted by ``chat_message``.

    Registry fallbacks may label a whole created work as ``transcript`` and
    providers occasionally introduce new author labels. Preserve the original
    parser value in message attrs, but do not leak that open vocabulary into
    chunk rendering or the database contract.
    """

    normalized = (role or "unknown").strip().lower()
    return normalized if normalized in _CHAT_ROLES else "unknown"


def _conversation_attrs(first: NormalizedRecord) -> dict[str, Any]:
    return {key: first.attrs[key] for key in ("archive", "archive_member") if key in first.attrs}


def _message_content_hash(source: str, conversation_id: str, message_index: int, content: str) -> str:
    """Deterministic hash for dedup. Uses message_index for ordering."""
    raw = f"{source}:{conversation_id}:{message_index}:{content[:500]}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _extract_thinking(attrs: dict[str, Any]) -> str | None:
    """Extract chain-of-thought from attrs if present (Claude/o1 only)."""
    return attrs.get("thinking") or attrs.get("reasoning")


def _extract_attachments(attrs: dict[str, Any]) -> list[str]:
    """Extract file refs / URLs / links referenced in the message."""
    raw = attrs.get("attachments")
    if not raw:
        return []
    if isinstance(raw, list):
        return [str(a) for a in raw]
    if isinstance(raw, str):
        return [raw]
    return []


def normalize_to_chat(
    records: list[NormalizedRecord],
    file_path: str | None = None,
) -> tuple[ChatConversation | None, list[ChatMessage]]:
    """Convert parser output to ChatConversation + list[ChatMessage].

    Groups records by conversation_id. If multiple conversations are present,
    returns the FIRST conversation (or None if empty) and all messages from all
    conversations. Callers wanting per-conversation handling should group
    records themselves before calling this.
    """
    if not records:
        return None, []

    # Group by conversation_id
    conversations: dict[str, list[NormalizedRecord]] = {}
    for rec in records:
        conv_id = rec.conversation_id or "unknown"
        conversations.setdefault(conv_id, []).append(rec)

    all_messages: list[ChatMessage] = []
    first_conv: ChatConversation | None = None

    for conv_id, conv_records in conversations.items():
        # Extract conversation-level metadata from first record
        first = conv_records[0]
        title = first.attrs.get("conversation_title") or first.attrs.get("title")
        created_at = first.occurred_at

        conv = ChatConversation(
            source=first.source,
            conversation_id=conv_id,
            title=title,
            created_at=created_at,
            file_path=file_path,
            attrs=_conversation_attrs(first),
        )

        if first_conv is None:
            first_conv = conv

        # Convert each record to ChatMessage
        for idx, rec in enumerate(conv_records):
            thinking = _extract_thinking(rec.attrs or {})
            attachments = _extract_attachments(rec.attrs or {})

            msg = ChatMessage(
                source=rec.source,
                conversation_id=conv_id,
                message_index=idx,
                role=normalize_chat_role(rec.role),
                content=rec.content or "",
                timestamp=rec.occurred_at,
                thinking=thinking,
                attachments=attachments,
                attrs=rec.attrs or {},
            )
            all_messages.append(msg)

    return first_conv, all_messages


def normalize_many(
    records: list[NormalizedRecord],
    file_path: str | None = None,
) -> list[tuple[ChatConversation, list[ChatMessage]]]:
    """Like normalize_to_chat but returns ALL conversations, not just the first."""
    if not records:
        return []

    conversations: dict[str, list[NormalizedRecord]] = {}
    for rec in records:
        conv_id = rec.conversation_id or "unknown"
        conversations.setdefault(conv_id, []).append(rec)

    result: list[tuple[ChatConversation, list[ChatMessage]]] = []

    for conv_id, conv_records in conversations.items():
        first = conv_records[0]
        title = first.attrs.get("conversation_title") or first.attrs.get("title")
        created_at = first.occurred_at

        conv = ChatConversation(
            source=first.source,
            conversation_id=conv_id,
            title=title,
            created_at=created_at,
            file_path=file_path,
            attrs=_conversation_attrs(first),
        )

        messages: list[ChatMessage] = []
        for idx, rec in enumerate(conv_records):
            thinking = _extract_thinking(rec.attrs or {})
            attachments = _extract_attachments(rec.attrs or {})

            msg = ChatMessage(
                source=rec.source,
                conversation_id=conv_id,
                message_index=idx,
                role=normalize_chat_role(rec.role),
                content=rec.content or "",
                timestamp=rec.occurred_at,
                thinking=thinking,
                attachments=attachments,
                attrs=rec.attrs or {},
            )
            messages.append(msg)

        result.append((conv, messages))

    return result


def compute_content_hash(msg: ChatMessage) -> str:
    """Compute the content_hash for a ChatMessage (for PG dedup)."""
    return _message_content_hash(
        msg.source,
        msg.conversation_id,
        msg.message_index,
        msg.content,
    )
