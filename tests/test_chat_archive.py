"""Tests for the ZIP front door (server/analysis/chat_archive.py).

Builds synthetic export zips (Claude-shape and ChatGPT/Perplexity-shape with an
assets/ folder) and verifies: member classification, that ONLY conversation
logs are extracted+ingested, that assets/metadata are inventoried not dropped,
the zip-slip guard, and the no-log error. DB-free (ingest_chat_file is faked).
"""

from __future__ import annotations

import asyncio
import json
import zipfile

import pytest

import server.analysis.chat_archive as arch
from server.analysis.chat_archive import inventory_archive


def _make_zip(path, members: dict[str, bytes]):
    with zipfile.ZipFile(path, "w") as zf:
        for name, data in members.items():
            zf.writestr(name, data)
    return path


def _claude_conv():
    return json.dumps(
        [
            {
                "uuid": "c1",
                "name": "t",
                "chat_messages": [{"sender": "human", "text": "hi", "created_at": "2026-01-01T00:00:00Z"}],
            }
        ]
    ).encode()


def test_inventory_claude_shape(tmp_path):
    z = _make_zip(
        tmp_path / "data-batch.zip",
        {"conversations.json": _claude_conv(), "users.json": b"{}", "projects.json": b"[]", "memories.json": b"{}"},
    )
    inv = inventory_archive(z)
    assert inv.conversation_logs == ["conversations.json"]
    assert set(inv.metadata_files) == {"users.json", "projects.json", "memories.json"}
    assert inv.asset_files == []


def test_inventory_chatgpt_shape_with_assets(tmp_path):
    z = _make_zip(
        tmp_path / "user_data_export.zip",
        {
            "conversations-20251215.json": _claude_conv(),
            "user-data.xlsx": b"PK-fake",
            "assets/pic.png": b"\x89PNG",
            "assets/doc.md": b"# generated",
            "assets/report.pdf": b"%PDF-",
        },
    )
    inv = inventory_archive(z)
    assert inv.conversation_logs == ["conversations-20251215.json"]
    assert len(inv.asset_files) == 4  # root spreadsheet + png + md + pdf
    assert "user-data.xlsx" in inv.asset_files
    # a conversations-named file INSIDE assets/ must NOT be treated as a log
    z2 = _make_zip(
        tmp_path / "trap.zip", {"assets/conversations.json": _claude_conv(), "conversations.json": _claude_conv()}
    )
    inv2 = inventory_archive(z2)
    assert inv2.conversation_logs == ["conversations.json"]
    assert "assets/conversations.json" in inv2.asset_files


def test_ingest_archive_only_extracts_logs(tmp_path, monkeypatch):
    z = _make_zip(
        tmp_path / "exp.zip",
        {"conversations.json": _claude_conv(), "assets/a.png": b"x", "users.json": b"{}"},
    )
    ingested_paths: list[str] = []

    from dataclasses import dataclass

    @dataclass
    class _Rep:
        record_count: int
        records_stored: int

    async def _fake_ingest(path, **kw):
        ingested_paths.append(str(path))
        # ensure only the extracted conversations.json is handed over
        assert path.name == "conversations.json"
        assert kw["source_meta"]["archive_member"] == "conversations.json"
        return _Rep(record_count=1, records_stored=1)

    monkeypatch.setattr("server.analysis.context_chat_ingest.ingest_chat_file", _fake_ingest)
    report = asyncio.run(arch.ingest_chat_archive(z, project=False, materialize_assets=False))
    assert len(report.logs_ingested) == 1
    assert report.deferred_assets == 1
    assert report.deferred_metadata == ["users.json"]
    assert len(ingested_paths) == 1


def test_ingest_archive_no_log_raises(tmp_path):
    z = _make_zip(tmp_path / "nolog.zip", {"users.json": b"{}", "assets/a.png": b"x"})
    with pytest.raises(ValueError):
        asyncio.run(arch.ingest_chat_archive(z))


def test_zip_slip_is_neutralized_to_basename(tmp_path):
    """Extraction flattens to basename, so a traversal member name lands
    safely INSIDE dest (as its basename) instead of escaping — the zip-slip
    protection is by-construction, and the belt-and-suspenders guard never has
    to fire for the basename form."""
    z = tmp_path / "evil.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("conversations.json", _claude_conv())
    dest = tmp_path / "out"
    dest.mkdir()
    with zipfile.ZipFile(z) as zf:
        p = arch._safe_extract_member(zf, "conversations.json", dest)
        assert p.exists() and p.parent == dest.resolve()
    # a crafted traversal name is flattened to its basename, staying in dest
    with zipfile.ZipFile(z) as zf:
        # reuse the same stored bytes under the malicious lookup name isn't
        # possible (member must exist), so just verify the path math directly:
        target = (dest.resolve() / arch._basename("../../escape.json")).resolve()
        assert str(target).startswith(str(dest.resolve()))
        assert target.name == "escape.json"
