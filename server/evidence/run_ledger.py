"""
evidence/run_ledger.py — C0 run ledger: persist per-run + per-stage state as
the evidence workflows (server/evidence/workflows.py) execute, so a run is a
first-class, inspectable DB object (ops.workflow_run /
ops.workflow_run_stage, sql/0005_workflow_run_ledger.sql) instead of a
black box whose only telemetry is the final in-memory step_log.

Engine pattern mirrors server/evidence/store.py exactly (module-level lazy
engine, sqlalchemy `text()`, `db_url` imported lazily to avoid import-time
env coupling) — this module does not invent a second connection helper.

Byline: Claude Code · Sonnet (agent) · 2026-07-20
Byline: Codex · GPT-5 · 2026-08-13 (durable run reports and review actions)
Byline: Codex · GPT-5 · 2026-08-18 (durable source/acquisition replay context)
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import create_engine, text

_engine = None


def _get_engine():
    global _engine
    if _engine is None:
        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def ping() -> None:
    """Cheap connectivity check — SELECT 1 against the same engine every
    other function in this module uses. Raises on failure; the caller (C2.6
    requirement 4, GET /v1/health/deps in server/api/run_routes.py) decides
    how to time-box and report it."""
    with _get_engine().connect() as conn:
        conn.execute(text("SELECT 1"))


def _jsonb(value: Any) -> Any:
    """Round-trip a jsonb column value to a plain Python object.

    Some driver/SQLAlchemy combinations already deserialize jsonb to
    dict/list; others hand back the raw json text. Handle both so callers
    always get parsed data.
    """
    if value is None:
        return None
    if isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def create_run(
    workflow: str,
    mode: str = "auto",
    source_name: str | None = None,
    source_path: str | None = None,
    domain: str | None = None,
    parent_run_id: str | None = None,
    custody_tier: str = "full",
    source_context: dict[str, Any] | None = None,
) -> str:
    """Insert a new ops.workflow_run row (status='running'). Returns run_id.

    parent_run_id (C2 retry lineage, sql/0006): set when this run was created
    by POST /v1/runs/{id}/retry — links back to the terminal-failed run it
    re-runs from. custody_tier (C2 two-tier custody, sql/0006): 'full'
    (default, unchanged historical meaning) or 'light' — see
    server/evidence/custody.py's ingest_artifact() docstring.
    """
    with _get_engine().begin() as conn:
        run_id = conn.execute(
            text(
                "INSERT INTO ops.workflow_run "
                "(workflow, mode, source_name, source_path, domain, parent_run_id, custody_tier, source_context) "
                "VALUES (:workflow, :mode, :source_name, :source_path, :domain, :parent_run_id, :custody_tier, "
                "        CAST(:source_context AS jsonb)) "
                "RETURNING run_id"
            ),
            {
                "workflow": workflow,
                "mode": mode,
                "source_name": source_name,
                "source_path": source_path,
                "domain": domain,
                "parent_run_id": parent_run_id,
                "custody_tier": custody_tier,
                "source_context": json.dumps(source_context or {}),
            },
        ).scalar()
    return str(run_id)


def seed_stages(run_id: str, names: list[str]) -> None:
    """Seed one 'pending' row per stage name, in seq order (1-based — matches
    workflows.py's `enumerate(wf.steps, start=1)` wrapping order)."""
    if not names:
        return
    rows = [{"run_id": run_id, "seq": i, "name": name} for i, name in enumerate(names, start=1)]
    with _get_engine().begin() as conn:
        conn.execute(
            text("INSERT INTO ops.workflow_run_stage (run_id, seq, name) VALUES (:run_id, :seq, :name)"),
            rows,
        )


def stage_start(run_id: str, seq: int) -> None:
    """Flip a seeded stage to 'running' and stamp started_at (server-side now())."""
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE ops.workflow_run_stage "
                "SET status = 'running', started_at = now(), finished_at = NULL, "
                "    outcome_reason_code = NULL, outcome_reason_detail = NULL "
                "WHERE run_id = :run_id AND seq = :seq"
            ),
            {"run_id": run_id, "seq": seq},
        )


