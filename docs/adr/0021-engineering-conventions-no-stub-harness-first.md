# ADR-0021: Engineering conventions — no-stub discipline, harness-first tests, embedder/secret fixes
- Status: Accepted
- Date: 2026-06-11

## Context
An honest audit found the platform looked more finished than it was: silent incomplete connective
tissue (HITL unwired), `NotImplementedError` stubs, empty evals, a query/passage embedding bug, and
an ephemeral pg_duckdb S3 secret. The owner mandated: **no stubs unless truly unavoidable (and then
loud and obvious), and tests must work.**

## Decision
Adopt as standing conventions:
- **No-stub rule.** Any unavoidable stub gets a grep-able `# STUB: <tag>` marker AND a row in
  `docs/DEBT.md`; `grep -rn "# STUB:"` must match the register exactly. Nothing else ships
  incomplete-and-silent. `trash_cloud_file` was *removed* from the active toolset rather than shipped
  as a `NotImplementedError`.
- **Harness-first testing.** `pytest` + the agno-eval harness must run green with a starter set per
  layer (custody, registry, normalize, workflow, HITL; routing/governance evals), then expand.
- **Embedder query/passage correctness** (`db/embedder.py` `NimEmbedder`): documents embed as
  `passage`, search queries as `query` (NIM asymmetric). Fixes silent retrieval degradation.
- **Persistent pg_duckdb R2 secret** (`ensure_duckdb_r2_secret()` at API startup): survives DB
  recreate; init-SQL can't (no env substitution, runs only on empty data dir).

## Consequences
- `docs/DEBT.md` is the live register, updated as part of every change.
- CI/local both run `pytest` + `python -m evals`; write paths aren't trusted until governance/boundary
  evals pass.
- These conventions gate the Part 1 round (`plans/logical-herding-forest.md`).

## Alternatives considered
- Ship stubs to move fast — rejected by owner directive; silent stubs are how a platform looks done
  but isn't.
- Defer tests — rejected: the evidence/HITL paths must be trustworthy.
