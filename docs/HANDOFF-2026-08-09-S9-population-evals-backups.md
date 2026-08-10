# HANDOFF S9 — Population, evals, backups (proof + safety net)
> _2026-08-09 · repo @ a68fabd · STATUS: population BLOCKED on OQ-11/D-008 signature; evals BLOCKED on S6; backups READY after S3 · Depends: S6, S7 (+S8 for graph backfill trigger) · Blocks: Part 2 build-out_
> Inventory items: T5, TD-E7, TD-EV, SD-7, M-4, DEBT-P2 population row, OQ-11 + post-ruling closeout of OQ-2/7/9 TODOs.
> MANDATORY: read PLAN-2026-08-09-completion-master.md §Standing constraints before executing.

## Goal
Real data through the real pipeline, the platform's highest-value assertion running as a standing
eval, and the whole thing surviving a disk fire.

## Tasks
1. [OQ-11] Evidence pipeline population against the SIGNED D-008 schema (RESTART-0001
   per-source raw tables + file_custody anchor), landing as NEW migration
   `sql/0023_restart0001_evidence_schema.sql` (next free number after S6's 0022 — never hand-pick
   another number; never edit applied files). DO NOT build against the old ingestion schema
   (owner-declared DEAD) or the unsigned draft. Pipeline writes ALL clocks (occurred_at,
   acquired_at; realized_at stays NULL pending HITL) + full custody from day one; every write →
   ledger. Live evidence schema was near-empty at audit (evidence_hash = 26 rows) — this step is
   the largest open item in the register (DEBT P2). Triggers S8 task 7 backfill when done.
2. [T5/TD-EV/SD-7/M-4] Evals — populate evals/cases.py via native agno.eval (harness shape already
   correct; docstring already names AgentAsJudgeEval/ReliabilityEval; never a custom harness):
   a. **Horizon-leak canary** (the single highest-value assertion): fixture corpus seeded with a
      planted future fact; string-verifiable cases where the correct Pass-1 answer DIFFERS from the
      hindsight answer (M-4 pattern: independent, read-only, verifiable by comparison); an
      as-lived agent citing the planted fact = hard fail.
   b. ReliabilityEval tool-call assertions for the SBV facade + gateway quad.
   c. AgentAsJudgeEval pass checks for walk outputs (post-S6).
   `docker compose run --rm agentos-api python -m evals` runs non-empty and green — README's
   "must run green" claim becomes true. Until this task, cases.py stays `CASES = ()` and is NOT
   drift (documented intentional stub).
3. [TD-E7] Recurring backups: pg_dump + Neo4j dump (BOTH DozerDB databases) → R2 (`nexus` creds
   already in .env per canon §7). Existing scripts/backup_ovhdata_hot.sh is a one-time migration
   snapshot that skips Neo4j dumps and does not push R2 — extend or supersede it. Include
   `schema_baseline.sql` regeneration in every cycle (so the S3/FC drift class cannot recur) and
   an ops.audit_ledger chain-verify. Mechanism: a dedicated compose service (`backup`) on a cron
   loop — default choice; host cron only if the owner prefers. Check: restore drill on a scratch
   DB reproduces schema + data + a verifying ledger chain.
4. Closeout: docs/DEBT.md rows updated (population, evals, backups → resolved with dates); canon
   §6 round status updated INCLUDING resolving every `TODO(OQ-2)`/OQ-7/OQ-9 marker S1 left, per
   the signed rulings sheet (OQ-7 execution: move 00_analysis_graph.surql to `_stale/` or port
   per ruling); final coverage sweep against INVENTORY-2026-08-09.md — every row's segment work
   either done or explicitly re-registered in docs/DEBT.md with an owner-visible reason.

## Acceptance
Population: signed-schema rows flowing with clocks + custody + ledger entries. Evals: non-empty,
green, canary armed. Backups: restore drill passes. DEBT/canon reflect reality; inventory sweep
clean.

## Constraints
Standing constraints per PLAN master. Population BLOCKED until D-008 signed — do as much prep
(fixtures, harness, backup plumbing) as possible without guessing the schema. R2 credentials never
in command lines/transcripts. Backups are trash-only lifecycle (no permanent-delete automation).