def stage_finish(
    run_id: str,
    seq: int,
    status: str,
    content: str | None = None,
    output: dict[str, Any] | None = None,
    reason_code: str | None = None,
    reason_detail: str | None = None,
) -> None:
    """Record a stage's terminal status/content/typed-output; stamp finished_at.

    On an exception in the wrapped step, callers pass status='failed' and
    content=str(exc) (see workflows.py's `_fail` helper).
    """
    if status not in {"success", "failed", "skipped"}:
        raise ValueError(f"terminal stage status required, got {status!r}")
    resolved_reason = (
        reason_code
        or {
            "success": "completed",
            "failed": "stage_error",
            "skipped": "unspecified_skip",
        }[status]
    )
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE ops.workflow_run_stage "
                "SET status = :status, content = :content, "
                "    output = CAST(:output AS jsonb), "
                "    outcome_reason_code = :reason_code, "
                "    outcome_reason_detail = :reason_detail, finished_at = now() "
                "WHERE run_id = :run_id AND seq = :seq"
            ),
            {
                "run_id": run_id,
                "seq": seq,
                "status": status,
                "content": content,
                "output": json.dumps(output) if output is not None else None,
                "reason_code": resolved_reason,
                "reason_detail": reason_detail,
            },
        )


def set_gate(run_id: str, state: str | None, status: str | None = None) -> None:
    """Set ops.workflow_run.gate_state (C2 supervised gates, sql/0006).

    state: 'waiting' | 'released' | 'abort' | None (None clears the gate —
    used when a release lets the run resume).

    status: optional — when given, updated in the SAME statement as gate_state
    (one round-trip instead of two): the supervised-gate wrapper in
    workflows.py uses this to pause ('waiting' + status='paused') and resume
    ('None' + status='running') atomically; run_routes.py's /continue
    endpoint uses it the same way. Left out (None) leaves status untouched —
    e.g. the /abort endpoint on a RUNNING run only flips gate_state; the run's
    own background task is what eventually calls finish_run(status='failed').
    """
    with _get_engine().begin() as conn:
        if status is not None:
            conn.execute(
                text(
                    "UPDATE ops.workflow_run "
                    "SET gate_state = :state, status = :status, updated_at = now() "
                    "WHERE run_id = :run_id"
                ),
                {"run_id": run_id, "state": state, "status": status},
            )
        else:
            conn.execute(
                text("UPDATE ops.workflow_run SET gate_state = :state, updated_at = now() WHERE run_id = :run_id"),
                {"run_id": run_id, "state": state},
            )


def read_gate(run_id: str) -> str | None:
    """Read the current gate_state for a run — a lightweight single-column
    read (no stage join), used by the supervised-gate poll loop in
    workflows.py (every ~2s while paused) and the run-control endpoints'
    abort-at-boundary check. Returns None if the run doesn't exist or has no
    gate open."""
    with _get_engine().connect() as conn:
        row = conn.execute(
            text("SELECT gate_state FROM ops.workflow_run WHERE run_id = :run_id"),
            {"run_id": run_id},
        ).first()
    return row[0] if row is not None else None


def skip_remaining_stages(
    run_id: str,
    from_seq: int = 0,
    *,
    reason_code: str = "run_aborted",
    reason_detail: str | None = None,
) -> None:
    """Mark every still-'pending' stage after `from_seq` as 'skipped' — used
    when an operator aborts at a supervised gate, a gate times out (24h
    ceiling with no operator decision), or an operator aborts a RUNNING run
    (the `status='pending' AND seq > from_seq` filter means passing
    from_seq=0 safely skips 'whatever is still pending' without needing to
    know the exact current stage)."""
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE ops.workflow_run_stage "
                "SET status = 'skipped', finished_at = now(), "
                "    outcome_reason_code = :reason_code, "
                "    outcome_reason_detail = :reason_detail "
                "WHERE run_id = :run_id AND seq > :from_seq AND status = 'pending'"
            ),
            {
                "run_id": run_id,
                "from_seq": from_seq,
                "reason_code": reason_code,
                "reason_detail": reason_detail,
            },
        )


