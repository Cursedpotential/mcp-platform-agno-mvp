# Release Custody — Platform Runtime + Matter MVP

> _Byline: Codex · GPT-5 · 2026-08-15_

STATUS: **PARTIAL — partitioned commits pushed to `main`; nothing applied or deliberately deployed**

## Non-negotiable release holds

- `sql/0030_matter_case_foundation.sql` may be committed while marked HELD, but
  it must not be applied until held migrations `0026`–`0029` complete their own
  review and promotion path in numerical order.
- `WORKBENCH_API_KEY` must be provisioned before deployment. With no key, every
  Workbench path except exact `/health` intentionally returns `503`.
- Full-baseline proof still requires the canonical custom PostgreSQL 18 image
  with pg_duckdb, PostGIS, pgvector, and pgcrypto. The local stock PostgreSQL
  proof is a rollback-only reduced-schema proof, not a production substitute.
- No Horizon execution may be exposed until the R0/R2 replay and contamination
  defects are resolved.

## Recommended commit sequence

1. `docs(adr): accept Matter and CourtCase identity boundary`
   - ADR-0055, D-060 and only their focused canon/ADR-index hunks.
2. `feat(db): add held Matter and CourtCase foundation`
   - `sql/0030_matter_case_foundation.sql`, its fixture, validators, migration
     tests, SQL index hunk, and Matter foundation pre-mortem.
3. `feat(case): add neutral case-management spine`
   - case contracts/repository/service/routes, route registration hunk, and
     focused spine tests.
4. `feat(workbench-api): enforce authenticated case-scoped access`
   - mandatory inbound auth, bounded Knowledge retrieval, Matter proxy,
     resolution/promotion/review/history, deployment env wiring, and tests.
5. `feat(workbench-web): add Matter-bound Knowledge review flow`
   - Matter/Knowledge pages and components, typed client contracts, Matter-only
     navigation hunks, and operator safety states.
6. `test(workbench-web): add Matter journey smoke`
   - `workbench/web/smoke/matter-flow.smoke.test.mjs` and package-script hunk.
7. `docs(matter): record verified local state and remaining release gates`
   - R9, Matter Workbench pre-mortem, focused README/status/index hunks.

## Shared-file custody warnings

Do not whole-stage these files without reviewing individual hunks:

- `workbench/api/main.py` — Matter/auth and Classification lanes coexist.
- `workbench/web/src/components/layout/app-sidebar.tsx` — Matter and
  Classification navigation coexist.
- `workbench/api/app/runtime/knowledge.py` and
  `workbench/web/src/lib/api-client.ts` — canonical Knowledge and Graphiti
  namespace-safety changes coexist.
- `README.md`, `AGENTS.md`, `docs/PROJECT_CANON.md`,
  `docs/DECISION_LOG.md`, `docs/CHANGE-ORDER.md`, `docs/DEBT.md` — broad runtime,
  Wave-1, provider, and Matter changes coexist.

Keep Wave-1 (`0026`–`0029`), provider/OpenCode, Classification, design mockups,
and broad architecture documentation as separate review lanes. Never use a
whole-tree commit merely to obtain a clean status.

## Per-commit gate

Before every commit:

1. Inspect `git diff --cached --name-only` against that commit's explicit
   allowlist.
2. Inspect the complete staged diff and run `git diff --cached --check`.
3. Run the focused tests for the staged lane.
4. Confirm HELD/UNAPPLIED/UNDEPLOYED wording remains truthful.
5. Do not push until the owner has reviewed the partition and resulting commit
   hashes.

## Documentation custody after commits

After a local commit exists, replace only stale `uncommitted/dirty-tree`
wording in R9, `docs/BUILD_PLAN.md`, `docs/COORDINATION.md`, `docs/HANDOFFS.md`,
and the Workbench READMEs. Retain `0030 unapplied`, `undeployed`, and
`live proof unknown` until those facts actually change. Preserve D-041 as
historical provenance but mark its identity consequence superseded in part by
D-060. Historical SurrealDB/LiteLLM handoff text needs a visible superseded
annotation, not deletion.
