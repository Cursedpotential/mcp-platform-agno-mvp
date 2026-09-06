# Prompt: present the remaining identifier rulings to the owner (R-1..R-18)

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Agent-ready prompt file. Read `README.md` in this folder for the standing rules._

## Goal
`docs/registers/RENAME-BLAST-RADIUS-2026-09-05.md` lists 18 identifiers the product rename did NOT settle. Present them to the owner one screen at a time with the recommendation and the live risk, record each ruling as a D-entry in `docs/DECISION_LOG.md`, and execute only what is ruled.

## The list (recommendation in parentheses)
- R-1 docker network `agno` (keep; highest blast radius of any single rename)
- R-2 `/data/agno/` host root (keep; plumbing, not a product name)
- R-3 `agentos-db` / `agentos-api` (→ `probata-db` / `probata-api`; `DB_ID` is a live registry key, one deliberate step with a smoke test)
- R-4 `agentos.mitechconsult.com` DNS, live and returning 503 (retire, do not rename)
- R-5 `AGENTOS_*` env names (→ `PROBATA_*`; Coolify renders env literals at deploy, so reader, writer, and Coolify var change together)
- R-6 `OS_SECURITY_KEY` (retire the name; no code reads it)
- R-7 PG database name (none needed; it is `platform`)
- R-8 role `agno_app` (→ `probata_app`; rename invalidates the password, maintenance window; see 04)
- R-9 `SURREALDB_NS=agno` (decide `probata` vs `indagatio` BEFORE the analysis engine splits, or it migrates twice)
- R-10 `svc:workbench`, `svc:tool-gateway` (keep; component names)
- R-11 `knowledge-workbench` image / npm name / API title (→ `workbench`; the Coolify app is already renamed)
- R-12 `platform-api` (keep; component name)
- R-13 `unified-operator-surface` (retire; a design mockup)
- R-14 `graphiti*`, `phase1-surreal*` apps (retire; three are still running on ovh-files)
- R-15 task queue (DONE 2026-09-06)
- R-16 checkout directory (see 01)
- R-17 `ghcr.io/cursedpotential/agno-postgres` (publish as `probata-postgres`, repoint, then deprecate; two live databases pull it, one by digest)
- R-18 archived transcript filename under `knowledge/` (rename the file only, never the contents)
