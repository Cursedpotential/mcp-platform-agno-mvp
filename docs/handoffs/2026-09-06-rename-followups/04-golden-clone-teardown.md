# Prompt: golden template database + teardown (D-142 §3), for the ingest session

> _Byline: Claude Code · Fable 5.1 · 2026-09-06. Agent-ready prompt file. Read `README.md` in this folder for the standing rules._

## Goal
Replace row purges with teardown + re-clone. A golden template holds schema + `reference.*` + `analysis.human_label*` + the Case Bible catalog; the working database is re-created FROM it.

## Facts you must not rediscover
- Zero committed live evidence exists (D-142). `working.*`, `evidence.*`, `context.*`, retained originals, Temporal history, and vector collections are fixtures.
- PG is at `100.91.190.107` (ovh-files); live DB `platform`; roles `platform_*` and legacy `agno_app`. `agno_app` was created live with NO migration file (`sql/0046` is missing). A golden template rebuilt from `sql/` will not have it unless you add the migration first.
- `sql/` is applied history: never edit an applied migration; add new ones.
- PG tables `uiw_preview_*` and `uiw_source_context_revision` keep their names until a migration renames them to `proffer_*`. Do that in this lane.

## Do
1. Write the template build as a script under `scripts/` that creates `probata_golden` from the `sql/` migrations plus a `reference.*`/labels/catalog restore. Prove `CREATE DATABASE platform_scratch TEMPLATE probata_golden` works (the template must have zero connections).
2. Write the teardown as: drop working DB → re-create from template → run the smoke suite. Keep it feature-flagged (D-127) and confirm with the owner before touching `platform`.
3. Record decisions in `docs/DECISION_LOG.md` (append) and the plan under `docs/planning/`.
