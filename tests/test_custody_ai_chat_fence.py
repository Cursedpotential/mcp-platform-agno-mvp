"""D-082 permanent AI-chat evidence fence (GAP-032/WP-C01).

server/evidence/custody.py::ingest_artifact() is the sole writer of the
`evidence` schema (see its module docstring), so it is the single,
non-bypassable enforcement point: AI-chat exports must never reach evidence
custody, regardless of caller (REST, CLI, Temporal, the generic /v1/ingest
route). These are unit tests — the fence fires before ``_get_engine()`` is
ever called, so no live Postgres is needed to prove zero DB/blob writes;
monkeypatching ``_get_engine`` to raise proves the guard runs first.
"""

from __future__ import annotations

import json

import pytest

from server.evidence import custody
from server.evidence.custody import AIChatEvidenceDenied


@pytest.fixture
def blob_root(tmp_path, monkeypatch):
    root = tmp_path / "r2"
    monkeypatch.setenv("EVIDENCE_BLOB_ROOT", str(root))
    return root


@pytest.fixture
def no_db(monkeypatch):
    """Proves the fence fires before any DB access — a call reaching
    _get_engine() means the guard did not run first."""

    def _boom():
        raise AssertionError("ingest_artifact reached the DB engine — the D-082 fence did not fire first")

    monkeypatch.setattr(custody, "_get_engine", _boom)


# --- workflow-marker denial ---------------------------------------------------


def test_workflow_marker_denies_before_any_db_or_blob_write(blob_root, no_db, tmp_path):
    src = tmp_path / "transcript.txt"
    src.write_text("just plain text, not chat-shaped at all", encoding="utf-8")

    with pytest.raises(AIChatEvidenceDenied) as excinfo:
        custody.ingest_artifact(src, {"workflow": "chat-transcript"})

    assert excinfo.value.detected_by == "workflow-marker"
    assert "D-082" in excinfo.value.reason
    assert not blob_root.exists()  # denied before the write-once blob copy ever ran


def test_non_chat_workflow_marker_is_unaffected(blob_root, tmp_path, monkeypatch):
    """sms-xml (a real, non-AI-chat evidence vertical) must still reach the DB —
    the fence is source-class specific, not a blanket block on ingest_artifact."""
    reached = {"db": False}

    class _FakeEngine:
        def connect(self):
            reached["db"] = True
            raise RuntimeError("stop here — we only need to prove the guard let us reach the DB")

    monkeypatch.setattr(custody, "_get_engine", lambda: _FakeEngine())
    src = tmp_path / "backup.xml"
    src.write_text("<smses></smses>", encoding="utf-8")

    with pytest.raises(RuntimeError, match="stop here"):
        custody.ingest_artifact(src, {"workflow": "sms-xml"})

    assert reached["db"] is True


# --- content-sniff denial (no workflow marker present) ------------------------


def test_content_sniff_denies_chatgpt_export_shape(blob_root, no_db, tmp_path):
    src = tmp_path / "conversations.json"
    src.write_text(json.dumps([{"mapping": {}, "title": "a chat"}]), encoding="utf-8")

    with pytest.raises(AIChatEvidenceDenied) as excinfo:
        custody.ingest_artifact(src, {"source_type": "document"})  # no workflow marker at all

    assert excinfo.value.detected_by == "content-sniff"
    assert "mapping" in excinfo.value.reason


def test_content_sniff_denies_claude_ai_export_shape(blob_root, no_db, tmp_path):
    src = tmp_path / "claude_export.json"
    src.write_text(json.dumps({"chat_messages": [], "uuid": "x"}), encoding="utf-8")

    with pytest.raises(AIChatEvidenceDenied) as excinfo:
        custody.ingest_artifact(src)

    assert excinfo.value.detected_by == "content-sniff"
    assert "chat_messages" in excinfo.value.reason


def test_content_sniff_denies_claude_code_jsonl_session_shape(blob_root, no_db, tmp_path):
    src = tmp_path / "session.jsonl"
    src.write_text(json.dumps({"type": "user", "sessionId": "abc", "uuid": "1"}) + "\n", encoding="utf-8")

    with pytest.raises(AIChatEvidenceDenied) as excinfo:
        custody.ingest_artifact(src)

    assert excinfo.value.detected_by == "content-sniff"
    assert "Claude Code" in excinfo.value.reason


def test_content_sniff_ignores_unrelated_json(blob_root, tmp_path, monkeypatch):
    """A generic JSON evidence document (no mapping/chat_messages key) must not
    be denied — proves the sniff is narrow, not a blanket .json/.jsonl block."""
    reached = {"db": False}

    class _FakeEngine:
        def connect(self):
            reached["db"] = True
            raise RuntimeError("stop here")

    monkeypatch.setattr(custody, "_get_engine", lambda: _FakeEngine())
    src = tmp_path / "device_dump.json"
    src.write_text(json.dumps({"contacts": [], "calls": []}), encoding="utf-8")

    with pytest.raises(RuntimeError, match="stop here"):
        custody.ingest_artifact(src)

    assert reached["db"] is True


def test_content_sniff_only_applies_to_json_family(blob_root, tmp_path, monkeypatch):
    """Non-JSON evidence formats (PDF, media, SMS-XML) are never sniffed —
    zero extra I/O for the common evidence case."""
    reached = {"db": False}

    class _FakeEngine:
        def connect(self):
            reached["db"] = True
            raise RuntimeError("stop here")

    monkeypatch.setattr(custody, "_get_engine", lambda: _FakeEngine())
    src = tmp_path / "export.xml"
    # Even if the bytes happened to contain the word "mapping", .xml is never sniffed.
    src.write_text('<mapping key="chat_messages">not actually json</mapping>', encoding="utf-8")

    with pytest.raises(RuntimeError, match="stop here"):
        custody.ingest_artifact(src)

    assert reached["db"] is True


def test_looks_like_ai_chat_export_helper_returns_none_for_plain_text(tmp_path):
    src = tmp_path / "notes.json"
    src.write_text("not even valid json", encoding="utf-8")
    assert custody._looks_like_ai_chat_export(src) is None


def test_denial_reason_and_str_are_populated():
    exc = AIChatEvidenceDenied("some reason", detected_by="workflow-marker")
    assert str(exc) == "some reason"
    assert exc.reason == "some reason"
    assert exc.detected_by == "workflow-marker"
