"""Tests for the damaged-file lifecycle: rewrite, flag, quarantine.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

Owner directive 2026-08-02: write a repaired file and quarantine the damaged
one, or at minimum flag it so it stops being re-parsed. These tests pin the
safety properties of all three, especially the ones that protect originals.
"""

from __future__ import annotations

import json

import pytest

from server.tools.repair import (
    DamageLedger,
    RepairReport,
    flag_damaged,
    handle_damaged,
    iter_chunks,
    plan_quarantine,
    quarantine_file,
    sha256_file,
    write_repaired,
)

pytest.importorskip("lxml")

ROW = '<sms address="+1555000{n}" date="17000000000{n}0" type="1" body="hello {n}" />'


def _damaged_xml(tmp_path, name="s.xml"):
    p = tmp_path / name
    body = "\n".join(ROW.format(n=i) for i in range(8))
    p.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<smses>\n{body}\n</smses>\n',
                 encoding="utf-8")
    p.write_bytes(p.read_bytes().replace(b'body="hello 3"', b'body="bad \x0b\x1f"', 1))
    return p


# ------------------------------------------------------------------- rewrite


def test_rewrite_xml_produces_a_clean_reparsable_file(tmp_path):
    src = _damaged_xml(tmp_path)
    dest = tmp_path / "out" / "clean.xml"

    rep = write_repaired(src, dest)
    assert dest.exists()

    # the rewritten file parses with NO recovery errors at all
    clean = RepairReport()
    chunks = list(iter_chunks(dest, report=clean))
    assert chunks
    assert clean.lossy_count == 0
    assert clean.clean
    assert len(chunks) == rep.chunks_ok


def test_rewrite_refuses_to_overwrite_the_original(tmp_path):
    src = _damaged_xml(tmp_path)
    with pytest.raises(ValueError, match="refuses to overwrite its input"):
        write_repaired(src, src, overwrite=True)


def test_rewrite_leaves_the_original_untouched(tmp_path):
    src = _damaged_xml(tmp_path)
    before = sha256_file(src)
    write_repaired(src, tmp_path / "clean.xml")
    assert sha256_file(src) == before


def test_rewrite_csv_keeps_overflow_fields_as_columns(tmp_path):
    src = tmp_path / "a.csv"
    src.write_text("a,b\n1,2\n3,4,SURPLUS\n", encoding="utf-8")
    dest = tmp_path / "clean.csv"
    write_repaired(src, dest)

    text = dest.read_text(encoding="utf-8")
    assert "SURPLUS" in text, "an extra field is real content and must survive a rewrite"


def test_rewrite_json_emits_valid_json(tmp_path):
    src = tmp_path / "a.json"
    src.write_text('{"messages": [{"c": "one"}, {"c": "two"}]}', encoding="utf-8")
    dest = tmp_path / "clean.json"
    write_repaired(src, dest)

    data = json.loads(dest.read_text(encoding="utf-8"))
    assert data == [{"c": "one"}, {"c": "two"}]


# -------------------------------------------------------------------- ledger


def test_flag_records_the_artifact_and_ingest_can_skip_it(tmp_path):
    src = _damaged_xml(tmp_path)
    ledger = DamageLedger(tmp_path / "ledger.jsonl")

    rep = RepairReport()
    list(iter_chunks(src, report=rep))
    entry = flag_damaged(src, rep, ledger=ledger)

    assert entry.status == "damaged"
    assert entry.skip_ingest
    assert ledger.should_skip(src) is True


def test_healthy_file_is_not_flagged(tmp_path):
    ledger = DamageLedger(tmp_path / "ledger.jsonl")
    good = tmp_path / "good.xml"
    good.write_text('<?xml version="1.0"?>\n<smses>\n<sms body="a"/>\n</smses>\n', encoding="utf-8")
    assert ledger.should_skip(good) is False


