"""Tests for the explicit format/engine override surface (owner 2026-08-12,
Task 15: the operator explicitly specifies the FORMAT and the parse ENGINE per
ingest; explicit flags beat the detection router, invalid combos fail loudly,
and an explicit override NEVER silently falls back to the other engine — D-053).

DB-free and SBV-free, mirroring test_engine_dynamic_parse.py: the Go path is
exercised with a FakeSBVClient, and --dry-run CLI runs never touch Postgres.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

import server.analysis.context_chat_ingest as mod
from server.analysis.context_chat_ingest import parse_chat_export
from server.analysis.format_router import GO_IMPORTER_FORMATS, SIGNATURES, resolve_format_override
from server.analysis.sbv_transcript import parse_via_sbv
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
    """Stands in for the SBV Go service (same seam as test_engine_dynamic_parse.py)."""

    def __init__(self, rows):
        self._rows = rows
        self.import_calls: list[dict] = []

    def import_file(self, file_path, filename=None, format=None):
        self.import_calls.append({"file_path": file_path, "filename": filename, "format": format})
        return {"import_id": 42}

    def wait_for_import(self, import_id, timeout_s=600.0):
        assert import_id == 42
        return {"status": "completed"}

    def import_records(self, import_id, **kw):
        assert import_id == 42
        return self._rows


def _fake_sbv(monkeypatch, rows=None):
    """Patch the dispatcher's Go path onto a FakeSBVClient; returns the fake."""
    rows = rows or [
        {
            "kind": "message",
            "content": "hello from go",
            "occurred_at": "2026-01-01T10:00:00Z",
            "format": "chatgpt-official-json",
            "metadata": {"conversation_id": "c-9", "role": "user"},
        },
    ]
    fake = FakeSBVClient(rows)
    monkeypatch.setattr(
        "server.analysis.sbv_transcript.parse_via_sbv",
        lambda path, *, format=None, source_meta=None: parse_via_sbv(
            path, format=format, source_meta=source_meta, client=fake
        ),
    )
    return fake


# ---------------------------------------------------------------------------
# mirror integrity: GO_IMPORTER_FORMATS must stay in sync with the Go registry
# ---------------------------------------------------------------------------


def test_go_format_mirror_matches_router_signatures():
    """Every SIGNATURES go_format must appear in GO_IMPORTER_FORMATS — the
    mirror of vendored/sbv/internal/importer.go the override validates against."""
    for sig in SIGNATURES:
        if sig.go_format:
            assert sig.go_format in GO_IMPORTER_FORMATS


# ---------------------------------------------------------------------------
# resolver semantics (pure, no files)
# ---------------------------------------------------------------------------


def test_resolve_router_format_id_is_go_primary_when_go_decoder_exists():
    engine, go_id, py_id = resolve_format_override("chatgpt-official", "auto")
    assert (engine, go_id, py_id) == ("go", "chatgpt-official-json", None)


def test_resolve_router_format_id_falls_to_python_when_no_go_decoder():
    engine, go_id, py_id = resolve_format_override("claude-ai-export", "auto")
    assert (engine, go_id, py_id) == ("python", None, "transcripts.claude-ai-export")


def test_resolve_go_importer_id_and_python_tool_id_spellings():
    assert resolve_format_override("chatgpt-official-json", "auto") == ("go", "chatgpt-official-json", None)
    assert resolve_format_override("transcripts.claude-ai-export", "auto") == (
        "python",
        None,
        "transcripts.claude-ai-export",
    )


def test_resolve_engine_go_rejects_python_only_format():
    with pytest.raises(ValueError, match="no SBV decoder"):
        resolve_format_override("claude-ai-export", "go")


def test_resolve_engine_python_rejects_go_importer_id():
    with pytest.raises(ValueError, match="no parser"):
        resolve_format_override("chatgpt-official-json", "python")


def test_resolve_unknown_format_lists_known_values():
    with pytest.raises(ValueError, match="unknown format override"):
        resolve_format_override("whatsapp-desktop", "auto")


# ---------------------------------------------------------------------------
# dispatcher: explicit --format bypasses the detection router, strictly
# ---------------------------------------------------------------------------


def test_format_override_bypasses_detection_router(tmp_path, monkeypatch):
    """With an explicit format, detect_format must NEVER run."""
    f = _claude_export(tmp_path)
    monkeypatch.setattr(
        "server.analysis.format_router.detect_format",
        lambda *a, **kw: pytest.fail("detect_format ran under an explicit --format override"),
    )
    records, parser_id, attempts = parse_chat_export(f, engine="auto", format="claude-ai-export")
    assert parser_id == "transcripts.claude-ai-export"
    assert len(records) == 2
    assert attempts == [{"tool": "transcripts.claude-ai-export", "ok": True}]


def test_format_override_pinned_parser_even_in_python_engine(tmp_path, monkeypatch):
    """--engine python --format pins ONE parser (no registry mesh)."""
    f = _claude_export(tmp_path)
    records, parser_id, _ = parse_chat_export(f, engine="python", format="transcripts.claude-ai-export")
    assert parser_id == "transcripts.claude-ai-export"
    assert len(records) == 2


def test_format_override_absent_means_router_runs(tmp_path, monkeypatch):
    """Flags absent => the D-051 router runs (precedence: explicit > router)."""
    f = _claude_export(tmp_path)
    from server.analysis import format_router

    calls = []
    real = format_router.detect_format
    monkeypatch.setattr(format_router, "detect_format", lambda *a, **kw: (calls.append(True), real(*a, **kw))[1])
    _, parser_id, _ = parse_chat_export(f, engine="auto")
    assert calls == [True]
    assert parser_id == "transcripts.claude-ai-export"  # claude sig routes to python


