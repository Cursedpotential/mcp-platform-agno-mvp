# A2 — SSOT PRE-SCAN: Locked DB/Storage Architecture + Drift

> _Byline: Claude Code · Opus 4.8 (1M) · 2026-06-30_
> Sources: `Agno-MCP-Platform/docs/PROJECT_CANON.md` (updated 2026-06-13), `docs/MEMORY_ARCHITECTURE.md`,
> ADRs 0001–0032 (`docs/adr/`), planning docs (build-history). PROJECT_CANON §5 + the ADR README index
> are authoritative; `docs/planning/*` and MIGRATION_PLAN_v8 are explicitly superseded build-history.

**Headline:** There is **no live three-way conflict.** ADR-0003 vs 0013 vs 0010 only *look* like peers;
read chronologically they form a clean supersession chain. The genuine drift is doc-lag inside the still-LIVE
PG image (pgvector role) and one item the master prompt treats as new that is actually already ratified.

---

## 1. LOCKED DECISIONS (current, with ADR refs + dates)

| Layer | Locked decision | ADR / source | Date | State |
|---|---|---|---|---|
| Relational + analytics PG | Custom **PostgreSQL 18** image (`agno-postgres:18-duckdb`): native `uuidv7()`, **pg_duckdb** ext, **PostGIS**, pgvector, pg_trgm, pgcrypto, pg_stat_statements | **ADR-0013** (supersedes 0003 no-DuckDB) | 2026-06-10 | **LIVE** |
| DuckDB | **pg_duckdb extension INSIDE Postgres** (engines talk natively) — NOT a standalone DuckDB service | ADR-0013; reaffirmed ADR-0030, ADR-0032 | 2026-06-10→06-26 | **LIVE** |
| R2/S3 reach | SQL/forensic reads via **pg_duckdb account-wide S3 secret**; file ingest via **rclone bucket mount**; creds in Coolify env | **ADR-0030** (extends 0007/0013) | 2026-06-23 | LIVE |
| Cross-source federation | **Drop** Multicorn2/neo4j-fdw hub; reach = pg_duckdb (files/S3/relational) + native Cypher driver (Neo4j) + Milvus SDK (vectors); PG→Surreal pipeline | **ADR-0032** | 2026-06-26 | Accepted |
| Vector / ANN substrate | **Milvus** is the single platform-wide vector store (code index + Case Bible + domain-partitioned Knowledge + evidence text); Agno-native; one collection per embedder; hybrid dense+sparse/BM25 | **ADR-0027** (+0026) | 2026-06-13 | **LIVE on ovh2** (Milvus 3.0 standalone + Attu, Coolify); Knowledge migration = Phase B/D |
| Embedding contract | **One vector collection per embedder** (text vs code), raw docs = source of truth; contract carries from pgvector → Milvus collections | ADR-0010 (storage superseded-in-part by 0027) | 2026-06-01 | Shape in force; storage→Milvus |
| Embedder dims | text `nvidia/llama-nemotron-embed-vl-1b-v2` 2048-d / code `nv-embedcode-7b-v1` 4096-d; (Milvus code+CaseBible use OpenRouter `codestral-embed-2505` 1536-d) | ADR-0011, ADR-0026 | 2026-06-07/13 | In force |
| Graph cognition | **Neo4j community + Graphiti MCP** = bitemporal cognition substrate (VIP, NOT replaced); valid+knowledge-time + disclosure-tier multi-pass | ADR-0014, ADR-0018, ADR-0031 (supersedes FalkorDB) | 2026-06-10→ | **LIVE** |
| Store/session/memory + bitemporal records + analysis sink | **SurrealDB** (Agno-native multi-model, native bitemporal); PG→Surreal is the downstream analysis sink | **ADR-0024** (amended by 0027, 0032) | 2026-06-13 | **RATIFIED, NOT YET DEPLOYED** — migration sequenced Phase D |
| Semantica | Decision/provenance substrate, **pulled forward** as bitemporal substrate; multi-pass *use* = Part 2; seed-first per project memory | PROJECT_CANON §5 (locked) | 2026-06-13 | Locked, build pending |
| Model gateway | **LiteLLM** (`gateway` :4000); **Ollama Cloud `glm-5.1` = PRIMARY LLM**; NVIDIA NIM = embed/rerank/backup. **Compute is CLOUD-PRIMARY** (no GPU; local ≤4B only) | ADR-0015 (supersedes 0011 runtime) + memory | 2026-06-11 | LIVE |
| Tool gateway | **IBM ContextForge** MCP gateway (off-the-shelf, NOT custom, NOT DIAL); pinned **0.8.0** (per project memory); distinct from LiteLLM | ADR-0025 (+ canon §5) | 2026-06-13 | Accepted |
| Object store | **Cloudflare R2** = blob/object landing zone (buckets `nexus`, `casebible-*`) | ADR-0007 | 2026-06-01 | LIVE |

