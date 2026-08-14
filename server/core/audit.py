"""
core/audit.py — the ONE writer of ``ops.audit_ledger`` (ADR-0047 / D-042).

Owner ruling 2026-08-09 (R-1, ratified as ADR-0047, accepted/signed same day):
"every decision, every action, every modification, every read — everything
needs to be audited, with that information on my call." This module is the
single insert path for that ledger — nothing else may write
``ops.audit_ledger`` (mirrors ``server/evidence/custody.py``'s sole-writer
contract for the ``evidence`` schema).

Public surface
--------------
``record()``            — the ONLY insert path. Every other helper here
                           (``record_custody_ref``, ``record_read``,
                           ``record_approval``, ``audit_tool_hook``) is a thin
                           wrapper around it.
``verify_chain()``       — walks the whole chain and re-derives every
                           ``entry_hash``; raises ``AuditChainError`` LOUDLY
                           on the first mismatch. Intended call sites (not
                           wired here — outside this module's scope):
                           ``server/api/main.py``'s ``lifespan()`` (startup)
                           and the S9 backup cycle (ADR-0047 consequences).
``record_custody_ref()`` — log a ``write`` row that REFERENCES an
                           ``evidence.custody_event`` id rather than
                           duplicating its detail (ADR-0047 decision 4:
                           "one fact, one home").
``record_read()``        — the ``read`` INTERFACE (ADR-0047 decision 4 /
                           S5 handoff task 5): S6 lands the per-lane hooks
                           (Postgres wrapper, KnowledgeHandle/Weaviate,
                           Graphiti client, MCP doors) that call this.
``record_approval()``    — approval-resolution logging. agno's native
                           ``/approvals`` router is auto-mounted from
                           installed ``agno.os.routers.approvals.router``
                           (NOT vendored, not in this repo's file scope) and
                           has no hook parameter — wiring this helper in
                           cleanly needs either a thin wrapper around the
                           ``os_db`` handed to ``AgentOS(db=admin_db, ...)``
                           in ``server/api/main.py`` (wrap
                           ``admin_db.update_approval`` to call
                           ``record_approval()`` after a successful
                           resolve) or ASGI middleware on
                           ``POST /approvals/{id}/resolve``. That edit is
                           OUTSIDE this module's file scope (S5 handoff:
                           "if the native /approvals surface has no clean
                           hook point without invasive changes, implement
                           the helper + document the call site for S6") —
                           documented here for S6, not wired.
``audit_tool_hook()``    — the agno-native ``tool_hooks`` callable (ADR-0047
                           decision 4: "tool invocations via agno tool_hooks
                           — native, never a custom interception layer").
                           Wired onto every Agent/Team ``server.agents.
                           factory.build_agent_team()`` constructs — see
                           that function's integration-point comment.

No raw case content — ever
---------------------------
Every argument that ends up in a ledger row must be a hash, an id, or a
short structural fact (a byte count, a schema name) — NEVER message text,
file contents, tool-call payload bytes, or anything a court would call
"the evidence itself". ``payload_hash`` exists so callers can prove *what*
was read/written/called without the ledger ever holding *what it says*.
This is enforced by convention and by this docstring, not by a runtime
content filter (there is no reliable way to detect "is this string case
content" after the fact) — every caller is responsible for hashing before
calling ``record()``. The one runtime guard this module DOES apply:
``payload_hash``/``prev_hash``/``entry_hash`` must look like hex digests,
which incidentally also catches "someone passed raw text as payload_hash".

Chain design
------------
``entry_hash = sha256(prev_hash + canonical_json(business_fields))`` where
``business_fields`` is the sorted-keys JSON of
``{ts, actor, action_type, object_schema, object_ref, horizon_context,
base_version, payload_hash}`` — NOT including ``prev_hash`` itself (that is
prepended raw, matching the S5 handoff spec literally) or the ``id`` (insertion
order already fixes the chain's position; hashing the identity-assigned id
would make the hash depend on a value chosen by Postgres rather than by the
event).

Unlike ``evidence.custody_event`` (whose chain hash is computed in a DB
TRIGGER — ``evidence.chain_custody_event``, see
``sql/bootstrap/schema_baseline.sql``), this ledger's hash is computed HERE,
in application code, before the row is ever sent to Postgres. That is a
deliberate reversal, not an oversight: the trigger approach chains PER
``source_id`` (one custody subject, one lock key); this ledger is ONE global
chain across every actor and action type, so the serialization boundary has
to be the whole table, and holding that boundary in a DB trigger would still
need the same PostgreSQL-side advisory lock this module takes explicitly —
doing it in Python keeps the single-writer contract (and the "only
``record()`` may INSERT this table" contract) visible in one place instead of
split across a Python caller and a SQL trigger body.

Concurrency: two overlapping transactions must never observe the same
"current last row" and both compute the same ``prev_hash`` — that would fork
the chain. A bare ``SELECT ... ORDER BY id DESC LIMIT 1 FOR UPDATE`` does NOT
prevent this at READ COMMITTED: the row it locks is the OLD last row, which
is never itself UPDATEd by the next INSERT, so a blocked-then-unblocked
waiter still reads stale (pre-INSERT) data once it gets the lock — it does
not get re-pointed at the row the other transaction just committed. This
module instead takes a single-key transaction-scoped advisory lock
(``pg_advisory_xact_lock``) BEFORE reading the last row — the same pattern
already in-tree for ``evidence.custody_event`` (``evidence.chain_custody_event``
locks ``hashtextextended(NEW.source_id::text, 0)`` before its own
prev-digest lookup). Whichever transaction acquires the lock first serializes
every reader/writer behind it; the lock is released automatically at
COMMIT/ROLLBACK (``_xact`` — no explicit unlock needed, and none is skipped
by an exception).
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-09 (ADR-0047 / D-042 — S5 handoff)
# Byline: Codex · GPT-5 · 2026-08-13 (shared-transaction audit writes)

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from typing import Any, Callable

_engine: Any = None

# The six action_types ADR-0047 decision 1 / sql/0020's CHECK constraint name.
ACTION_TYPES = frozenset({"decision", "write", "read", "tool_call", "approval", "derivation"})

# One fixed advisory-lock key for the whole ledger (see module docstring,
# "Concurrency"). hashtext() is a stable 32-bit hash of the literal string —
# any two processes computing pg_advisory_xact_lock(hashtext('ops.audit_ledger'))
# contend for the SAME lock.
_CHAIN_LOCK_KEY_SQL = "hashtext('ops.audit_ledger')"

_HEX_RE = re.compile(r"^[0-9a-f]+$", re.IGNORECASE)


class AuditChainError(RuntimeError):
    """Raised by verify_chain() the instant a stored entry_hash does not
    match its re-derivation — tamper or corruption, either way LOUD."""


def _get_engine() -> Any:
    """Lazy SQLAlchemy engine, mirroring server/core/session.py /
    server/evidence/custody.py / server/evidence/store.py / server/agents/
    factory.py's `_get_write_engine()` — created on first use, not at
    import, so this module can be imported with no DB available (tests,
    tool-facade construction)."""
    global _engine
    if _engine is None:
        from sqlalchemy import create_engine

        from server.core.url import db_url

        _engine = create_engine(db_url, pool_pre_ping=True)
    return _engine


def _check_hex(value: str | None, field: str) -> None:
    if value is not None and not _HEX_RE.match(value):
        raise ValueError(
            f"audit.record: {field}={value!r} does not look like a hex digest — "
            "this ledger is hashes/refs ONLY, never raw content (ADR-0047 decision 3)."
        )


def _canonical_json(fields: dict[str, Any]) -> str:
    """Sorted-keys, separator-tight JSON — the exact bytes that go into the
    chain hash. `default=str` covers datetimes (ISO 8601 already applied by
    the caller, but any stray datetime/UUID still serializes deterministically
    rather than raising)."""
    return json.dumps(fields, sort_keys=True, separators=(",", ":"), default=str)


def record(
    action_type: str,
    object_ref: str | None,
    *,
    actor: str,
    ctx: dict[str, Any] | None = None,
    object_schema: str | None = None,
    base_version: int | None = None,
    payload_hash: str | None = None,
    engine: Any = None,
    connection: Any = None,
) -> int:
    """Append ONE row to ``ops.audit_ledger``. The ONLY insert path.

    Parameters
    ----------
    action_type:
        One of ``ACTION_TYPES`` (``decision``, ``write``, ``read``,
        ``tool_call``, ``approval``, ``derivation`` — ADR-0047 decision 1).
    object_ref:
        A reference into ``object_schema`` — a row id, a
        ``custody_event.id``, an approval id, a tool name — NEVER content.
    actor:
        Who/what performed the action (agent id, ``"owner"``, a tool name,
        a script name). Required — this is a single-operator platform, but
        every ledger row still names its actor (owner ruling: never
        multi-user fields, but "actor" here is attribution, not a user
        account).
    ctx:
        ``horizon_context`` — ``{case_id, pass_id, horizon, actor}`` or a
        caller-defined dict of the same shape. ``None`` means an explicit
        hindsight grant (ADR-0047 decision 1) — NOT "unknown"; callers that
        genuinely don't know the horizon should still pass an empty dict,
        not rely on ``None``'s hindsight meaning by accident.

        For a ``read`` row (see ``record_read()``): this MUST be the
        ``HorizonContext`` actually used to filter/serve that read — this
        is the field a future "what could the agent see and when" audit
        query reads.
    object_schema:
        The schema the event concerns (``"evidence"``, ``"working"``,
        ...). Optional — a bare ``tool_call`` with no DB object has none.
    base_version:
        The version/generation this event was computed against (derivation
        provenance, ADR-0045 condition 3). Optional elsewhere.
    payload_hash:
        sha256 hex digest of whatever payload this event carries. NEVER
        the raw payload. Optional (some events, e.g. a bare read of a
        single row by id, may have nothing worth hashing beyond
        ``object_ref`` itself).
    engine:
        Override the SQLAlchemy engine (tests use this to point at a
        scratch DB). Defaults to the lazy module-level engine.
    connection:
        Existing SQLAlchemy connection whose surrounding transaction must
        also contain this audit row. This is used when an authoritative
        action and its audit entry must commit atomically. Mutually exclusive
        with ``engine``; callers retain transaction ownership.

    Returns
    -------
    int
        The new row's ``id``.

    Raises
    ------
    ValueError
        ``action_type`` not in ``ACTION_TYPES``, or ``payload_hash`` is
        present but not hex (see module docstring, "No raw case content").
    """
    if action_type not in ACTION_TYPES:
        raise ValueError(f"audit.record: action_type must be one of {sorted(ACTION_TYPES)}, got {action_type!r}")
    _check_hex(payload_hash, "payload_hash")
    if engine is not None and connection is not None:
        raise ValueError("audit.record: pass either engine or connection, not both")

    from sqlalchemy import text

    ts = datetime.now(timezone.utc)
    business_fields = {
        "ts": ts.isoformat(),
        "actor": actor,
        "action_type": action_type,
        "object_schema": object_schema,
        "object_ref": object_ref,
        "horizon_context": ctx,
        "base_version": base_version,
        "payload_hash": payload_hash,
    }
    canonical = _canonical_json(business_fields)

    def _insert(conn: Any) -> int:
        # Single-key advisory lock BEFORE reading the chain head — see the
        # module docstring's "Concurrency" section for why a bare
        # `SELECT ... FOR UPDATE` on the last row is not sufficient here.
        conn.execute(text(f"SELECT pg_advisory_xact_lock({_CHAIN_LOCK_KEY_SQL})"))
        prev_hash = conn.execute(text("SELECT entry_hash FROM ops.audit_ledger ORDER BY id DESC LIMIT 1")).scalar()
        entry_hash = hashlib.sha256(((prev_hash or "") + canonical).encode("utf-8")).hexdigest()
        new_id = conn.execute(
            text(
                "INSERT INTO ops.audit_ledger "
                "(ts, actor, action_type, object_schema, object_ref, horizon_context, "
                " base_version, payload_hash, prev_hash, entry_hash) "
                "VALUES (:ts, :actor, :action_type, :object_schema, :object_ref, "
                " CAST(:ctx AS jsonb), :base_version, :payload_hash, :prev_hash, :entry_hash) "
                "RETURNING id"
            ),
            {
                "ts": ts,
                "actor": actor,
                "action_type": action_type,
                "object_schema": object_schema,
                "object_ref": object_ref,
                "ctx": json.dumps(ctx) if ctx is not None else None,
                "base_version": base_version,
                "payload_hash": payload_hash,
                "prev_hash": prev_hash,
                "entry_hash": entry_hash,
            },
        ).scalar()
        if new_id is None:
            raise RuntimeError("audit.record: INSERT did not return an id")
        return int(new_id)

    if connection is not None:
        return _insert(connection)
    eng = engine if engine is not None else _get_engine()
    with eng.begin() as conn:
        return _insert(conn)


def record_custody_ref(
    custody_event_id: str,
    *,
    actor: str,
    ctx: dict[str, Any] | None = None,
    base_version: int | None = None,
    payload_hash: str | None = None,
    engine: Any = None,
) -> int:
    """Log a ``write`` ledger row that REFERENCES an
    ``evidence.custody_event`` id, rather than duplicating its detail
    (ADR-0047 decision 4: "one fact, one home" — ``evidence.custody_event``
    is the detail record, ``ops.audit_ledger`` is the index that binds it
    into the one-pull chronology). Call this immediately after
    ``server/evidence/custody.py``'s ``record_custody_event()`` returns its
    new id.
    """
    return record(
        "write",
        str(custody_event_id),
        actor=actor,
        ctx=ctx,
        object_schema="evidence",
        base_version=base_version,
        payload_hash=payload_hash,
        engine=engine,
    )


def record_read(
    object_ref: str | None,
    *,
    actor: str,
    ctx: dict[str, Any] | None = None,
    object_schema: str | None = None,
    base_version: int | None = None,
    payload_hash: str | None = None,
    engine: Any = None,
) -> int:
    """READ-AUDIT INTERFACE (S5 handoff task 5 / ADR-0047 decision 4).

    This IS a working call — it inserts a real ``read`` row — but S5 only
    defines the contract; no lane calls it yet. S6 wires one call per lane,
    each stamped with the ``HorizonContext`` actually used to serve that
    read, and each lane's acceptance criterion is "the read appears in the
    ledger":

    * Postgres wrapper — around every agent-facing SELECT (or the
      ``working.horizon_visible``-filtered views/functions from
      ``sql/0018_retrieval_axes.sql``).
    * ``KnowledgeHandle`` (Weaviate) — around every ``search``/``asearch``
      that returns results to an agent.
    * Graphiti client — around every query against the evidence graph.
    * MCP doors — around every tool call that crosses an MCP boundary into
      a read.

    ``ctx`` is the HorizonContext (case_id/pass_id/horizon/actor) that
    governed what the read could see; ``object_schema``/``object_ref``
    identify what was read (schema + a row/document id or query hash — not
    the returned content); ``payload_hash`` may carry a hash of the result
    set if that is useful for later verification. Signature matches
    ``record()`` exactly (this is a thin, semantically-named wrapper) —
    ``action_type='read'`` is fixed so no lane can call this and produce a
    row typed something other than 'read'.
    """
    return record(
        "read",
        object_ref,
        actor=actor,
        ctx=ctx,
        object_schema=object_schema,
        base_version=base_version,
        payload_hash=payload_hash,
        engine=engine,
    )


def record_approval(
    approval_id: str,
    status: str,
    *,
    actor: str,
    ctx: dict[str, Any] | None = None,
    payload_hash: str | None = None,
    engine: Any = None,
) -> int:
    """Log an ``approval`` ledger row for one resolved agno native approval.

    NOT WIRED in S5 — documented for S6 (S5 handoff task 4: "if the native
    /approvals surface has no clean hook point without invasive changes,
    implement the helper + document the call site ... rather than forcing
    it"). agno auto-mounts ``POST /approvals/{id}/resolve`` from the
    INSTALLED ``agno.os.routers.approvals.router`` (verified against
    installed agno==2.8.7 — not a file in this repo, not vendored) with no
    hook parameter of its own; the resolve handler calls
    ``os_db.update_approval(...)`` (``os_db`` = the ``admin_db`` passed to
    ``AgentOS(db=admin_db, ...)`` in ``server/api/main.py``).

    The clean call site for S6 is therefore one of:

    1. Wrap ``admin_db.update_approval`` at construction time in
       ``server/api/main.py`` (monkeypatch-by-composition: keep the
       original bound method, call it, then call ``record_approval()``
       with its return value's ``status``/``resolved_by`` on success) — the
       least invasive option since it touches one call site, not agno's
       installed package.
    2. ASGI middleware in ``server/api/main.py`` matching
       ``POST /approvals/{id}/resolve`` responses.

    Neither touches this module's file scope (``server/core/audit.py``),
    which is why this is a helper + a documented call site rather than a
    wired hook.

    Parameters
    ----------
    approval_id:
        The agno approval row's id.
    status:
        The resolution (``"approved"`` / ``"rejected"`` / ...).
    actor:
        The human who resolved it (``resolved_by`` from the approval row —
        NEVER the JWT/user id verbatim if that would be PII beyond what
        this single-operator platform already treats as the owner's own
        identity).
    """
    return record(
        "approval",
        approval_id,
        actor=actor,
        ctx=ctx,
        object_schema="ops",
        payload_hash=payload_hash,
        engine=engine,
    )


def audit_tool_hook(
    function_name: str,
    function: Callable[..., Any],
    arguments: dict[str, Any],
    agent: Any = None,
    team: Any = None,
) -> Any:
    """agno-native ``tool_hooks`` callable (ADR-0047 decision 4: "tool
    invocations via agno ``tool_hooks`` — native, never a custom
    interception layer").

    Wired onto every ``Agent``/``Team`` ``server/agents/factory.py``
    constructs (see that module's ``build_agent_team()`` integration-point
    comment) via ``obj.tool_hooks = [*(obj.tool_hooks or []), audit_tool_hook]``.

    Signature confirmed against the INSTALLED ``agno==2.8.7`` package
    (``agno/tools/function.py``, ``FunctionCall._build_hook_args`` +
    ``_build_nested_execution_chain`` — not vendored in this repo; read
    inside the container per the handoff): a tool hook is a plain callable;
    agno introspects its parameter NAMES (not types, not decorators) and
    injects whichever of ``{agent, team, run_context, name, function_name,
    function, func, function_call, args, arguments}`` it declares.
    ``function``/``func``/``function_call`` is the CONTINUATION — the hook
    MUST call it (here: ``function(**arguments)``) and return its result,
    or the tool never actually executes and no result is ever produced.
    Hooks run wrapped-innermost-first when more than one is registered
    (``_build_nested_execution_chain``'s ``reduce`` over reversed hooks).
    Sync-only: agno silently skips async hooks when the tool call itself is
    sync (``execute()``'s ``iscoroutinefunction`` filter) — this hook is
    synchronous so it always runs.

    Logs ONE ``tool_call`` ledger row per invocation: the tool name, a
    sha256 of the CANONICALIZED (sorted-keys JSON) arguments — never the
    raw arguments, which may carry case content (ADR-0047 decision 3) — and
    the result size (``len()`` of the stringified result, never the result
    itself). Actor is the calling agent/team id when agno supplies one,
    else the tool name.

    Audit-write failures are NOT swallowed: ADR-0047's "no sampling, no
    tiering, no exceptions — an exception list is where audit trails go to
    die" reads as a promise that a broken audit path fails the action it
    was supposed to audit, not one that silently drops it. If
    ``ops.audit_ledger`` is unreachable, the tool call raises instead of
    completing unaudited.
    """
    canonical_args = _canonical_json(arguments)
    args_hash = hashlib.sha256(canonical_args.encode("utf-8")).hexdigest()

    result = function(**arguments)

    try:
        result_size = len(result) if isinstance(result, (str, bytes)) else len(_canonical_json({"r": result}))
    except Exception:
        result_size = -1

    actor = getattr(agent, "id", None) or getattr(team, "id", None) or function_name
    record(
        "tool_call",
        function_name,
        actor=str(actor),
        payload_hash=args_hash,
        ctx={"result_size": result_size},
    )
    return result


def verify_chain(engine: Any = None) -> int:
    """Walk ``ops.audit_ledger`` in id order and re-derive every
    ``entry_hash``. Raises ``AuditChainError`` the instant a stored hash
    does not match its re-derivation (tamper or corruption — LOUD, no
    partial-trust return value).

    Intended call sites (both OUTSIDE this module's file scope, per the S5
    handoff — documented here, not wired):

    * ``server/api/main.py``'s ``lifespan()`` — run once at API startup
      (S5 handoff task 2: "chain head cached, verified on startup").
    * The S9 backup cycle — ADR-0047 consequences: "backup cycles (S9)
      verify the chain, so tampering or corruption surfaces on schedule."

    Returns
    -------
    int
        The number of rows verified (0 for an empty, trivially-valid
        chain).
    """
    from sqlalchemy import text

    eng = engine if engine is not None else _get_engine()
    prev_hash: str | None = None
    n = 0
    with eng.connect() as conn:
        rows = (
            conn.execute(
                text(
                    "SELECT id, ts, actor, action_type, object_schema, object_ref, "
                    "horizon_context, base_version, payload_hash, prev_hash, entry_hash "
                    "FROM ops.audit_ledger ORDER BY id ASC"
                )
            )
            .mappings()
            .all()
        )
    for row in rows:
        n += 1
        if row["prev_hash"] != prev_hash:
            raise AuditChainError(
                f"ops.audit_ledger id={row['id']}: prev_hash={row['prev_hash']!r} does not match "
                f"the actual previous entry_hash={prev_hash!r} — chain is broken (row inserted "
                "out of order, or a row was tampered/removed)."
            )
        ts = row["ts"]
        ts_iso = ts.isoformat() if isinstance(ts, datetime) else ts
        horizon_context = row["horizon_context"]
        if isinstance(horizon_context, str):
            horizon_context = json.loads(horizon_context)
        business_fields = {
            "ts": ts_iso,
            "actor": row["actor"],
            "action_type": row["action_type"],
            "object_schema": row["object_schema"],
            "object_ref": row["object_ref"],
            "horizon_context": horizon_context,
            "base_version": row["base_version"],
            "payload_hash": row["payload_hash"],
        }
        canonical = _canonical_json(business_fields)
        expected = hashlib.sha256(((prev_hash or "") + canonical).encode("utf-8")).hexdigest()
        if expected != row["entry_hash"]:
            raise AuditChainError(
                f"ops.audit_ledger id={row['id']}: entry_hash mismatch — stored "
                f"{row['entry_hash']!r}, re-derived {expected!r}. Chain tampered or corrupted "
                f"at or before this row (actor={row['actor']!r}, action_type={row['action_type']!r})."
            )
        prev_hash = row["entry_hash"]
    return n
