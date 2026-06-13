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
RUN apt-get update && apt-get install -y --no-install-recommends \
        postgresql-18-postgis-3 \
        postgresql-18-pgvector \
    && rm -rf /var/lib/apt/lists/*
USER postgres

# pg_stat_statements ships with core PG; it needs shared_preload_libraries.
# pg_duckdb already requires its own preload, so chain both.
CMD ["postgres", "-c", "shared_preload_libraries=pg_duckdb,pg_stat_statements"]
