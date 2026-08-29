# server/contracts/ — the import-light record contract

> _Byline: Claude Code · 2026-07-27; verification refresh by Codex · GPT-5.6-Sol · 2026-08-29._

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

> _Sprint-mode policy REMOVED 2026-08-25 on owner order ("you're grounded — remove it entirely"). Confirm-and-discuss-before-changing is back in force._
