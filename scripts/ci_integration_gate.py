"""CI gate for the mandatory pytest integration suite (GAP-021).

Parses a pytest JUnit XML report produced by `pytest -m integration
--junitxml=<path>` and fails loudly if the run proves nothing: zero tests
collected, every collected test skipped, or any test failed/errored. A
green run of this gate is the proof that at least one live-service
integration test actually executed and passed — closing the
"all-skipped-is-still-green" loophole named in
docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md row GAP-021
(`.github/workflows/validate.yml` previously ran unit tests only;
`tests/integration/test_ingest_scratch_live.py` and
`tests/test_schema_docs_current.py` carry `@pytest.mark.integration` but
were never exercised by CI).

Also emits a machine-readable JSON receipt (`--receipt FILE`) recording,
per collected test: node id, outcome, elapsed time, and a best-effort
category tag (custody/horizon/store/walk/other) inferred from the test's
own file/class path — a diagnostic label for the receipt, not a formal
taxonomy claim. The receipt contains only test identities, outcomes, and
counts — never environment values, so it is safe to publish as a CI
artifact without redaction.

Usage:
    uv run python scripts/ci_integration_gate.py --junit artifacts/integration-junit.xml
    uv run python scripts/ci_integration_gate.py --junit artifacts/integration-junit.xml --receipt artifacts/integration-receipt.json

Exit code: 0 if at least one collected test passed and none failed/errored;
1 otherwise (including zero tests collected, or the junit file is missing).
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-26

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree as ET

# Substring -> category, checked in order against the lowercased node id.
# Best-effort only: today's tracked integration suite is
# tests/test_schema_docs_current.py (store), tests/integration/
# test_ingest_scratch_live.py (horizon), and tests/test_timeline_projection.py
# (walk). No live-marked "custody" test exists yet — see the GAP-021 status
# doc's "Limitations" section.
_CATEGORY_HINTS: tuple[tuple[str, str], ...] = (
    ("custody", "custody"),
    ("horizon", "horizon"),
    ("scratch", "horizon"),
    ("schema_docs", "store"),
    ("timeline", "walk"),
    ("walk", "walk"),
)


def categorize(node_id: str) -> str:
    lowered = node_id.lower()
    for needle, category in _CATEGORY_HINTS:
        if needle in lowered:
            return category
    return "other"


@dataclass
class TestOutcome:
    node_id: str
    outcome: str  # "passed" | "failed" | "error" | "skipped"
    time_seconds: float
    category: str
    detail: str = ""

    def to_json(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "outcome": self.outcome,
            "time_seconds": self.time_seconds,
            "category": self.category,
            "detail": self.detail,
        }


def parse_junit(path: Path) -> list[TestOutcome]:
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else list(root.iter("testsuite"))
    results: list[TestOutcome] = []
    for suite in suites:
        for case in suite.iter("testcase"):
            classname = case.get("classname", "")
            name = case.get("name", "")
            node_id = f"{classname}::{name}" if classname else name
            time_seconds = float(case.get("time", "0"))
            skipped = case.find("skipped")
            failure = case.find("failure")
            error = case.find("error")
            if failure is not None:
                outcome, detail = "failed", failure.get("message", "")
            elif error is not None:
                outcome, detail = "error", error.get("message", "")
            elif skipped is not None:
                outcome, detail = "skipped", skipped.get("message", "")
            else:
                outcome, detail = "passed", ""
            results.append(TestOutcome(node_id, outcome, time_seconds, categorize(node_id), detail))
    return results


@dataclass
class Summary:
    total: int
    counts: dict[str, int]
    by_category: dict[str, dict[str, int]]
    gate_passed: bool


def summarize(results: list[TestOutcome]) -> Summary:
    counts = {"passed": 0, "failed": 0, "error": 0, "skipped": 0}
    by_category: dict[str, dict[str, int]] = {}
    for r in results:
        counts[r.outcome] = counts.get(r.outcome, 0) + 1
        bucket = by_category.setdefault(r.category, {"passed": 0, "failed": 0, "error": 0, "skipped": 0})
        bucket[r.outcome] = bucket.get(r.outcome, 0) + 1
    total = len(results)
    gate_passed = total > 0 and counts["passed"] > 0 and counts["failed"] == 0 and counts["error"] == 0
    return Summary(total=total, counts=counts, by_category=by_category, gate_passed=gate_passed)


def build_receipt(
    results: list[TestOutcome],
    summary: Summary,
    *,
    git_sha: str | None,
    run_url: str | None,
    generated_at: str,
) -> dict[str, object]:
    return {
        "schema_version": 1,
        "gap": "GAP-021",
        "generated_at": generated_at,
        "git_sha": git_sha,
        "run_url": run_url,
        "total_collected": summary.total,
        "counts": summary.counts,
        "by_category": summary.by_category,
        "gate_passed": summary.gate_passed,
        "tests": [r.to_json() for r in results],
    }


def _run_url() -> str | None:
    server = os.environ.get("GITHUB_SERVER_URL")
    repo = os.environ.get("GITHUB_REPOSITORY")
    run_id = os.environ.get("GITHUB_RUN_ID")
    if server and repo and run_id:
        return f"{server}/{repo}/actions/runs/{run_id}"
    return None


def _print_summary(summary: Summary) -> None:
    c = summary.counts
    print(
        f"ci_integration_gate: {summary.total} collected — "
        f"{c['passed']} passed, {c['skipped']} skipped, {c['failed']} failed, {c['error']} error",
        file=sys.stderr,
    )
    for category, bucket in sorted(summary.by_category.items()):
        print(f"  {category}: {bucket}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--junit", required=True, type=Path, help="pytest --junitxml output to gate on")
    parser.add_argument("--receipt", type=Path, default=None, help="write the JSON receipt here")
    args = parser.parse_args(argv)

    if not args.junit.exists():
        print(
            f"ci_integration_gate: FAIL — junit report not found at {args.junit} "
            "(pytest did not run, or wrote its report elsewhere)",
            file=sys.stderr,
        )
        return 1

    results = parse_junit(args.junit)
    summary = summarize(results)
    receipt = build_receipt(
        results,
        summary,
        git_sha=os.environ.get("GITHUB_SHA"),
        run_url=_run_url(),
        generated_at=datetime.now(timezone.utc).isoformat(),
    )

    if args.receipt is not None:
        args.receipt.parent.mkdir(parents=True, exist_ok=True)
        args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")

    _print_summary(summary)

    if not summary.gate_passed:
        if summary.total == 0:
            print(
                "ci_integration_gate: FAIL — zero integration tests collected "
                "(marker not found, or the suite is misconfigured)",
                file=sys.stderr,
            )
        elif summary.counts["passed"] == 0:
            print(
                "ci_integration_gate: FAIL — every collected integration test was skipped; "
                "no live proof executed this run",
                file=sys.stderr,
            )
        else:
            print("ci_integration_gate: FAIL — one or more integration tests failed or errored", file=sys.stderr)
        return 1

    print("ci_integration_gate: PASS — at least one live integration test executed and passed", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
