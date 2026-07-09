"""Unit tests for chatminer.core.types — the contract every parser emits.

ParsedMessage/ParsedConversation are the atoms passed between parsing, storage,
and export. The serialization round-trip and content-hash (chain of custody)
are the parts most likely to break silently.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from server.vendored.chatminer.core.types import (
    ContentType,
    MessageRole,
    ParsedConversation,
    ParsedMessage,
)


def _msg(**kw: Any) -> ParsedMessage:
    base: dict[str, Any] = {
        "message_id": "m1",
        "source_file": "f.md",
        "source_format": "generic_md",
        "source_index": 0,
        "content": "hello",
    }
    base.update(kw)
    return ParsedMessage(**base)


def test_message_roundtrip_to_from_dict():
    msg = _msg(
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        sender="You",
        sender_role=MessageRole.USER,
        content_type=ContentType.TEXT,
    )
    restored = ParsedMessage.from_dict(msg.to_dict())
    assert restored.message_id == msg.message_id
    assert restored.sender_role is MessageRole.USER
    assert restored.content_type is ContentType.TEXT
    assert restored.timestamp == msg.timestamp
    assert restored.content == "hello"


def test_content_hash_is_stable_and_content_derived():
    a = _msg(content="identical")
    b = _msg(message_id="different-id", content="identical")
    # Hash is over verbatim content, not identity -> dedup across sources works.
    assert a.compute_hash() == b.compute_hash()
    assert _msg(content="other").compute_hash() != a.compute_hash()


def test_to_dict_includes_message_hash():
    assert "message_hash" in _msg().to_dict()


def test_conversation_role_partitions():
    conv = ParsedConversation(conversation_id="c1", source_file="f", source_format="generic_md")
    conv.messages = [
        _msg(message_id="u1", sender_role=MessageRole.USER),
        _msg(message_id="a1", sender_role=MessageRole.ASSISTANT),
        _msg(message_id="a2", sender_role=MessageRole.ASSISTANT, content_type=ContentType.CODE),
    ]
    assert conv.message_count == 3
    assert [m.message_id for m in conv.user_messages] == ["u1"]
    assert [m.message_id for m in conv.assistant_messages] == ["a1", "a2"]
    assert [m.message_id for m in conv.code_blocks] == ["a2"]


def test_conversation_json_serializes():
    conv = ParsedConversation(conversation_id="c1", source_file="f", source_format="generic_md")
    conv.messages = [_msg()]
    blob = conv.to_json()
    assert '"conversation_id": "c1"' in blob
    assert '"message_count": 1' in blob
