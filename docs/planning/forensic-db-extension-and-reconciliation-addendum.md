# Forensic-Evidence DB — Extension Audit & As-Built Reconciliation Addendum

> _Byline: Claude Code · Opus 4.8 · 2026-06-30_
> **Durable record** (intentionally in the repo, not session scratchpad) so it survives context loss.
> Pairs with the 91k-word architecture draft generated 2026-06-30 (currently in session scratchpad:
> `…/scratchpad/forensic-db-arch/FORENSIC_DB_ARCHITECTURE_DRAFT.md`; companions in `discovery/`, `sections/`, `review/`).
> **Owner intent:** hold individual fixes for the as-built DDL reconciliation pass and land them in ONE consolidated final report. This file records what must be fixed so nothing is lost in the meantime.

## A. PostgreSQL extension contract (source of truth = `docker/postgres/Dockerfile` + `sql/0001_init_extensions.sql`)

**Live & enabled** in the unified PG resource (`agno-postgres:18-duckdb`, base `pgduckdb/pgduckdb:18-v1.1.1`):
`pg_duckdb` (embedded DuckDB + R2/S3 httpfs; in `shared_preload_libraries`), `postgis`, `pgvector` (**legacy/migration-only** — vectors moved to Milvus, ADR-0027), `pg_stat_statements`, **`pgcrypto`** (crypto hashing — `digest()`/`hmac()` for SHA-256 custody), `pg_trgm`, **`fuzzystrmatch`** (soundex/levenshtein/metaphone → entity resolution), `citext`, `ltree`, `hstore`, `btree_gin`, **`btree_gist`** (powers bitemporal `EXCLUDE` no-overlap on `tstzrange`), `unaccent`. Native PG18 `uuidv7()`; core `tsvector` FTS. Core `postgres_fdw`/`file_fdw` ship but unused.

**BM25 — STAGED, NOT present.** `pg_textsearch` is **not baked** (Dockerfile: "no PGDG package; add vendor build step when retrieval quality demands BM25+RRF") and **not enabled** (`sql/0001`). ⚠️ `docs/planning/EXECUTION_PLAN.md:126` and `goals/agno-mvp-boot-ingest/plan.md:30` wrongly say it is "in the image" — **stale, fix to 'staged, not baked.'**

