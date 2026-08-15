"""agents/tools/realization_tools.py — agno ``@tool`` wrappers over the
realization-event writers (Wave 1.2, ADR-0045 §A.4).

Two gates, two surfaces (per W1.1 pre-mortem F6):

  * ``realization_propose``  — plain ``@tool``. PROPOSING is inert (writes a
    'proposed' row that ``visible_from`` never reads), so it needs NO HITL
    pause — an analysis lane or ingest lane proposes freely, in bulk.
  * ``realization_approve`` / ``realization_supersede`` — ``@approval`` +
    ``@tool(requires_confirmation=True)``. APPROVING or SUPERSEDING a
    realization changes ``visible_from`` for linked records (it is
    visible-from-TRUTH-affecting), so the run pauses for a recorded human
    approval before the body executes. That is the HITL gate ADR-0045 §A.4
    mandates; the DB-level backstop (``visible_from`` reads only 'approved'
    events) catches any writer that bypasses the tool.

Error convention (OQ-8, same as gateway_tools.py): these wrappers do NOT
catch exceptions — the F5 ``ValueError`` (realized_at precedes linked
occurred_at), a bad ISO timestamp, a bad UUID, all propagate. agno's
``Function.execute()`` catches them and reports ``status="failure"`` to the
model, which is the signal we want preserved.

Wiring: ``REALIZATION_TOOLS`` is registered in ``providers.source_tools`` as
of W1.5 (appended to the platform ``source_tools`` list, so every agent gets
the propose + approve/supersede surface). Lane binding: ``realization_propose``
is inert + free on all agents (analysis / ingest propose in bulk);
``realization_approve`` / ``realization_supersede`` are ``@approval``-gated, so
any call PAUSES for a recorded human (owner) approval — the ``@approval`` gate
is the lane boundary, so tool placement does not change enforcement. OPEN owner
refinement: scope approve/supersede to the ``review_gatekeeper`` only (needs
per-agent tool customization in ``factory.py``, which today passes one uniform
``source_tools``); deferred — the @approval backstop holds.

Byline: Claude Code . glm-5.2:cloud . 2026-08-14
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from agno.approval import approval
from agno.tools import tool

from server.evidence.realization import (
    approve_realizations,
    propose_realization,
    supersede_realization,
)


@tool
def realization_propose(
    kind: str,
    realized_at: str,
    record_ids: list[str] | None = None,
    case_id: str = "primary",
    trigger_record_id: str | None = None,
    evidence_pointer: dict[str, Any] | None = None,
    proposer: str = "algorithm",
    notes: str | None = None,
) -> dict[str, Any]:
    """Propose a realization event linking one or more evidence records.

    A proposal is INERT: until it is approved (see ``realization_approve``) it
    changes no record's ``visible_from``. An analysis lane or ingest lane may
    call this freely, including in bulk. ``kind`` must be one of
    ``contradiction`` | ``export_read`` | ``told_by_person`` | ``manual``.

    Parameters
    ----------
    kind:
        Discovery vocabulary: ``contradiction`` (a later record contradicts an
        earlier belief — also the lie register), ``export_read`` (reading an
        export revealed records), ``told_by_person`` (a person disclosed it),
        ``manual`` (a human entered it directly).
    realized_at:
        ISO-8601 timestamp of when the party understood the significance. MUST
        not precede the earliest linked record's ``occurred_at`` (F5 guard — a
        realization cannot predate what it reveals, or the clock moves
        backwards); a proposal violating this is rejected, not clamped.
    record_ids:
        UUIDs of the ``working.normalized_record`` rows this realization
        reveals. May be empty only for a ``told_by_person`` / ``manual``
        realization with no records yet.
    case_id:
        Case identifier (default ``"primary"``).
    trigger_record_id:
        Optional UUID of the single record that triggered the realization.
    evidence_pointer:
        Structured provenance (the contradicting record id, the export name,
        the person, a quote, ...) stored as JSONB. Default ``{}``.
    proposer:
        ``"algorithm"`` (the analysis layer matched it) or ``"owner"`` (a
        human entered it). Default ``"algorithm"``.

    Returns
    -------
    dict
        ``{"event_id": <uuid str>, "status": "proposed",
        "linked_records": <count>}``.
    """
    rid_list = [uuid.UUID(r) for r in record_ids] if record_ids else []
    eid = propose_realization(
        kind=kind,
        realized_at=datetime.fromisoformat(realized_at),
        record_ids=rid_list,
        case_id=case_id,
        trigger_record_id=uuid.UUID(trigger_record_id) if trigger_record_id else None,
        evidence_pointer=evidence_pointer,
        proposer=proposer,
        notes=notes,
    )
    return {
        "event_id": str(eid),
        "status": "proposed",
        "linked_records": len(rid_list),
    }


@approval  # type: ignore[call-overload]
@tool(requires_confirmation=True)
def realization_approve(event_ids: list[str], approved_by: str = "owner") -> dict[str, Any]:
    """Batch-approve proposed realization events (the HITL gate).

    Pauses the run for recorded human approval BEFORE the body executes (native
    ``@approval`` flow, ADR-0002). Approving flips each event's
    ``approval_state`` 'proposed' -> 'approved', which makes its
    ``realized_at`` count toward the linked records' ``visible_from`` — i.e.
    this is visible-from-TRUTH-affecting, so it requires a human.

    Idempotent: only 'proposed' rows are flipped; already-approved, superseded,
    or unknown ids come back in ``not_proposed`` (not an error), so a replayed
    batch is safe.

    Parameters
    ----------
    event_ids:
        UUIDs of the realization events to approve (all must be 'proposed').
    approved_by:
        Who approved (default ``"owner"``). Recorded on each event.

    Returns
    -------
    dict
        ``{"approved": [<uuid>...], "not_proposed": [<uuid>...]}``.
    """
    return approve_realizations(
        event_ids=[uuid.UUID(e) for e in event_ids],
        approved_by=approved_by,
    )


@approval  # type: ignore[call-overload]
@tool(requires_confirmation=True)
def realization_supersede(event_id: str) -> dict[str, Any]:
    """Mark an approved realization event superseded (the HITL gate).

    Pauses the run for recorded human approval BEFORE the body executes
    (native ``@approval`` flow). Superseding removes the event from
    ``visible_from``'s approved set, so the affected records' clock reverts to
    the next approved event or their ``occurred_at`` — visible-from-TRUTH
    affecting, hence the human gate. This is the ONE sanctioned UPDATE of an
    approved row (only ``approval_state``, never the content — append-only).

    Idempotent: returns ``superseded: false`` if the id was missing or not
    'approved' (not an error).

    Parameters
    ----------
    event_id:
        UUID of the approved realization event to supersede.

    Returns
    -------
    dict
        ``{"event_id": <uuid str>, "superseded": <bool>}``.
    """
    ok = supersede_realization(event_id=uuid.UUID(event_id))
    return {"event_id": event_id, "superseded": ok}


# Exported for ``providers.source_tools`` registration in W1.5. NOT appended
# there in W1.2 — which agents may propose vs. approve is a lane binding.
REALIZATION_TOOLS: list[Any] = [realization_propose, realization_approve, realization_supersede]
