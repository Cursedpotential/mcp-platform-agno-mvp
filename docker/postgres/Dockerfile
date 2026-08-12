# =============================================================================
# Custom PostgreSQL 18 image — the extension contract (handoff §10.2, ADR-0013)
# Byline: Claude Code · Kimi K3 (drift-fix) · 2026-08-12 — ADR-0024 Surreal-sink
#         comment corrected (SurrealDB RETIRED, ADR-0043); Windmill citation noted dead.
# =============================================================================
# Base: official pg_duckdb image (PG18 + DuckDB engine embedded in Postgres —
# owner decision 2026-06-10, supersedes ADR-0003's no-DuckDB stance).
# pg_duckdb also gives Postgres native S3/R2 reads via DuckDB httpfs.
#
# Added on top: PostGIS (geospatial) + pgvector (embeddings) from PGDG.
#
# pg_textsearch (BM25): staged, NOT baked yet — no PGDG package; add the
# vendor build step here when retrieval quality demands BM25+RRF (§10.4).
#
# Volume note: same PG major (18) as the previous agnohq/pgvector:18 image,
# so the existing pgdata volume carries over; new extensions just become
# available. Init SQL only runs on EMPTY volumes — apply 0001/0002 manually
# (or compose down -v) when switching images on an existing volume.

FROM pgduckdb/pgduckdb:18-v1.1.1

USER root

# --- Geospatial + vector types (proven, baked) --------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-18-postgis-3 \
        postgresql-18-pgvector \
    && rm -rf /var/lib/apt/lists/*

# --- Cross-source reach: pg_duckdb, NOT a custom FDW hub (ADR-0032) ------------
# Earlier plan (handoff 2026-06-14): PG as a LIVE federation hub via Multicorn2
# FDW (compiled neo4j-fdw + REST wrappers). DROPPED 2026-06-26 — see ADR-0032.
#
# Why it's gone: that plan existed because PG was meant to be the analysis
# TARGET, so every source had to be queryable IN PG. ~~SurrealDB is now the
# downstream analysis sink (ADR-0024): processed data flows PG -> Surreal and
# analysis happens THERE.~~ Corrected 2026-08-12: SurrealDB is RETIRED
# (ADR-0043, owner ruling 2026-08-06), zero callers — there is NO downstream
# Surreal sink; PG itself is the operational + working store since the
# 2026-08-04 flatten (ADR-0043 decision 3). With no in-PG cross-source
# analysis requirement, the
# live FDW hub was custom build glue for a capability nothing calls — and it was
# never build-verified. Removing it deletes a brittle compile step (minimize
# custom code; default off-the-shelf).
#
# Cross-source reach is now off-the-shelf, no custom compile:
#   * files / object store / relational -> pg_duckdb (R2/S3, Parquet, CSV, JSON;
#     ATTACH Postgres/SQLite) — already embedded in the base image.
#   * graph (Neo4j)  -> native Cypher driver at the agent/orchestration tier
#     (graph <-> SQL through an FDW is an impedance mismatch).
#   * vectors (Weaviate) -> Weaviate SDK (vectors don't federate via SQL).
#     (Corrected 2026-08-12: was Milvus — superseded by ADR-0040; Milvus
#     data-vector app DOWN deliberately since 2026-08-10.)
#   * the source -> process pipeline -> orchestration substrate
#     (~~ADR-0028/0029~~ Corrected 2026-08-12: the Windmill lane is DEAD —
#     ADR-0029 supersedes ADR-0028), not query-time federation.
# core postgres_fdw + file_fdw still ship with the base image if a plain
# Postgres-to-Postgres link is ever needed (CREATE EXTENSION only, no build).

USER postgres

# pg_stat_statements ships with core PG; it needs shared_preload_libraries.
# pg_duckdb already requires its own preload, so chain both.
CMD ["postgres", "-c", "shared_preload_libraries=pg_duckdb,pg_stat_statements"]
