# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""SBV promotion & universal import (SBV donor API term) forensic parity.

Byline: Claude Code . Fable 5 . 2026-08-09 (S2 build-and-test-green task 4)

Rewritten for the 2026-08-05 SBV-promotion ruling (DECISION_LOG D-040, PR
#18): the resolution contract is now SBV (`messages.sms-xml-sbv`) as PRIMARY
`parse.sms-xml` whenever `SBV_SERVICE_PASS` is wired
(server/tools/parsers/messaging/sbv_sms.py::_sbv_enabled), with sms_xml.py
(`messages.sms-xml`) as the automatic fallback otherwise. There is NO
`SBV_PRIMARY_ENABLED` gate any more — that env var was removed from
`_sbv_enabled`'s predicate when SBV was promoted; a test that still asserted
its old on/off behavior would only be testing dead code.

These tests also RE-PIN, against the LIVE paths, the two forensic guarantees
the 2026-08-02 parser-gap review (docs/HANDOFF-2026-08-02-sbv-chatminer-
parser-gap-review.md) exists to protect:

  * bodyless-media retention (the 516-dropped-MMS lesson) — an
    attachment-only MMS/message must never be silently discarded.
  * outbound-role mapping — SMS/MMS types 2 (sent) / 4 (outbox) / 5 (failed) /
    6 (queued) are all owner-authored.

Both are pinned against `_map_universal_record` (the live SBV path used by
`sbv_sms.parse()`) AND against sms_xml.py's `_map_sms`/`_map_call` (the pure-
Python fallback) — the review's core P0 finding was that the two parsers'
outputs were NOT equivalent, so pinning only one side would let them silently
drift apart again.