**BM25 location conflict to resolve:** ADR-0013/handoff (pg_textsearch in PG) vs **ADR-0027 + PROJECT_CANON** (Milvus hybrid dense+sparse/BM25). Recommended: **Milvus owns primary semantic/hybrid/BM25**; PG keeps `tsvector`+`pg_trgm` for cheap local lookups; `pg_textsearch` stays an optional staged PG-local fallback (don't bake preemptively).

**Stale / do NOT inherit:** Multicorn2 live-FDW hub (`neo4j_fdw`,`duckdb_fdw`) + a March `shared_preload_libraries='timescaledb,pg_search,pg_cron,…'` line — **dropped by ADR-0032**; `pgvectorscale` (superseded by Milvus); Apache AGE (Semantica backend option only, not deployed).

## B. As-built schema reality (active repo `sql/0001–0004`) — and the gap vs the paper design

The live schema is **small but deliberate**, and the paper draft (§03/§04) invented *parallel* structures instead of building on it. Reconciliation must MERGE into the as-built, not beside it.
- **Security boundary:** schemas `evidence` (agents read-only, connection-enforced) · `analysis` (writes only after recorded approval) · `public` (HITL audit + Agno-managed). The paper draft's `core/raw/extracted/geo/legal/…` top-level schemas must be re-homed under this boundary.
- **Tables:** `agent_run`,`approval_request` (LEGACY — superseded by native `agno_approvals`), `evidence.evidence_hash` (custody: `digest BYTEA`, `blob_key`, `meta`), `working.normalized_record` (bitemporal: `occurred_at` valid-time, `knowledge_time`, `disclosure_tier`), `transcript_insight`.
- **Custom types (`0004`):** enums `entity_type`,`temporal_class`,`event_type`,`mcl_factor (a–l)`,`source_system (postgres/neo4j/milvus/surrealdb)`,`match_method`; domains `confidence numeric(4,3)`,`canonical_id uuid`,`geo_point geography(Point,4326)`; composite `source_ref(system,native_id,locator)`. Reuse these — don't redefine.
- **🐞 As-built bug to fix in reconciliation:** `disclosure_tier` is defined **two incompatible ways** — `0003` text CHECK `('contemporaneous','hindsight','discovered')` vs `0004` ENUM `('public','restricted','sealed')`. Pick one meaning (the bitemporal one in 0003 is the substantive one; rename the 0004 enum, e.g. `sensitivity_tier`).

## C. Prior-iteration expansive schemas to extract (owner: "a lot of heavily iterated expansive schemas … within the code")

Index: `dev-resources/Archives/OTHER_RESOURCES_TO_SORT/Case/COMPLETE_SCHEMA_PARSER_INVENTORY.md` (Salem Forensic Trinity, compiled 2026-01-06). Canonical copies (many duplicates exist — dedupe):
- **Messaging forensic core (900+ lines):** `…/TheBigOne/TraceIQ/TraceIQ-fresh/00_Documentation/STACK_Deployment/n8n-local/supabase_production_schema.sql` — `messaging_documents/conversations/messages/attachments/behaviors`, ref `mcl_factors`, `behavior_categories` (18: gaslighting, blame_shifting, minimizing, love_bombing, stonewalling, parental_alienation, coercive_control, financial_abuse, substance_weaponization, reactive_abuse, darvo, character_assassination, isolation, hoovering, triangulation, parenting_time, gatekeeping, special_needs), court `messaging_evidence_items/factor_citations/timeline_events`.
- **Richest timeline (24 tables):** `…/Archives/Voice_Analysis/Context_Analysis_Suite/Chat_Parser_App/timeline_ingestion_schema.sql`.
- **TraceIQ:** `…/TheBigOne/TraceIQ/TraceIQ_Main/schema_complete.sql` (10) + `src/normalized_geo_schema_v5.sql` (8); Google-Timeline `timeline_events/waypoints/processing_metadata` (PostGIS).
- **Pattern persistence:** `…/dial-stack/server/database/migrations/create_pattern_persistence_tables.sql` (7).
- **MCP-tool-platform (drizzle ORM):** `…/The_Platform_Archive/TheBigOne_SAFE_COPY/mcp-tool-platform/drizzle/0000_*.sql`,`0001_*.sql` (+ `_project_dirs_loose/0003_*.sql`).
- **Alpha Agno iteration:** `…/Archives/Agno-MCP-Platform-alpha/sql/schema.sql`.
- **Ontology/models:** `salem_v3.py` (zep ontology), zep `src/db/models.py`, `…/mcp-servers/py-mcp-server/src/document_intelligence/models.py`, semantica `decision_models.py`.
- **Detection logic:** `detection_patterns.py` (320+ lines; 15+ regex patterns, child-name patterns, MCL scores) + Chunker `schemas/{facebook,snapchat,generic_html}.json`.

## D. Deferred corrections to apply during the reconciliation pass (consolidate in final report)
1. §04 extension list → full init set (add `fuzzystrmatch`,`citext`,`ltree`,`hstore`,`unaccent`,`btree_gist`).
2. §03 entity-resolution `id_xref` → `fuzzystrmatch`+`pg_trgm`+`citext`.
3. §08 temporal → `btree_gist` `EXCLUDE` on `tstzrange`.
4. §04/§05 → write the BM25 resolution (Milvus primary; pg_textsearch staged fallback).
5. §15/gap report → track the `pg_textsearch` doc inconsistency + BM25-location conflict + the `disclosure_tier` double-definition bug.
6. §09 custody → confirm `pgcrypto.digest(...,'sha256')`.
7. Re-home paper-design schemas under the `evidence`/`analysis`/`public` boundary; reuse `0004` custom types.
8. Fold in the prior-iteration tables/intents from §C (adopt/adapt, not reinvent).
9. **Acceptance step (verify-before-claiming):** diff the reconciled DDL against the LIVE `agno-postgres:18-duckdb`, Milvus, Neo4j before writing any migration.
