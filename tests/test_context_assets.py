"""Tests for context asset classification + the dry-run cost preview
(server/analysis/context_assets.py). No DB / no R2 — the real upload path is
exercised by the live materialization run against a real export zip.
"""

from __future__ import annotations

import zipfile

from server.analysis.context_assets import _ext, _r2_key, categorize, materialize_archive


def test_categorize_routes_by_extension():
    assert categorize("assets/report.pdf") == "document"
    assert categorize("assets/notes.md") == "document"
    assert categorize("assets/script.py") == "code"
    assert categorize("assets/query.sql") == "code"
    assert categorize("assets/pic.png") == "image"
    assert categorize("assets/data.csv") == "data"
    assert categorize("assets/weird.xyz") == "other"


def test_ext_and_r2_key():
    assert _ext("a/b/c.PDF") == "pdf"
    assert _ext("noext") == ""
    key = _r2_key("abcd1234", "pdf")
    assert key == "context-assets/ab/abcd1234.pdf"
    assert _r2_key("ff00", "") == "context-assets/ff/ff00"


def test_dry_run_classifies_without_writing(tmp_path):
    z = tmp_path / "exp.zip"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("conversations.json", b"[]")
        zf.writestr("users.json", b"{}")
        zf.writestr("assets/a.pdf", b"%PDF-1")
        zf.writestr("assets/b.png", b"\x89PNG")
        zf.writestr("assets/c.py", b"print(1)")
        zf.writestr("assets/d.md", b"# doc")
    rep = materialize_archive(z, provider="perplexity", dry_run=True)
    assert rep.dry_run is True
    assert rep.asset_total == 4
    assert rep.by_category == {"document": 2, "image": 1, "code": 1}  # pdf+md, png, py
    assert rep.metadata_files == ["users.json"]
    assert rep.uploaded == 0  # dry-run never uploads
    assert rep.archive_sha256 == "(dry-run)"