CODE FIX landed alongside this rewrite (not just a test change): SBV's
SMS-XML importer (vendored/sbv/internal/sms_xml_importer.go) projects a
universal import (SBV donor API term) row's `metadata` straight from the RAW XML entry — it has no
"role"/"sender" key for this format (verified by reading both
vendored/sbv/internal/parser.go's SMSEntry/MMSEntry/CallEntry structs and
sms_xml_importer.go's messageSourceRecord/callSourceRecord). Before this
rewrite, `_map_universal_record`'s role fell straight through to
`participants[0]` whenever no explicit "role"/"sender" key was present — and
because SMS Backup & Restore's `address`/`number` attribute names the OTHER
party on both received AND SENT records, that resolved EVERY message/call to
the counterparty regardless of direction, silently misattributing every
owner-authored record. This is the exact bug the 2026-08-02 review found in
the (now-retired) legacy `_map_message` — see
_stale/sbv_sms_map_message_legacy.py — just reappearing on the universal path
that superseded it. Fixed minimally in
server/tools/parsers/messaging/sbv_sms.py::_role_for_universal_record: fall
back to the same type-code -> OWNER mapping sms_xml.py uses (2/4/5/6 for
messages, 2 for calls) before finally using the first participant. See that
function's docstring for the full trace.

Legacy `_map_message` (the pre-universal import (SBV donor API term) SBV mapper this file used to
test directly) had zero production callers as of 2026-08-09 and is retired to
_stale/sbv_sms_map_message_legacy.py per the workspace never-delete rule.
"""

from __future__ import annotations

from server.tools import registry as registry_mod
from server.tools.parsers.messaging import sbv_sms, sms_xml
from server.tools.parsers.messaging.sbv_sms import _map_universal_record
from server.tools.parsers.messaging.sms_xml import _map_sms
from server.tools.registry import load_builtin_tools


def _loaded_registry():
    load_builtin_tools()
    return registry_mod.registry


def _run_sms_xml(tmp_path, name, xml):
    p = tmp_path / name
    p.write_text(xml, encoding="utf-8")
    return sms_xml.parse({"path": str(p)})


# ---- resolution: SBV primary iff SBV_SERVICE_PASS wired; sms_xml is the fallback ----


def test_sbv_resolves_first_when_service_pass_wired(monkeypatch):
    monkeypatch.setenv("SBV_SERVICE_PASS", "x")
    reg = _loaded_registry()
    candidates = [t.id for t in reg.resolve("parse.sms-xml", media_hint="a.xml", size_bytes=10)]
    assert candidates[:1] == ["messages.sms-xml-sbv"]
    assert "messages.sms-xml" in candidates  # fallback stays a substitution candidate


def test_sms_xml_is_the_only_candidate_without_service_pass(monkeypatch):
    monkeypatch.delenv("SBV_SERVICE_PASS", raising=False)
    reg = _loaded_registry()
    candidates = reg.resolve("parse.sms-xml", media_hint="a.xml", size_bytes=10)
    assert candidates, "pure-Python parser must always accept .xml"
    assert candidates[0].id == "messages.sms-xml"
    assert "messages.sms-xml-sbv" not in [t.id for t in candidates]


def test_sbv_primary_has_no_primary_enabled_gate(monkeypatch):
    """D-040: SBV_PRIMARY_ENABLED no longer gates anything — SBV_SERVICE_PASS
    is the only gate now. Setting the old env var (even to a value that would
    previously have DISABLED SBV) must have zero effect on resolution."""
    monkeypatch.setenv("SBV_SERVICE_PASS", "x")
    monkeypatch.delenv("SBV_PRIMARY_ENABLED", raising=False)
    reg = _loaded_registry()
    baseline = [t.id for t in reg.resolve("parse.sms-xml", media_hint="a.xml", size_bytes=10)]
    assert baseline == ["messages.sms-xml-sbv", "messages.sms-xml"]

    monkeypatch.setenv("SBV_PRIMARY_ENABLED", "0")
    with_stale_env_set = [t.id for t in reg.resolve("parse.sms-xml", media_hint="a.xml", size_bytes=10)]
    assert with_stale_env_set == baseline


def test_sbv_gated_off_still_fetchable_by_id(monkeypatch):
    """Even when SBV won't be chosen automatically, it must stay directly
    addressable by tool id (a caller can still force it)."""
    monkeypatch.delenv("SBV_SERVICE_PASS", raising=False)
    reg = _loaded_registry()
    assert reg.get("messages.sms-xml-sbv").id == "messages.sms-xml-sbv"


# ---- forensic guarantee: bodyless-media retention (the 516-dropped-MMS lesson) ----


def test_universal_record_keeps_bodyless_media_row():
    """`_map_universal_record` must never drop a row for lacking body text —
    it always projects whatever SBV accepted; content=None becomes "", never
    a dropped record. Mirrors the pure-Python fallback's own fix below."""
    row = {
        "kind": "message",
        "content": None,  # SBV returns no content for an attachment-only MMS
        "occurred_at": "2023-11-14T22:13:20+00:00",
        "participants": ["+15551234567"],
        "seq": 3,
        "metadata": {"Type": "1", "Address": "+15551234567"},
    }
    rec = _map_universal_record(row, import_id=1, attachments_by_seq={3: [{"id": 9, "mime_type": "image/jpeg"}]})
    assert rec is not None
    assert rec.content == ""
    assert rec.attrs["attachment_count"] == 1


def test_sms_xml_keeps_attachment_only_mms(tmp_path):
    xml = """<smses count="1">
      <mms address="+15551234567" date="1700000000000" type="1">
        <parts><part ct="image/jpeg" cl="a.jpg" data="QUJDREVGRw=="/></parts>
      </mms>
    </smses>"""
    result = _run_sms_xml(tmp_path, "mms.xml", xml)
    assert result["stats"]["messages"] == 1
    rec = result["records"][0]
    assert rec["content"] == ""
    assert rec["attrs"]["body_present"] is False
    assert rec["attrs"]["attachment_count"] == 1


def test_sms_xml_bodyless_with_counterparty_kept_as_empty_body():
    rec = _map_sms({"address": "+15551234567", "type": "1"}, body="")
    assert rec is not None
    assert rec.attrs["body_present"] is False
    assert rec.attrs["empty_body"] is True


def test_sms_xml_bodyless_no_anchor_is_dropped():
    """Only a record with NEITHER a timestamp NOR a counterparty is unusable."""
    assert _map_sms({"type": "1"}, body="") is None


# ---- forensic guarantee: outbound role for types 2/4/5/6 ----------------------


def test_universal_record_outbound_types_map_to_owner_role():
    for t in ("2", "4", "5", "6"):
        row = {
            "kind": "message",
            "content": "hi",
            "participants": ["+15551234567"],
            # No "role"/"sender" key — matches the LIVE metadata shape SBV's
            # Go importer actually emits for SMS-XML (structMetadata(source)
            # over the raw XML entry; see vendored/sbv/internal/
            # sms_xml_importer.go). Relying on an explicit role/sender key
            # here would test a shape SBV never sends for this format.
            "metadata": {"Type": t, "Address": "+15551234567"},
        }
        rec = _map_universal_record(row, import_id=1, attachments_by_seq={})
        assert rec.role == sbv_sms.OWNER, f"type {t} must be owner-authored"

    inbound = _map_universal_record(
        {"kind": "message", "content": "hi", "participants": ["+15551234567"], "metadata": {"Type": "1"}},
        import_id=1,
        attachments_by_seq={},
    )
    assert inbound.role != sbv_sms.OWNER


def test_universal_record_role_prefers_explicit_metadata_over_type_fallback():
    row = {
        "kind": "message",
        "content": "hi",
        "participants": ["+15551234567"],
        "metadata": {"Type": "1", "role": "someone_else"},
    }
    rec = _map_universal_record(row, import_id=1, attachments_by_seq={})
    assert rec.role == "someone_else"


def test_universal_record_call_outbound_type_maps_to_owner_role():
    row = {"kind": "call", "content": "", "participants": ["+15551234567"], "metadata": {"Type": "2"}}
    rec = _map_universal_record(row, import_id=1, attachments_by_seq={})
    assert rec.role == sbv_sms.OWNER


def test_sms_xml_outbound_types_map_to_owner_role():
    for t in ("2", "4", "5", "6"):
        rec = _map_sms({"type": t, "address": "+15551234567"}, body="hi")
        assert rec.role == sms_xml.OWNER, f"type {t} must be owner-authored"
    inbound = _map_sms({"type": "1", "address": "+15551234567"}, body="hi")
    assert inbound.role != sms_xml.OWNER
