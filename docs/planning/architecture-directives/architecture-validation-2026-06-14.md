# Architecture Validation — SurrealDB / pgwire / Portkey / Federation
> _Byline: Claude Code · Opus 4.8 · 2026-06-14_
> Validates (and corrects) the target in [[ARCHITECTURE-HANDOFF-2026-06-14]] §3–4.
> **Supersedes** the "drop Postgres via SurrealDB-pgwire" path. Read this before reopening the pgwire spike.

## 0. TL;DR
The aggressive blueprint — **SurrealDB-central via pgwire, drop pg_duckdb/Postgres** — **does not function** and the gating spike is pre-answered: don't run it. The committed conservative shape (SurrealDB via native WS/RPC, Postgres kept) is correct and stays. SurrealDB's real role is a **consolidated analysis/correlation projection**; **Postgres becomes the live federation hub** (FDWs) and the richly-typed system of record. Portkey-at-edge is independent and may proceed.

## 1. Verified findings (primary sources, 2026-06-14)

| Claim in §3–4 | Verdict | Evidence |
|---|---|---|
| SurrealDB exposes a Postgres wire endpoint :5432 | **Not GA** — "In development", target 2026 Q2 | surrealdb.com/roadmap |
| pgwire lets DuckDB `postgres` ATTACH read SurrealDB → drop pg_duckdb | **❌ blocked** | DuckDB postgres ext uses libpq + scans `pg_catalog`; SurrealDB pgwire carries **SurrealQL**, not Postgres SQL |
| SurrealDB ANSI/standard SQL | **Not GA** — "In development" | surrealdb.com/features |
| FerretDB :27017 → pgwire → SurrealDB | **❌ wrong premise** | FerretDB needs a real Postgres/DocumentDB backend; SurrealDB can't be one |
| "Native GIS (geometry+MTREE) replaces PostGIS" | **Overstated** | SurrealDB has GeoJSON types + geo fns, but **no mature spatial index** (open issue surrealdb/surrealdb#5567) → geo queries scan |

**Logical floor:** SurrealDB has no SQL parser yet → its pgwire *cannot* accept Postgres SQL regardless of transport maturity. Waiting for pgwire GA does **not** unblock DuckDB/Postgres-client goals; that also needs the (separate, in-dev) ANSI SQL milestone + `pg_catalog` emulation. Treat "SurrealDB speaks Postgres" as **out of scope indefinitely**.

## 2. Locked decisions

1. **Data layer = the guaranteed fallback, now the only path.** Keep Postgres + pg_duckdb + Milvus + Neo4j. SurrealDB is added via **native WS/RPC** (`ws://…:8000/rpc`, agno `SurrealDb`) — already committed (700eefe). **Do NOT drop `agentos-db`.**
2. **SurrealDB role = consolidation / analysis-correlation projection**, NOT pgwire-central and NOT a federation engine (it has no FDW/live-attach; it only queries data physically in its own engine). Multi-model correlation — "entity X's relationships near location Y in window Z" in one SurrealQL query — is its job.
3. **Postgres role = live federation hub + richly-typed SoR.** FDWs give the query-time federation SurrealDB can't. This is the complement, not a duplicate.
4. **Analysis split:** SurrealDB = graph+temporal+geo *correlation*; DuckDB (pg_duckdb) = heavy columnar *aggregation*. No overlap.
5. **Graph SoR = Neo4j** (workhorse; feeds Graphiti + Semantica). SurrealDB holds only a *projection* of the graph — resolves the "two graph stores" risk: Neo4j owns, SurrealDB borrows.
6. **Geo:** heavy/indexed geo stays in **PostGIS** (real GiST index); SurrealDB gets a GeoJSON projection (scan-OK at analysis scale).
7. **Portkey** replaces LiteLLM at the edge — independent of all the above; proceeds in parallel. (MCP-gateway→ContextForge chain not yet deep-validated.)

## 3. Cross-store ID scheme (correlation glue)

**Principle: mint once, propagate — don't make N systems generate matching ids.** Postgres is the ID authority (PG18 native `uuidv7()`). The batch sync carries that one canonical uuid outward.

| System | Physical id (native, kept) | Shared key carried as |
|---|---|---|
| Postgres | `uuid v7` PK | *is* the canonical key |
| SurrealDB | record id = the uuid (`type::thing(tbl,<uuid>$id)`) | the record id itself |
| Milvus | **int64 auto-id** (fast) | `canonical_id` VARCHAR scalar field, indexed |
| Neo4j | internal node id | `:Label {canonical_id}` indexed property |

- **Retrieval glue:** Milvus ANN → returns uuids → SurrealDB `WHERE id IN [...]` hydrate/correlate → PG/DuckDB for raw rows/aggregation.
- **The real risk is representation, not capability:** SurrealDB v2+ needs `u"…"`/`<uuid>` to treat a string as uuid — `evidence:u"…"` ≠ `evidence:`…``. Pick uuid-typed everywhere; canonical lowercase-hyphenated form everywhere.
- **Two link problems, two mechanisms:**
  - *Mechanical* (same row across stores after sync) → stamped `canonical_id` attribute. No central table.
  - *Semantic* (deciding two independently-created entities are the same real thing) → the `id_xref` crosswalk (long/vertical, with `match_method` + `confidence`). Build this **only** for entity resolution, not routine sync.
- **Prerequisite:** Neo4j nodes must carry the PG uuid as a property for the Neo4j→SurrealDB projection to preserve the key. Confirm entities share a uuid across PG and Neo4j today, or add that mapping as a sync step.

## 4. Sync pipeline
- **Batch** (Windmill job), not CDC — analysis tolerates staleness; near-real-time deferred unless proven needed.
- Carries: Neo4j (graph) + Postgres (records) → SurrealDB projection, stamping `canonical_id` + serializing rich PG types (PostGIS→GeoJSON, tstzrange→start/end, enums→strings). That serialization is the per-type cost of rich PG typing.

## 5. Postgres = federation hub + rich types (implemented this session)
- **Image: Path A** — extend the proven `pgduckdb/pgduckdb:18-v1.1.1` base (`docker/postgres/Dockerfile`), not a third-party bundling image. Adds **Multicorn2** (catch-all Python FDW → neo4j-fdw + REST/SurrealDB wrappers) on top of existing PostGIS+pgvector. Protocol FDWs (mongo_fdw→FerretDB, redis_fdw→Dragonfly) staged/commented pending final selection. Milvus FDW skipped (vectors don't federate via SQL).
- **Rich types** (`sql/0001` + new `sql/0004_custom_types.sql`): citext, ltree, hstore, fuzzystrmatch added; enums (entity_type, temporal_class, event_type, disclosure_tier, mcl_factor, source_system, match_method), domains (confidence, canonical_id, geo_point), composite source_ref. Bitemporal `tstzrange` + GiST EXCLUDE pattern documented.
- **CAVEATS:** (a) init SQL only runs on an EMPTY pgdata volume — apply 0004 by hand on existing volumes; (b) the Multicorn2 build layer is **not build-verified in-repo** — it compiles on the Coolify/OVH-3 host; verify there, pin a tag if it fails; (c) every FDW/Multicorn wrapper — check predicate pushdown (Multicorn often pulls-then-filters: fine for analysis tables, painful on big ones).

## 6. Open / next
- Build the custom PG image on OVH-3 (Coolify) and confirm the Multicorn layer compiles against PG18.
- Finalize the protocol-FDW selection (Mongo/Redis) → uncomment the staged Dockerfile block.
- Confirm Neo4j entities carry the PG uuid (ID-scheme prerequisite).
- Deep-validate Portkey → ContextForge → Windmill MCP chain (separate spike).
- Author the Windmill batch-sync job (Neo4j+PG → SurrealDB projection).

## Sources
- SurrealDB roadmap (pgwire: in dev, Q2 2026) — surrealdb.com/roadmap
- SurrealDB features (ANSI SQL: in dev) — surrealdb.com/features
- Geospatial model + spatial-index gap — surrealdb.com/docs/surrealdb/models/geospatial ; surrealdb/surrealdb#5567
- Record IDs / UUID cast rules — surrealdb.com/docs/surrealql/datamodel/ids ; /datamodel/uuid
- DuckDB postgres extension (libpq/pg_catalog) — duckdb.org/docs/current/core_extensions/postgres/overview
- FDWs — wiki.postgresql.org/wiki/Foreign_data_wrappers ; pgsql-io/multicorn2 ; sim51/neo4j-fdw
