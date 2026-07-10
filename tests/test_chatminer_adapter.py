"""Unit tests for server.tools._chatminer_adapter — the ChatMiner bridge (HA.1).

The adapter is the seam between the vendored chatminer parsers and the
canonical NormalizedRecord shape. What matters forensically: verbatim content,
the per-message hash riding in attrs, tz-aware valid time, and HARD failure
(never silent-empty) so the registry substitution mesh keeps moving.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from server.vendored.chatminer.core.base import BaseParser
from server.vendored.chatminer.core.types import (
    ContentType,
    MessageRole,
    ParsedConversation,
    ParsedMessage,
    ParseResult,
)
from server.contracts.records import RecordType
from server.tools._chatminer_adapter import run_chatminer_parser, to_normalized_records


def _msg(i: int, role: MessageRole, content: str, ts: datetime | None, **kw) -> ParsedMessage:
    return ParsedMessage(
        message_id=f"m{i}",
        source_file="chat.json",
        source_format="chatgpt_official",
        source_index=i,
        timestamp=ts,
        sender="You" if role is MessageRole.USER else "ChatGPT",
        sender_role=role,
        content=content,
        **kw,
    )


def _conv(messages: list[ParsedMessage]) -> ParsedConversation:
    return ParsedConversation(
        conversation_id="uuid-per-parse",
        source_file="chat.json",
        source_format="chatgpt_official",
        title="Custody timeline",
        messages=messages,
        metadata={"file_hash": "abc123", "conversation_id": "orig-conv-77"},
    )


def test_two_message_conversation_maps_to_two_records():
    aware = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    naive = datetime(2026, 1, 2, 3, 4, 6)  # tz-naive — must come out UTC-aware
    conv = _conv(
        [
            _msg(0, MessageRole.USER, "what happened on pickup day?", aware),
            _msg(
                1, MessageRole.ASSISTANT, "```python\nx=1\n```", naive, content_type=ContentType.CODE, language="python"
            ),
        ]
    )
    result = ParseResult(conversations=[conv])

    records = to_normalized_records(result)
    assert len(records) == 2
    user, asst = records

    # HA.1 accept condition: occurred_at set on both, always tz-aware.
    assert user.occurred_at == aware
    assert asst.occurred_at is not None and asst.occurred_at.tzinfo is not None

    assert user.record_type is RecordType.message
    assert user.source == "chatgpt-official"  # source_format, house dash style
    assert user.role == "user" and asst.role == "assistant"
    assert user.content == "what happened on pickup day?"  # verbatim
    # Original export conversation id wins over chatminer's per-parse uuid.
    assert user.conversation_id == "orig-conv-77"
    assert user.participants == ["You", "ChatGPT"]

    # Forensic attrs: hash, content type, provenance extras.
    assert user.attrs["message_hash"] == conv.messages[0].compute_hash()
    assert user.attrs["content_type"] == "text"
    assert asst.attrs["content_type"] == "code"
    assert asst.attrs["language"] == "python"
    assert user.attrs["conversation_title"] == "Custody timeline"
    assert user.attrs["conversation_metadata"]["file_hash"] == "abc123"
    assert user.attrs["source_index"] == 0 and asst.attrs["source_index"] == 1


def test_falls_back_to_parse_uuid_without_original_conversation_id():
    conv = _conv([_msg(0, MessageRole.USER, "hi", None)])
    conv.metadata = {}
    [rec] = to_normalized_records(ParseResult(conversations=[conv]))
    assert rec.conversation_id == "uuid-per-parse"
    assert rec.occurred_at is None  # no timestamp in source -> stays unset


class _FakeParser(BaseParser):
    """Canned-result BaseParser: fixed detection confidence + ParseResult."""

    SOURCE_NAME = "fake"
    confidence = 1.0
    result = ParseResult()

    def read_file(self, path):
        return "content"

    def can_parse(self, content, path=None):
        return self.confidence

    def parse_content(self, content, source_file=""):
        return list(self.result.conversations)

    def parse_file(self, path):
        return self.result


def test_run_hard_fails_below_detection_confidence(tmp_path):
    f = tmp_path / "x.md"
    f.write_text("whatever")

    class Low(_FakeParser):
        confidence = 0.2

    with pytest.raises(ValueError, match="detection confidence"):
        run_chatminer_parser(Low, {"path": str(f)})
    # ...unless the wrapper opts into a lower gate (generic_md does).
    Low.result = ParseResult(conversations=[_conv([_msg(0, MessageRole.USER, "hi", None)])])
    out = run_chatminer_parser(Low, {"path": str(f)}, min_confidence=0.1)
    assert out["stats"]["record_count"] == 1


def test_run_hard_fails_on_parser_errors(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")

    class Bad(_FakeParser):
        result = ParseResult(errors=[{"file": "x.json", "error": "boom"}])

    with pytest.raises(ValueError, match="parse failed"):
        run_chatminer_parser(Bad, {"path": str(f)})


def test_run_hard_fails_on_zero_messages_never_silent_empty(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")

    class Hollow(_FakeParser):
        result = ParseResult(conversations=[_conv([])])

    with pytest.raises(ValueError, match="0 messages"):
        run_chatminer_parser(Hollow, {"path": str(f)})


def test_run_output_is_records_out_shape(tmp_path):
    f = tmp_path / "x.json"
    f.write_text("{}")

    class Ok(_FakeParser):
        result = ParseResult(conversations=[_conv([_msg(0, MessageRole.USER, "hi", None)])])

    out = run_chatminer_parser(Ok, {"path": str(f)})
    assert set(out) == {"records", "stats"}
    assert out["stats"]["record_count"] == 1
    assert out["stats"]["conversation_count"] == 1
    assert out["stats"]["detection_confidence"] == 1.0
    # records are JSON-safe dicts (workflow store step re-validates them)
    assert out["records"][0]["content"] == "hi"
