# Autonomous Resume Loop — Forensic-DB Reconciliation

> _Byline: Claude Code · Opus 4.8 · 2026-06-30 ~06:30 EDT_
> Self-executing loop the assistant runs while the owner is at work. Wakes ~every 20 min, waits for the session token-limit reset (8:00 a.m. America/New_York), then resumes and completes the reconciliation. Durable on purpose.

## Trigger / state
- **Blocker:** session token limit hit during the reconciliation run; resets **08:00 ET**.
- **Ready test (each wake):** `date '+%H:%M'` local (this box's local = EDT = America/New_York; the `TZ=America/New_York` db is flaky, so use plain local `date`). **Ready when local time ≥ 08:10 EDT.**
- **Run to resume:** `wf_edbd50a7-cb5` — script at
  `C:\Users\matts\.claude\projects\E--AI-Workspace-Projects-the-platform-workspace\b617be3e-47f0-4f54-a2b3-33d9ef0d27a0\workflows\scripts\forensic-db-asbuilt-reconciliation-wf_edbd50a7-cb5.js`
  Resume: `Workflow({ scriptPath: <above>, resumeFromRunId: "wf_edbd50a7-cb5" })` (Extract phase E1–E5 is cached/on-disk → only Reconcile→Review→Consolidate run live).

## Each-wake procedure
1. `date` → if **before 08:10 EDT**: emit ONE status line (`waited, T-minus N min`), reschedule ~20 min (1200s), do nothing else. Keep it cheap.
2. If **≥ 08:10 EDT** and reconciliation not yet complete: fire the resume Workflow. Then **stop polling** — workflow completion auto-notifies (do not wake to babysit it). If the resume itself errors with a limit message, reschedule ~20 min and retry.
3. On workflow-completion notification: run the **Definition of Done** checks below. If pass → finalize + STOP the loop. If a phase failed on the limit again → reschedule ~20 min and resume again.

## Guardrails (hard)
- **Reversible only.** All output stays under `docs/planning/forensic-db-reconciliation/`. **Never** edit the live `sql/0001–0004` init files, never run migrations, never deploy.
- **Live-DB introspection/diff: GO** (owner granted 2026-06-30). Access verified over Tailscale SSH to ovh3-data (100.119.96.29) — snapshots captured in `live-introspection/`. Read-only introspection only; **never execute migrations/DDL on the live DB** without a fresh explicit go-ahead.
- **Don't redo finished work** — extracts E1–E5 are done; always `resumeFromRunId`, never a fresh full run.
- **No git commits/pushes.** Files only.
- **Failure cap:** if **3 consecutive** resume attempts fail for a NON-limit reason (script/logic error), STOP, write `STATUS.md` describing the failure, and wait for the owner. Do not spin.
- **Cost awareness:** one resume run is ~0.4–0.8M subagent tokens; don't launch duplicate/overlapping runs. One in flight at a time.

## Definition of Done (deliverables)
1. `RECONCILED_SCHEMA.sql` exists, non-empty; contains `CREATE SCHEMA evidence/analysis`, reuses `0004` custom types, tables in dependency order; `disclosure_tier` conflict resolved.
2. `FINAL_RECONCILIATION_REPORT.md` exists, non-empty; has the table-by-table adopt/adapt matrix, applied-corrections checklist, per-store summary (Milvus/Neo4j/Surreal + BM25 verdict + Surreal defer), migration plan, and the live-verify acceptance checklist.
3. `review/integrity.md` and `review/court_safety.md` exist.
4. Tasks #2 and #3 marked completed.
5. A short `STATUS.md` recap written here + a recap surfaced to the owner.
6. **STOP** the loop (stop rescheduling).

## Out of scope until owner returns
- Live-DB reconciliation/diff and any deploy/migration execution.
- Promoting the scratchpad 91k-word architecture draft into the canonical docs tree.
