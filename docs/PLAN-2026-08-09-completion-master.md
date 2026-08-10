# Completion Plan — Master Index
> _Byline: Claude (Cowork) · Fable 5 · 2026-08-09 · repo @ a68fabd (local checkout verified identical)_
> Source: full repo audit 2026-08-09 + owner planning session. Companion: `INVENTORY-2026-08-09.md`
> (every finding/ruling maps to at least one segment, primary owner first; adversarial coverage
> pass ran 2026-08-09 — 22 findings, all fixed same day).

## Segments (each has its own HANDOFF file; each is one agent-executable unit of work)

| Seg | Handoff | Theme | Depends on | Owner decisions needed |
|-----|---------|-------|------------|------------------------|
| S4 | HANDOFF-…-S4-adr-package-owner-rulings | ADR-0045/0046/0047 drafts + rulings sheet | — | SIGN 0045 · rule OQ-2/7/8/9/10/11 |
| S1 | HANDOFF-…-S1-docs-registers-true-up | Docs/canon/DEBT true-up + traceability checks | S4 task 4 (D-NNN ids allocated) | none |
| S2 | HANDOFF-…-S2-build-and-test-green | requirements regen, test fixes, green suite | S4 task 4 (D-NNN ids); OQ-10 improves task 1 | none |
| S3 | HANDOFF-…-S3-sql-bootstrap-hygiene | baseline regen, 0019 bridge, README honesty | S2 | none |
| S5 | HANDOFF-…-S5-audit-ledger | ops.audit_ledger + tool_hooks (VIP: audit everything) | S3, ADR-0047 | none |
| S6 | HANDOFF-…-S6-horizon-spine-derivation-engine | clocks, derivation engine, all 5 lanes bound | S3, S5, ADR-0045 signed, OQ-8 ruled (OQ-3 probe is an S6 task, not a gate) | OQ-8 |
| S7 | HANDOFF-…-S7-sbv-live-test-parser-lane | SBV live verification + registry/contract/repair | S2, S5 (audit hooks) | OQ-9 (doc only) |
| S8 | HANDOFF-…-S8-semantica-graph-lane | Semantica worker slice → evidence graph (tasks 1–6; task 7 backfill AFTER S9 task 1) | S5, S6 (visible_from) | none |
| S9 | HANDOFF-…-S9-population-evals-backups | pipeline population, horizon canary evals, R2 backups | S6, S7; E1 gated on OQ-11/D-008 | OQ-11 sign |

## Critical path
S4(sign 0045) → S2 → S3 → S5 → S6 → S8 → S9(population→canary)
S1 parallel once S4 allocates D-NNN ids. S7 parallel after S5.

## Standing constraints (every segment inherits; every handoff carries a MANDATORY pointer here — a fresh agent reads this section before executing any handoff)
Never delete → `_stale/` · containerized-only (`docker compose`) · never edit applied migrations ·
SURREALDB_URL default untouched · agent-ui+browser+hotfix branch never resurrected · no secrets/PII
in git or transcripts · dict filters ONLY on Weaviate · extraction horizon-blind · evidence schema
append-only, custody.py sole writer · VIP components never forked around · HITL-first ·
PROJECT_CANON §5 locked decisions cited, never reopened · NEVER multi-case/multi-user (owner ruling
2026-08-09) · every action/write/read audited to the ledger once S5 lands (owner VIP ruling 2026-08-09).

## Architecture rulings this plan implements (owner, 2026-08-09 session)
1. **Checkpoint-derivation architecture**: canonical factual layer (ingestion + Semantica) is the only
   authored store; pass corpora (as-lived incremental, hindsight on-prompt) are DERIVED by one
   grant-locked refresher through one predicate, version-pinned, hash-attested. Canon §1 amended
   accordingly (ADR-0045). Walk-ledger = the as-lived derivation log (closes OQ-1).
2. **visible_from = COALESCE(realized_at, occurred_at)** is the recommended horizon clock (ADR-0045
   Option A; acquired_at is custody metadata — bulk-acquisition failure case documented in the ADR).
3. **Audit-everything**: hash-chained `ops.audit_ledger`; decisions, actions, modifications, and READS.
4. **Never multi-case/multi-user**: case_id stays TEXT `'primary'`; no unification migration; no
   multi-user auth anywhere in this plan.