Reaffirmed principles: minimize custom code / off-the-shelf-first; VIP-never-fork (Agno, custom Graphiti,
Semantica, ContextForge, forked SBV, CopilotKit); never-delete→`_stale/`; HITL on every write.

---

## 2. CONFLICTS / DRIFT — adjudicated

| # | Apparent conflict | Verdict | Resolution |
|---|---|---|---|
| **C1 (the named conflict)** | ADR-0003 "PG18 pgvector-only, **NO DuckDB**, FalkorDB deferred" vs ADR-0013 "pg_duckdb custom image" vs ADR-0010 "two-collection pgvector embeddings" | **NOT a live conflict — supersession chain.** ADR-0003 is **superseded on every axis**: no-DuckDB→**ADR-0013** (pg_duckdb in PG); FalkorDB-deferred→**ADR-0014** (Neo4j+Graphiti pulled forward); pgvector-as-vector-store→**ADR-0027** (Milvus). ADR-0013 is **current & LIVE**. ADR-0010's *shape* (one collection/embedder, raw=truth) survives; its *pgvector storage* is superseded-in-part by ADR-0027. | Mark ADR-0003 **Superseded (0013+0014+0027)** in the README (currently still listed "Accepted" — drift). Keep ADR-0013 as the PG image SSOT. Treat ADR-0010 as embedder-contract-only, storage = Milvus. **DuckDB = pg_duckdb-in-PG ONLY; standalone DuckDB is NOT blessed.** |
| C2 | pgvector still compiled into the LIVE PG18 image (ADR-0013) but ADR-0027 retires pgvector as the Knowledge vector store | Both true: pgvector **physically present** (image), but **vector role moved to Milvus**. Knowledge-engine migration off pgvector is **Phase B/D**, not done. | Doc-lag only. Note pgvector is legacy-resident; new vectors → Milvus. No image change required now. |
| C3 | ADR-0024 SurrealDB "store/session/Knowledge/memory" vs ADR-0027 Milvus owns vectors | Resolved **inside ADR-0027**: SurrealDB keeps store/session/memory + bitemporal records; **vector/Knowledge role → Milvus**. | Already reconciled. SurrealDB ≠ vector store. |
| C4 | README index lists ADR-0003 as "Accepted" (line 16) | Stale status label. | Flag for fix → "Superseded by 0013/0014/0027." (Per never-delete: supersede, don't rewrite the ADR body.) |
| C5 | MIGRATION_PLAN_v8 / planning/* still describe PG16, pgvector-hybrid, `uuid_generate_v4` | Explicitly **build-history**, superseded by BUILD_PLAN/CANON. | No action; do not treat planning/* as current. |

---

## 3. Master-prompt proposed stack (PG / DuckDB / PostGIS / Milvus / Neo4j / Graphiti / Semantica / SurrealDB) — ADDS vs EXISTS

| Component | Status vs SSOT | Flag |
|---|---|---|
| **PostgreSQL** | EXISTS — ADR-0013, LIVE | — |
| **DuckDB** | EXISTS **only as pg_duckdb-in-PG** (ADR-0013/0030/0032) | ⚠️ **standalone/separate DuckDB = NEW & UNRATIFIED** — ADR-0003 explicitly rejected a separate DuckDB service; only the in-PG extension is blessed. If the proposal means a standalone DuckDB, it needs a new ADR. |
| **PostGIS** | **EXISTS** — layered into the custom PG18 image (ADR-0013, carried from 0003) | ✅ NOT new (corrects the prompt's hypothesis that PostGIS is unratified). |
| **Milvus** | EXISTS — ADR-0026/0027, **LIVE on ovh2** | — |
| **Neo4j** | EXISTS — ADR-0014, LIVE | — |
| **Graphiti** | EXISTS — ADR-0014/0018/0031, VIP, LIVE | — |
| **Semantica** | EXISTS (ratified, locked in CANON §5; build/seed pending) | — |
| **SurrealDB** | **RATIFIED — ADR-0024** (amended 0027/0032), but **NOT YET DEPLOYED** (Phase D) | ⚠️ corrects the prompt's hypothesis: SurrealDB is **not new/unratified** — it is locked, just unbuilt. |

**Net new/unratified introduced by the master prompt:** only **standalone DuckDB** (as distinct from
pg_duckdb). **PostGIS and SurrealDB are already ratified** (PostGIS present in image; SurrealDB ratified
but Phase-D-pending) — the prompt mis-flags both as new. Everything else already exists and is mostly LIVE.
