"""server/evidence/derivation.py — the SOLE-writer derivation engine (W1.3, ADR-0045 §B).

ADR-0045 §B (signed D-042) sanctions version-pinned DERIVED pass materializations
and FORBIDS parallel authored as-lived/hindsight stores. There is ONE authored
store (``working.normalized_record`` + ``working.realization_event``); the pass
corpora that analysis agents read are DERIVED projections of it. This module is
the SOLE writer of those projections (``working.walk_run`` / ``working.walk_step`` /
``working.walk_step_retrieval`` = ``working.walk_ledger``, ``sql/0027``).

THE CONTRACT (ADR-0045 §B), every item enforced here + proven by the validation
script before any agent binds:

  * **Sole writer.** A single-writer refresher — no other code path may write
    ``working.walk_*``. Enforced TWO ways: (i) app-side ``pg_advisory_xact_lock``
    (F13) so two refresher runs cannot interleave; (ii) DB-side default-deny
    grants (W1.4) so only the refresher role has INSERT. The lock is the
    in-process guard; the grants are the cross-process guard.
  * **Version-pinned.** Each run derives against a ``base_version`` — a
    content-hash of the authored store (the case's normalized records + its
    APPROVED realization events) at derivation time. Re-deriving at the SAME
    ``base_version`` MUST reproduce the identical hash chain. Moving the base
    forward produces a NEW run (append-only — a run is never mutated).
  * **Snapshot-stable (W1.5 / P2).** The derivation transaction is pinned to
    REPEATABLE READ so the whole walk sees ONE snapshot — a concurrent
    realization approval mid-walk cannot move ``visible_from`` between steps
    and break the chain. See ``_get_engine``.
  * **Chain-hashed per step.** ``corpus_hash = sha256(prev_hash || slice)``
    where ``slice`` is the canonical serialization of the records visible in
    the step's horizon window. ``prev_hash`` chains to the prior step's
    ``corpus_hash`` (step 1's ``prev_hash`` = ``run.genesis_hash``). The chain
    is tamper-evident AND reproducible.
  * **Hash-attested to ops.audit_ledger.** Every step is attested via
    ``server.core.audit.record(action_type='derivation', payload_hash=<corpus_hash>,
    connection=conn)`` in the SAME transaction as the write — atomic (the audit
    row and the checkpoint commit together or not at all). The precise
    ``base_version`` (a content-hash) lives in ``working.walk_run.base_version``
    (TEXT); ``audit_ledger.base_version`` is BIGINT (a generation number), so
    the attestation carries the corpus_hash + run id, not the content-hash.

Two schedules (canon §1 — a pass is a knowledge horizon bound to an agent):

  * **As-lived (ignorant).** The horizon ADVANCES each step; the agent lives
    events as they were actually discovered. Each step appends the
    newly-visible source and realization atoms (``visible_from <= horizon_at``) and
    chain-hashes it. Gaslighting works here, and only here — the delta vs the
    hindsight walk IS the manipulation.
  * **Hindsight.** A single step with ``horizon_at IS NULL`` (no cutoff) — the
    whole case, including hindsight-tagged records, is visible at once.

Contamination (the silent killer, AGENTS.md WHY THIS EXISTS): the visible slice
reads ``working.vw_horizon_atom``. Raw sources use source availability
(occurrence for first-party; acquisition for acquired third-party); approved
realizations are separate atoms at their own dates. NULL availability fails
closed for an as-lived step.

Writes ride the platform write engine (``server.core.url.db_url``), NOT an
agent's read-only engine (ADR-0005). ``connection=`` lets a caller share an outer
transaction (atomic audit / rollback-transaction validation).

Byline: Claude Code . glm-5.2:cloud . 2026-08-14
Byline amendment: Codex · GPT-5 · 2026-08-18 (source availability + realization atoms)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import create_engine, text

# F13 sole-writer lock. Distinct namespace from audit's chain lock
# (hashtext('ops.audit_ledger')) — no collision. pg_advisory_xact_lock releases
# automatically at transaction end, so a crashed refresher cannot hold the lock.
_LOCK_KEY_SQL = "hashtext('working.walk_ledger')"

_ENGINE: Any = None  # lazy: created on first write, not at import


def _get_engine() -> Any:
    """Lazily create the write engine. Mirrors realization.py / store.py.

    Pinned to **REPEATABLE READ** (W1.5 / W1.3 pre-mortem P2). The §B contract
    requires that once a derivation pins ``base_version``, the WHOLE walk sees a
    single stable snapshot of the authored store — ``_compute_base_version`` and
    every ``_visible_slice`` call observe the same snapshot. Under the default
    READ COMMITTED, a concurrent realization approval mid-walk would move
    ``visible_from`` for a record between step N and step N+1, making the chain
    dependent on approval timing and ``verify_reproducibility`` non-deterministic.
    REPEATABLE READ (Postgres) takes the snapshot at the txn's first statement
    (here, the ``pg_advisory_xact_lock``), so the walk is frozen for its duration.
    The append-only INSERTs do not conflict with the snapshot.

    Callers passing ``connection=`` (an outer txn) are responsible for its
    isolation: the REPEATABLE READ guarantee holds only when the derivation owns
    the transaction. The validation scripts pass a ``connection=`` from a
    rollback txn they control (single-threaded, no concurrency) — acceptable
    for validation; production callers that need atomicity + reproducibility must
    open their own REPEATABLE READ txn or let the derivation own it.
    """
    global _ENGINE
    if _ENGINE is None:
        from server.core.url import db_url

        _ENGINE = create_engine(db_url, pool_pre_ping=True, isolation_level="REPEATABLE READ")
    return _ENGINE


def _with_conn(connection: Any, fn: Any) -> Any:
    if connection is not None:
        return fn(connection)
    with _get_engine().begin() as conn:
        return fn(conn)


# ---------------------------------------------------------------------------
# Canonical serialization + hashing — the reproducibility foundation.
# ---------------------------------------------------------------------------
# Every hash is over a DETERMINISTIC byte string. Datetimes are normalized to
# UTC ISO-8601, keys are sorted, UUIDs are lowercased str. Same inputs => same
# hash on any machine, any timezone, any re-derivation. This is what makes
# "re-derivation at the same base_version reproduces the identical hash" true.


def _utc_iso(value: Any) -> Any:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("derivation timestamps must be timezone-aware")
        return value.astimezone(timezone.utc).isoformat()
    return value


def _canonical_json(fields: dict[str, Any]) -> str:
    """Sorted-keys, separator-tight JSON — the exact bytes hashed. Mirrors
    audit._canonical_json (kept local to avoid a private import)."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)


