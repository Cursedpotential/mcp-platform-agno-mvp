"""Unit tests for server.tools.parsers.messaging.facebook_messenger_json.

The court-critical bits: Facebook double-encodes UTF-8 as latin-1 (mojibake),
so text must be repaired or the evidence is garbage; non-text messages
(media/calls) get synthesized searchable content; reaction-only noise is
dropped; calls are typed as calls.
"""

from __future__ import annotations

import json

import pytest

from server.tools.parsers.messaging.facebook_messenger_json import parse


def _run(tmp_path, payload_obj):
    p = tmp_path / "message_1.json"
    p.write_text(json.dumps(payload_obj), encoding="utf-8")
    return parse({"path": str(p)})


def test_mojibake_repair_media_and_call(tmp_path):
    result = _run(
        tmp_path,
        {
            "participants": [{"name": "Me"}, {"name": "Ex"}],
            "title": "Ex",
            "thread_path": "inbox/ex_123",
            "messages": [
                {"sender_name": "Ex", "timestamp_ms": 1700000000000, "content": "meet at the cafÃ©"},
                {"sender_name": "Me", "timestamp_ms": 1700000100000, "photos": [{"uri": "photos/1.jpg"}]},
                {"sender_name": "Ex", "timestamp_ms": 1700000200000, "type": "Call", "call_duration": 42},
                {"sender_name": "Me", "timestamp_ms": 1700000300000, "reactions": [{"reaction": "x", "actor": "Ex"}]},
            ],
        },
    )

    # reaction-only message dropped -> 2 messages + 1 call.
    assert result["stats"] == {
        "record_count": 3,
        "messages": 2,
        "calls": 1,
        "files": 1,
        "participants": 2,
    }

    cafe, photo, call = result["records"]  # sorted chronologically
    # "cafÃ©" (latin-1-over-utf-8) repairs to "café".
    assert cafe["content"] == "meet at the café"
    assert cafe["role"] == "Ex" and cafe["record_type"] == "message"

    assert photo["content"] == "[sent 1 attachment(s): photo]"
    assert photo["attrs"]["media"][0]["kind"] == "photo"

    assert call["record_type"] == "call"
    assert call["content"] == "Call (42s)"
    assert call["attrs"]["is_call"] is True
    assert call["attrs"]["call_duration_seconds"] == 42


def test_rejects_non_facebook_json(tmp_path):
    with pytest.raises(ValueError, match="not a Facebook DYI export"):
        _run(tmp_path, {"some": "other json"})
