# Live-DB Introspection Summary (ground truth)

> _Byline: Claude Code · Opus 4.8 · 2026-06-30 ~09:10 EDT_
> Captured over Tailscale SSH from the deployed stack on **ovh3-data (100.119.96.29)** (app tier on ovh1 100.72.169.40). Raw artifacts alongside: `PG_live_schema.sql`, `PG_live_summary.txt`, `PG_live_types.txt`, `NEO4J_live.txt`, `SURREAL_live.txt`, `MILVUS_live.txt`. This is the diff baseline for `../RECONCILED_SCHEMA.sql`.

## Containers (all reachable)
`agentos-db` = `agno-postgres:18-duckdb` · `neo4j:5-community` · `milvus v3.0-beta` (+`attu`) · `surrealdb v3.1.4`, all on ovh3-data. App tier (gateway, platform-tools) on ovh1.

## PostgreSQL (db `ai`, user `ai`)
- **Schemas:** `evidence`, `analysis`, `public`, `ai` (Agno-owned), `duckdb` (pg_duckdb internal). ✅ the design's `evidence`/`analysis`/`public` boundary EXISTS.
- **Extensions LIVE:** `btree_gin 1.3`, `btree_gist 1.8`, `pg_duckdb 1.1.0`, `pg_stat_statements 1.12`, `pg_trgm 1.6`, `pgcrypto 1.4`, `postgis 3.6.4`, `unaccent 1.1`, `vector 0.8.2`, `plpgsql`.
- **🔴 DRIFT — extensions in `sql/0001` but NOT installed live:** `citext`, `ltree`, `hstore`, `fuzzystrmatch`. (Entity-resolution design leans on `fuzzystrmatch`+`citext` — migration must `CREATE EXTENSION` these. `pg_textsearch`/BM25 absent as expected = staged.)
- **🔴 DRIFT — `sql/0004` custom types NOT applied:** no `entity_type`/`event_type`/`temporal_class`/`mcl_factor`/`source_system`/`match_method` enums, no `confidence`/`geo_point`/`canonical_id` domains, no `source_ref` composite present. Live has only `0001`+`0002`+`0003`. (Matches Dockerfile note: 0004 must be applied by hand on existing volumes.) → migration applies 0004 FIRST (with the `disclosure_tier` fix).
- **Tables live (forensic-relevant):** `evidence.evidence_hash` (custody), `analysis.normalized_record` (bitemporal spine), `public.{agent_run, approval_request, transcript_insight}`. Everything else is Agno-managed (`ai.agno_*`, `ai.*_contents` knowledge vectors) or PostGIS (`public.spatial_ref_sys`).
- **🟢 Implication:** the entire rich domain model (messages, events, entities, geo, behavioral findings, legal, work-product ledger) is **greenfield** — migration is **additive/low-risk**, not a destructive alter.

## Neo4j (Graphiti)
- Labels: `Saga`, `Episodic`, `Entity`, `Community`. Rels: `MENTIONS`, `NEXT_EPISODE`, `HAS_EPISODE`, `HAS_MEMBER`, `RELATES_TO`. Graphiti property keys (`uuid`, `group_id`, `valid_at`, `expired_at`, `fact`, …).
- **Node count: 0** — bare Graphiti schema, no data, **no Semantica labels** yet. Design's Semantica entity layer is not deployed.

## SurrealDB (v3.1.4)
- Namespaces: `agno`, `main`. DB `main:main` → **zero tables/functions/analyzers** (completely empty). Confirms design status "ratified (ADR-0024) but not yet used." Root user only.

## Milvus (v3.0-beta)
- **Live collections (4):** `casebible_ai_conversations`, `agent_session_memory`, `ms_scratchpad_31bc129d`, `ms_matts_f436780d` — i.e. app/agent-memory + memsearch collections. **None** of the design's forensic collections (messages, ocr_text, event_summaries, claims, pattern_findings, legal_issue, multimodal) exist yet → additive.

## Net assessment
The deployed forensic layer is at an **early spine stage**: boundary + custody hash + bitemporal `normalized_record` exist; everything else is greenfield. So the reconciled schema lands as a **mostly-additive migration**. Two real corrective items before/with it: (1) install `citext/ltree/hstore/fuzzystrmatch`; (2) apply the (fixed) `0004` custom types. The diff/migration report will enumerate per-object create-vs-exists status against this baseline.
