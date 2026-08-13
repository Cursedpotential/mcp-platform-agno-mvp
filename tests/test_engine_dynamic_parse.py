"""Tests for the engine-dynamic parse seam (owner 2026-08-12: the pipeline
must pull from EITHER the Go OR the Python parser, not be dedicated to one).

DB-free and SBV-free: the Go path is exercised with a fake SBVClient so the
dispatcher routing + the SBV-row -> NormalizedRecord mapping are verified
without a live SBV service.

Byline: Codex · GPT-5 · 2026-08-13 (lint-only import cleanup)
"""

from __future__ import annotations

import json

import pytest

from server.analysis.context_chat_ingest import parse_chat_export
from server.analysis.sbv_transcript import _row_to_record, parse_via_sbv
from server.tools.registry import load_builtin_tools


@pytest.fixture(autouse=True)
def _builtins():
    load_builtin_tools()


def _claude_export(tmp_path):
    f = tmp_path / "conversations.json"
    f.write_text(
        json.dumps(
            [
                {
                    "uuid": "conv-1",
                    "name": "pickup schedule",
                    "chat_messages": [
                        {"sender": "human", "text": "she moved pickup again", "created_at": "2026-01-01T10:00:00Z"},
                        {"sender": "assistant", "text": "log it.", "created_at": "2026-01-01T10:00:05Z"},
                    ],
                }
            ]
        ),
        encoding="utf-8",
    )
    return f


class FakeSBVClient:
    """Stands in for the SBV Go service: records the import call and returns
    canned canonical rows (as the real /imports/{id}/records would)."""

    def __init__(self, rows):
        self._rows = rows
        self.import_calls: list[dict] = []

    def import_file(self, file_path, filename=None, format=None):
        self.import_calls.append({"file_path": file_path, "filename": filename, "format": format})
        return {"import_id": 42}

    def wait_for_processing(self, timeout_s=600.0):
        return {"status": "completed"}

    def import_records(self, import_id, **kw):
        assert import_id == 42
        return self._rows


# ---------------------------------------------------------------------------
# dispatcher routing
# ---------------------------------------------------------------------------


def test_engine_python_uses_registry(tmp_path):
    f = _claude_export(tmp_path)
    records, parser_id, _ = parse_chat_export(f, engine="python")
    assert parser_id == "transcripts.claude-ai-export"  # a Python registry tool
    assert len(records) == 2


def test_engine_auto_defaults_to_python_for_mvp(tmp_path):
    f = _claude_export(tmp_path)
    _, parser_id, _ = parse_chat_export(f, engine="auto")
    assert parser_id == "transcripts.claude-ai-export"


def test_engine_go_routes_to_sbv(tmp_path, monkeypatch):
    f = _claude_export(tmp_path)
    rows = [
        {
            "kind": "message",
            "content": "hello from go",
            "occurred_at": "2026-01-01T10:00:00Z",
            "format": "chatgpt-official-json",
            "metadata": {"conversation_id": "c-9", "role": "user"},
        },
    ]
    fake = FakeSBVClient(rows)
    # parse_chat_export builds its own client; inject via parse_via_sbv's client kw
    # by patching the module-level import path the dispatcher calls.
    monkeypatch.setattr(
        "server.analysis.sbv_transcript.parse_via_sbv",
        lambda path, *, format=None, source_meta=None: parse_via_sbv(
            path, format=format, source_meta=source_meta, client=fake
        ),
    )
    records, parser_id, attempts = parse_chat_export(
        f,
        engine="go",
        format="chatgpt-official-json",
        source_meta={"archive": "export.zip", "archive_member": "conversations.json"},
    )
    assert parser_id == "sbv-go:chatgpt-official-json"
    assert len(records) == 1
    assert records[0].content == "hello from go"
    assert records[0].source == "chatgpt-official-json"
    assert records[0].attrs["archive"] == "export.zip"
    assert fake.import_calls[0]["format"] == "chatgpt-official-json"


def test_unknown_engine_raises(tmp_path):
    f = _claude_export(tmp_path)
    with pytest.raises(ValueError):
        parse_chat_export(f, engine="rust")


# ---------------------------------------------------------------------------
# SBV row -> NormalizedRecord mapping (chat-aware)
# ---------------------------------------------------------------------------


def test_row_to_record_pulls_chat_fields_from_metadata():
    row = {
        "kind": "message",
        "content": "she moved pickup again",
        "occurred_at": "2026-01-01T10:00:00Z",
        "format": "chatgpt-official-json",
        "participants": ["user"],
        "metadata": {"conversation_id": "conv-1", "conversation_title": "pickup schedule", "role": "user"},
    }
    rec = _row_to_record(row, "sbv-go")
    assert rec.source == "chatgpt-official-json"
    assert rec.conversation_id == "conv-1"
    assert rec.role == "user"
    assert rec.attrs["conversation_title"] == "pickup schedule"
    assert rec.attrs["engine"] == "go"
    assert rec.occurred_at is not None and rec.occurred_at.tzinfo is not None


def test_row_to_record_epoch_millis_timestamp():
    rec = _row_to_record({"content": "x", "occurred_at": 1735725600000, "metadata": {}}, "sbv-go")
    assert rec.occurred_at is not None and rec.occurred_at.year == 2025


def test_parse_via_sbv_skips_empty_content(tmp_path):
    f = tmp_path / "conversations.json"
    f.write_text("[]", encoding="utf-8")
    rows = [
        {"content": "keep", "metadata": {"role": "user"}},
        {"content": "   ", "metadata": {}},  # whitespace-only -> dropped
        {"content": "", "metadata": {}},  # empty -> dropped
    ]
    records, parser_id, attempts = parse_via_sbv(f, client=FakeSBVClient(rows))
    assert len(records) == 1
    assert records[0].content == "keep"
    assert attempts[0]["record_count"] == 1
