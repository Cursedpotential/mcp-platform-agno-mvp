"""server/evidence/realization.py — realization-event writers (Wave 1.2, ADR-0045 §A.4).

Realization events are the horizon CLOCK source of truth: a discovery that
can reveal many records at once (reading one export surfaces hundreds), and
whose ``realized_at`` pushes those records' ``visible_from`` past their
``occurred_at``. This module is the WRITE side of that clock — the read side
is ``working.visible_from(record_id)`` (landed W1.1, ``sql/0026``).

Lifecycle (append-only; never UPDATE an approved row's content — supersede it):

    propose  ->  realization_event(approval_state='proposed')   # INERT for visible_from
    approve  ->  approval_state='approved', approved_at/by set  # visible_from now moves
    supersede->  approval_state='superseded'                    # visible_from reverts

Two independent gates (reconciled here, per W1.1 pre-mortem F6):
  * DB-level: ``visible_from`` reads ONLY ``approval_state='approved'`` events
    (fail-closed — a 'proposed' row changes no record's clock, regardless of
    how it was written).
  * agno-level: the ``@approval`` run-pause on ``realization_approve`` /
    ``realization_supersede`` (``server/agents/tools/realization_tools.py``)
    gates the approve/supersede TOOL bodies — a human must resolve the pending
    approval before the flip runs. This writer module is HITL-agnostic: it is a
    thin SQL inserter like ``server/evidence/store.py::store_records``; the
    human gate lives on the ``@approval``-decorated tool that calls it.

F5 app-side guard: ``realized_at >= min(linked occurred_at)`` is NOT
DB-enforceable (cross-table CHECK not expressible); ``propose_realization``
rejects (not clamps) a ``realized_at`` that precedes the earliest linked
``occurred_at``, or the clock could move backwards. See the WARNING on
``working.realization_event.realized_at`` (sql/0026).

Writes ride the platform write engine (``server.core.url.db_url``), NOT an
agent's read-only engine (ADR-0005 — agent connections are read-only by
infrastructure). ``connection=`` lets a caller share an outer transaction
(atomic audit via ``server/core/audit.py::record(connection=...)``, or
rollback-transaction validation).

Byline: Claude Code . glm-5.2:cloud . 2026-08-14
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

    F5 guard: rejects ``realized_at < min(linked occurred_at)`` — a realization
    cannot predate what it reveals, or the clock moves backwards (the DB
    cannot enforce this cross-table; sql/0026 WARNING).

    Returns the new ``realization_event.id``.
    """
    _check_kind(kind)
    _check_proposer(proposer)
    if not case_id or not case_id.strip():
        raise ValueError("case_id must be a non-empty string.")
    record_ids = list(record_ids or [])

    def _do(conn: Any) -> uuid.UUID:
        # F5 app-side ordering guard: realized_at >= min(linked occurred_at).
        if record_ids and realized_at is not None:
            stmt = text(
                "SELECT MIN(occurred_at) FROM working.normalized_record WHERE id IN :ids AND occurred_at IS NOT NULL"
            ).bindparams(bindparam("ids", expanding=True))
            min_occ = conn.execute(stmt, {"ids": [str(r) for r in record_ids]}).scalar()
            if min_occ is not None and realized_at < min_occ:
                raise ValueError(
                    f"realized_at {realized_at.isoformat()} precedes the earliest "
                    f"linked occurred_at {min_occ.isoformat()}; a realization cannot "
                    f"predate what it reveals (F5 guard, ADR-0045 §A.4 / sql/0026 "
                    f"WARNING). Rejecting — not clamping."
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
    content — append-only model, ADR-0045 §A.4). Once superseded, ``visible_from``
    no longer reads the event and the affected records' clock reverts to the
    next approved event or their ``occurred_at``. Returns True if an approved
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
