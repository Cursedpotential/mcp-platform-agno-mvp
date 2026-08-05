> _Byline: Claude Code · Sonnet (R1e) · 2026-07-11_

# 05 — Storage substrates beyond Agno: SurrealDB, Milvus, Graphiti/Zep, pgvector + pg_duckdb

Agno's own memory/storage primitives are covered elsewhere in this reference set. This
document is the **capabilities reference** for the four non-Agno storage substrates the
platform runs (or has run) underneath/alongside Agno: SurrealDB (operational store),
Milvus (vector/ANN), Graphiti on Neo4j (temporal knowledge graph), and pgvector/pg_duckdb
on PostgreSQL 18 (superseded-for-Knowledge but still live for sessions/analytics/R2 access).
Focus is **what each substrate CAN do**, including capabilities we are not yet using, with a
short "How WE run it" per section pinned to the actual compose/config files in this repo.

STATUS: draft, filling incrementally.

---

## 1. SurrealDB v3.x

SurrealDB is a multi-model database: document, graph, relational, vector, full-text, and
(loosely) time-series data all live in one engine addressed by one query language,
SurrealQL. The pitch relevant to us is "the context layer for AI agents" — storage, session
state, and retrieval consolidated instead of stitched across three or four specialized stores.

**SurrealQL / multi-model.** Records are schemaless-or-schemafull documents (`CREATE`,
`UPDATE`, `UPSERT`) addressable by typed record IDs (`table:id`). Fields can themselves hold
arrays, nested objects, or **record links** (a field literally storing another record's ID,
resolved with `.field` dot-traversal — a lightweight join without a join). Graph edges are a
first-class primitive via `RELATE user:tobie->wrote->article:surreal` — SurrealDB stores the
edge as its own record (can carry its own fields/permissions) and graph traversal reads as
`->wrote->article` in a `SELECT`, no separate graph engine bolted on. This is the "document +
graph" half of multi-model; the same query language does relational joins and time-series-ish
range queries over the same records.

**Vector search.** Two ANN index types as of v3.1: **HNSW** (in-memory graph index —
`DEFINE INDEX ... HNSW DIMENSION @d [TYPE F64|F32|I64|I32|I16] [DIST euclidean|cosine|...] [EFC
150] [M ...]`, bounded 256 MiB cache by default, `SURREAL_HNSW_CACHE_SIZE` to tune) and, new in
v3.1.0, **DISKANN** (on-disk Vamana-graph index — `DEFINE INDEX ... DISKANN DIMENSION @d [TYPE
F32|F16|I8|U8] [DIST EUCLIDEAN|COSINE|INNER_PRODUCT|COSINE_NORMALIZED] [DEGREE 64] [L_BUILD 100]
[ALPHA 1.2] [HASHED_VECTOR]`, also cached, `SURREAL_DISKANN_CACHE_SIZE`, not available on WASM)
for larger-than-memory vector sets. MTREE is the older/simpler metric-tree index (still
available, cosine and other distances) for smaller vector sets where HNSW's memory overhead
isn't worth it. Vectors are just another field type, so a query can combine `<|K,EF|>` KNN
search with ordinary `WHERE` filters and graph traversal in the same `SELECT` — this is the
capability we'd lean on to search evidence text semantically **and** filter to a case/tier
**and** walk a graph edge to related exhibits, in one statement, without round-tripping through
a separate vector DB.

