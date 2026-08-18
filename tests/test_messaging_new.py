# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""Unit tests for the three new forensic messaging parsers.

messaging_transcript: transcript-marker grammar (.txt / .csv)
messaging_csv: tabular messaging CSV (iMazing/AnyTrans/SMS export)
imessage_pdf: PDF text extraction -> TXT grammar (sniff + rejection only,
              since pypdf/pdfplumber are not installed in the test env)

Forensic contract: sender attribution, direction tagging, conversation_id
derivation from content, hard-fail on empty-after-markers, format rejection.
"""

from __future__ import annotations

import pytest

from server.tools.parsers.messaging.messaging_transcript import parse as transcript_parse
from server.tools.parsers.messaging.messaging_csv import parse as csv_parse, looks_like_messages_csv


# ──────────────────────────────────────────────────────────────────────────────
# messaging_transcript
# ──────────────────────────────────────────────────────────────────────────────

_TRANSCRIPT_TXT = """\
[2022-05-17 5:29 PM] Me:
Hey, are you picking up the kids?

[2022-05-17 5:30 PM] Ex Partner:
No, I can't today.

[2022-05-17 5:31 PM] Ex Partner:
Missed call
"""


def _write(tmp_path, text, name):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return p


def test_transcript_txt_roles_and_direction(tmp_path):
    p = _write(tmp_path, _TRANSCRIPT_TXT, "thread.txt")
    result = transcript_parse({"path": str(p)})
    assert result["stats"]["messages"] == 2
    assert result["stats"]["calls"] == 1

    mine, theirs, call = result["records"]

    assert mine["role"] == "owner"
    assert mine["attrs"]["direction"] == "outbound"
    assert "picking up the kids" in mine["content"]

    assert theirs["role"] == "Ex Partner"
    assert theirs["attrs"]["direction"] == "inbound"
    assert "can't today" in theirs["content"]

    assert call["record_type"] == "call"
    assert "Missed call" in call["content"]


def test_transcript_conversation_id_derived_from_content(tmp_path):
    p = _write(tmp_path, _TRANSCRIPT_TXT, "8102689630.txt")
    result = transcript_parse({"path": str(p)})
    # conv_id is derived from the OTHER speaker, not the filename
    for rec in result["records"]:
        assert rec["conversation_id"] == "Ex Partner"


def test_transcript_timestamps_are_tz_aware(tmp_path):
    p = _write(tmp_path, _TRANSCRIPT_TXT, "thread.txt")
    rec = transcript_parse({"path": str(p)})["records"][0]
    assert rec["occurred_at"].startswith("2022-05-17")
    assert rec["occurred_at"].endswith("+00:00") or rec["occurred_at"].endswith("Z")


def test_transcript_rejects_non_transcript_txt(tmp_path):
    p = _write(tmp_path, "just a normal note\nwith no markers\n", "notes.txt")
    with pytest.raises(ValueError, match="not a transcript-marker export"):
        transcript_parse({"path": str(p)})


def test_transcript_csv_format(tmp_path):
    csv_text = (
        "[2022-05-17 5:29 PM] Me:,extra\n"
        "Hey are you picking up the kids?,\n"
        "[2022-05-17 5:30 PM] Ex Partner:,\n"
        "No I can't today.,\n"
    )
    p = _write(tmp_path, csv_text, "thread.csv")
    result = transcript_parse({"path": str(p)})
    assert result["stats"]["messages"] == 2
    mine, theirs = result["records"]
    assert mine["role"] == "owner"
    assert theirs["role"] == "Ex Partner"


def test_transcript_participants_list(tmp_path):
    p = _write(tmp_path, _TRANSCRIPT_TXT, "thread.txt")
    result = transcript_parse({"path": str(p)})
    participants = result["records"][0]["participants"]
    assert "owner" in participants
    assert "Ex Partner" in participants


def test_transcript_resolves_self_only_from_source_metadata(tmp_path):
    p = _write(tmp_path, _TRANSCRIPT_TXT, "thread.txt")
    result = transcript_parse(
        {
            "path": str(p),
            "source_meta": {
                "source_principal": "source-account@example.test",
                "message_corpus": "acquired_third_party",
            },
        }
    )
    mine, theirs, _call = result["records"]
    assert mine["sender"] == "source-account@example.test"
    assert mine["role"] == "owner"
    assert mine["recipients"] == [{"identity": "Ex Partner", "role": "to"}]
    assert mine["message_corpus"] == "acquired_third_party"
    assert theirs["sender"] == "Ex Partner"
    assert theirs["recipients"] == [{"identity": "source-account@example.test", "role": "to"}]


# ──────────────────────────────────────────────────────────────────────────────
# messaging_csv
# ──────────────────────────────────────────────────────────────────────────────

_CSV_CONTENT = """\
date,sender name,text,is from me,service
2022-05-17 17:29:42,Ex Partner,Why are you late again,False,iMessage
2022-05-17 17:30:10,Me,Traffic on the bridge,True,iMessage
2022-05-17 17:31:00,Ex Partner,Missed call,False,SMS
"""


def test_csv_roles_and_direction(tmp_path):
    p = _write(tmp_path, _CSV_CONTENT, "thread.csv")
    result = csv_parse({"path": str(p)})
    assert result["stats"]["messages"] == 2
    assert result["stats"]["calls"] == 1

    ex, me, call = result["records"]
    assert ex["role"] == "Ex Partner"
    assert ex["attrs"]["direction"] == "inbound"
    assert "late again" in ex["content"]

    assert me["role"] == "owner"
    assert me["attrs"]["direction"] == "outbound"
    assert "Traffic" in me["content"]

    assert call["record_type"] == "call"


def test_csv_raw_row_preserved(tmp_path):
    p = _write(tmp_path, _CSV_CONTENT, "thread.csv")
    result = csv_parse({"path": str(p)})
    # Forensic contract: original columns kept in attrs.raw_row
    for rec in result["records"]:
        assert "raw_row" in rec["attrs"]
        assert "service" in rec["attrs"]["raw_row"]


def test_csv_timestamps_are_tz_aware(tmp_path):
    p = _write(tmp_path, _CSV_CONTENT, "thread.csv")
    rec = csv_parse({"path": str(p)})["records"][0]
    assert rec["occurred_at"].startswith("2022-05-17")
    assert rec["occurred_at"].endswith("+00:00") or rec["occurred_at"].endswith("Z")


def test_csv_imessage_source_detected(tmp_path):
    p = _write(tmp_path, _CSV_CONTENT, "thread.csv")
    result = csv_parse({"path": str(p)})
    # iMessage service => source = imessage-csv
    assert result["records"][0]["source"] == "imessage-csv"


def test_csv_rejects_non_messaging_csv(tmp_path):
    csv_text = "name,age,city\nAlice,30,New York\n"
    p = _write(tmp_path, csv_text, "data.csv")
    with pytest.raises(ValueError, match="not a messaging CSV"):
        csv_parse({"path": str(p)})


def test_looks_like_messages_csv_positive():
    assert looks_like_messages_csv(["date", "sender name", "text"])
    assert looks_like_messages_csv(["timestamp", "from", "message"])
    assert looks_like_messages_csv(["date", "is from me", "body"])


def test_looks_like_messages_csv_negative():
    assert not looks_like_messages_csv(["name", "age"])
    assert not looks_like_messages_csv(["date", "amount"])  # no text col


def test_csv_participants_backfilled(tmp_path):
    p = _write(tmp_path, _CSV_CONTENT, "thread.csv")
    result = csv_parse({"path": str(p)})
    for rec in result["records"]:
        assert "owner" in rec["participants"]
        assert "Ex Partner" in rec["participants"]


# ──────────────────────────────────────────────────────────────────────────────
# imessage_pdf — sniff + rejection (no pypdf in test env)
# ──────────────────────────────────────────────────────────────────────────────


def test_imessage_pdf_import_available():
    """Parser module must be importable (no eager import of pypdf)."""
    from server.tools.parsers.messaging import imessage_pdf  # noqa: F401


def test_imessage_pdf_rejects_without_pdf_lib(tmp_path, monkeypatch):
    """When neither pypdf nor pdfplumber are installed, parse() raises RuntimeError."""
    import builtins

    real_import = builtins.__import__

    def blocked_import(name, *args, **kwargs):
        if name in ("pypdf", "pdfplumber"):
            raise ImportError(f"blocked: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", blocked_import)

    p = tmp_path / "thread.pdf"
    p.write_bytes(b"%PDF-1.4 fake pdf content")

    from server.tools.parsers.messaging.imessage_pdf import parse

    with pytest.raises(RuntimeError, match="imessage-pdf needs pypdf or pdfplumber"):
        parse({"path": str(p)})