def _compute_base_version(conn: Any, case_id: str) -> str:
    """Hash every visibility-bearing source, route, acquisition, and realization input."""
    rows = conn.execute(
        text(
            "SELECT input_kind, input_key, input_payload "
            "FROM working.vw_walk_base_version_input "
            "WHERE case_id=:cid ORDER BY input_kind, input_key"
        ),
        {"cid": case_id},
    ).fetchall()
    canon = _canonical_json({"inputs": [{"kind": str(row[0]), "key": str(row[1]), "payload": row[2]} for row in rows]})
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _genesis_hash(base_version: str, parameters: dict[str, Any]) -> str:
    """prev_hash for step 1 = sha256(base_version || canonical parameters)."""
    return hashlib.sha256((base_version + _canonical_json(parameters)).encode("utf-8")).hexdigest()


def _canonical_slice(visible_rows: list[Any], horizon_at: datetime | None) -> str:
    """Deterministic serialization of a step's visible slice for hashing.
    ``visible_rows`` are (atom_kind, atom_id, occurred_at, visible_from,
    disclosure_tier) tuples. Sorted by kind/id so re-derivation is stable.
    """
    payload = [
        {
            "atom_kind": str(r[0]),
            "atom_id": str(r[1]),
            "occurred_at": _utc_iso(r[2]),
            "visible_from": _utc_iso(r[3]),
            "disclosure_tier": r[4],
        }
        for r in sorted(
            visible_rows,
            key=lambda r: (str(r[0]), str(r[1])),
        )
    ]
    return _canonical_json({"horizon_at": _utc_iso(horizon_at), "slice": payload})


