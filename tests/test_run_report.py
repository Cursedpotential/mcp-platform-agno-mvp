"""Contract tests for the durable workflow report projection.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from server.evidence.run_report import build_run_report


def test_run_report_migration_is_append_only_and_reasoned():
    sql = (Path(__file__).resolve().parents[1] / "sql" / "0025_durable_run_reports.sql").read_text(
        encoding="utf-8"
    )
    assert "outcome_reason_code" in sql
    assert "workflow_run_stage_terminal_reason" in sql
    assert "CREATE TABLE IF NOT EXISTS ops.workflow_run_review_action" in sql
    assert "workflow_run_review_action_append_only" in sql
    assert "BEFORE UPDATE OR DELETE" in sql


def test_report_itemizes_skips_and_review_actions():
    started = datetime.now(timezone.utc)
    finished = started + timedelta(seconds=2)
    run = {
        "run_id": "run-1",
        "workflow": "chat-transcript",
        "status": "completed",
        "created_at": started,
        "updated_at": finished,
        "trace_id": "a" * 32,
        "stages": [
            {
                "seq": 1,
                "name": "custody",
                "status": "success",
                "outcome_reason_code": "completed",
                "output": {"duration_s": 0.5},
            },
            {
                "seq": 2,
                "name": "parse",
                "status": "skipped",
                "outcome_reason_code": "inherited_from_parent",
                "outcome_reason_detail": "Reused parent output.",
                "output": None,
            },
        ],
    }
    actions = [{"action_id": "action-1", "action_type": "approve", "reason": "Expected reuse."}]

    report = build_run_report(run, actions, trace_url="https://langfuse.example/trace/" + "a" * 32)

    assert report["schema_version"] == "1.0"
    assert report["data"]["summary"] == {
        "total": 2,
        "passed": 1,
        "failed": 0,
        "skipped": 1,
        "pending": 0,
        "running": 0,
    }
    assert report["data"]["stages"][1]["reason"]["code"] == "inherited_from_parent"
    assert report["data"]["stages"][1]["review"]["decision_required"] is True
    assert report["warnings"][0]["stage_seq"] == 2
    assert report["data"]["review_actions"] == actions
    assert report["data"]["trace"]["authority"] == "diagnostic_only"


def test_failed_run_maps_to_blocked_and_itemized_error():
    run = {
        "run_id": "run-2",
        "workflow": "sms-xml",
        "status": "failed",
        "stages": [
            {
                "seq": 1,
                "name": "custody",
                "status": "failed",
                "outcome_reason_code": "stage_error",
                "outcome_reason_detail": "hash writer unavailable",
            }
        ],
    }

    report = build_run_report(run)

    assert report["pass"]["status"] == "BLOCKED"
    assert report["errors"] == [
        {
            "code": "stage_error",
            "message": "hash writer unavailable",
            "stage_seq": 1,
            "recoverable": True,
        }
    ]
