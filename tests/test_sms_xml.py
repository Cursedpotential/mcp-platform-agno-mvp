"""Unit tests for server.tools.parsers.messaging.sms_xml — "SMS Backup & Restore" parser.

Court-critical forensic logic: sent/received attribution, MMS body extraction,
and the call-block forensic flags (rejected / refuse-list / outgoing-zero-
duration). Tested at the tool boundary: parse({"path": ...}) -> records_out.
"""

from __future__ import annotations

from server.tools.parsers.messaging.sms_xml import parse


def _run(tmp_path, name, xml):
    p = tmp_path / name
    p.write_text(xml, encoding="utf-8")
    return parse({"path": str(p)})


def test_sms_messages_roles_mms_and_empty_bodies(tmp_path):
    xml = """<smses count="4">
      <sms address="+15551234567" contact_name="Ex Partner" date="1700000000000" type="1" body="why are you late"/>
      <sms address="+15551234567" contact_name="Ex Partner" date="1700000100000" type="2" body="I am on my way"/>
      <sms address="+15551234567" date="1700000200000" type="1" body="null"/>
      <mms address="+15551234567" date="1700000300000" type="1">
        <parts><part ct="text/plain" text="see the photo"/></parts>
      </mms>
    </smses>"""
    result = _run(tmp_path, "sms.xml", xml)

    # A body-less record is KEPT and flagged, not dropped. This test previously
    # asserted the opposite; that behaviour silently discarded 516 attachment-only
    # MMS from a real 636 MiB export (2026-08-01). A message with a timestamp and a
    # counterparty is an event whether or not it carries text.
    assert result["stats"]["messages"] == 4
    assert result["stats"]["calls"] == 0
    recs = result["records"]
    assert [r["content"] for r in recs] == [
        "why are you late", "I am on my way", "", "see the photo",
    ]

    received, sent, empty, mms = recs
    assert received["attrs"]["direction"] == "received" and received["role"] == "Ex Partner"
    assert sent["attrs"]["direction"] == "sent" and sent["role"] == "owner"
    assert received["occurred_at"] and received["occurred_at"].startswith("2023")
    assert empty["attrs"]["body_present"] is False and empty["attrs"]["empty_body"] is True
    assert mms["attrs"]["channel"] == "mms"


def test_attachment_only_mms_is_kept_and_identifiable(tmp_path):
    """An image-only MMS must survive parsing and stay distinguishable from another.

    Identity comes from the attachment digest — without it, two captionless photos
    sent to the same number in the same second are byte-identical records and the
    raw-layer dedup index would collapse one of them away.
    """
    xml = """<smses count="2">
      <mms address="+15551234567" date="1700000000000" type="1">
        <parts>
          <part ct="application/smil" text="&lt;smil/&gt;"/>
          <part ct="image/jpeg" cl="a.jpg" data="QUJDREVGRw=="/>
        </parts>
      </mms>
      <mms address="+15551234567" date="1700000000000" type="1">
        <parts><part ct="image/jpeg" cl="b.jpg" data="WllYV1ZVVA=="/></parts>
      </mms>
    </smses>"""
    result = _run(tmp_path, "mms.xml", xml)

    assert result["stats"]["messages"] == 2
    first, second = result["records"]
    for r in (first, second):
        assert r["content"] == ""
        assert r["attrs"]["body_present"] is False
        # the SMIL layout part is not an attachment
        assert r["attrs"]["attachment_count"] == 1
        # the base64 payload is never retained on the record
        assert "data" not in r["attrs"]["attachments"][0]
    assert (first["attrs"]["attachments"][0]["b64_sha256"]
            != second["attrs"]["attachments"][0]["b64_sha256"])


def test_call_block_forensic_flags(tmp_path):
    xml = """<calls count="3">
      <call number="+15551234567" contact_name="Ex" date="1700000000000" type="3" duration="0"/>
      <call number="+15551234567" date="1700000100000" type="5" duration="0"/>
      <call number="+15551234567" date="1700000200000" type="2" duration="0"/>
    </calls>"""
    result = _run(tmp_path, "calls.xml", xml)

    assert result["stats"]["calls"] == 3
    # rejected (type 5) + outgoing-zero-duration (type 2) are blocked; missed is not.
    assert result["stats"]["blocked_calls"] == 2

    missed, rejected, outgoing = result["records"]
    assert missed["attrs"]["call_type"] == "missed" and missed["attrs"]["blocked"] is False
    assert rejected["attrs"]["blocked"] is True
    assert "call actively rejected" in rejected["attrs"]["forensic_flags"]
    assert "FORENSIC FLAG" in rejected["content"]
    assert outgoing["attrs"]["blocked"] is True
    assert outgoing["role"] == "owner"
    assert any("0 duration" in f for f in outgoing["attrs"]["forensic_flags"])


def test_rejects_non_sms_backup_xml(tmp_path):
    import pytest

    p = tmp_path / "other.xml"
    p.write_text("<rss><channel><item>not sms</item></channel></rss>", encoding="utf-8")
    with pytest.raises(ValueError, match="not an SMS Backup"):
        parse({"path": str(p)})


def test_malformed_xml_bare_ampersand_recovers(tmp_path):
    # Stray '&' is common in these dumps; the parser sanitizes + retries.
    xml = '<smses count="1"><sms address="+1" date="1700000000000" type="1" body="Tom & Jerry"/></smses>'
    result = _run(tmp_path, "amp.xml", xml)
    assert result["stats"]["messages"] == 1
    assert result["records"][0]["content"] == "Tom & Jerry"
