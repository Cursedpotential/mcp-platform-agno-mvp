"""Tests for server/tools/repair — the streaming repair + chunking layer.

Byline: Claude Code . Opus 5 (1M) . 2026-08-02

Every fixture is synthesised in tmp_path. Nothing here reads the real corpus:
these tests must run in CI and must never depend on a file containing PII.

Several cases below are REGRESSION tests for bugs found while building this,
and each says so — they are the reason the module looks the way it does.
"""

from __future__ import annotations

import pytest

from server.tools.repair import (
    HEALTHY,
    LOSSY,
    RECONSTRUCTED,
    UNRECOVERABLE,
    Chunk,
    RepairEvent,
    RepairReport,
    available,
    detect,
    engine_for,
    inspect_pdf,
    iter_chunks,
    iter_csv,
    iter_json,
    manifest,
    repair_pdf,
)

pikepdf = pytest.importorskip("pikepdf", reason="structural PDF repair needs pikepdf")


# ------------------------------------------------------------------ fixtures


def _xml(tmp_path, body: str):
    p = tmp_path / "s.xml"
    p.write_text(f'<?xml version="1.0" encoding="UTF-8"?>\n<smses count="2">\n{body}\n</smses>\n',
                 encoding="utf-8")
    return p


ROW = '<sms address="+15550001" date="1700000000000" type="1" body="hello {n}" />'


def _tiny_pdf(tmp_path, name="ok.pdf"):
    p = tmp_path / name
    pdf = pikepdf.new()
    pdf.add_blank_page(page_size=(200, 200))
    pdf.add_blank_page(page_size=(200, 200))
    pdf.save(str(p))
    return p


# ----------------------------------------------------------------- severity


def test_report_clean_requires_no_loss_no_failure_no_truncation():
    rep = RepairReport()
    rep.record(Chunk(index=0, kind="row", node={}))
    assert rep.clean

    rep.record(Chunk(index=1, kind="row", node={},
                     repairs=[RepairEvent(kind="x", detail="d", severity=LOSSY)]))
    assert not rep.clean
    assert rep.lossy_count == 1


def test_failed_chunk_is_not_conflated_with_lossy():
    """An absent chunk and a degraded chunk are different facts.

    Conflating them is how a reconciliation ends up claiming a clean run.
    """
    rep = RepairReport()
    rep.record(Chunk(index=0, kind="row", node=None, ok=False, error="boom"))
    assert rep.chunks_failed == 1
    assert rep.lossy_count == 0
    assert not rep.clean


# ---------------------------------------------------------------- detection


def test_detects_xml_json_csv_ndjson(tmp_path):
    x = _xml(tmp_path, ROW.format(n=1))
    assert detect(x).fmt == "xml"

    j = tmp_path / "a.json"
    j.write_text('{"messages": [{"a": 1}]}', encoding="utf-8")
    assert detect(j).fmt == "json"

    c = tmp_path / "a.csv"
    c.write_text("a,b,c\n1,2,3\n4,5,6\n", encoding="utf-8")
    assert detect(c).fmt == "csv"

    n = tmp_path / "a.jsonl"
    n.write_text('{"a": 1}\n{"a": 2}\n{"a": 3}\n', encoding="utf-8")
    assert detect(n).fmt == "ndjson"


def test_content_beats_extension(tmp_path):
    """Extensions lie constantly in this corpus; content must win."""
    p = tmp_path / "actually_xml.csv"
    p.write_text('<?xml version="1.0"?><smses><sms body="x"/></smses>', encoding="utf-8")
    det = detect(p)
    assert det.fmt == "xml"
    assert any("extension" in note for note in det.notes)


def test_pdf_magic_number_detected(tmp_path):
    p = _tiny_pdf(tmp_path)
    assert detect(p).fmt == "pdf"