def test_ledger_is_append_only_and_latest_entry_wins(tmp_path):
    src = _damaged_xml(tmp_path)
    ledger = DamageLedger(tmp_path / "ledger.jsonl")

    rep = RepairReport()
    list(iter_chunks(src, report=rep))
    flag_damaged(src, rep, ledger=ledger)
    flag_damaged(src, rep, ledger=ledger, status="repaired", note="second pass")

    lines = (tmp_path / "ledger.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 2, "history must be preserved, not rewritten"
    assert ledger.by_sha(sha256_file(src)).status == "repaired"


def test_ledger_survives_a_malformed_line(tmp_path):
    """A damage ledger that dies on its own bad line is worse than useless."""
    path = tmp_path / "ledger.jsonl"
    path.write_text('{"not": "an entry"}\nnot json at all\n', encoding="utf-8")
    assert DamageLedger(path).entries() == {}


def test_ledger_keys_on_content_so_a_moved_file_stays_flagged(tmp_path):
    src = _damaged_xml(tmp_path)
    ledger = DamageLedger(tmp_path / "ledger.jsonl")
    rep = RepairReport()
    list(iter_chunks(src, report=rep))
    flag_damaged(src, rep, ledger=ledger)

    sha = sha256_file(src)
    moved = tmp_path / "elsewhere" / "renamed.xml"
    moved.parent.mkdir()
    moved.write_bytes(src.read_bytes())

    assert ledger.by_path(moved) is None          # path lookup misses
    assert ledger.by_sha(sha) is not None          # content lookup still finds it
    assert ledger.should_skip(moved, verify_hash=True) is True


# ---------------------------------------------------------------- quarantine


def test_quarantine_is_dry_run_by_default_and_moves_nothing(tmp_path):
    src = _damaged_xml(tmp_path)
    plan = plan_quarantine([src], tmp_path / "q", tmp_path)[0]

    assert quarantine_file(plan) is None
    assert src.exists(), "dry run must never move the original"
    assert not plan.dest.exists()


def test_quarantine_plan_is_a_full_manifest(tmp_path):
    src = _damaged_xml(tmp_path)
    plan = plan_quarantine([src], tmp_path / "q", tmp_path)[0]
    assert plan.sha256 == sha256_file(src)
    assert plan.size == src.stat().st_size
    assert plan.dest == tmp_path / "q" / src.name


def test_quarantine_executes_only_when_explicitly_told(tmp_path):
    src = _damaged_xml(tmp_path)
    original = sha256_file(src)
    ledger = DamageLedger(tmp_path / "ledger.jsonl")

    plan = plan_quarantine([src], tmp_path / "q", tmp_path)[0]
    entry = quarantine_file(plan, ledger=ledger, dry_run=False)

    assert entry is not None and entry.status == "quarantined"
    assert not src.exists(), "the original was moved"
    assert plan.dest.exists()
    assert sha256_file(plan.dest) == original, "quarantine must be byte-identical"


def test_quarantine_refuses_to_clobber_an_existing_target(tmp_path):
    src = _damaged_xml(tmp_path)
    plan = plan_quarantine([src], tmp_path / "q", tmp_path)[0]
    plan.dest.parent.mkdir(parents=True)
    plan.dest.write_text("something already here", encoding="utf-8")

    with pytest.raises(FileExistsError):
        quarantine_file(plan, dry_run=False)
    assert src.exists(), "a refused quarantine must leave the original in place"


# ------------------------------------------------------------- orchestration


def test_handle_damaged_flags_and_rewrites_without_quarantining(tmp_path):
    src = _damaged_xml(tmp_path)
    ledger = DamageLedger(tmp_path / "ledger.jsonl")
    rep = RepairReport()
    list(iter_chunks(src, report=rep))

    entry = handle_damaged(src, rep, repaired_dir=tmp_path / "repaired", ledger=ledger)

    assert entry.status == "repaired"
    assert entry.repaired_path and (tmp_path / "repaired" / src.name).exists()
    assert entry.repaired_sha256 != entry.sha256
    assert src.exists(), "quarantine is opt-in; the original stays put by default"
