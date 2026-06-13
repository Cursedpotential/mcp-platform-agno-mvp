-- 0001_init_extensions.sql — extensions first, then schema (handoff §8.1)
-- Runs once at first boot via /docker-entrypoint-initdb.d.
-- uuidv7() is NATIVE on PG18 — no extension needed.
-- pg_textsearch is not enabled here; add when Agno hybrid search proves insufficient.

CREATE EXTENSION IF NOT EXISTS vector;       -- embeddings (required)
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- fuzzy/trigram match; feeds dedup later
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- HASHING only (digest/hmac for custody), not UUIDs on PG18
CREATE EXTENSION IF NOT EXISTS btree_gin;    -- mixed scalar+text composite indexes
CREATE EXTENSION IF NOT EXISTS btree_gist;
CREATE EXTENSION IF NOT EXISTS unaccent;     -- accent-insensitive FTS for messy logs

-- postgis + pg_duckdb + pg_stat_statements live in the custom PG image
-- (docker/postgres/Dockerfile). Guarded so boot never fails on a stock image.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS postgis;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'postgis not available in this image — skipped (custom PG image provides it)';
END $$;

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_duckdb;   -- DuckDB engine in PG (owner decision 2026-06-10)
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pg_duckdb not available in this image — skipped (custom PG image provides it)';
END $$;

DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS pg_stat_statements;  -- needs preload (custom image CMD)
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'pg_stat_statements preload missing — skipped (custom PG image provides it)';
END $$;
