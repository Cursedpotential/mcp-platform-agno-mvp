# PostgreSQL Extension Audit — the unified PG resource

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> Source of truth: `Agno-MCP-Platform/docker/postgres/Dockerfile` + `Agno-MCP-Platform/sql/0001_init_extensions.sql` (authoritative over planning docs). Companion to `FORENSIC_DB_ARCHITECTURE_DRAFT.md` §04. Requested follow-up: "other extensions for full search, crypto hashing, BM25 … supposed to or possibly embedded into PG."

## 1. What is ACTUALLY in the live PG resource (`agno-postgres:18-duckdb`)

| Extension | How present | Purpose | In draft §04? |
|---|---|---|---|
| **pg_duckdb** | baked (base `pgduckdb/pgduckdb:18-v1.1.1`) + `CREATE EXTENSION`; in `shared_preload_libraries` | embedded DuckDB analytical engine + native R2/S3/Parquet/CSV/JSON reads (httpfs) | ✅ |
| **PostGIS** (`postgresql-18-postgis-3`) | baked + `CREATE EXTENSION` | geometry/geography, spatial indexes | ✅ |
| **pgvector** (`vector`) | baked + enabled at init | embeddings — **legacy/migration-resident only**; vectors moved to Milvus (ADR-0027) | ✅ (as legacy) |
| **pg_stat_statements** | core, preloaded | query stats | ✅ |
| **pgcrypto** | enabled at init | **CRYPTO HASHING** — `digest()`/`hmac()` for the SHA-256 chain-of-custody (explicitly "HASHING only, not UUIDs") | ✅ (custody) |
| **pg_trgm** | enabled at init | fuzzy/trigram match; feeds dedup + entity resolution | ✅ |
| **fuzzystrmatch** | enabled at init | **soundex / levenshtein / metaphone → entity resolution** (`id_xref`) | ❌ **missing** |
| **citext** | enabled at init | case-insensitive text: names, emails, handles | ❌ **missing** |
| **ltree** | enabled at init | hierarchical labels: MCL-factor trees, evidence taxonomies | ❌ **missing** |
| **hstore** | enabled at init | key-value tag bags | ❌ **missing** |
| **btree_gin** | enabled at init | mixed scalar+text composite indexes | ⚠️ partial |
| **btree_gist** | enabled at init | **powers `EXCLUDE` no-overlap constraints on `tstzrange` → bitemporal integrity** | ❌ **missing (notable for §08 temporal)** |
| **unaccent** | enabled at init | accent-insensitive FTS over messy logs | ❌ **missing** |
| core `postgres_fdw`, `file_fdw` | ship with base, NOT enabled | plain PG↔PG link if ever needed (CREATE EXTENSION only) | n/a |
| native **`uuidv7()`** | PG18 built-in (no extension) | time-ordered PKs | ✅ |
| native **FTS** (`tsvector`/`tsquery` + GIN) | core | keyword/full-text search inside PG | ✅ |

## 2. The BM25 question — `pg_textsearch` is STAGED, not present

- **`pg_textsearch` (BM25) is NOT baked and NOT enabled.** Dockerfile §10: *"staged, NOT baked yet — no PGDG package; add the vendor build step when retrieval quality demands BM25+RRF."* `sql/0001` confirms: *"pg_textsearch is not enabled here; add when Agno hybrid search proves insufficient."*
- The intended upgrade path: enable `pg_textsearch` → build a BM25 index → fuse with vector ranks via **Reciprocal Rank Fusion (RRF)**. Staged for when keyword retrieval over long/repetitive chat-log corpora becomes the bottleneck.
- **⚠️ Doc inconsistency (staleness):** `docs/planning/EXECUTION_PLAN.md:126` and `goals/agno-mvp-boot-ingest/plan.md:30` claim *"pg_textsearch is in the image but NOT enabled."* The **Dockerfile (authoritative) says it is NOT in the image at all.** → those two planning docs are stale; fix to "staged, not baked."

## 3. The real conflict to resolve — WHERE does BM25 live?

Two live decisions point different directions:
- **In PG:** ADR-0013 + handoff §10.4 + init SQL → BM25 via `pg_textsearch` (staged).
- **In Milvus:** **ADR-0027** (Milvus = platform-wide vector substrate) + `PROJECT_CANON.md:224` → "hybrid **dense+sparse / BM25**" retrieval is a Milvus capability.

**Recommended resolution** (consistent with the 4-resource topology + ADR-0027 being the newer platform-wide decision):
- **Milvus owns primary semantic + hybrid (dense+sparse/BM25) retrieval** across the evidence/chat corpus.
- **PG keeps core `tsvector` FTS + `pg_trgm`** for cheap exact/keyword/fuzzy lookups *within* the relational resource (no cross-resource hop).
- **`pg_textsearch` BM25 stays a staged PG-local fallback** — only worth baking if you need court-grade keyword ranking co-located with the canonical rows (e.g., to avoid round-tripping to Milvus for an exhibit search). Don't bake it preemptively.

## 4. Stale / dropped extension ideas — do NOT inherit

| Idea | Where it appears | Status |
|---|---|---|
| Live FDW federation hub: **`neo4j_fdw`, `duckdb_fdw`, Multicorn2** | handoff 2026-06-14; `shared_preload_libraries='timescaledb,pg_search,pg_cron,pg_stat_statements,pg_duckdb,duckdb_fdw,neo4j_fdw'` (plannotator draft 2026-03-07) | **DROPPED — ADR-0032.** PG is no longer the federation target; cross-source reach = pg_duckdb + native drivers + PG→Surreal pipeline. |
| **`pg_search` (ParadeDB), `timescaledb`, `pg_cron`** | that same March preload line | **Abandoned** with the FDW hub. Not in any current image/init. |
| **`pgvectorscale` (DiskANN)** | handoff (in-PG vector scale path) | **Superseded by Milvus (ADR-0027).** pgvector itself is now legacy/migration-only. |
| **Apache AGE** (`CREATE EXTENSION age`) | Semantica `graph_store` backend option/tests | **Not deployed** — platform graph is Neo4j; AGE is a Semantica-supported alternative only. |

## 5. Corrections to fold into the architecture draft

1. **§04 extension contract** — replace the partial list with the full init set above; add `fuzzystrmatch`, `citext`, `ltree`, `hstore`, `unaccent`, `btree_gist`.
2. **§03 / entity resolution** — `id_xref` should explicitly use `fuzzystrmatch` (soundex/levenshtein/metaphone) + `pg_trgm` + `citext`.
3. **§08 temporal** — bitemporal no-overlap integrity should use `btree_gist`-backed `EXCLUDE` constraints on `tstzrange` (already enabled).
4. **§05 Milvus / §04** — state the BM25 resolution from §3 above so the two ADRs stop pointing different ways.
5. **§15 risks / gap report** — add the `pg_textsearch` doc-vs-Dockerfile inconsistency and the BM25-location conflict as tracked items.
6. **§09 custody** — confirm hashing uses `pgcrypto.digest(... ,'sha256')` (extension present); SHA-256 chain is supported in-DB.
