"""Mandatory JSON + interactive HTML reports for every first-party pytest run.

Generated reports live under ignored ``build/test-reports``. They enumerate
every test outcome and every skip reason; aggregate counts are never the only
record of what happened.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

_results: dict[str, dict[str, Any]] = {}
_started_at: datetime | None = None
_run_id: str | None = None
_written_paths: tuple[Path, Path] | None = None
_DISPLAY_TIME_ZONE = "America/New_York"
_DISPLAY_ZONE = ZoneInfo(_DISPLAY_TIME_ZONE)


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("durable-run-report")
    group.addoption("--run-report-json", default=None)
    group.addoption("--run-report-html", default=None)


def pytest_sessionstart(session: pytest.Session) -> None:
    global _run_id, _started_at, _written_paths
    _results.clear()
    _started_at = datetime.now(timezone.utc)
    _run_id = f"{_started_at.strftime('%Y%m%dT%H%M%S%fZ')}-{uuid4().hex[:8]}"
    _written_paths = None


def _reason(report: Any) -> str | None:
    if report.skipped:
        longrepr = report.longrepr
        if isinstance(longrepr, tuple) and len(longrepr) == 3:
            return str(longrepr[2])
    if report.failed:
        return str(report.longrepr).splitlines()[-1][:2000]
    return None


def pytest_runtest_logreport(report: pytest.TestReport) -> None:
    if report.when == "teardown" and report.passed:
        return
    if report.when == "setup" and report.passed:
        return
    status = "passed" if report.passed else "skipped" if report.skipped else "failed"
    path, line, _ = report.location
    _results[report.nodeid] = {
        "id": report.nodeid,
        "status": status,
        "phase": report.when,
        "reason": _reason(report),
        "duration_ms": round(report.duration * 1000, 3),
        "source": {"path": path.replace("\\", "/"), "line": (line or 0) + 1},
        "remediation": _remediation(_reason(report)),
    }


def pytest_collectreport(report: pytest.CollectReport) -> None:
    """Record collection failures/skips that never become test reports."""
    if report.passed:
        return
    status = "skipped" if report.skipped else "failed"
    location = getattr(report, "location", None)
    path = str(location[0]) if location else str(report.nodeid)
    line = (location[1] or 0) + 1 if location else 1
    reason = _reason(report)
    result_id = f"{report.nodeid} [collection]"
    _results[f"collection::{report.nodeid}"] = {
        "id": result_id,
        "status": status,
        "phase": "collect",
        "reason": reason,
        "duration_ms": round(getattr(report, "duration", 0.0) * 1000, 3),
        "source": {"path": path.replace("\\", "/"), "line": line},
        "remediation": _remediation(reason),
    }


def _remediation(reason: str | None) -> str | None:
    if not reason:
        return None
    if "CHAT_SAMPLE_DIR" in reason:
        return "Set CHAT_SAMPLE_DIR to the private Desktop corpus directory and rerun."
    if "scratch Postgres" in reason:
        return "Start/configure the scratch PostgreSQL test service, then rerun the audit-ledger tests."
    if "sqlparse" in reason:
        return "Install the declared development dependencies and rerun."
    return "Review the skip/failure reason and rerun the named test after resolving it."


def _build_report(exitstatus: int) -> dict[str, Any]:
    finished = datetime.now(timezone.utc)
    results = list(_results.values())
    counts = {"total": len(results), "passed": 0, "failed": 0, "skipped": 0}
    for result in results:
        counts[result["status"]] += 1
    errors = [
        {"code": "test_failed", "message": item["reason"] or item["id"], "test_id": item["id"]}
        for item in results
        if item["status"] == "failed"
    ]
    warnings = [
        {"code": "test_skipped", "message": item["reason"] or "No reason recorded", "test_id": item["id"]}
        for item in results
        if item["status"] == "skipped"
    ]
    duration_ms = round((finished - (_started_at or finished)).total_seconds() * 1000)
    return {
        "_comment": "Mandatory per-test report; aggregate counts never replace itemized outcomes.",
        "schema_version": "1.0",
        "pass": {
            "number": 1,
            "name": "pytest",
            "status": "COMPLETE" if exitstatus == 0 else "BLOCKED",
        },
        "metadata": {
            "timestamp": finished.isoformat(),
            "timestamp_display": finished.astimezone(_DISPLAY_ZONE).isoformat(),
            "display_timezone": _DISPLAY_TIME_ZONE,
            "platform": "Agno MCP Platform",
            "byline_revision": "Codex · GPT-5 · 2026-08-13",
            "duration_ms": duration_ms,
            "run_id": _run_id,
        },
        "input": {"runner": "pytest"},
        "output": counts,
        "errors": errors,
        "warnings": warnings,
        "handoff": {
            "status": "ready" if exitstatus == 0 else "review_required",
            "next_action": "Open the HTML report, inspect named outcomes, resolve prerequisites, and rerun.",
        },
        "data": {"summary": counts, "tests": results},
    }


def _write_html(report: dict[str, Any], path: Path) -> None:
    rows = []
    for item in report["data"]["tests"]:
        source = item["source"]
        source_href = "../../" + source["path"]
        rows.append(
            f'<tr data-status="{html.escape(item["status"])}">'
            f'<td><span class="pill {html.escape(item["status"])}">{html.escape(item["status"])}</span></td>'
            f"<td><code>{html.escape(item['id'])}</code></td>"
            f"<td>{html.escape(item['reason'] or '—')}</td>"
            f"<td>{html.escape(item['remediation'] or '—')}</td>"
            f'<td><a href="{html.escape(source_href)}#L{source["line"]}">{html.escape(source["path"])}:{source["line"]}</a></td>'
            "</tr>"
        )
    counts = report["data"]["summary"]
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pytest durable run report</title><style>
body{{font:14px system-ui;margin:0;background:#0b1020;color:#e5e7eb}}main{{max-width:1500px;margin:auto;padding:24px}}
.cards{{display:flex;gap:12px;flex-wrap:wrap}}.card{{background:#151d31;border:1px solid #334155;border-radius:10px;padding:12px 18px}}
button{{background:#1e293b;color:#e5e7eb;border:1px solid #475569;border-radius:7px;padding:7px 10px;cursor:pointer}}table{{width:100%;border-collapse:collapse;margin-top:18px}}
th,td{{border-bottom:1px solid #273449;padding:9px;text-align:left;vertical-align:top}}th{{position:sticky;top:0;background:#111827}}code{{font-size:12px}}a{{color:#93c5fd}}
.pill{{border-radius:999px;padding:3px 8px;font-weight:700}}.passed{{background:#14532d}}.skipped{{background:#713f12}}.failed{{background:#7f1d1d}}
</style></head><body><main><h1>Durable pytest report</h1>
<p>Every test is itemized. Generated {html.escape(report["metadata"]["timestamp_display"])} ({html.escape(report["metadata"]["display_timezone"])}) · {html.escape(report["metadata"]["byline_revision"])}</p>
<div class="cards"><div class="card"><b>{counts["passed"]}</b> passed</div><div class="card"><b>{counts["skipped"]}</b> skipped</div><div class="card"><b>{counts["failed"]}</b> failed</div><div class="card"><b>{counts["total"]}</b> total</div></div>
<p><button onclick="filterRows('all')">All</button> <button onclick="filterRows('passed')">Passed</button> <button onclick="filterRows('skipped')">Skipped</button> <button onclick="filterRows('failed')">Failed</button></p>
<table><thead><tr><th>Status</th><th>Test</th><th>Why</th><th>What next</th><th>Source</th></tr></thead><tbody>{"".join(rows)}</tbody></table>
<script>function filterRows(s){{document.querySelectorAll('tbody tr').forEach(r=>r.hidden=s!=='all'&&r.dataset.status!==s)}}</script>
</main></body></html>"""
    path.write_text(document, encoding="utf-8")


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    global _written_paths
    report = _build_report(exitstatus)
    archive_dir = Path("build/test-reports")
    archive_json = archive_dir / f"pytest-{_run_id}.json"
    archive_html = archive_dir / f"pytest-{_run_id}.html"
    requested_json = session.config.getoption("--run-report-json")
    requested_html = session.config.getoption("--run-report-html")
    json_path = Path(str(requested_json)) if requested_json else archive_json
    html_path = Path(str(requested_html)) if requested_html else archive_html

    json_targets = {archive_json, json_path, archive_dir / "latest.json"}
    html_targets = {archive_html, html_path, archive_dir / "latest.html"}
    serialized = json.dumps(report, indent=2, default=str)
    for target in json_targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(serialized, encoding="utf-8")
    for target in html_targets:
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_html(report, target)
    _written_paths = (json_path, html_path)


def pytest_terminal_summary(terminalreporter: Any) -> None:
    paths = _written_paths or (Path("build/test-reports/latest.json"), Path("build/test-reports/latest.html"))
    terminalreporter.write_sep(
        "=",
        f"durable reports: {paths[0]} | {paths[1]} (latest.* refreshed)",
    )
