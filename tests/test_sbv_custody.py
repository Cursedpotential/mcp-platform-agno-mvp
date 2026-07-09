"""Unit tests for the SBV forensic reconciliation (Phase 4).

Cover the two custody outcomes without a live Postgres:
  * H1 match      -> a `verified` custody_event + H2/H3 evidence_hash rows.
  * H1 mismatch   -> an `integrity_violation` custody_event and NO derived rows
                     (SBV's H2/H3 are not trusted when the file hash disagrees).
Plus the sbv_sms wrapper: it passes SBV's hashes through to custody, and is a
clean no-op when the opt-in flag is unset or custody is unavailable.
"""

from __future__ import annotations

from typing import Any, cast

import pytest

from server.evidence import custody
from server.tools import sbv_sms
from server.tools._sbv_client import SBVClient


class _DummyConn:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _DummyEngine:
    def connect(self):
        return _DummyConn()


def _fake_ref(sha: str) -> custody.ArtifactRef:
    return custody.ArtifactRef(
        artifact_id="EH1",
        sha256=sha,
        source_ref="/orig/a.xml",
        blob_key="aa/aaaa/a.xml",
        size_bytes=10,
        duplicate=False,
        ingested_at="2026-07-09T00:00:00+00:00",
    )


@pytest.fixture
def capture(monkeypatch, tmp_path):
    """Patch out every DB touchpoint; capture the custody writes."""
    src = tmp_path / "a.xml"
    src.write_bytes(b"<smses count='0'></smses>")

    events: list[dict] = []
    hashes: list[dict] = []

    def _rec_event(source_id, event_type, actor, detail=None, evidence_hash_id=None, file_node_id=None):
        events.append({"source_id": source_id, "event_type": event_type, "actor": actor, "detail": detail})
        return "EV1"

    def _rec_hash(**kw):
        hashes.append(kw)
        return f"H{len(hashes)}"

    monkeypatch.setattr(custody, "_get_engine", lambda: _DummyEngine())
    monkeypatch.setattr(custody, "_source_id_for_hash", lambda conn, ehid: "SRC1")
    monkeypatch.setattr(custody, "record_custody_event", _rec_event)
    monkeypatch.setattr(custody, "record_evidence_hash", _rec_hash)
    return {"src": src, "events": events, "hashes": hashes}


def test_reconcile_verified_records_events_and_hashes(monkeypatch, capture):
    monkeypatch.setattr(custody, "ingest_artifact", lambda s, m: _fake_ref("abcd1234"))

    res = custody.reconcile_sbv_import(
        capture["src"],
        {"source_type": "chat_export"},
        sbv_file_hash="ABCD1234",  # case-insensitive match to our "abcd1234"
        sbv_record_hashes=["11aa", "22bb"],
        sbv_chain_hash="cc33",
    )

    assert res["verified"] is True
    assert res["event"] == "verified"
    # exactly one custody event, of type verified
    assert [e["event_type"] for e in capture["events"]] == ["verified"]
    # two H2 rows + one H3 row recorded, at the right levels
    levels = [h["level"] for h in capture["hashes"]]
    assert levels == ["H2", "H2", "H3"]
    assert capture["hashes"][0]["digest_hex"] == "11aa"
    assert capture["hashes"][-1]["digest_hex"] == "cc33"
    assert capture["hashes"][-1]["canon_version"] == custody.H3_CANON
    assert res["h2_hash_ids"] and res["h3_hash_id"]


def test_reconcile_mismatch_flags_integrity_violation(monkeypatch, capture):
    monkeypatch.setattr(custody, "ingest_artifact", lambda s, m: _fake_ref("abcd1234"))

    res = custody.reconcile_sbv_import(
        capture["src"],
        {},
        sbv_file_hash="ffffffff",  # DOES NOT match our H1
        sbv_record_hashes=["11aa", "22bb"],
        sbv_chain_hash="cc33",
    )

    assert res["verified"] is False
    assert res["event"] == "integrity_violation"
    assert [e["event_type"] for e in capture["events"]] == ["integrity_violation"]
    # On a file-hash mismatch we do NOT record SBV's derived H2/H3.
    assert capture["hashes"] == []
    assert res["h2_hash_ids"] == [] and res["h3_hash_id"] is None


def test_reconcile_missing_sbv_hash_is_violation(monkeypatch, capture):
    monkeypatch.setattr(custody, "ingest_artifact", lambda s, m: _fake_ref("abcd1234"))
    res = custody.reconcile_sbv_import(capture["src"], {}, sbv_file_hash=None)
    assert res["verified"] is False
    assert res["event"] == "integrity_violation"


# --- sbv_sms wrapper ----------------------------------------------------------


class _FakeSBVClient:
    def __init__(self, hashes: dict):
        self._hashes = hashes

    def hashes(self, import_id="latest"):
        return self._hashes


def _rec(content_hash: str):
    """Minimal stand-in with the .attrs the wrapper reads."""

    class _R:
        attrs = {"content_hash": content_hash}

    return _R()


def test_sbv_sms_reconcile_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("SBV_CUSTODY_ENABLED", raising=False)
    called = {"n": 0}
    monkeypatch.setattr(custody, "reconcile_sbv_import", lambda *a, **k: called.__setitem__("n", called["n"] + 1))
    client = cast(SBVClient, _FakeSBVClient({"file_hash": "x"}))
    out = sbv_sms._reconcile_custody(tmp_path / "a.xml", {}, client, cast(Any, [_rec("11")]))
    assert out is None
    assert called["n"] == 0  # opt-in only


def test_sbv_sms_reconcile_passes_sbv_hashes(monkeypatch, tmp_path):
    monkeypatch.setenv("SBV_CUSTODY_ENABLED", "1")
    seen: dict = {}

    def _capture(src, meta, *, sbv_file_hash, sbv_record_hashes, sbv_chain_hash):
        seen.update(
            sbv_file_hash=sbv_file_hash,
            sbv_record_hashes=sbv_record_hashes,
            sbv_chain_hash=sbv_chain_hash,
        )
        return {"verified": True}

    monkeypatch.setattr(custody, "reconcile_sbv_import", _capture)

    client = cast(SBVClient, _FakeSBVClient({"file_hash": "H1HEX", "chain_hash": "H3HEX", "record_count": 2}))
    records = cast(Any, [_rec("aa"), _rec("bb"), _rec("")])
    out = sbv_sms._reconcile_custody(tmp_path / "a.xml", {}, client, records)
    assert out == {"verified": True}
    assert seen["sbv_file_hash"] == "H1HEX"
    assert seen["sbv_chain_hash"] == "H3HEX"
    # empty content_hash entries are filtered out
    assert seen["sbv_record_hashes"] == ["aa", "bb"]
