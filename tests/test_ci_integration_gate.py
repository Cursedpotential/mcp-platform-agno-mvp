"""Tests for scripts/ci_integration_gate.py (GAP-021).

Fixture-only: parses static JUnit XML files, no pytest subprocess, no live
service. Exercises the "all tests skip = still green" loophole this gate
exists to close, the file-path category heuristic, and the receipt shape.
Not marked `integration` — this suite proves the gate's own logic and must
run in the default (non-live) job so the gate is validated before CI ever
depends on it against real services.
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-26

from __future__ import annotations

import json
from pathlib import Path

from scripts.ci_integration_gate import build_receipt, categorize, main, parse_junit, summarize

FIXTURES = Path(__file__).parent / "fixtures" / "ci_integration_gate"


def test_categorize_matches_known_hints() -> None:
    assert categorize("tests/integration/test_ingest_scratch_live.py::test_x") == "horizon"
    assert categorize("tests.test_schema_docs_current::test_y") == "store"
    assert categorize("tests.test_timeline_projection::test_z") == "walk"
    assert categorize("tests.test_custody_canon_vectors::test_w") == "custody"
    assert categorize("tests.test_something_unrelated::test_v") == "other"


def test_parse_junit_all_skipped() -> None:
    results = parse_junit(FIXTURES / "all_skipped.xml")
    assert len(results) == 2
    assert all(r.outcome == "skipped" for r in results)


def test_summarize_fails_gate_when_all_skipped() -> None:
    summary = summarize(parse_junit(FIXTURES / "all_skipped.xml"))
    assert summary.total == 2
    assert summary.counts["passed"] == 0
    assert summary.gate_passed is False


def test_summarize_fails_gate_when_zero_collected() -> None:
    summary = summarize(parse_junit(FIXTURES / "empty.xml"))
    assert summary.total == 0
    assert summary.gate_passed is False


def test_summarize_fails_gate_on_any_failure() -> None:
    summary = summarize(parse_junit(FIXTURES / "mixed_pass_fail.xml"))
    assert summary.counts["passed"] >= 1
    assert summary.counts["failed"] >= 1
    assert summary.gate_passed is False


def test_summarize_passes_gate_when_all_passed() -> None:
    summary = summarize(parse_junit(FIXTURES / "all_passed.xml"))
    assert summary.total == summary.counts["passed"] > 0
    assert summary.gate_passed is True


def test_summarize_categorizes_the_tracked_live_suite() -> None:
    summary = summarize(parse_junit(FIXTURES / "all_passed.xml"))
    assert set(summary.by_category) == {"store", "horizon", "walk"}


def test_build_receipt_contains_no_secret_shaped_fields() -> None:
    results = parse_junit(FIXTURES / "all_passed.xml")
    summary = summarize(results)
    receipt = build_receipt(
        results, summary, git_sha="deadbeef", run_url=None, generated_at="2026-08-26T00:00:00+00:00"
    )
    assert receipt["gap"] == "GAP-021"
    assert receipt["gate_passed"] is True
    blob = json.dumps(receipt)
    assert "DB_PASS" not in blob
    assert "secret" not in blob.lower()


def test_main_exits_nonzero_on_all_skipped(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    code = main(["--junit", str(FIXTURES / "all_skipped.xml"), "--receipt", str(receipt_path)])
    assert code == 1
    written = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert written["gate_passed"] is False


def test_main_exits_zero_on_all_passed(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    code = main(["--junit", str(FIXTURES / "all_passed.xml"), "--receipt", str(receipt_path)])
    assert code == 0
    written = json.loads(receipt_path.read_text(encoding="utf-8"))
    assert written["gate_passed"] is True


def test_main_reports_missing_junit_file(tmp_path: Path) -> None:
    missing = tmp_path / "does-not-exist.xml"
    assert main(["--junit", str(missing)]) == 1