def set_trace_id(run_id: str, trace_id: str) -> None:
    """Correlate the authoritative run with an Agno/OTel/Langfuse trace."""
    with _get_engine().begin() as conn:
        conn.execute(
            text("UPDATE ops.workflow_run SET trace_id = :trace_id, updated_at = now() WHERE run_id = :run_id"),
            {"run_id": run_id, "trace_id": trace_id},
        )


def record_review_action(
    run_id: str,
    action_type: str,
    reason: str,
    *,
    actor: str = "owner",
    stage_seq: int | None = None,
    replacement: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Atomically append an operator decision and its global audit entry."""
    if action_type not in {"acknowledge", "approve", "override", "continue", "abort", "retry"}:
        raise ValueError(f"unsupported review action {action_type!r}")
    if not reason.strip():
        raise ValueError("review action reason is required")
    with _get_engine().begin() as conn:
        row = (
            conn.execute(
                text(
                    "INSERT INTO ops.workflow_run_review_action "
                    "(run_id, stage_seq, action_type, actor, reason, replacement) "
                    "VALUES (:run_id, :stage_seq, :action_type, :actor, :reason, CAST(:replacement AS jsonb)) "
                    "RETURNING action_id, run_id, stage_seq, action_type, actor, reason, replacement, created_at"
                ),
                {
                    "run_id": run_id,
                    "stage_seq": stage_seq,
                    "action_type": action_type,
                    "actor": actor,
                    "reason": reason.strip(),
                    "replacement": json.dumps(replacement) if replacement is not None else None,
                },
            )
            .mappings()
            .first()
        )
        if row is None:
            raise RuntimeError("review action INSERT did not return a row")
        action = dict(row)
        action["action_id"] = str(action["action_id"])
        action["run_id"] = str(action["run_id"])
        action["replacement"] = _jsonb(action.get("replacement"))

        from server.core.audit import record

        canonical = json.dumps(
            {
                "action_id": action["action_id"],
                "run_id": action["run_id"],
                "stage_seq": action.get("stage_seq"),
                "action_type": action["action_type"],
                "actor": action["actor"],
                "reason": action["reason"],
                "replacement": action.get("replacement"),
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )
        record(
            "approval" if action["action_type"] == "approve" else "decision",
            action["action_id"],
            actor=action["actor"],
            ctx={},
            object_schema="ops",
            payload_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
            connection=conn,
        )
    return action


def list_review_actions(run_id: str) -> list[dict[str, Any]]:
    """Return append-only operator decisions for a run in recorded order."""
    with _get_engine().connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT action_id, run_id, stage_seq, action_type, actor, reason, replacement, created_at "
                    "FROM ops.workflow_run_review_action WHERE run_id = :run_id "
                    "ORDER BY created_at, action_id"
                ),
                {"run_id": run_id},
            )
            .mappings()
            .all()
        )
    actions: list[dict[str, Any]] = []
    for row in rows:
        action = dict(row)
        action["action_id"] = str(action["action_id"])
        action["run_id"] = str(action["run_id"])
        action["replacement"] = _jsonb(action.get("replacement"))
        actions.append(action)
    return actions


def finish_run(
    run_id: str,
    status: str,
    summary: dict[str, Any] | None = None,
    error: str | None = None,
    sha256: str | None = None,
    artifact_id: str | None = None,
) -> None:
    """Mark the run terminal (completed/failed/paused) with the runner's summary dict.

    sha256/artifact_id use COALESCE so a late-arriving None never clobbers a
    value already recorded by an earlier stage.
    """
    with _get_engine().begin() as conn:
        conn.execute(
            text(
                "UPDATE ops.workflow_run "
                "SET status = :status, summary = CAST(:summary AS jsonb), error = :error, "
                "    sha256 = COALESCE(:sha256, sha256), "
                "    artifact_id = COALESCE(:artifact_id, artifact_id), "
                "    updated_at = now() "
                "WHERE run_id = :run_id"
            ),
            {
                "run_id": run_id,
                "status": status,
                "summary": json.dumps(summary) if summary is not None else None,
                "error": error,
                "sha256": sha256,
                "artifact_id": artifact_id,
            },
        )


def get_run(run_id: str) -> dict[str, Any] | None:
    """Return the run row + its ordered stages (jsonb parsed), or None if missing."""
    with _get_engine().connect() as conn:
        run_row = (
            conn.execute(
                text("SELECT * FROM ops.workflow_run WHERE run_id = :run_id"),
                {"run_id": run_id},
            )
            .mappings()
            .first()
        )
        if run_row is None:
            return None
        stage_rows = (
            conn.execute(
                text("SELECT * FROM ops.workflow_run_stage WHERE run_id = :run_id ORDER BY seq"),
                {"run_id": run_id},
            )
            .mappings()
            .all()
        )

    run = dict(run_row)
    run["run_id"] = str(run["run_id"])
    if run.get("parent_run_id") is not None:
        run["parent_run_id"] = str(run["parent_run_id"])
    run["summary"] = _jsonb(run.get("summary"))
    run["source_context"] = _jsonb(run.get("source_context")) or {}

    stages = []
    for row in stage_rows:
        stage = dict(row)
        stage["run_id"] = str(stage["run_id"])
        stage["output"] = _jsonb(stage.get("output"))
        stages.append(stage)
    run["stages"] = stages
    return run


_LIST_RUNS_STAGE_CONTENT_MAX_CHARS = 500  # matches _ledger_stage_output's sample_records truncation convention


def list_runs(limit: int = 50, status: str | None = None) -> list[dict[str, Any]]:
    """List runs (most recent first), each carrying its per-stage name/status pairs.

    Single round-trip: LIMIT applies to runs (via a subquery), then a LEFT JOIN
    pulls each run's stages so pagination isn't skewed by stage fan-out.

    Each stage dict also carries `content` (C2.6 requirement 3, truncated to
    500 chars server-side) — a failed run's Runs-table row shows a truncated
    error snippet without a second round-trip to GET /v1/runs/{run_id}.
    """
    where_clause = "WHERE status = :status" if status is not None else ""
    sql = text(
        "SELECT r.run_id, r.workflow, r.mode, r.source_name, r.source_path, r.sha256, "
        "       r.artifact_id, r.domain, r.status, r.summary, r.error, r.created_at, r.updated_at, "
        "       r.gate_state, r.parent_run_id, r.custody_tier, r.source_context, "
        "       s.seq, s.name AS stage_name, s.status AS stage_status, s.content AS stage_content "
        f"FROM (SELECT * FROM ops.workflow_run {where_clause} "
        "       ORDER BY created_at DESC LIMIT :limit) r "
        "LEFT JOIN ops.workflow_run_stage s ON s.run_id = r.run_id "
        "ORDER BY r.created_at DESC, s.seq"
    )
    params: dict[str, Any] = {"limit": limit}
    if status is not None:
        params["status"] = status

    with _get_engine().connect() as conn:
        rows = conn.execute(sql, params).mappings().all()

    runs: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    for row in rows:
        rid = str(row["run_id"])
        if rid not in runs:
            # .get() (not row[...]) for the three C2 columns: keeps this
            # resilient for callers/test doubles built against pre-0006 row
            # shapes (a real 0006-applied DB always has them via the SELECT).
            parent_run_id = row.get("parent_run_id")
            runs[rid] = {
                "run_id": rid,
                "workflow": row["workflow"],
                "mode": row["mode"],
                "source_name": row["source_name"],
                "source_path": row["source_path"],
                "sha256": row["sha256"],
                "artifact_id": row["artifact_id"],
                "domain": row["domain"],
                "status": row["status"],
                "gate_state": row.get("gate_state"),
                "parent_run_id": str(parent_run_id) if parent_run_id is not None else None,
                "custody_tier": row.get("custody_tier", "full"),
                "source_context": _jsonb(row.get("source_context")) or {},
                "summary": _jsonb(row["summary"]),
                "error": row["error"],
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "stages": [],
            }
            order.append(rid)
        if row["seq"] is not None:
            content = row.get("stage_content")
            runs[rid]["stages"].append(
                {
                    "seq": row["seq"],
                    "name": row["stage_name"],
                    "status": row["stage_status"],
                    "content": content[:_LIST_RUNS_STAGE_CONTENT_MAX_CHARS] if content else content,
                }
            )
    return [runs[rid] for rid in order]