def _step_corpus_hash(prev_hash: str, slice_canonical: str) -> str:
    """corpus_hash = sha256(prev_hash || slice). Binds the chain so any
    tampering with an earlier step changes every downstream hash."""
    return hashlib.sha256((prev_hash + slice_canonical).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# The visible-slice query — the horizon pre-filter (the contamination guard).
# ---------------------------------------------------------------------------

_SLICE_SQL = """
    SELECT atom_kind, atom_id, occurred_at, visible_from, disclosure_tier
      FROM working.vw_horizon_atom
     WHERE case_id = :cid
       AND visible_from IS NOT NULL
       AND visible_from <= :horizon
       AND disclosure_tier <> 'hindsight'
"""

_HINDSIGHT_SLICE_SQL = """
    SELECT atom_kind, atom_id, occurred_at, visible_from, disclosure_tier
      FROM working.vw_horizon_atom
     WHERE case_id = :cid
"""


def _visible_slice(conn: Any, case_id: str, horizon_at: datetime | None) -> list[Any]:
    """The records visible at a step. Ignorant: visible_from <= horizon AND not
    hindsight-tagged (the contamination pre-filter). Hindsight: the whole case."""
    if horizon_at is None:
        return conn.execute(text(_HINDSIGHT_SLICE_SQL), {"cid": case_id}).fetchall()
    return conn.execute(text(_SLICE_SQL), {"cid": case_id, "horizon": horizon_at}).fetchall()


# ---------------------------------------------------------------------------
# derive_walk — the SOLE-writer entry point.
# ---------------------------------------------------------------------------


def derive_walk(
    *,
    case_id: str = "primary",
    agent_id: str,
    horizon_policy: str,  # 'ignorant' | 'hindsight' | 'custom'
    horizon_schedule: list[datetime] | None,  # ignorant: advancing horizons; else None/[]
    bound_lane: str | None = None,
    model_id: str | None = None,
    prompt_version: str | None = None,
    parameters: dict[str, Any] | None = None,
    custom_horizon_ceiling: datetime | None = None,
    connection: Any = None,
) -> uuid.UUID:
    """Derive + persist ONE walk_run. The SOLE-writer entry for pass corpora.

    For an **ignorant** walk, ``horizon_schedule`` is the list of advancing
    horizon timestamps (one per step); the agent lives events as discovered.
    For **hindsight**, pass ``horizon_schedule=None`` — a single step with no
    cutoff sees the whole case. For **custom**, pass ``custom_horizon_ceiling``
    and an optional schedule (the ceiling caps each step).

    Acquires the F13 sole-writer advisory lock, pins ``base_version``, computes
    ``genesis_hash``, walks the schedule writing steps (each chain-hashed) +
    the final ``final_corpus_hash``, and attests every step + the final hash to
    ``ops.audit_ledger`` (atomic via ``connection``). Returns the ``walk_run.id``.
    """
    if horizon_policy not in ("ignorant", "hindsight", "custom"):
        raise ValueError(f"horizon_policy {horizon_policy!r} not allowed.")
    if horizon_policy == "custom" and custom_horizon_ceiling is None:
        raise ValueError("custom policy requires custom_horizon_ceiling.")
    if horizon_policy == "hindsight":
        # Hindsight = one step, no cutoff.
        horizon_schedule = [None]  # type: ignore[list-item]
    elif not horizon_schedule:
        raise ValueError(f"{horizon_policy} walk requires a non-empty horizon_schedule.")

    params = dict(parameters or {})

    def _do(conn: Any) -> uuid.UUID:
        # F13: sole-writer lock for the whole derivation. Two refreshers cannot
        # interleave; a crash releases it at txn end.
        conn.execute(text(f"SELECT pg_advisory_xact_lock({_LOCK_KEY_SQL})"))

        base_version = _compute_base_version(conn, case_id)
        genesis = _genesis_hash(base_version, params)

        run_id = conn.execute(
            text(
                "INSERT INTO working.walk_run "
                "(case_id, agent_id, bound_lane, horizon_policy, horizon_ceiling, "
                " model_id, prompt_version, base_version, parameters, genesis_hash) "
                "VALUES (:cid, :agent, :lane, :policy, :ceiling, :model, :prompt, "
                "        :base_version, CAST(:params AS jsonb), :genesis) RETURNING id"
            ),
            {
                "cid": case_id,
                "agent": agent_id,
                "lane": bound_lane,
                "policy": horizon_policy,
                "ceiling": custom_horizon_ceiling,
                "model": model_id,
                "prompt": prompt_version,
                "base_version": base_version,
                "params": _canonical_json(params),
                "genesis": genesis,
            },
        ).scalar()
        run_uuid = uuid.UUID(str(run_id))

        prev_hash = genesis
        from server.core.audit import record as audit_record  # local import (cycle-safe)

        for step_no, horizon_at in enumerate(horizon_schedule, start=1):
            # custom policy caps each step's horizon at the ceiling.
            if horizon_policy == "custom" and horizon_at is not None and custom_horizon_ceiling is not None:
                if horizon_at > custom_horizon_ceiling:
                    horizon_at = custom_horizon_ceiling

            slice_rows = _visible_slice(conn, case_id, horizon_at)
            slice_canonical = _canonical_slice(slice_rows, horizon_at)
            corpus_hash = _step_corpus_hash(prev_hash, slice_canonical)

            step_id = conn.execute(
                text(
                    "INSERT INTO working.walk_step "
                    "(walk_run_id, step_no, horizon_at, corpus_hash, prev_hash) "
                    "VALUES (:run, :step, :horizon, :corpus, :prev) RETURNING id"
                ),
                {
                    "run": str(run_uuid),
                    "step": step_no,
                    "horizon": horizon_at,
                    "corpus": corpus_hash,
                    "prev": prev_hash,
                },
            ).scalar()

            # Preserve typed provenance; realization UUIDs are not record UUIDs.
            record_rows = [row for row in slice_rows if row[0] == "normalized_record"]
            realization_rows = [row for row in slice_rows if row[0] == "realization_event"]
            if record_rows:
                conn.execute(
                    text(
                        "INSERT INTO working.walk_step_retrieval "
                        "(walk_step_id, record_id, store, was_used) "
                        "VALUES (:sid, :rid, 'postgres', true)"
                    ),
                    [{"sid": str(step_id), "rid": str(row[1])} for row in record_rows],
                )
            if realization_rows:
                conn.execute(
                    text(
                        "INSERT INTO working.walk_step_realization_retrieval "
                        "(walk_step_id, realization_event_id, store, was_used) "
                        "VALUES (:sid, :eid, 'postgres', true)"
                    ),
                    [{"sid": str(step_id), "eid": str(row[1])} for row in realization_rows],
                )

            # Hash-attest this step to ops.audit_ledger, atomically with the write.
            # base_version is BIGINT in audit_ledger (a generation number); the
            # precise content-hash lives in working.walk_run.base_version (TEXT),
            # so we attest the corpus_hash as payload_hash + the run id as
            # object_ref. The §B "records base_version" requirement is met by
            # walk_run.base_version + walk_step.corpus_hash/prev_hash; this audit
            # row is the tamper-evident attestation of the chain.
            audit_record(
                "derivation",
                str(run_uuid),
                actor=agent_id,
                ctx={"case_id": case_id, "pass_id": bound_lane, "horizon": _utc_iso(horizon_at)},
                object_schema="working",
                payload_hash=corpus_hash,
                connection=conn,
            )

            prev_hash = corpus_hash

        final_corpus_hash = prev_hash
        conn.execute(
            text(
                "UPDATE working.walk_run SET status='completed', finished_at=now(), final_corpus_hash=:h WHERE id=:id"
            ),
            {"h": final_corpus_hash, "id": str(run_uuid)},
        )
        return run_uuid

    return _with_conn(connection, _do)


# ---------------------------------------------------------------------------
# verify_reproducibility — the §B pre-binding gate.
# ---------------------------------------------------------------------------


def verify_reproducibility(
    *,
    walk_run_id: uuid.UUID,
    connection: Any = None,
) -> dict[str, Any]:
    """Re-derive the hash chain for a completed run at its RECORDED base_version
    and compare. The §B gate: a run is not bindable until this returns
    ``reproducible=True`` — same base_version => identical chain.

    Returns ``{reproducible: bool, recorded_base_version, current_base_version,
    step_count, mismatch_step}``. If the authored store changed since the run
    was derived, ``current_base_version`` differs (a new run is required by
    design — append-only), and ``reproducible=False`` with a clear reason.
    """

    def _do(conn: Any) -> dict[str, Any]:
        run = conn.execute(
            text("SELECT case_id, base_version, parameters, genesis_hash FROM working.walk_run WHERE id=:id"),
            {"id": str(walk_run_id)},
        ).first()
        if run is None:
            raise ValueError(f"walk_run {walk_run_id} not found.")
        case_id, recorded_base, params_json, genesis = run
        # params is fetched for completeness; the re-derivation is driven by the
        # recorded base_version + the live visible slices (genesis was already
        # computed from base_version+params at derivation time).
        current_base = _compute_base_version(conn, case_id)
        if current_base != recorded_base:
            return {
                "reproducible": False,
                "recorded_base_version": recorded_base,
                "current_base_version": current_base,
                "step_count": 0,
                "mismatch_step": 0,
                "reason": "authored store changed since derivation; a new run is required (append-only).",
            }

        steps = conn.execute(
            text(
                "SELECT step_no, horizon_at, corpus_hash, prev_hash "
                "FROM working.walk_step WHERE walk_run_id=:id ORDER BY step_no"
            ),
            {"id": str(walk_run_id)},
        ).fetchall()

        prev_hash = genesis
        for step_no, horizon_at, recorded_corpus, recorded_prev in steps:
            if prev_hash != recorded_prev:
                return {
                    "reproducible": False,
                    "recorded_base_version": recorded_base,
                    "current_base_version": current_base,
                    "step_count": len(steps),
                    "mismatch_step": step_no,
                    "reason": f"prev_hash mismatch at step {step_no} (chain broken).",
                }
            slice_rows = _visible_slice(conn, case_id, horizon_at)
            slice_canonical = _canonical_slice(slice_rows, horizon_at)
            recomputed = _step_corpus_hash(prev_hash, slice_canonical)
            if recomputed != recorded_corpus:
                return {
                    "reproducible": False,
                    "recorded_base_version": recorded_base,
                    "current_base_version": current_base,
                    "step_count": len(steps),
                    "mismatch_step": step_no,
                    "reason": f"corpus_hash mismatch at step {step_no}.",
                }
            prev_hash = recorded_corpus

        return {
            "reproducible": True,
            "recorded_base_version": recorded_base,
            "current_base_version": current_base,
            "step_count": len(steps),
            "mismatch_step": None,
        }

    return _with_conn(connection, _do)
