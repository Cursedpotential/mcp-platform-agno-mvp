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

### LANE C — "Infra/gateway" (Coolify + ContextForge + Portkey chat)
**Scope:** VPS/Coolify ops, ContextForge, Portkey/LiteLLM, MCP wiring, tailnet. Does NOT
touch repo structure, schema design, or ingestion logic. Repo footprint is minimal and
listed here so Lane A can carry it through the repack:
- **exec-tier Coolify app now deploys from `main`** (was `hotfix/agent-ui-lockfile`,
  repointed 2026-07-08 per owner). ⚠️ Any merge to main auto-redeploys the exec tier on
  ovh-app (gateway/CF/agentos/sandbox/desktop/agent-ui). When the Lane-A repack merges,
  expect that redeploy — and note `docker/` Dockerfiles COPY configs at build time
  (gateway bakes `docker/gateway/litellm-config.yaml`), so keep `docker/` paths stable or
  flag here.
- Lane C commits on main: `6ad0c25` (agent-ui Dockerfile pnpm9/OOM fix ported from the
  hotfix branch — main was unbuildable without it). On `hotfix/agent-ui-lockfile`:
  `740675b` (embed-text → nv-embed-v1). **Stray commit `6bcfddc` on
  `claude/ingestion-offline-work-hu8eud`** (Lane B's branch?) — same embed fix, landed
  there by accident mid-rebase; content harmless (touches only
  `docker/gateway/litellm-config.yaml`); drop or keep at Lane B's discretion.
- embed-text MUST stay `nvidia/nv-embed-v1` (4096-d): the graphiti Neo4j graph is
  embedded at 4096-d; any dim change breaks vector search (bit us twice).
- In flight: exec-tier redeploy-from-main verification (background watcher);
  Portkey routing configs pending an owner planning session.

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
- **2026-07-08 (A):** SEED RECONCILIATION RESOLVED — no action needed: live (164/527) ==
  exact `0007` prefix of Lane B's committed migration chain (0006+0007+0008);
  `evidence/patterns.py` chain validator OK; corpus fully homed (0 missing); only the 4
  contradiction rules remain unhomed (pending owner table decision). My earlier "drift"
  read compared live against 0006 alone — wrong baseline, withdrawn. Full gates green
  (186 tests) + live smoke ALL-PASS (PG ontology/source/detection-dry-run, Milvus,
  wiring). Added `scripts/dump_live_ontology.py` (read-only → gitignored `live-dumps/`).
  NEXT: Tier 3 Option A repack — built and gated ON BRANCH `restructure/option-a`,
  **NOT merged** (Lane C: main auto-deploys the exec tier; merge needs owner + Lane C go,
  Docker paths move in lockstep in the same commit).
- **2026-07-08 (C):** CF v1.0.4 live + federation verified (41 tools / 4 gateways); graphiti
  hostfix sidecar (`0f2cd16`); graphiti CF virtual server + Claude Code rewire (restart
  pending); Portkey 1.15.2 live on ovh-app:8787; exec-tier repointed hotfix→main + agent-ui
  Dockerfile fix ported (`6ad0c25`); redeploy-from-main verification in flight.
- **2026-07-08 ~AM (A):** Tier 0/1 done on `restructure/option-a` (dead venvs deleted,
  recall fragments → `../_stale/repo-recall-fragments-2026-07-08/`, goals/.planning/plans
  consolidated into `docs/planning/`). Next: seed reconciliation (read-only vs live), then
  Tier 3 repack. Final deliverable: illustrated HTML report in `docs/planning/`.
