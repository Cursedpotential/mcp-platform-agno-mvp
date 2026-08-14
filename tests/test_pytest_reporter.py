"""Regression tests for mandatory itemized pytest reports.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from types import SimpleNamespace

from server.observability import pytest_reporter


def test_collection_failure_is_itemized():
    original_results = pytest_reporter._results
    pytest_reporter._results = {}
    try:
        report = SimpleNamespace(
            passed=False,
            skipped=False,
            failed=True,
            nodeid="tests/test_broken.py",
            longrepr="ImportError while importing test module\nModuleNotFoundError: missing_package",
            location=("tests/test_broken.py", 0, "tests/test_broken.py"),
            duration=0.125,
        )

        pytest_reporter.pytest_collectreport(report)
        built = pytest_reporter._build_report(exitstatus=2)

        assert built["output"]["failed"] == 1
        assert built["data"]["tests"][0]["phase"] == "collect"
        assert built["data"]["tests"][0]["id"] == "tests/test_broken.py [collection]"
        assert "missing_package" in built["errors"][0]["message"]
    finally:
        pytest_reporter._results = original_results


def test_default_outputs_are_unique_and_refresh_latest(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    original_state = (
        pytest_reporter._results,
        pytest_reporter._started_at,
        pytest_reporter._run_id,
        pytest_reporter._written_paths,
    )
    pytest_reporter._results = {}
    pytest_reporter._started_at = None
    pytest_reporter._run_id = None
    pytest_reporter._written_paths = None
    try:
        session = SimpleNamespace(config=SimpleNamespace(getoption=lambda _name: None))
        pytest_reporter.pytest_sessionstart(session)
        pytest_reporter.pytest_sessionfinish(session, exitstatus=0)

        report_dir = tmp_path / "build" / "test-reports"
        archives = list(report_dir.glob("pytest-*.json"))
        assert len(archives) == 1
        assert archives[0].with_suffix(".html").is_file()
        assert (report_dir / "latest.json").is_file()
        assert (report_dir / "latest.html").is_file()
    finally:
        (
            pytest_reporter._results,
            pytest_reporter._started_at,
            pytest_reporter._run_id,
            pytest_reporter._written_paths,
        ) = original_state
