# COORDINATION — multi-chat war room for Agno-MCP-Platform

> _Byline: Claude Code · Fable 5 · 2026-07-08_
> **Purpose:** two (or more) Claude chats work this repo concurrently. This file is the
> shared ledger: who owns what, what's in flight, what's frozen, and handoffs. **Append,
> don't rewrite history** — add timestamped entries under your lane; strike (~~…~~) items
> you complete. Commit this file with your changes so the other lane sees it on pull.

## Lanes & ownership (as of 2026-07-08)

### LANE A — "Restructure" (this file created by Lane A)
**Scope:** repo structure + seed reconciliation. Branch: `restructure/option-a`.
- Tier 0/1 hygiene + planning consolidation (in flight)
- Seed reconciliation: read-only dump of live ontology → committed seed catches up
  (live drifted: behavior_category 153→164, detection_pattern 512→527); promote applied
  0005/0006 into `sql/`; retire the parallel P2.1 tables (`analysis_module`,
  `pattern_phrase`, `mcl_factor_ref`, `contradiction_rule` — never applied live)
- Tier 3 Option A code repack: `server/{api,core,agents,evidence,analysis,vendored}` —
  **moves every Python package; imports rewritten** (~200 sites)
- Contract rewrite (`docs/REPO_STRUCTURE.md`) + final HTML report with diagrams
- **Lane A does NOT touch:** ingestion/detection LOGIC, table schema design, live DB
  writes (read-only dumps only), `analytics/` (untracked, not Lane A's)

### LANE B — "Ingestion/table redesign" (the other chat)
**Scope (per owner):** table structure + question/ingestion workflow redesign — the
"solid brainstorm". Data in live PG stays frozen meanwhile.
- Owns: future schema of `analysis.*` ontology/finding tables, ingestion flow redesign,
  detection/analysis rework
- Untracked `analytics/visit-locations/` presumed Lane B / owner-local — Lane A won't touch
- **Requested of Lane B:** log your in-flight items below; avoid committing to `main`
  while Lane A's repack PR is open (or coordinate here first); after the repack merges,
  note that **import paths change** (`evidence.*` → `server.evidence.*` etc.)

## FROZEN (owner mandate, 2026-07-08)
- Live PG data: unchanged until the Lane-B brainstorm lands
- Ingestion + detection logic: as-is (structure moves it; behavior identical)

## Hazards / heads-up board
- **2026-07-08 (A):** repack will move every top-level Python package under `server/`.
  If Lane B edits `.py` files on main between now and the repack merge, say so HERE —
  Lane A will rebase and carry the edits through the move.
- **2026-07-08 (A):** live ontology drift (+11 categories, +15 patterns beyond committed
  0006) — being captured into the committed seed by Lane A, **content-faithful, no
  redesign** (redesign is Lane B's).
- **2026-07-08 (A):** sealed-lexicon rows: committed seeds keep `[REDACTED:]` placeholders
  ONLY; real values never enter git (0006 court-safety rule).

## Ledger (append below; newest on top)
- **2026-07-08 ~AM (A):** Tier 0/1 done on `restructure/option-a` (dead venvs deleted,
  recall fragments → `../_stale/repo-recall-fragments-2026-07-08/`, goals/.planning/plans
  consolidated into `docs/planning/`). Next: seed reconciliation (read-only vs live), then
  Tier 3 repack. Final deliverable: illustrated HTML report in `docs/planning/`.
