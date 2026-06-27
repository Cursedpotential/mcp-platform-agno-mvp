"""Unit tests for evidence.tools.imessage_txt — imessage-exporter TXT grammar.

Reconstructs message blocks (timestamp header + sender + body), read receipts,
announcements (rename/etc.), and the call heuristic. Forensic contract: nothing
silently dropped; sender attribution and read receipts preserved.
"""

from __future__ import annotations

import pytest

from evidence.tools.imessage_txt import parse

# Note the DOUBLE space before the time — the exporter's "%b %d, %Y  %l:%M:%S %p".
_EXPORT = """May 17, 2022  5:29:42 PM (Read by you after 1 hour, 2 minutes)
Me
Hey, are you picking up the kids?

May 17, 2022  5:30:10 PM
Ex Partner
No, I can't today.

May 17, 2022  5:31:00 PM
Ex Partner
Missed call

May 17, 2022  6:00:00 PM You renamed the conversation to Custody.
"""


def _run(tmp_path, text=_EXPORT, name="thread.txt"):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return parse({"path": str(p)})


def test_blocks_receipts_calls_and_announcements(tmp_path):
    result = _run(tmp_path)
    assert result["stats"]["messages"] == 2
    assert result["stats"]["calls"] == 1
    assert result["stats"]["announcements"] == 1

    mine, theirs, call, announcement = result["records"]  # sorted by time

    assert mine["role"] == "owner"
    assert mine["attrs"]["direction"] == "outbound"
    assert "picking up the kids" in mine["content"]
    assert mine["attrs"]["read_receipt"]["reader"] == "you"
    assert mine["record_type"] == "message"

    assert theirs["role"] == "Ex Partner"
    assert theirs["attrs"]["direction"] == "inbound"
    assert "can't today" in theirs["content"]

    assert call["record_type"] == "call"
    assert "Missed call" in call["content"]

    assert announcement["record_type"] == "event"
    assert announcement["attrs"]["kind"] == "announcement"
    assert "renamed" in announcement["content"]
    assert announcement["role"] == "owner"


def test_timestamps_are_tz_aware(tmp_path):
    rec = _run(tmp_path)["records"][0]
    assert rec["occurred_at"] and rec["occurred_at"].startswith("2022-05-17")
    # Must carry a tz offset — a naive timestamp (no "+00:00"/"Z") is a regression
    # against the normalize layer's tz-aware contract.
    assert rec["occurred_at"].endswith("+00:00") or rec["occurred_at"].endswith("Z")


def test_rejects_non_imessage_text(tmp_path):
    with pytest.raises(ValueError, match="not an imessage-exporter TXT export"):
        _run(tmp_path, text="just a normal note\nwith no timestamps\n")
