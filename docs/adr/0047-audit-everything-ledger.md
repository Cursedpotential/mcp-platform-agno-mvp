# ADR-0047 — Audit-everything ledger (ops.audit_ledger, hash-chained, reads included)

> _Byline: Claude (Cowork) · Fable 5 · 2026-08-09_

- **Status:** **Accepted** (owner signed 2026-08-09; ratifies the same-day audit-everything ruling; recorded as D-042)
- **Context sources:** owner ruling 2026-08-09: "every decision, every action, every
  modification, every read — everything needs to be audited, with that information on my call."
  Pattern donors already in-tree: SBV's hash-chained repair ledger, `evidence.custody_event`,
  `sql/0017_append_only_guards.sql`.

## Context

The platform already audits pieces of itself — custody events for evidence writes, SBV's
hash-chained repair log, native `/approvals` records — but there is no single, queryable,
tamper-evident record of everything that happened, and READS are audited nowhere. For a
court-facing platform whose core claim is "this is what the agent could know and when," the
read trail is as probative as the write trail.

## Decision

1. **One ledger:** `ops.audit_ledger` — append-only (0017-style guard triggers), hash-chained:
   `entry_hash = sha256(prev_hash || canonical-serialization(row))`. Columns: id, ts, actor,
   `action_type` ∈ {decision, write, read, tool_call, approval, derivation}, object_schema,
   object_ref, horizon_context JSONB (case_id/pass_id/horizon/actor; NULL = explicit hindsight
   grant), base_version, payload_hash, prev_hash, entry_hash.
2. **One writer:** `server/core/audit.py::record()` — the only insert path. `verify_chain()`
   re-hashes the chain and fails LOUDLY on mismatch; it runs at startup and in every backup
   cycle.
3. **No raw case content in the ledger** — hashes and references only, so the ledger is always
   safely dumpable. Detail stays in its home (custody_event, approvals, pass corpora); the
   ledger is the index that binds them.
4. **Coverage:** tool invocations via agno `tool_hooks` (native — never a custom interception
   layer); HITL approval resolutions; evidence writes (by reference to custody_event); every
   derivation with its corpus hash (ADR-0045 condition 3); every agent-facing READ across all
   lanes — Postgres, Weaviate, Graphiti, MCP doors — stamped with the HorizonContext used.
5. **Retrieval on demand:** `scripts/audit_dump.py` — filterable (time/actor/action/object) +
   chain verification. Single-operator schema; no multi-user fields, ever (D-041).

## Consequences

- S5 builds the ledger + write/action hooks; each S6 lane lands its read hook as part of the
  lane's acceptance ("the read appears in the ledger").
- The ledger becomes the spine that ADR-0045's attestations and ADR-0046's MCP audit rows hang
  from; backup cycles (S9) verify the chain, so tampering or corruption surfaces on schedule.
- Cost: one insert per audited event. At single-operator scale this is noise; no sampling, no
  tiering, no exceptions — an exception list is where audit trails go to die.

## Alternatives considered

- **Per-store audit tables only (no unified ledger)** — rejected: "what happened around 3pm
  Tuesday" would require joining N stores with N conventions; the owner's requirement is one
  pull.
- **Log-file auditing** — rejected: not queryable, not tamper-evident, not restorable with the
  database.
- **Auditing writes only** — rejected by the owner ruling explicitly; the read trail is the
  point.
- **Custom tool-call interception** — rejected: agno `tool_hooks` is the native mechanism
  (Agno-native audit table, DEBT.md).
