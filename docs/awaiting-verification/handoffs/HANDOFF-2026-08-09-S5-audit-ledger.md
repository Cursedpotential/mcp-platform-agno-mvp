# HANDOFF S5 — Audit ledger (owner VIP: audit EVERYTHING)
> _2026-08-09 · repo @ a68fabd · STATUS: READY after S3 + ADR-0047 draft · Depends: S3 · Blocks: S6, S7, S8 audit hooks_
> Inventory items: R-1, ADR-0047 implementation. Pattern donors: SBV hash-chained repair ledger, evidence.custody_event.
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.
> Gating note: ADR-0047 DRAFT suffices to build (unlike S6's signed-0045 gate) because the underlying
> decision — audit everything, including reads — is an owner ruling already made 2026-08-09 (R-1);
> the ADR is its ratification. The schema is additive and append-only; signature flips Status only.

## Goal
One append-only, hash-chained ledger recording every decision, action, modification, and READ —
retrievable on the owner's demand. Single-operator schema (owner ruling: never multi-user).

## Tasks
1. New migration `sql/0020_audit_ledger.sql` (number after S3's 0019): `ops.audit_ledger`
   (id, ts, actor, action_type ENUM('decision','write','read','tool_call','approval','derivation'),
   object_schema, object_ref, horizon_context JSONB (case_id/pass_id/horizon/actor or NULL=hindsight-grant),
   base_version, payload_hash, prev_hash, entry_hash). entry_hash = sha256(prev_hash || canonical
   row serialization) — same chain discipline as SBV's repair ledger. Append-only trigger (reuse
   0017_append_only_guards pattern). Header cites ADR-0047.
2. Writer: `server/core/audit.py` — single `record(action_type, object_ref, ctx, payload)` function;
   the ONLY insert path; chain head cached, verified on startup (`verify_chain()` walks and
   re-hashes; mismatch = loud failure).
3. Action auditing: agno `tool_hooks` wrapper logging every tool invocation (tool id, args hash —
   never raw args if they may contain case content; store payload_hash) — the Agno-native audit
   table already prescribes tool_hooks for custody/audit wrapping; do NOT build a custom
   interception layer. HITL approvals: log approval resolution events alongside native /approvals.
4. Modification auditing: cross-reference — evidence.custody_event and 0017 append-only guards
   already cover evidence-schema writes; ledger `write` entries reference custody_event ids rather
   than duplicating them (one fact, one home; the ledger is the index, custody_event the detail).
5. Read auditing — INTERFACE ONLY in this segment: `record('read', …)` call signature + docs.
   Actual read hooks land lane-by-lane in S6 (Postgres wrapper, KnowledgeHandle, Graphiti client,
   MCP doors) — each S6 lane's acceptance includes "read appears in ledger."
6. Retrieval: `scripts/audit_dump.py` — filterable dump (by time range, actor, action_type,
   object) + chain verification; containerized invocation documented. This is the "on my call"
   surface.
7. Tests: chain integrity (tamper a row in a scratch DB → verify_chain fails); append-only trigger
   rejects UPDATE/DELETE; tool_hook fires on a registered tool call.

## Acceptance
`docker compose run --rm agentos-api python scripts/audit_dump.py --verify` → chain OK; a test tool
call and a test approval each produce exactly one ledger row; UPDATE on ops.audit_ledger raises.

## Constraints
Standing constraints per PLAN master. No raw case content in ledger rows (hashes + refs only —
the ledger must be safely dumpable). Never multi-user fields. New files cite ADR-0047.
