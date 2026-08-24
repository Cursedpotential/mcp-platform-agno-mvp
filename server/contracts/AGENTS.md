# server/contracts/ — the import-light record contract

> Nested map. Parent: `../AGENTS.md`. Root: `../../AGENTS.md`.

## What's here

```
records.py    NormalizedRecord / RecordType / DisclosureTier
```

One shape every parser emits into (message / call / event / media) — storage,
analysis, and export never care which of the 20+ parsers produced a record.
Carries the bitemporal substrate: `occurred_at` (valid time) vs `knowledge_time`
(when the platform learned it) vs `disclosure_tier` (contemporaneous / hindsight /
discovered).

## The one hard rule: MUST stay dependency-free

`server/contracts/__init__.py` is deliberately empty of heavy imports (no
sqlalchemy / agno / duckdb) — **do not change that.** Why: the `docker/tools`
platform-tools facade is a dep-light container that mounts the whole `server/` tree
and imports every parser to build its registry; every parser imports
`server.contracts.records`. If this package's `__init__` ever pulls in a heavy
dependency, the facade FATAL-loops on startup — the exact failure mode ADR-0033
already paid a 2-day outage for once. Keep new code in `records.py` itself
free of heavy deps too; if you need something heavier, it belongs in
`server/core/` or `server/evidence/`, not here.

## Why it lives here, not `server/core/`

ADR-0035 (Option A, owner-confirmed): `server/core/__init__.py` eagerly imports
`server.core.session` (postgres/agno/duckdb), so `server/core/records.py` would have
run that whole chain on any import — including from the facade. `server/contracts/`
is a new, deliberately minimal package created to be facade-safe by construction.
`server/evidence/normalize.py` is a thin deprecated re-export shim pointing here —
don't add new code to it.

## Relevant ADR

- ADR-0035 — full rationale, the two candidate homes considered (`server/core/` vs
  here), and the as-built Outcome section. Read it before moving or extending this
  contract — don't restate the tradeoff here.

---

<!-- live-testing-policy:start -->
## Testing & Deployment Policy — LIVE ONLY, SPRINT MODE

> _Owner directive 2026-08-20 · recorded by Claude Code · Opus 5._
> _Supersedes any prior testing, staging, or change-approval guidance in this file._

- **Sprint mode is the default.** Bias to action. Ship the smallest working increment now,
  verify it live, keep moving. Do not stall on approval gates for routine work.
- **All testing is live testing.** Verify against the real deployed service, real data, real
  endpoints. A proxy signal is not verification.
- **No out-of-band testing.** No mocks, stubs, or synthetic fixtures standing in for a real
  dependency. A green unit test is not evidence the thing works.
- **No stubs. Write the whole function.** If it is a function, implement it fully. A stub is
  permitted ONLY when the real data or upstream service genuinely does not exist yet.
- **Any stub that must exist is marked LOUDLY and tracked.** Inline `# STUB:` / `// STUB:` at the
  site, plus an entry in `docs/URGENT-TODO.md`. A silent stub is a defect.
- **Ship and watch.** If it works, it stays up. If it breaks, fix it and put it back up.
  Breakage is the feedback loop, not a reason to stage.
- **On success, purge the test data.** Clear every row and artifact the live run created, then
  move on. Test data must never become canonical.
- **On failure, adjust in place and retry live.** Fix the real thing and run it again — never
  retreat to a mock, a staging copy, or a parallel instance to "prove" it.
- **No parallel stacks.** One live instance per service. No shadow deploys, no staging copies,
  no side-by-side `v2` beside `v1` — replace in place.
- **Fix forward.** Roll back only to restore service, never as a substitute for fixing the cause.
- **Mid-task feedback is QUEUED, not switched to.** If input arrives that is not about the task in
  flight, append it to `docs/URGENT-TODO.md` and keep going. Finish the current task; address the
  queued item at the point that work was already scheduled. Do not context-switch mid-task.

**Still stop and ask for:** destroying data, terminating/wiping a host, anything outward-facing
(publishing, sending, paying), and irreversible spend. Sprint mode removes ceremony, not judgment.
<!-- live-testing-policy:end -->
