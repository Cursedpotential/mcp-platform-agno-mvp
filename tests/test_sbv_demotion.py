"""SBV demotion (2026-08-02, parser-gap review P0) — registry + mapper parity.

Byline: Claude Code . Fable 5 . 2026-08-02

The review found the SBV path reads the service account's whole persistent
corpus after upload (false-provenance risk), so SBV must not be auto-selected
until import-scoped reads exist. These tests pin the gate and the mapper fixes
that make SBV's shadow output equivalent to the pure-Python parser (bodyless
retention per the 516-dropped-MMS lesson; outbound role for types 2/4/5/6).
"""

from __future__ import annotations

from server.tools import registry as registry_mod
from server.tools.parsers.messaging import sbv_sms
from server.tools.parsers.messaging.sbv_sms import _map_message
from server.tools.registry import load_builtin_tools


def _loaded_registry():
    load_builtin_tools()
    return registry_mod.registry


def test_sbv_not_resolved_without_primary_override(monkeypatch):
    monkeypatch.setenv("SBV_SERVICE_PASS", "x")
    monkeypatch.delenv("SBV_PRIMARY_ENABLED", raising=False)
    reg = _loaded_registry()
    candidates = reg.resolve("parse.sms-xml", media_hint="a.xml", size_bytes=10)
    assert candidates, "pure-Python parser must always accept .xml"
    assert candidates[0].id == "messages.sms-xml"
    assert "messages.sms-xml-sbv" not in [t.id for t in candidates]


def test_sbv_resolves_first_with_explicit_override(monkeypatch):
    monkeypatch.setenv("SBV_SERVICE_PASS", "x")
    monkeypatch.setenv("SBV_PRIMARY_ENABLED", "1")
    reg = _loaded_registry()
    candidates = reg.resolve("parse.sms-xml", media_hint="a.xml", size_bytes=10)
    assert candidates[0].id == "messages.sms-xml-sbv"


def test_gated_off_sbv_still_fetchable_by_id(monkeypatch):
    monkeypatch.delenv("SBV_PRIMARY_ENABLED", raising=False)
    monkeypatch.delenv("SBV_SERVICE_PASS", raising=False)
    reg = _loaded_registry()
    assert reg.get("messages.sms-xml-sbv").id == "messages.sms-xml-sbv"


def test_bodyless_media_message_is_kept():
    rec = _map_message(
        {"body": "", "type": "1", "date": 1700000000000, "address": "+15551234567",
         "media_type": "image/jpeg"}
    )
    assert rec is not None
    assert rec.content == ""
    assert rec.attrs["body_present"] is False
    assert rec.attrs["attachment_count"] == 1
    assert rec.attrs["channel"] == "mms"


def test_bodyless_no_anchor_is_dropped():
    assert _map_message({"body": "null", "type": "1"}) is None


def test_bodyless_with_counterparty_kept_as_empty_body():
    rec = _map_message({"body": "", "type": "1", "address": "+15551234567"})
    assert rec is not None
    assert rec.attrs["body_present"] is False
    assert rec.attrs["empty_body"] is True


def test_outbound_types_map_to_owner_role():
    for t in ("2", "4", "5", "6"):
        rec = _map_message({"body": "hi", "type": t, "address": "+15551234567"})
        assert rec.role == sbv_sms.OWNER, f"type {t} must be owner-authored"
    inbound = _map_message({"body": "hi", "type": "1", "address": "+15551234567"})
    assert inbound.role != sbv_sms.OWNER
