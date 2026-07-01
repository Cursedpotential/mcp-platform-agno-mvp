# ADR-0032: Drop the PG Multicorn FDW federation hub; cross-source reach = pg_duckdb + native drivers
- Status: Accepted
- Date: 2026-06-26
- Supersedes: the "PG = live federation hub" stance introduced 2026-06-14 (Dockerfile `docker/postgres/Dockerfile`, commit `bb08045`)
- Related: ADR-0024 (SurrealDB = store/analysis layer), ADR-0013 (pg_duckdb custom image), ADR-0028/0029 (orchestration substrate)
- _Byline: Claude Code · Opus 4.8 · 2026-06-26_

## Context
The 2026-06-14 handoff made Postgres a **live federation hub**: a custom PG18 image
compiled Multicorn2 (Python FDW framework) plus `neo4j-fdw`, so PG could query
Neo4j / REST sources at runtime. That design rested on one assumption — **PG was the
analysis target**, so every source had to be queryable *inside* PG.

That assumption no longer holds. Per ADR-0024, **SurrealDB is the downstream
consolidation / analysis sink**: processed data flows **PG → Surreal**, and analysis
happens in Surreal. There is no in-PG cross-source analysis requirement, so the live
FDW hub solves a problem the platform no longer has. It also carried real cost:

- **Custom build glue** — clone + compile Multicorn2 against PG18 headers + pip
  `neo4j-fdw`. Brittle across base-image bumps. The Dockerfile itself flagged the
  layer as **"NOT build-verified."**
- **Slow at runtime** — Multicorn FDWs are Python, row-by-row, little predicate
  pushdown; querying Neo4j / REST through SQL is the slow path and doesn't parallelize.
- **Operational coupling** — a down source can break PG queries that touch it.
- Conflicts with the owner principle: *minimize custom code, default to off-the-shelf*.

## Decision
**Remove the Multicorn2 / `neo4j-fdw` build from the custom PG image.** PG remains the
processing/staging hub, but its reach into other systems comes from off-the-shelf
parts already in the stack — no custom compile:

| Need | Mechanism |
|------|-----------|
| Files / object store / relational | **pg_duckdb** (R2/S3, Parquet, CSV, JSON; `ATTACH` Postgres/SQLite) — already in the base image |
| Graph (Neo4j) | **Native Cypher driver** at the agent / orchestration tier (graph↔SQL via FDW is an impedance mismatch; `neo4j-fdw` is immature) |
| Vectors (Milvus) | **Milvus SDK** (vectors don't federate via SQL) |
| source → process → Surreal pipeline | **Orchestration substrate** (ADR-0028/0029), not query-time federation |

Core `postgres_fdw` / `file_fdw` ship with the base image and stay available
(`CREATE EXTENSION` only, no build) for a plain Postgres↔Postgres link if ever needed.

## Consequences
- `docker/postgres/Dockerfile`: Multicorn2 / `neo4j-fdw` build step removed; the
  staged protocol-FDW block (mongo_fdw / redis_fdw) goes with it.
- `sql/0001_init_extensions.sql`: the guarded `CREATE EXTENSION multicorn` removed.
- Custom PG image build gets simpler and faster, and loses an unverified compile step.
- "Live cross-source SQL JOIN in PG" is no longer a capability. If a concrete need for
  query-time JOINs across PG + a non-DuckDB-reachable source ever appears, revisit
  (pin a tagged Multicorn2 release and build-verify on the host) — but not speculatively.

## Alternatives considered
- **Keep Multicorn, fix only the docs** (Surreal mislabeled as an FDW source) — rejected:
  fixes wording but keeps a brittle, unverified, unused build layer.
- **Keep Multicorn for future-proofing** — rejected: speculative; YAGNI vs. the
  minimize-custom-code principle. Easy to re-add behind a tagged release if justified.
- **duckdb_fdw instead of pg_duckdb** — moot: pg_duckdb already embeds DuckDB.