def test_tab_separated_is_csv_with_a_note(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("a\tb\tc\n1\t2\t3\n4\t5\t6\n", encoding="utf-8")
    det = detect(p)
    assert det.fmt == "csv"
    assert any("delimiter" in note for note in det.notes)


# ---------------------------------------------------------------------- xml


def test_xml_streams_all_records(tmp_path):
    body = "\n".join(ROW.format(n=i) for i in range(50))
    p = _xml(tmp_path, body)
    assert len(list(iter_chunks(p))) == 50


def test_xml_recovery_loss_is_reported_not_silent(tmp_path):
    """REGRESSION: recover=True DISCARDS what it cannot parse and never raises.

    A truncated element (attribute value cut off mid-tag, no closing `/>`)
    costs records while the iteration completed normally — the identical
    silent-loss shape as the 516 dropped body-less MMS. The loss is only
    visible in `ctx.error_log`, so the contract is that a short read MUST
    come with lossy events.

    NOTE 2026-08-09 (S2 requirements-regen task): the original fixture used a
    bare control character (\\x0b\\x1f) inside an attribute value. Under
    lxml 6.1.1 / libxml2 2.14.6 (pulled in by the requirements.txt regen that
    fixed the missing lxml/beautifulsoup4/pikepdf/etc. pins — see
    scripts/generate_requirements.sh), libxml2's recover=True now sanitises
    that specific damage in place instead of dropping the record, so the old
    fixture stopped exercising the loss path (which is exactly what its own
    assertion message told the next person to do: "pick harsher damage").
    Truncating the element itself (no closing `/>`) still forces libxml2 to
    skip past unparsable content and drop records under this and presumably
    future libxml2 versions, so it re-pins the guarantee this test protects.
    """
    body = "\n".join(ROW.format(n=i) for i in range(10))
    p = _xml(tmp_path, body)
    p.write_bytes(p.read_bytes().replace(
        b'<sms address="+15550001" date="1700000000000" type="1" body="hello 3" />',
        b'<sms address="+15550001" date="1700000000000" type="1" body="hello 3',
        1,
    ))

    rep = RepairReport()
    chunks = list(iter_chunks(p, fmt="xml", report=rep))

    assert len(chunks) < 10, "fixture no longer causes loss; pick harsher damage"
    assert rep.lossy_count > 0, "records were lost and NOTHING reported it"
    assert any(e.kind == "xml_recovery_error" for e in rep.events)
    assert not rep.clean


def test_xml_bare_ampersand_alone_is_absorbed(tmp_path):
    """A bare & is recoverable with no record loss — libxml2 keeps it as text."""
    body = "\n".join(ROW.format(n=i) for i in range(10))
    p = _xml(tmp_path, body)
    p.write_bytes(p.read_bytes().replace(b'body="hello 3"', b'body="Tom & Jerry"', 1))
    assert len(list(iter_chunks(p, fmt="xml"))) == 10


def test_xml_unclosed_root_still_yields_records(tmp_path):
    body = "\n".join(ROW.format(n=i) for i in range(10))
    p = _xml(tmp_path, body)
    p.write_bytes(p.read_bytes().replace(b"</smses>", b""))
    assert len(list(iter_chunks(p, fmt="xml"))) == 10


def test_xml_materialize_survives_the_loop(tmp_path):
    """REGRESSION: without materialize, collected elements come back emptied.

    That is the documented lifetime contract, not a bug — but callers that
    collect need the opt-out, so it must actually work.
    """
    from server.tools.repair import iter_xml

    p = _xml(tmp_path, "\n".join(ROW.format(n=i) for i in range(5)))

    streamed = [c.node for c in iter_xml(p)]
    assert all(not dict(e.attrib) for e in streamed)  # cleared, as documented

    kept = [c.node for c in iter_xml(p, materialize=True)]
    assert all(dict(e.attrib).get("address") for e in kept)


# --------------------------------------------------------------------- json


def test_json_picks_the_record_array_not_the_first_one(tmp_path):
    """REGRESSION: a Facebook Messenger export opens with `participants`.

    Selecting the first array in document order streamed 2 participants,
    reported a clean run, and returned data that were not messages at all.
    """
    p = tmp_path / "message_1.json"
    p.write_text(
        '{"participants": [{"name": "A"}, {"name": "B"}],'
        ' "messages": [{"content": "m1"}, {"content": "m2"}, {"content": "m3"}],'
        ' "magic_words": []}',
        encoding="utf-8",
    )
    chunks = list(iter_chunks(p))
    assert len(chunks) == 3
    assert all("content" in c.node for c in chunks)


def test_json_array_selection_is_recorded(tmp_path):
    """The choice of array is a decision and must be auditable, not silent."""
    p = tmp_path / "a.json"
    p.write_text('{"participants": [{"n": 1}], "messages": [{"c": "x"}]}', encoding="utf-8")
    rep = RepairReport()
    list(iter_json(p, report=rep))
    assert any(e.kind == "json_array_selected" for e in rep.events)


def test_json_top_level_array(tmp_path):
    p = tmp_path / "a.json"
    p.write_text('[{"a": 1}, {"a": 2}]', encoding="utf-8")
    assert len(list(iter_chunks(p))) == 2


def test_ndjson_bad_line_costs_only_that_line(tmp_path):
    p = tmp_path / "a.jsonl"
    p.write_text('{"a": 1}\n{"a": 2,}\n{"a": 3}\n', encoding="utf-8")
    rep = RepairReport()
    chunks = list(iter_chunks(p, report=rep))
    assert len(chunks) == 3
    assert rep.chunks_failed == 0


# ---------------------------------------------------------------------- csv


def test_csv_short_row_is_padded_not_dropped(tmp_path):
    p = tmp_path / "a.csv"
    p.write_text("a,b,c\n1,2,3\n4,5\n", encoding="utf-8")
    rep = RepairReport()
    chunks = list(iter_csv(p, report=rep))
    assert len(chunks) == 2
    assert chunks[1].node == {"a": "4", "b": "5", "c": ""}
    assert any(e.kind == "ragged_row_short" for e in rep.events)


def test_csv_long_row_preserves_extras_and_never_truncates(tmp_path):
    """An extra field usually means an unescaped delimiter inside real content.

    Dropping it would discard evidence, so extras are preserved.
    """
    p = tmp_path / "a.csv"
    p.write_text("a,b\n1,2\n3,4,SURPLUS\n", encoding="utf-8")
    rep = RepairReport()
    chunks = list(iter_csv(p, report=rep))
    assert chunks[1].node["__overflow__"] == ["SURPLUS"]
    assert any(e.kind == "ragged_row_long" for e in rep.events)
    assert rep.lossy_count == 0  # preserved, so nothing was lost


def test_csv_quoted_newline_is_one_row(tmp_path):
    """Row boundaries come from the csv reader, never from splitting on \\n."""
    p = tmp_path / "a.csv"
    p.write_text('a,b\n1,"line one\nline two"\n', encoding="utf-8")
    chunks = list(iter_csv(p))
    assert len(chunks) == 1
    assert "\n" in chunks[0].node["b"]


# ----------------------------------------------------------------- capability


def test_manifest_reports_every_format():
    formats = {m["format"] for m in manifest()}
    assert {"xml", "html", "json", "ndjson", "csv", "pdf"} <= formats


def test_available_reports_versions_not_booleans():
    caps = available()
    assert "lxml" in caps
    assert caps["lxml"] is None or isinstance(caps["lxml"], str)
    assert engine_for("xml") is not None
    assert engine_for("nonsense-format") is None


# ----------------------------------------------------------------------- pdf


def test_pdf_healthy_file_reports_healthy(tmp_path):
    assert inspect_pdf(_tiny_pdf(tmp_path)).status == HEALTHY


def test_pdf_damaged_xref_is_reported_not_swallowed(tmp_path):
    """REGRESSION: a rebuilt xref opens CLEANLY with the right page count.

    Reading qpdf recovery off the pikepdf logger or Python warnings captured
    NOTHING and reported `healthy` for a corrupted file. Pdf.get_warnings() is
    the only reliable source.
    """
    p = _tiny_pdf(tmp_path)
    p.write_bytes(p.read_bytes().replace(b"startxref", b"startxrefX", 1))
    health = inspect_pdf(p)
    assert health.status == RECONSTRUCTED
    assert health.warnings
    assert health.needs_repair


def test_pdf_mangled_header_is_caught_before_qpdf(tmp_path):
    """A broken %PDF- header is a content problem, not a structure problem.

    This started life asserting RECONSTRUCTED — gating status on a
    reconstruction-keyword allowlist had let "can't find PDF header" through as
    `healthy`. The content check now catches it earlier and more precisely: the
    file is not a PDF, so it needs re-acquisition rather than a repair attempt.
    The any-warning rule it originally guarded is still exercised by
    test_pdf_damaged_xref_is_reported_not_swallowed.
    """
    from server.tools.repair.pdf import NOT_PDF

    p = _tiny_pdf(tmp_path)
    p.write_bytes(b"%PDX-1.4" + p.read_bytes()[8:])
    health = inspect_pdf(p)
    assert health.status == NOT_PDF
    assert health.status != HEALTHY
    assert health.needs_reacquisition


def test_pdf_truncated_is_never_reported_healthy(tmp_path):
    """A truncated file must be flagged, but WHICH failure depends on survival.

    qpdf recovered a 50%-truncated blank 2-page PDF (its objects were all in
    the surviving half) while a real 80%-truncated document was unrecoverable.
    Asserting one specific status would encode an accident of the fixture, so
    the contract is only that it is never `healthy` and the missing %%EOF is
    seen.
    """
    p = _tiny_pdf(tmp_path)
    blob = p.read_bytes()
    p.write_bytes(blob[: int(len(blob) * 0.5)])
    health = inspect_pdf(p)
    assert health.status in (RECONSTRUCTED, UNRECOVERABLE)
    assert health.status != HEALTHY
    assert not health.has_eof
    assert health.needs_repair


def test_pdf_repair_produces_an_openable_file(tmp_path):
    p = _tiny_pdf(tmp_path)
    pages_before = inspect_pdf(p).pages
    p.write_bytes(p.read_bytes().replace(b"startxref", b"startxrefX", 1))

    dest = tmp_path / "out" / "fixed.pdf"
    result = repair_pdf(p, dest)

    assert result.ok
    assert result.pages_after == pages_before
    assert inspect_pdf(dest).status == HEALTHY
    assert result.source_sha256 != result.repaired_sha256


def test_zero_byte_pdf_is_empty_not_unrecoverable(tmp_path):
    """REGRESSION: 130 zero-byte files were reported as `unrecoverable`.

    True, but useless: it implies a repair attempt is worth making when there
    are no bytes to repair. These need RE-ACQUISITION, not QPDF.
    """
    from server.tools.repair.pdf import EMPTY

    p = tmp_path / "empty.pdf"
    p.write_bytes(b"")
    health = inspect_pdf(p)
    assert health.status == EMPTY
    assert health.needs_reacquisition
    assert not health.needs_repair


def test_html_saved_as_pdf_is_reported_as_wrong_content(tmp_path):
    """REGRESSION: downloads that returned an HTML error page, saved as .pdf.

    Three benchbooks in the corpus were exactly this. No repair can turn an
    HTML page into the PDF it was supposed to be.
    """
    from server.tools.repair.pdf import NOT_PDF

    p = tmp_path / "benchbook.pdf"
    p.write_bytes(b"\r\n<!DOCTYPE HTML>\r\n<html><body>Access denied</body></html>")
    health = inspect_pdf(p)
    assert health.status == NOT_PDF
    assert "html" in (health.error or "").lower()
    assert health.needs_reacquisition


def test_nul_filled_file_is_reported_as_wrong_content(tmp_path):
    from server.tools.repair.pdf import NOT_PDF

    p = tmp_path / "nul.pdf"
    p.write_bytes(b"\x00" * 4096)
    health = inspect_pdf(p)
    assert health.status == NOT_PDF
    assert "NUL" in (health.error or "")


def test_pdf_repair_refuses_to_overwrite_its_input(tmp_path):
    """The original is the custody anchor. In-place repair would destroy it."""
    p = _tiny_pdf(tmp_path)
    with pytest.raises(ValueError, match="refuses to write over its input"):
        repair_pdf(p, p, overwrite=True)


def test_pdf_repair_records_its_provenance(tmp_path):
    p = _tiny_pdf(tmp_path)
    p.write_bytes(p.read_bytes().replace(b"startxref", b"startxrefX", 1))
    result = repair_pdf(p, tmp_path / "fixed.pdf")

    prov = result.provenance()
    assert prov["source_sha256"] and prov["derived_sha256"]
    assert prov["source_sha256"] != prov["derived_sha256"]
    assert "qpdf" in prov["method"]
    assert prov["reconstructions"]


def test_pdf_original_is_never_modified(tmp_path):
    from server.tools.repair import sha256_file

    p = _tiny_pdf(tmp_path)
    p.write_bytes(p.read_bytes().replace(b"startxref", b"startxrefX", 1))
    before = sha256_file(p)

    repair_pdf(p, tmp_path / "fixed.pdf")
    assert sha256_file(p) == before
