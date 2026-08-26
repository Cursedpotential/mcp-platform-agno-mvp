"""D-082 permanent AI-chat evidence fence (GAP-032/WP-C01) — the
chat-transcript vertical (server/evidence/workflows.py) IS the AI-chat
ingestion path by definition, so its custody_step must deny unconditionally,
via ingest_artifact()'s workflow-marker check, before any DB/blob write —
and every caller that reaches it (server/api/evidence_routes.py, /v1/runs,
AgentOS's native POST /workflows/chat-transcript/runs, the CLI) inherits the
denial for free.

sms-xml (a real, non-AI-chat evidence vertical, Workflow A) is the negative
control proving the fence is source-class specific, not a blanket block on
every workflow's custody step.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from server.evidence import custody
from server.evidence.workflows import build_chat_transcript_workflow, build_sms_xml_workflow


@pytest.fixture
def blob_root(tmp_path, monkeypatch):
    root = tmp_path / "r2"
    monkeypatch.setenv("EVIDENCE_BLOB_ROOT", str(root))
    return root


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return self

    def first(self):
        return self._row

    def scalar(self):
        return self._row


class _FakeConn:
    def __init__(self, engine):
        self._engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, _stmt, _params=None):
        return _FakeResult(self._engine._next_row())


class _FakeEngine:
    def __init__(self, rows):
        self._rows = list(rows)
        self._i = 0

    def _next_row(self):
        row = self._rows[self._i]
        self._i += 1
        return row

    def connect(self):
        return _FakeConn(self)

    def begin(self):
        return _FakeConn(self)


def test_chat_transcript_custody_step_denies_before_any_db_write(blob_root, tmp_path, monkeypatch):
    def _boom():
        raise AssertionError("custody_step reached the DB engine — D-082 fence did not fire first")

    monkeypatch.setattr(custody, "_get_engine", _boom)

    # Plain .txt — would NOT trip the content sniff. This proves the
    # workflow-marker path denies on its own, regardless of file shape.
    src = tmp_path / "transcript.txt"
    src.write_text("hello", encoding="utf-8")

    wf, ctx = build_chat_transcript_workflow(str(src))
    custody_step = wf.steps[0].executor
    out = custody_step(None)

    assert out.success is False
    assert out.stop is True
    assert "DENIED" in out.content
    assert "D-082" in out.content
    assert ctx.get("ai_chat_denied_reason")
    assert "artifact" not in ctx


def test_chat_transcript_custody_step_denies_regardless_of_source_meta(blob_root, tmp_path, monkeypatch):
    """The caller's source_meta cannot spoof past the fence — custody_step
    hardcodes workflow="chat-transcript" itself, overriding anything the
    caller passed in."""

    def _boom():
        raise AssertionError("custody_step reached the DB engine")

    monkeypatch.setattr(custody, "_get_engine", _boom)
    src = tmp_path / "transcript.txt"
    src.write_text("hello", encoding="utf-8")

    wf, ctx = build_chat_transcript_workflow(str(src), source_meta={"workflow": "not-chat-transcript-at-all"})
    custody_step = wf.steps[0].executor
    out = custody_step(None)

    assert out.success is False
    assert "artifact" not in ctx


def test_sms_xml_custody_step_is_not_denied_by_the_ai_chat_fence(blob_root, tmp_path, monkeypatch):
    fake = _FakeEngine([None, 101, {"id": 42, "hashed_at": datetime(2026, 1, 1, tzinfo=timezone.utc)}])
    monkeypatch.setattr(custody, "_get_engine", lambda: fake)

    src = tmp_path / "backup.xml"
    src.write_text("<smses></smses>", encoding="utf-8")

    wf, ctx = build_sms_xml_workflow(str(src))
    custody_step = wf.steps[0].executor
    out = custody_step(None)

    assert out.success is True
    assert "artifact" in ctx
    assert ctx["artifact"].duplicate is False
