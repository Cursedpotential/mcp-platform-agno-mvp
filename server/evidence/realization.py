"""server/evidence/realization.py — realization-event writers (Wave 1.2, ADR-0045 §A.4).

Realization events are separate, plural knowledge atoms: a discovery can link
to many records at once (reading one export may surface hundreds), but its
``realized_at`` never rewrites when the raw source became available. Raw-source
availability is computed by ``working.source_available_from(record_id)``;
approved realizations enter ``working.vw_horizon_atom`` at their own dates.

Lifecycle (append-only; never UPDATE an approved row's content — supersede it):

    propose  ->  realization_event(approval_state='proposed')   # INERT for visible_from
    approve  ->  approval_state='approved', approved_at/by set  # knowledge atom appears
    supersede->  approval_state='superseded'                    # atom leaves active horizon

Two independent gates (reconciled here, per W1.1 pre-mortem F6):
  * DB-level: ``vw_horizon_atom`` reads ONLY approved realization events
    (fail-closed — a proposed row changes no horizon, regardless of writer).
  * agno-level: the ``@approval`` run-pause on ``realization_approve`` /
    ``realization_supersede`` (``server/agents/tools/realization_tools.py``)
    gates the approve/supersede TOOL bodies — a human must resolve the pending
    approval before the flip runs. This writer module is HITL-agnostic: it is a
    thin SQL inserter like ``server/evidence/store.py::store_records``; the
    human gate lives on the ``@approval``-decorated tool that calls it.

The app-side guard requires ``realized_at`` to be at or after every linked
record's source-availability boundary. Cross-table CHECK constraints cannot
express this, so missing/unrouted records fail closed here.

Writes ride the platform write engine (``server.core.url.db_url``), NOT an
agent's read-only engine (ADR-0005 — agent connections are read-only by
infrastructure). ``connection=`` lets a caller share an outer transaction
(atomic audit via ``server/core/audit.py::record(connection=...)``, or
rollback-transaction validation).

Byline: Claude Code . glm-5.2:cloud . 2026-08-14
Byline amendment: Codex · GPT-5 · 2026-08-18 (separate source and realization clocks)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import bindparam, create_engine, text

_ENGINE: Any = None  # lazy: created on first write, not at import (tests, tool-facade)

_ALLOWED_KINDS = frozenset({"contradiction", "export_read", "told_by_person", "manual"})
_ALLOWED_PROPOSERS = frozenset({"algorithm", "owner"})


def _get_engine() -> Any:
    """Return (and lazily create) the SQLAlchemy write engine for the working schema.

    Created on first use — not at import time — so this module imports in
    contexts with no DB (tests, tool-facade). Mirrors
    ``server/evidence/store.py::_get_engine``.
    """
    global _ENGINE
    if _ENGINE is None:
        from server.core.url import db_url

        _ENGINE = create_engine(db_url, pool_pre_ping=True)
    return _ENGINE


def _with_conn(connection: Any, fn: Any) -> Any:
    """Run fn(connection) either on a caller-supplied connection (caller owns
    the transaction) or inside a fresh ``engine.begin()`` (auto-commit on
    success, auto-rollback on exception)."""
    if connection is not None:
        return fn(connection)
    with _get_engine().begin() as conn:
        return fn(conn)


def _check_kind(kind: str) -> None:
    if kind not in _ALLOWED_KINDS:
        raise ValueError(f"kind {kind!r} not allowed; must be one of {sorted(_ALLOWED_KINDS)}.")


def _check_proposer(proposer: str) -> None:
    if proposer not in _ALLOWED_PROPOSERS:
        raise ValueError(f"proposer {proposer!r} not allowed; must be one of {sorted(_ALLOWED_PROPOSERS)}.")


def propose_realization(
    *,
    kind: str,
    realized_at: datetime,
    record_ids: list[uuid.UUID] | None = None,
    case_id: str = "primary",
    trigger_record_id: uuid.UUID | None = None,
    evidence_pointer: dict[str, Any] | None = None,
    proposer: str = "algorithm",
    notes: str | None = None,
    connection: Any = None,
) -> uuid.UUID:
    """Propose a realization event + its record links. Writes a ``proposed``
    (INERT) row — ``visible_from`` changes for NO record until it is approved.

    Rejects a realization before any linked source was available. Missing,
    unrouted, or cross-case record ids fail closed.

    Returns the new ``realization_event.id``.
    """
    _check_kind(kind)
    _check_proposer(proposer)
    if not case_id or not case_id.strip():
        raise ValueError("case_id must be a non-empty string.")
    record_ids = list(record_ids or [])

    def _do(conn: Any) -> uuid.UUID:
        # Cross-table ordering guard: realization >= every source boundary.
        if record_ids and realized_at is not None:
            stmt = text(
                "SELECT COUNT(*)::int, COUNT(working.source_available_from(id))::int, "
                "       MAX(working.source_available_from(id)) "
                "FROM working.normalized_record WHERE case_id = :case_id AND id IN :ids"
            ).bindparams(bindparam("ids", expanding=True))
            row = conn.execute(
                stmt,
                {"ids": [str(r) for r in record_ids], "case_id": case_id},
            ).fetchone()
            expected = len(set(record_ids))
            found, available, latest_boundary = row if row is not None else (0, 0, None)
            if found != expected or available != expected or latest_boundary is None:
                raise ValueError(
                    "every linked record must exist in the case and have an approved "
                    "source-availability boundary; rejecting realization"
                )
            if realized_at < latest_boundary:
                raise ValueError(
                    f"realized_at {realized_at.isoformat()} precedes the latest linked "
                    f"source availability {latest_boundary.isoformat()}; rejecting — not clamping"
                )

        evid_id = conn.execute(
            text(
                "INSERT INTO working.realization_event "
                "(case_id, kind, realized_at, trigger_record_id, evidence_pointer, "
                " proposer, approval_state, notes) "
                "VALUES (:case_id, :kind, :realized_at, :trigger_record_id, "
                "        CAST(:evidence_pointer AS jsonb), :proposer, 'proposed', :notes) "
                "RETURNING id"
            ),
            {
                "case_id": case_id,
                "kind": kind,
                "realized_at": realized_at,
                "trigger_record_id": str(trigger_record_id) if trigger_record_id else None,
                "evidence_pointer": json.dumps(evidence_pointer or {}),
                "proposer": proposer,
                "notes": notes,
            },
        ).scalar()
        evid_uuid = uuid.UUID(str(evid_id))

        if record_ids:
            conn.execute(
                text(
                    "INSERT INTO working.realization_event_record "
                    "(realization_event_id, normalized_record_id, case_id) "
                    "VALUES (:eid, :rid, :case_id)"
                ),
                [{"eid": str(evid_uuid), "rid": str(r), "case_id": case_id} for r in record_ids],
            )
        return evid_uuid

    return _with_conn(connection, _do)


def approve_realizations(
    *,
    event_ids: list[uuid.UUID],
    approved_by: str = "owner",
    connection: Any = None,
) -> dict[str, list[str]]:
    """Batch-approve proposed realization events (the HITL gate). Flips
    ``approval_state`` 'proposed' -> 'approved', stamps ``approved_at=now()`` /
    ``approved_by``. The DB CHECK ``realization_event_approved_iff_timestamp``
    guarantees an approved row carries its approval time, and a 'proposed' row
    carries none (approved_at/by are NULL iff proposed; set once at approval and
    retained through 'superseded' — see F15 in the W1.2 pre-mortem).

    Idempotent: only 'proposed' rows are touched; already-approved, superseded,
    or unknown ids are returned in ``not_proposed`` (not errored) so a replayed
    batch is safe. Returns ``{"approved": [...ids], "not_proposed": [...ids]}``.
    """
    if not event_ids:
        return {"approved": [], "not_proposed": []}
    if not approved_by or not approved_by.strip():
        raise ValueError("approved_by must be a non-empty string.")
    ids = [str(i) for i in event_ids]

    def _do(conn: Any) -> dict[str, list[str]]:
        stmt = text(
            "UPDATE working.realization_event SET approval_state='approved', "
            "approved_at=now(), approved_by=:by "
            "WHERE id IN :ids AND approval_state='proposed' RETURNING id"
        ).bindparams(bindparam("ids", expanding=True))
        result = conn.execute(stmt, {"ids": ids, "by": approved_by})
        approved = {str(r[0]) for r in result.fetchall()}
        return {"approved": sorted(approved), "not_proposed": sorted(set(ids) - approved)}

    return _with_conn(connection, _do)


def supersede_realization(
    *,
    event_id: uuid.UUID,
    connection: Any = None,
) -> bool:
    """Mark an approved realization event ``superseded``. This is the ONE
    sanctioned UPDATE of an approved row (only ``approval_state``, never the
    content — append-only model, ADR-0045 §A.4). Once superseded, the realization
    atom leaves active horizon views; raw-source availability is unchanged. Returns True if an approved
    row was superseded, False if the id was missing or not in the 'approved'
    state (idempotent).
    """

    def _do(conn: Any) -> bool:
        result = conn.execute(
            text(
                "UPDATE working.realization_event SET approval_state='superseded' "
                "WHERE id = :id AND approval_state='approved' RETURNING id"
            ),
            {"id": str(event_id)},
        )
        return result.fetchone() is not None

    return _with_conn(connection, _do)
