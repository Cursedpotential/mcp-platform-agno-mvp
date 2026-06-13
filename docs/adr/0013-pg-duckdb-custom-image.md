# ADR-0013: Adopt pg_duckdb in a custom PG18 image (supersedes ADR-0003's no-DuckDB stance)
- Status: Accepted
- Date: 2026-06-10

## Context
ADR-0003 locked "no DuckDB anywhere in the stack" for the MVP. On 2026-06-10 the owner
reversed this: DuckDB is wanted, and specifically **as the `pg_duckdb` extension inside
Postgres so the two engines communicate natively** (not a separate DuckDB service).

Verified the same day: pg_duckdb v1.1.x is production-ready, ships an official
**PG18** Docker image (`pgduckdb/pgduckdb:18-v1.1.1`), and PG18 is its default —
so the PG18 pin (ADR-0003, native `uuidv7()`) survives intact; no PG17 fallback needed.

## Decision
Build `docker/postgres/Dockerfile` on the `pgduckdb/pgduckdb:18` base and layer
PGDG packages on top: **PostGIS** and **pgvector**. Preload chain:
`shared_preload_libraries=pg_duckdb,pg_stat_statements`. `pg_textsearch` (BM25)
remains staged, added to the image when retrieval quality demands it (§10.4).

This one image now carries the whole extension contract: vector, postgis, pg_trgm,
pgcrypto, btree_gin/gist, unaccent, pg_duckdb, pg_stat_statements, uuidv7 (native).

## Consequences
- Postgres can run DuckDB-engine analytics over its own tables (`duckdb.force_execution`)
  and read **R2/S3 directly** via DuckDB httpfs — pairs with the R2 blob landing zone (ADR-0007).
- Same PG major (18): the existing pgdata volume carries over when the image switches;
  init SQL does not re-run on a non-empty volume — new `CREATE EXTENSION` statements
  are applied manually once (guarded DO blocks in 0001 keep stock-image boots safe).
- Heavier image and two preloaded libraries; acceptable on the 8 GB VPS.
- ADR-0003's datastore rationale otherwise stands (Postgres+pgvector primary; R2 blob zone).
