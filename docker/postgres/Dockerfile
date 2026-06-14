# =============================================================================
# Custom PostgreSQL 18 image — the extension contract (handoff §10.2, ADR-0013)
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

# --- FDW / federation layer (handoff 2026-06-14) ------------------------------
# PG is the LIVE federation hub (data stays in source systems, PG queries across
# them at runtime) — the complement to SurrealDB's CONSOLIDATION (copy-in) role.
# Multicorn2 is the catch-all Python FDW framework: one toolchain powers
# neo4j-fdw and any REST/SurrealDB wrapper, so sources without a native C FDW
# are still reachable. (multicorn2 fork: pgsql-io/multicorn2.)
#
# BUILD NOTE: this layer compiles against PG18 on the Docker host (Coolify on
# OVH-3). It is NOT build-verified in-repo (no docker build in the authoring
# session). If a step fails on the host, pin multicorn2 to a tagged release and
# confirm postgresql-server-dev-18 headers match the pgduckdb base PG build.
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential postgresql-server-dev-18 \
        python3 python3-dev python3-pip git \
    && git clone --depth 1 https://github.com/pgsql-io/multicorn2.git /tmp/multicorn2 \
    && make -C /tmp/multicorn2 \
    && make -C /tmp/multicorn2 install \
    && pip3 install --no-cache-dir --break-system-packages /tmp/multicorn2 \
    && pip3 install --no-cache-dir --break-system-packages neo4j-fdw \
    && rm -rf /tmp/multicorn2 /var/lib/apt/lists/*

# --- Protocol FDWs (STAGED — uncomment when the FDW set is locked) -------------
# FerretDB (Mongo wire) and Dragonfly (Redis wire) have native C FDWs that build
# against vendor drivers. Enable per selection:
#   * Mongo/FerretDB -> EnterpriseDB/mongo_fdw  (needs mongo-c-driver)
#   * Redis/Dragonfly -> pg-redis-fdw/redis_fdw (needs hiredis)
# OMITTED on purpose: mysql_fdw (no MySQL in stack); duckdb_fdw (pg_duckdb already
# embeds DuckDB); Milvus (vectors don't federate via SQL — use the Milvus SDK).
# core postgres_fdw + file_fdw ship with the base image (CREATE EXTENSION only).

USER postgres

# pg_stat_statements ships with core PG; it needs shared_preload_libraries.
# pg_duckdb already requires its own preload, so chain both.
CMD ["postgres", "-c", "shared_preload_libraries=pg_duckdb,pg_stat_statements"]