**Full-text search.** `DEFINE INDEX ... FULLTEXT ANALYZER @analyzer [BM25[(k1, b)]]
[HIGHLIGHTS]` — custom analyzers (tokenizers + filters), BM25 relevance scoring, and
`search::highlight()` for snippet highlighting. Combinable with vector search and scalar
filters in one query (SurrealDB's version of hybrid search) — a capability we are not
currently exercising anywhere.

**Live queries.** `LIVE SELECT` subscribes a client to ongoing changes on a query, with
filtering on what changes are pushed. Security-hardened: live queries terminate on session
invalidation, TTL expiry, or principal change, and a subscriber can't read hidden records via
captured values/events. Relevant to a future "push evidence/finding updates to a UI or agent
as they land" feature — nothing in the platform uses this yet.

**Permissions / namespaces / access control.** Two parallel auth models: **system users**
(`DEFINE USER ... ROLE OWNER|EDITOR|VIEWER`, scoped to root/namespace/database level — classic
RBAC for admins/services) and **record users** (`DEFINE ACCESS ... TYPE RECORD` with `SIGNUP`/
`SIGNIN`/`AUTHENTICATE` clauses — application end-users authenticate as regular table records,
JWT-based, and get **no** access by default; every table/field carries a `PERMISSIONS` clause
that defaults to `NONE` and must be explicitly opened). Namespaces nest databases for hard
multi-tenant isolation (separate namespace per tenant = provably separate data). None of this
fine-grained permission model is in play for us today — we run a single root-credentialed,
tailnet-isolated instance — but it's the mechanism that would let a future multi-user/
multi-case deployment wall off record-level access inside one SurrealDB instance instead of
standing up separate databases.

**Transactions.** Fully ACID, multi-row/multi-table, no hard time limit — relevant to
maintaining bitemporal invariants (e.g., an `EXCLUDE`-style no-overlap guarantee on a
valid-time range) transactionally rather than relying on application-level locking.

**Relevance to the planned bitemporal-record layer (ADR-0024/0027).** SurrealDB's storage
engine (SurrealKV / here, rocksdb) natively tracks valid-time and transaction-time per record
with time-travel query support — this is *why* ADR-0024 picked it as the bitemporal evidence-
record store (`NormalizedRecord.occurred_at` = valid time, `knowledge_time` = transaction
time). That's a different bitemporal mechanism than Graphiti's (which invalidates graph
*edges*/facts on contradiction inside a knowledge-graph cognition layer) — SurrealDB would be
bitemporal *storage*, Graphiti stays bitemporal *cognition*. As of this research pass the
bitemporal-record migration itself has not landed; SurrealDB's live role is Agno
sessions/state/memory only.

### How WE run it

- Image `surrealdb/surrealdb:v3.1.4`, `platform: linux/amd64`, single-node, storage engine
  `rocksdb:/data/surreal.db` (persistent file engine on an absolute host bind
  `/data/agno/volumes/surrealdb`) — see `compose.data-surreal.yaml`.
- Runs as its own Coolify app `data-surreal` on OVH-3, tailnet-only (`${BIND_IP}:8000`,
  never `0.0.0.0`), WS transport at `/rpc`. No Traefik labels — deliberately not
  internet-facing (no admin UI worth exposing, per the compose comments).
- Auth: `--user=${SURREALDB_USER:-root} --pass=${SURREALDB_PASS:-root}` (root creds, tailnet
  isolation is the perimeter control).
- Healthcheck uses the bundled `/surreal isready` binary (the image ships no `sh`/`curl`, so a
  CMD-SHELL curl check always false-failed — fixed 2026-07-05).
- Role per ADR-0024: the Agno-native **store / session / Knowledge / memory** engine, and the
  intended home for the **bitemporal evidence-record store** (`NormalizedRecord` occurred_at /
  knowledge_time / disclosure_tier — valid-time + transaction-time mapping). ADR-0027
  subsequently moved the platform's **vector/Knowledge** role to Milvus, so SurrealDB's live
  scope today is sessions/state/memory + (planned) bitemporal records — not vectors.
- Joins the shared external `agno` Docker network for cross-app DNS (`surrealdb:8000`).

---

## 2. Milvus 3.0

Milvus is a purpose-built vector/ANN database — the platform's designated single vector
substrate (ADR-0026/0027). What follows is its broader capability surface, including several
features the platform's current forensic schema does not yet turn on.

**Collection schema.** A collection is a set of typed fields: scalar (`INT64`, `VARCHAR`,
`BOOL`, `DOUBLE`, `JSON`, ...), one or more vector fields (`FLOAT_VECTOR`,
`SPARSE_FLOAT_VECTOR`, and reduced-precision variants), exactly one primary key (can be
`auto_id`), and — with `enable_dynamic_field=True` — an implicit catch-all JSON-like bucket
for fields not declared up front (write arbitrary extra keys per-row without a schema
migration). A collection can also hold a genuine `JSON` field for structured nested metadata
that isn't dynamic-field overflow.

**Partitions + partition key.** Two isolation mechanisms, easy to conflate. A **partition** is
a manually-created physical subdivision of a collection (`create_partition`) you load/release/
search independently. A **partition key** is a scalar field flagged `is_partition_key=True` at
schema time — Milvus then **hash-routes every row into one of N automatically-managed
partitions** (default 16, configurable up to 128+ via `num_partitions`) with no manual
partition management. A query with `partition_key == "x"` or `partition_key in [...]` prunes
the search to only the relevant partition(s) instead of scanning the whole collection. The
**Partition Key Isolation** feature (HNSW indexes only) goes further and builds a *separate
index per partition-key value*, eliminating cross-tenant scanning entirely. Milvus's own docs
frame partition key as the multi-tenancy answer for "millions of tenants" (weaker per-tenant
isolation than separate collections/databases, but near-unlimited scale, zero manual partition
ops). **This is directly relevant to us and unused**: our three forensic collections
(`forensic_records`/`forensic_findings`/`forensic_patterns`) have no partition key today —
`subject_type`/`category_id`/`source` would be natural partition-key candidates if/when the
platform needs to isolate search scope per domain (custody vs. financial vs. communications) or
per case without spinning up parallel collections.

**Hybrid search.** A single request can run **multiple vector fields** (e.g., a dense semantic
vector plus a sparse BM25 vector, or two different embedders) as parallel "ANN groups" and
fuse the ranked lists with a **reranker**: `RRFRanker` (Reciprocal Rank Fusion, smoothing
constant `k`, default 60 — democratic combination, no per-source weighting) or
`WeightedRanker` (explicit per-field weights when one signal should dominate). This is Milvus's
built-in analogue to Graphiti's RRF/MMR rerankers.

**Sparse vectors / BM25 function.** A collection can declare a `Function` of `type=BM25` that
derives a `SPARSE_FLOAT_VECTOR` field automatically from a `VARCHAR` text field at insert time
(no external BM25 computation needed) — indexed with `SPARSE_INVERTED_INDEX` and
`metric_type="BM25"`, typically `index_type="AUTOINDEX"`. Full-text/keyword search then
composes with dense vector search via the hybrid-search rerankers above. Our
`server/analysis/milvus_forensic.py` defines exactly this (`_bm25()` /
`_dense_and_text()`/`ENABLE_SPARSE_BM25`) but it ships **disabled by default**.

**Filtering pushdown.** Scalar filter expressions (`WHERE`-style boolean expressions over
scalar/JSON/dynamic fields) are evaluated as part of the ANN search itself (not a post-filter
on top-K results), so a restrictive filter (e.g., our court-safety gate fields) narrows the
candidate set the index actually searches rather than discarding already-fetched results.

**Indexes.** `AUTOINDEX` (Milvus picks the concrete algorithm/parameters — version-robust, what
we use) sits on top of a real algorithm menu: `HNSW`, `IVF_FLAT`/`IVF_SQ8`/`IVF_PQ`, `FLAT`
(brute-force, exact), `SCANN`, and `DiskANN` (SSD-resident Vamana-graph index for
larger-than-memory vector sets — the Milvus analogue of SurrealDB's DISKANN). Index types
support quantization variants and mmap for memory/speed trade-offs.

**Consistency levels.** Four levels, weakest→strongest: **Eventually** (fastest, no
freshness guarantee), **Session** (a client sees its own writes), **Bounded** (default —
bounded staleness window, good throughput/freshness balance), **Strong** (waits for all writes
up to request time to be visible — slowest, use when correctness beats latency). Collections
default to Bounded if unspecified; the platform hasn't pinned an explicit level.

**TTL.** Collection-level time-to-live — entities auto-expire after a configured duration. Not
used today; would be relevant for any ephemeral/cache-like vector data (as opposed to
evidence, which must persist).

**RBAC.** Full role-based access control — users, roles, privilege grants scoped to
collection/database/instance level, privilege *groups* for bundling common grant sets, and
(per Zilliz blog coverage) row-level access control for finer partition-key-based restriction.
We run single-credential `root:Milvus` auth today (`common.security.authorizationEnabled:
true` in `docker/milvus/user.yaml`) — no roles/users beyond root.

**Milvus Lite.** An embedded, pip-installable, file-backed variant of Milvus for local
dev/prototyping (no server) — not used here (we run standalone server mode with embedded
etcd/WoodPecker), but worth knowing about for quick local experiments against the same API
surface before touching the shared server.

### How WE run it

- Image `milvusdb/milvus:v3.0-beta-amd64`, explicit `amd64` (multi-arch segfaults at jemalloc
  on this host), standalone mode (`milvus run standalone`), embedded etcd
  (`ETCD_USE_EMBED=true`, config `docker/milvus/embedEtcd.yaml`) + WoodPecker (Milvus 3.0's
  streaming WAL) pinned to **local** storage (no MinIO/object-store needed for this
  single-node deploy) — `docker/milvus/user.yaml`.
- `stop_grace_period: 60s` — the embedded etcd needs time to flush its WAL on SIGTERM; the
  Coolify default (10s) SIGKILLed it and corrupted the WAL repeatedly (2026-06-25, 06-27,
  07-05) until this was set.
- Auth on (`common.security.authorizationEnabled: true`); default credential
  `root:Milvus` (client token `root:Milvus`) — flagged in the config comments to be changed.
- Split into its own Coolify app `data-vector` (ports 19530 gRPC + 9091 health, tailnet-only)
  after a 2026-06-25 incident where a Milvus crash-loop took the entire bundled data-tier down
  with it. Attu v3.0.0-beta.6 runs alongside as the GUI (port 3001).
- Forensic collection schema (`server/analysis/milvus_forensic.py`, DEFINE-ONLY module):
  three collections — `forensic_records` (normalized_record semantic index),
  `forensic_findings` (pattern_finding matched-text index), `forensic_patterns`
  (detection_pattern description+keyword index). Each is **1024-d COSINE** (`EMBED_TEXT_DIM`,
  bge-m3 via OpenRouter — a different embedder/dim than Graphiti's 4096-d nv-embed-v1), index
  `AUTOINDEX`, and every collection carries the same **court-safety scalar gate fields**:
  `review_status`, `safe_for_legal_use`, `requires_human_review`, `bias_caution`,
  `sensitivity_tier`, `data_tier` — so agents can filter to review-approved, non-sealed
  vectors only, mirroring the Postgres `pattern_finding`/`normalized_record` gates. Optional
  hybrid dense+sparse BM25 lane behind `ENABLE_SPARSE_BM25`/`FORENSIC_MILVUS_HYBRID` env
  (Milvus BM25 `Function` on the `text` field → `sparse` output field,
  `SPARSE_INVERTED_INDEX` + `BM25` metric) — off by default, on when retrieval quality
  demands it. `create_forensic_collections()` is dry-run by default (returns a plan, offline
  validation, no server contact); real creation is HITL/APPROVALS-gated.
- Semantica wiring (`server/analysis/semantica_wiring.py`, design/local only, no writes):
  targets the **same** three forensic collections (no second vector index), dimension-locked
  to the platform's 1024-d bge-m3 contract, `enable_hybrid_search: True`, `metric: cosine`.
- Role per ADR-0026/0027: **the single vector/ANN substrate for the entire platform** —
  code index, Case Bible corpus, the domain-partitioned Knowledge engine (migration off
  pgvector deferred to Phase B/D pending Milvus GA), and evidence-text embeddings. One
  collection per embedder/domain is the standing contract.

---

## 3. Graphiti (Zep) on Neo4j

Graphiti is the open-source "Context Graph" engine that also powers Zep's hosted product — a
temporal knowledge graph purpose-built for agent memory, not a general graph database wrapper.

**Episode model.** Data is ingested as discrete **episodes** — `text` (freeform), `message`
(chat-turn-shaped), or `json` (structured business data) — each preserving provenance (which
episode a fact came from) and enabling **incremental** entity/relationship extraction rather
than a single big batch job. Episodes can reference `previous_episode_uuids` for ordering
context, carry `reference_time` for when the content is *about* (vs. when it was ingested),
and support `excluded_entity_types`/`custom_extraction_instructions` to steer what the LLM
extraction pass pulls out.

**Bitemporal edges.** Every graph edge (fact/relationship) carries explicit validity fields:
`valid_at` (when the fact became true in the world) and `invalid_at`/`expired_at` (when it
stopped being true, or was superseded/contradicted). When new information contradicts an
existing edge, Graphiti **invalidates** the old edge rather than deleting it — the graph
retains a full point-in-time-queryable history of what was believed true when. This is the
"cognition" half of bitemporal (as opposed to SurrealDB's storage-level bitemporal records) —
automatic fact-invalidation on contradiction is Graphiti's headline capability and the reason
ADR-0024 keeps it as a VIP rather than folding its role into SurrealDB.

**Entity + community nodes.** Entities extracted from episodes become graph nodes; **community
nodes** are a second, independent structure built by Leiden community detection over the
entity graph — a global summarization layer (clusters of related entities get their own
summary node) distinct from single-entity or single-edge retrieval, useful for "what are the
major clusters of activity/actors" queries rather than point lookups. `build_communities` /
`summarize_saga` tools (re)compute these.

**group_id namespacing.** Every write and most search calls are scoped by `group_id` (or
`user_id`), which functions as a hard namespace — a search only sees nodes/edges/episodes
written under the same group_id. This is the mechanism a multi-tenant or multi-domain
deployment would use to keep graphs logically separate inside one Neo4j database without
separate databases. **See the flagged conflict below — this repo has two different group_ids
in play.**

**Hybrid retrieval recipes.** Search combines three retrieval methods and reranks the union:
**semantic** (embedding similarity over node/edge text), **BM25 full-text** (keyword/exact-term
match, complementing semantic), and **graph traversal** (`bfs_origin_node_uuids` — breadth-first
from given starting nodes, e.g. recent episodes, to bias results toward what's graph-local to
current context). Default combiner is **RRF** (Reciprocal Rank Fusion — the same technique
Milvus offers for its own hybrid search). Additional rerankers: **MMR** (Maximal Marginal
Relevance, `mmr_lambda` param — trades top-1 relevance for result diversity, avoiding a page of
near-duplicate facts), **node_distance** (reorders by graph distance from a designated centroid
node — "give me things close to X in the graph"), **episode_mentions** (ranks by how often an
entity/fact is mentioned across episodes — a cheap popularity/salience proxy), and
**cross_encoder** (jointly scores query+result pairs for higher-precision reranking at higher
cost). Results are filterable by entity type, edge type, and `valid_at`/`invalid_at` timestamp
ranges — i.e., "what did we believe was true as of date X" queries fall directly out of the
bitemporal model.

**Custom entity types.** Pydantic models define domain-specific entity/edge types (vs. letting
structure emerge unguided from extraction) — configured under the `graphiti:` section of
`config.yaml` via `entity_types`/`edge_types`/`edge_type_map` keys. Not exercised in our current
`docker/graphiti/config.yaml` (only `group_id` is set there) — this is a capability gap: a
`custody`/`financial_transaction`/`communication_event` entity-type schema would sharpen
extraction quality over generic entities, and would be the natural place to encode the
platform's existing behavioral-category ontology if Graphiti extraction is meant to align with
it (parallel to how Semantica's `seed_first_hybrid` wiring seeds from
`analysis.behavior_category`/`detection_pattern`).

**MCP server tool surface vs. the python library.** The `zepai/knowledge-graph-mcp` image we
run exposes a curated MCP tool set — `add_memory` (episode ingestion: text/message/json,
`reference_time`, `excluded_entity_types`, `custom_extraction_instructions`,
`previous_episode_uuids`, saga fields), `add_triplet` (insert a single fact directly, bypassing
LLM extraction — useful for known-good structured facts), `search_memory_facts` (edge search
with `edge_types`, `center_node_uuid`, `valid_at`/`invalid_at` range filters),
`search_nodes` (entity search), `summarize_saga`, and `build_communities`. This is a
**subset** of what the underlying `graphiti-core` Python library exposes — the library gives
direct programmatic access to the bitemporal edge model, custom entity/edge type registration,
community-building internals, and lower-level graph operations the MCP surface doesn't expose
as discrete tools. Practically: anything the MCP tool list above covers is reachable from
Claude Code / agents today (`mcp__graphiti__*`); anything deeper (e.g., registering custom
entity types, fine-grained community tuning) requires either a `config.yaml` change (entity
types) or dropping to `graphiti-core` directly in a Python service — the MCP server is not the
full API surface.

**Neo4j backend requirements.** Graphiti's storage layer is pluggable (Neo4j, FalkorDB, Amazon
Neptune, Kuzu per community docs) but we run Neo4j Community 5.x. Neo4j is the only backend
this platform has wired; no evaluation of FalkorDB/Neptune has been done here.

### How WE run it

- Image `zepai/knowledge-graph-mcp:latest` (the MCP server, not the raw `graphiti-core`
  Python library) — `compose.data-graphiti.yaml`, its own Coolify app `data-graphiti` on
  OVH-3, internal-only (no host port on the MCP container itself — a `graphiti-hostfix`
  nginx sidecar owns `${BIND_IP}:8071` and rewrites the `Host` header to `localhost:8071`
  before proxying, because the image's bundled MCP SDK hardcodes
  `allowed_hosts=["127.0.0.1:*","localhost:*"]` in its `FastMCP()` constructor — the
  `FASTMCP_TRANSPORT_SECURITY` env override is silently ignored upstream, discovered
  2026-07-07). MCP server is never exposed directly; external access is meant to route
  through the IBM ContextForge MCP gateway (ADR-0025 Phase D) — deliberately no Traefik
  labels.
- Backend: Neo4j `neo4j:5-community`, its own Coolify app `data-neo4j`, bolt on 7687 +
  browser on 7474, both tailnet-only. Auth via `NEO4J_AUTH=neo4j/${NEO4J_PASSWORD}`
  (env only consulted on a fresh/empty data dir — subsequent changes need a datadir reset).
  Reached over the shared external `agno` Docker network (cross-app DNS,
  `bolt://neo4j:7687`) rather than the tailnet host IP, since the 2026-07-05 shared-net
  migration.
- Config (`docker/graphiti/config.yaml`, ADR-0014): `server.transport: http` on port 8000
  inside the container; **LLM** = `nemotron` via the LiteLLM gateway
  (`OPENAI_API_URL`→`http://gateway:4000/v1`) — chosen over `glm-5.1` because glm-5.1 cannot
  emit schema-conformant structured JSON output, which silently failed every `add_memory`
  call until fixed 2026-07-04; **embedder** = `embed-text` (nvidia `nv-embed-v1`, symmetric,
  **4096-d**) via the same gateway; `graphiti.group_id: "platform"`.
- **CONFLICT FLAGGED**: `docker/graphiti/config.yaml` sets `group_id: "platform"` (the live
  MCP server default namespace), but `server/analysis/semantica_wiring.py`'s
  `graph_store_config()` hardcodes `group_id: "casebible"` for Semantica's read/derive-side
  Neo4j access — a different namespace than what the deployed Graphiti MCP server actually
  writes under. Semantica's config comment also asserts "Graphiti owns bitemporal writes to
  Neo4j under group_id='casebible'", which does not match the deployed config file's
  `"platform"`. Not reconciled as part of this research pass — flagging for the synthesis
  phase to check actual episode data (`graphiti-get-status` / `graphiti-search-nodes`) under
  both group_ids and decide which is canonical (or whether both are legitimately in use for
  different data).
- Role per ADR-0014/0024: the **bitemporal cognition** substrate — VIP, not being replaced by
  SurrealDB (which is bitemporal *storage*, a different altitude) or by Semantica (which is
  read/derive-side only; Graphiti stays the sole graph writer — "Semantica proposes, Graphiti
  persists").

---

## 4. pgvector + pg_duckdb on PostgreSQL 18

**pgvector — current capabilities (0.8 series).** Four vector types: `vector` (float32,
original), `halfvec` (float16 — halves storage/memory at modest recall cost, useful for large
collections where full float32 precision is overkill), `sparsevec` (sparse vectors — the
pgvector analogue of Milvus's `SPARSE_FLOAT_VECTOR`, for BM25-style or other sparse
embeddings), and `bit` (binary vectors, e.g. for Hamming-distance hashes). Six distance
operators across these types (L2, inner product, cosine, L1, Hamming, Jaccard depending on
type). Two ANN index methods: **HNSW** (recommended under ~5M vectors — faster reads, graceful
updates, no need to pre-load data before building the index) and **IVFFlat** (cheaper to build,
needs representative data present before index build, better for very large collections where
HNSW's memory footprint is prohibitive). **Iterative index scans** (0.8+,
`hnsw.iterative_scan`/`ivfflat.iterative_scan`) directly address the classic "vector search +
restrictive WHERE filter returns too few rows" problem — if the initial ANN scan under-returns
against the filter, pgvector keeps scanning further into the index (bounded by
`hnsw.max_scan_tuples`/`ivfflat.max_probes`) instead of just returning a short result set. This
is conceptually the same problem Milvus solves via filtering *pushdown into* the index search
rather than post-filtering — two different mechanisms converging on the same requirement
(scalar-filtered vector search that doesn't silently starve).

**pg_duckdb — what it enables.** Embeds DuckDB's columnar-vectorized execution engine *inside*
Postgres as an alternate query executor. Existing SQL runs unmodified; setting
`duckdb.force_execution=true` (or DuckDB auto-selection heuristics) routes a query through
DuckDB's engine instead of Postgres's row executor — DuckDB can read Postgres tables directly
(`SELECT` from Postgres tables executed by DuckDB) and supports **"dual execution"**: a single
query can join local Postgres tables against files/object-store data, and pg_duckdb figures out
where each part should run. Read/write support for Parquet, CSV, JSON, and read support for
**Iceberg and Delta Lake**, against **S3, GCS, Azure, and R2** — this is the mechanism behind
`read_parquet()`/`read_csv()`/`iceberg_scan()` reading straight from our R2 buckets. Secrets are
managed via `duckdb.secrets` (`type='S3'`, `key_id`, `secret`, region, endpoint) — exactly the
account-wide secret `ensure_duckdb_r2_secret()` creates for us (see below).

**pg_duckdb limits worth knowing.** Iceberg support is **read-heavy**: DuckDB's own Iceberg
writer only recently gained INSERT/UPDATE/DELETE (DuckDB 1.4.x) and even then only against
*unpartitioned, unsorted* tables — writing to partitioned/sorted Iceberg tables errors, and only
merge-on-read (positional deletes) is supported, not copy-on-write. The `iceberg_scan` path
does a **full table scan with no partition pruning**, so very large Iceberg tables can be slow
to query — a real limit if the platform ever points pg_duckdb at a large partitioned lakehouse
table rather than a modest analytics extract. Type mapping has edge cases too: Postgres
`numeric`'s arbitrary precision doesn't fully map to DuckDB's `decimal`, silently falling back
to `double precision` (potential precision loss) when precision exceeds what DuckDB supports.
None of these have bitten us yet (current use is R2 Parquet/CSV reads, not Iceberg writes or
huge partitioned scans), but they bound what "just point pg_duckdb at it" can safely do.

### How WE run it

- Custom image `agno-postgres:18-duckdb`, built from `pgduckdb/pgduckdb:18-v1.1.1` base
  (`docker/postgres/Dockerfile`), with PostGIS 3 and pgvector added via PGDG packages
  (`postgresql-18-postgis-3`, `postgresql-18-pgvector`). `pg_stat_statements` and `pg_duckdb`
  both need `shared_preload_libraries` — chained in the image `CMD`.
- Its own Coolify app `data-pg`, tailnet-only port 5432, absolute host bind
  `/data/agno/volumes/pgdata`.
- Extensions enabled at first boot (`sql/0001_init_extensions.sql`): `vector` (pgvector),
  `pg_trgm`, `pgcrypto` (hashing only, not UUIDs — PG18 has native `uuidv7()`), `btree_gin`,
  `btree_gist` (powers `EXCLUDE` constraints on `tstzrange` for bitemporal no-overlap),
  `unaccent`, `citext`, `ltree` (hierarchical labels — MCL factor trees, evidence taxonomies),
  `hstore`, `fuzzystrmatch` (soundex/levenshtein/metaphone → entity resolution). `postgis`,
  `pg_duckdb`, `pg_stat_statements` are guarded in `DO $$ ... EXCEPTION` blocks so boot never
  fails against a stock (non-custom) image. `pg_textsearch` (BM25) is explicitly **staged, not
  baked** — no PGDG package yet; add when Agno's built-in hybrid search proves insufficient.
- R2/S3 access: `ensure_duckdb_r2_secret()` (`server/core/session.py`) idempotently runs
  `duckdb.create_simple_secret(type:='S3', key_id:=…, secret:=…, region:='auto',
  endpoint:='{account}.r2.cloudflarestorage.com')` at API startup, reading
  `R2_ACCESS_KEY_ID`/`R2_SECRET_ACCESS_KEY`/`R2_ACCOUNT_ID` from env — **account-wide**, one
  secret covers every bucket (`nexus`, `casebible-sorted`, …). The secret lives in Postgres
  (survives container restarts; only a volume reset drops it) — this is ADR-0030's SQL/forensic
  read path, complementary to the separate rclone bucket-mount path used for file-level
  ingestion. The sandbox container is deliberately R2-isolated (no secret, no mount).
- Multicorn2 FDW (a live cross-source federation hub via compiled `neo4j-fdw` + REST
  wrappers) was **removed** 2026-06-26 (ADR-0032) once SurrealDB became the downstream
  analysis sink — cross-source reach is now pg_duckdb (files/object-store/relational) +
  native drivers (Neo4j Cypher, Milvus SDK) at the agent/orchestration tier, not query-time
  SQL federation. Core `postgres_fdw`/`file_fdw` remain available if a plain PG-to-PG link is
  ever needed.
- Role: **superseded for Knowledge** (ADR-0027 moved platform vector/ANN search to Milvus;
  ADR-0024 had already slated the Knowledge-vector role to move) but still the base
  relational store, still used for pg_duckdb-mediated R2/analytics reads, and still the home
  of the extension contract (bitemporal `EXCLUDE`/`tstzrange`, entity-resolution fuzzy match)
  that other analysis code depends on.

---

## Zep vs Graphiti-OSS — clarification

**Graphiti (OSS)** is the open-source Context Graph *engine* — the bitemporal
extraction/storage/retrieval library, pluggable across Neo4j/FalkorDB/Neptune (and per
community docs, Kuzu). Self-hosting it means running the graph database yourself, plus
whatever LLM/embedding infra the extraction and embedding pipeline needs (in our case, the
LiteLLM gateway) — "at least three systems to provision, monitor, and maintain" as one
comparison put it. That's exactly our deployment shape: `zepai/knowledge-graph-mcp` (the MCP
wrapper around graphiti-core) + Neo4j Community + the LiteLLM gateway, all self-hosted,
zero dependency on Zep's hosted service.

**Zep (hosted/Cloud)** is Zep Inc.'s managed product, built *on top of* the same Graphiti
engine, adding: proprietary extraction LLMs/reranker/embedding models tuned for the pipeline,
token-optimized retrieval and context assembly (sub-200ms latency SLA at scale), integrated
user/thread/message storage management (a higher-level session abstraction Graphiti-OSS
doesn't provide on its own), a dashboard (graph visualization, debug/API logs), enterprise
governance (RBAC, ABAC, audit, retention, multi-tenant isolation), and SOC2 Type II / HIPAA
compliance with flexible deployment (cloud, BYOK, BYOC). It's a credit-metered service — every
memory operation (add/search/episode processing) consumes credits.

**What we run and why it matters for this doc:** the platform runs **Graphiti MCP directly**,
not Zep Cloud and not Agno's `ZepTools` integration. Agno does ship a `ZepTools`/`ZepMemory`
toolkit (`agno.tools.zep` — wraps the `zep-python` client against a **Zep server**, whether
hosted Zep Cloud or Zep's self-hosted community edition, for agentic memory: `add_memory`,
`get_memory`, `get_messages`, `get_summary`, `update_summary`, `delete_memory`) — but that talks
to the *Zep* product's API surface, not the plain Graphiti MCP server we deployed. Because we
run `zepai/knowledge-graph-mcp` as its own MCP server (ADR-0014) rather than routing agent
memory through Agno's `ZepTools`, the platform bypasses Agno's Zep integration entirely — one
more instance (alongside SurrealDB vs. Agno's native `Db` and Milvus vs. Agno's native
`Knowledge` vector-store wiring) where the platform chose the substrate's own protocol/MCP
surface over Agno's built-in toolkit wrapper for that substrate.

---

## Coverage

**Local ground truth read:**
- `docker/graphiti/config.yaml`, `compose.data-graphiti.yaml`, `compose.data-neo4j.yaml`,
  `compose.data-pg.yaml`, `compose.data-surreal.yaml`, `compose.data-vector.yaml`
- `docker/milvus/embedEtcd.yaml`, `docker/milvus/user.yaml`, `docker/postgres/Dockerfile`
- `server/analysis/milvus_forensic.py`, `server/analysis/semantica_wiring.py`
- `sql/0001_init_extensions.sql`, `server/core/session.py` (`ensure_duckdb_r2_secret`)
- `docs/adr/0024-surrealdb-store-session-knowledge-memory.md`
- `docs/adr/0027-milvus-platform-wide-vector-substrate.md`
- `docs/adr/0030-r2-access-duckdb-secret-and-rclone-mount.md`
- `AGENTS.md` (repo root)

**Web sources consulted (via WebSearch/WebFetch, official docs prioritized):**
- SurrealDB: `surrealdb.com/docs/surrealql/statements/define/indexes` (HNSW/DISKANN/FULLTEXT
  DEFINE INDEX syntax), `surrealdb.com/docs/surrealdb/models/vector`,
  `surrealdb.com/docs/surrealdb/reference-guide/vector-search`, `surrealdb.com/3.0`,
  `surrealdb.com/3.1` (release notes), `surrealdb.com/docs/surrealql/transactions`,
  `surrealdb.com/docs/surrealql/statements/define/user`,
  `surrealdb.com/docs/surrealql/statements/define/access/record`,
  `surrealdb.com/docs/surrealdb/introduction/concepts/namespace`
- Milvus: `milvus.io/docs/use-partition-key.md`, `milvus.io/docs/multi_tenancy.md`,
  `milvus.io/docs/rrf-ranker.md`, `milvus.io/docs/bm25-function.md`,
  `milvus.io/docs/multi-vector-search.md`, `milvus.io/docs/rbac.md`,
  `milvus.io/docs/users_and_roles.md`, `milvus.io/docs/consistency.md`,
  `milvus.io/blog/understanding-consistency-levels-in-the-milvus-vector-database.md`
- Graphiti/Zep: `help.getzep.com/zep-vs-graphiti`, `help.getzep.com/v2/searching-the-graph`,
  `help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types`,
  `github.com/getzep/graphiti/blob/main/mcp_server/README.md` (via search summary),
  `neo4j.com/blog/developer/graphiti-knowledge-graph-memory/`
- pgvector/pg_duckdb: `postgresql.org/about/news/pgvector-080-released-2952`,
  `github.com/pgvector/pgvector`, `github.com/duckdb/pg_duckdb` (README + `docs/settings.md`,
  `docs/types.md`), `duckdb.org/docs/current/core_extensions/postgres/secrets`,
  `motherduck.com/blog/pg-duckdb-release`, `duckdb.org/2025/11/28/iceberg-writes-in-duckdb`
- Agno/Zep integration: `docs.agno.com/tools/toolkits/database/zep`

**Not verified in this pass (flagged for synthesis/follow-up):**
- The `group_id` conflict between `docker/graphiti/config.yaml` (`"platform"`) and
  `server/analysis/semantica_wiring.py` (`"casebible"`) — not resolved here; needs a live
  check via `graphiti-get-status`/`graphiti-search-nodes` against both group_ids to see which
  actually holds episodes, or whether the deployed config has drifted from what
  `semantica_wiring.py`'s comments assert.
- Custom entity/edge type configuration for our Graphiti deployment — capability documented,
  not implemented; `docker/graphiti/config.yaml` sets no `entity_types`/`edge_types`.
- Milvus partition key — capability documented, not implemented on any of the three forensic
  collections.
