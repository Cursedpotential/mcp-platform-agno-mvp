"""Versioned, durable workflow report projection.

Postgres run/stage/action rows are authoritative. This module builds a stable
JSON contract for APIs, HTML views, exports, and future report versions.
Langfuse is a correlated trace viewer, never the sole report store.

Byline: Codex · GPT-5 · 2026-08-13
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

SCHEMA_VERSION = "1.0"


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def _duration_ms(started: Any, finished: Any) -> int | None:
    if not isinstance(started, datetime) or not isinstance(finished, datetime):
        return None
    return max(0, round((finished - started).total_seconds() * 1000))


def _report_status(run_status: str) -> str:
    if run_status == "completed":
        return "COMPLETE"
    if run_status == "failed":
        return "BLOCKED"
    return "PARTIAL"


def build_run_report(
    run: dict[str, Any],
    actions: list[dict[str, Any]] | None = None,
    *,
    trace_url: str | None = None,
) -> dict[str, Any]:
    """Build the canonical report without mutating ledger data."""
    stages: list[dict[str, Any]] = []
    counts = {"total": 0, "passed": 0, "failed": 0, "skipped": 0, "pending": 0, "running": 0}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    for raw in run.get("stages", []):
        status = raw["status"]
        counts["total"] += 1
        count_key = {"success": "passed"}.get(status, status)
        if count_key in counts:
            counts[count_key] += 1
        reason_code = raw.get("outcome_reason_code")
        reason_detail = raw.get("outcome_reason_detail") or raw.get("content")
        stage = {
            "seq": raw["seq"],
            "name": raw["name"],
            "status": status,
            "disposition": "ran" if status in {"success", "failed"} else status,
            "reason": {"code": reason_code, "detail": reason_detail},
            "started_at": _iso(raw.get("started_at")),
            "finished_at": _iso(raw.get("finished_at")),
            "duration_ms": round(raw["output"]["duration_s"] * 1000)
            if isinstance(raw.get("output"), dict) and raw["output"].get("duration_s") is not None
            else _duration_ms(raw.get("started_at"), raw.get("finished_at")),
            "output": raw.get("output"),
            "review": {
                "decision_required": status in {"failed", "skipped"},
                "allowed_actions": ["acknowledge", "approve", "override", "retry"],
            },
        }
        stages.append(stage)
        if status == "failed":
            errors.append(
                {
                    "code": reason_code or "stage_error",
                    "message": reason_detail or f"stage {raw['name']} failed",
                    "stage_seq": raw["seq"],
                    "recoverable": True,
                }
            )
        elif status == "skipped":
            warnings.append(
                {
                    "code": reason_code or "unspecified_skip",
                    "message": reason_detail or f"stage {raw['name']} was skipped",
                    "stage_seq": raw["seq"],
                }
            )

    created_at = run.get("created_at")
    updated_at = run.get("updated_at")
    duration = _duration_ms(created_at, updated_at)
    return {
        "_comment": "Authoritative durable run report; traces are correlated diagnostic telemetry.",
        "schema_version": run.get("report_schema_version") or SCHEMA_VERSION,
        "pass": {
            "number": 1,
            "name": run.get("workflow", "workflow"),
            "status": _report_status(run.get("status", "running")),
        },
        "metadata": {
            "timestamp": _iso(updated_at),
            "platform": "Agno MCP Platform",
            "byline_revision": "Codex · GPT-5 · 2026-08-13",
            "duration_ms": duration,
        },
        "input": {
            "run_id": run["run_id"],
            "workflow": run.get("workflow"),
            "mode": run.get("mode"),
            "source_name": run.get("source_name"),
            "sha256": run.get("sha256"),
            "domain": run.get("domain"),
            "custody_tier": run.get("custody_tier"),
            "parent_run_id": run.get("parent_run_id"),
        },
        "output": run.get("summary"),
        "errors": errors,
        "warnings": warnings,
        "handoff": {
            "status": "ready" if run.get("status") == "completed" else "review_required",
            "next_action": "Review failed/skipped stages and approve, override, or retry as appropriate.",
        },
        "data": {
            "summary": counts,
            "stages": stages,
            "review_actions": actions or [],
            "trace": {
                "trace_id": run.get("trace_id"),
                "url": trace_url,
                "authority": "diagnostic_only",
            },
        },
    }