def test_format_override_routes_to_go_when_decoder_exists(tmp_path, monkeypatch):
    f = _claude_export(tmp_path)
    fake = _fake_sbv(monkeypatch)
    records, parser_id, _ = parse_chat_export(f, engine="auto", format="chatgpt-official")
    assert parser_id == "sbv-go:chatgpt-official-json"
    assert records[0].content == "hello from go"
    assert fake.import_calls[0]["format"] == "chatgpt-official-json"


# ---------------------------------------------------------------------------
# loud errors: an explicit override never falls back to anything
# ---------------------------------------------------------------------------


def test_engine_go_with_python_only_format_errors_before_any_sbv_call(tmp_path, monkeypatch):
    f = _claude_export(tmp_path)
    monkeypatch.setattr(
        "server.analysis.sbv_transcript.parse_via_sbv",
        lambda *a, **kw: pytest.fail("SBV must not be called for a rejected go/format combo"),
    )
    with pytest.raises(ValueError, match="no SBV decoder"):
        parse_chat_export(f, engine="go", format="claude-ai-export")


def test_engine_python_with_go_only_format_errors_without_parsing(tmp_path):
    f = _claude_export(tmp_path)
    with pytest.raises(ValueError, match="no parser"):
        parse_chat_export(f, engine="python", format="chatgpt-official-json")


def test_unknown_format_override_errors_without_parsing(tmp_path):
    f = _claude_export(tmp_path)
    with pytest.raises(ValueError, match="unknown format override"):
        parse_chat_export(f, engine="auto", format="whatsapp-desktop")


def test_unknown_python_parser_id_errors_listing_registered(tmp_path):
    f = _claude_export(tmp_path)
    with pytest.raises(ValueError, match="unknown python parser 'transcripts.no-such-parser'"):
        parse_chat_export(f, engine="python", format="transcripts.no-such-parser")


def test_pinned_parser_rejection_is_loud_no_mesh_fallback(tmp_path, monkeypatch):
    """A pinned parser that rejects the file raises; the rest of the registry
    mesh must NOT be tried (that would be a silent format swap)."""
    f = _claude_export(tmp_path)
    tool = mod.registry.get("transcripts.claude-ai-export")
    tried: list[str] = []

    def _reject(payload):
        tried.append(tool.id)
        raise RuntimeError("not a claude export")

    monkeypatch.setattr(tool, "fn", _reject)
    with pytest.raises(ValueError, match="rejected .* under the explicit format override"):
        parse_chat_export(f, engine="python", format="claude-ai-export")
    assert tried == ["transcripts.claude-ai-export"]  # exactly one parser ran


def test_explicit_go_without_format_still_delegates_detection_to_sbv(tmp_path, monkeypatch):
    """--engine go with NO --format hands detection to SBV itself (format=None)
    — unchanged D-049 behavior, pinned here so the override work can't regress it."""
    f = _claude_export(tmp_path)
    fake = _fake_sbv(monkeypatch)
    records, parser_id, _ = parse_chat_export(f, engine="go")
    assert fake.import_calls[0]["format"] is None
    assert parser_id == "sbv-go:auto-detect"
    assert len(records) == 1


def test_unknown_engine_still_raises(tmp_path):
    f = _claude_export(tmp_path)
    with pytest.raises(ValueError, match="unknown engine"):
        parse_chat_export(f, engine="rust", format="claude-ai-export")


# ---------------------------------------------------------------------------
# CLI surface: argparse validation + fail-fast exit 2
# ---------------------------------------------------------------------------


def _load_cli():
    """Import scripts/ingest_context_chat.py as a module (scripts/ is not a package)."""
    path = Path(__file__).resolve().parents[1] / "scripts" / "ingest_context_chat.py"
    spec = importlib.util.spec_from_file_location("ingest_context_chat_cli", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_rejects_invalid_engine_with_argparse_exit_2(tmp_path):
    cli = _load_cli()
    with pytest.raises(SystemExit) as excinfo:
        cli._parse_args([str(tmp_path / "x.json"), "--engine", "rust"])
    assert excinfo.value.code == 2


def test_cli_rejects_unknown_format_with_exit_2_and_clear_error(tmp_path, capsys):
    cli = _load_cli()
    f = _claude_export(tmp_path)
    rc = cli.main([str(f), "--dry-run", "--format", "whatsapp-desktop"])
    assert rc == 2
    assert "unknown format override" in capsys.readouterr().err


def test_cli_rejects_go_python_only_format_combo_with_exit_2(tmp_path, capsys):
    cli = _load_cli()
    f = _claude_export(tmp_path)
    rc = cli.main([str(f), "--dry-run", "--engine", "go", "--format", "claude-ai-export"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "error:" in err and "no SBV decoder" in err


def test_cli_explicit_format_python_dry_run_succeeds(tmp_path, capsys):
    """The full CLI path with flags present: parse pinned, dry-run, DB-free."""
    cli = _load_cli()
    f = _claude_export(tmp_path)
    rc = cli.main([str(f), "--dry-run", "--engine", "python", "--format", "claude-ai-export"])
    assert rc == 0
    report = json.loads(capsys.readouterr().out)
    assert report["parser_id"] == "transcripts.claude-ai-export"
    assert report["record_count"] == 2
    assert report["records_stored"] == 0
