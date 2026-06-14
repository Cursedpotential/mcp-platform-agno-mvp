-- 0001_init_extensions.sql — extensions first, then schema (handoff §8.1)
-- Runs once at first boot via /docker-entrypoint-initdb.d.
-- uuidv7() is NATIVE on PG18 — no extension needed.
-- pg_textsearch is not enabled here; add when Agno hybrid search proves insufficient.

CREATE EXTENSION IF NOT EXISTS vector;       -- embeddings (required)
CREATE EXTENSION IF NOT EXISTS pg_trgm;      -- fuzzy/trigram match; feeds dedup later
CREATE EXTENSION IF NOT EXISTS pgcrypto;     -- HASHING only (digest/hmac for custody), not UUIDs on PG18
CREATE EXTENSION IF NOT EXISTS btree_gin;    -- mixed scalar+text composite indexes
CREATE EXTENSION IF NOT EXISTS btree_gist;   -- powers EXCLUDE constraints on tstzrange (bitemporal no-overlap)
CREATE EXTENSION IF NOT EXISTS unaccent;     -- accent-insensitive FTS for messy logs

-- Rich/domain field types (all contrib — ship with the base image, no apt).
-- Replace generic text columns with these so data is self-describing/queryable.
CREATE EXTENSION IF NOT EXISTS citext;        -- case-insensitive text: names, emails, handles
CREATE EXTENSION IF NOT EXISTS ltree;         -- hierarchical labels: MCL factor trees, evidence taxonomies
CREATE EXTENSION IF NOT EXISTS hstore;        -- key-value attr bags (jsonb usually preferred; here for tags)
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch; -- soundex/levenshtein/metaphone -> entity resolution (id_xref)

-- Multicorn2 (Python FDW framework) — PG = live federation hub. Provided by the
-- custom image (docker/postgres/Dockerfile); guarded so boot never fails on stock.
DO $$
BEGIN
    CREATE EXTENSION IF NOT EXISTS multicorn;
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'multicorn not available in this image — skipped (FDW federation layer; custom PG image provides it)';
END $$;

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
