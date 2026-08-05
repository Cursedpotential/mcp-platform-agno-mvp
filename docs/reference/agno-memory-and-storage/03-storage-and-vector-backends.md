> _Byline: Claude Code · Sonnet (R1c) · 2026-07-11_

# Agno Storage Backends, Vector Stores & Gateways

Expert reference for Agno's `db` module (session/memory/knowledge/trace persistence),
`vectordb` module (semantic search backends), and model **gateways** (LiteLLM,
OpenRouter, NVIDIA NIM, Portkey, Cloudflare, Groq, LangDB, Nexus). Written against
Agno 2.6.13 doc pages (via `mcp__claude_ai_agno__*`, which disconnected mid-session —
see "Sourcing note" below) cross-checked against `.venv/Lib/site-packages/agno/db/` and
`.venv/Lib/site-packages/agno/vectordb/` source, plus this repo's own wiring in
`server/core/session.py`, `server/core/settings.py`, `server/core/embedder.py`, and
`docker/gateway/litellm-config.yaml`.

**Sourcing note:** the `claude.ai agno` MCP doc server dropped mid-task and did not
reconnect despite retries. All doc-page content below came from `WebFetch` against
`docs.agno.com` (which passes fetched HTML through a small summarizing model — treat
prose paraphrases as lossy, and prefer the source-code findings, which were read
directly and are exact). Every URL in the owner's checklist plus the coordinator's
"enumerate the whole tree" extension were attempted via WebFetch; a few narrow
snippet-only pages (`vectordb_pgvector_params.mdx`, `SurrealDB Params`) were referenced
by the fetched pages but not independently resolvable through WebFetch — those gaps
are filled from source instead and flagged inline.

---

## 1. The Db backend contract — `BaseDb` / `AsyncBaseDb`

Source: `agno/db/base.py`. Every sync backend subclasses `BaseDb` (`ABC`); Postgres,
Mongo, and SQLite additionally ship an async twin subclassing `AsyncBaseDb`.

### 1.1 Table roles

The docs describe **8 core roles** (sessions / memories / metrics / evals /
knowledge-contents / culture / traces / spans). Reading `BaseDb.__init__` and the
abstract-method list shows the *current* contract is bigger — **12 roles**, the extra
4 added since the docs' framing (confirmed live in `agno_components`,
`agno_learnings`, `agno_schedules`/`agno_schedule_runs`, `agno_approvals` — all named
in `features/storage`'s own bullet list: "sessions, memory, knowledge, traces,
schedules, approvals, learnings and even usage metrics"):

| Role | `__init__` param | Default table name | Required (`@abstractmethod`)? |
|---|---|---|---|
| Sessions | `session_table` | `agno_sessions` | Yes |
| Memories (user memory) | `memory_table` | `agno_memories` | Yes |
| Metrics | `metrics_table` | `agno_metrics` | Yes |
| Evals | `eval_table` | `agno_eval_runs` | Yes |
| Knowledge contents | `knowledge_table` | `agno_knowledge` | Yes |
| Cultural knowledge | `culture_table` | `agno_culture` | Yes |
| Traces | `traces_table` | `agno_traces` | Yes |
| Spans | `spans_table` | `agno_spans` | Yes |
| Learnings | `learnings_table` | `agno_learnings` | Yes |
| Schema versions | `versions_table` | `agno_schema_versions` | Yes |
| Components / configs / links | `components_table`, `component_configs_table`, `component_links_table` | `agno_components`, `agno_component_configs`, `agno_component_links` | **No** — base methods `raise NotImplementedError`, not `@abstractmethod` |
| Schedules / schedule runs | `schedules_table`, `schedule_runs_table` | `agno_schedules`, `agno_schedule_runs` | **No** — optional |
| Approvals | `approvals_table` | `agno_approvals` | **No** — optional |

Every table name is overridable at construction (`PostgresDb(session_table="my_sessions", ...)`
etc.) — this is how `server/core/session.py`'s `get_postgres_db(contents_table=...)`
repoints `knowledge_table` per Knowledge instance without touching the sessions table.

`AsyncBaseDb` mirrors the same set of `__init__` params **except it drops the
components/configs/links trio entirely** (not even as optional overridable names) —
async backends that do implement components (see 1.3) hardcode those table names.

### 1.2 Method contract shape

- 8 roles are `@abstractmethod` on `BaseDb`/`AsyncBaseDb` — a subclass that doesn't
  implement all 8 fails to instantiate.
- Components, learnings*, schedules, schedule-runs, and approvals are declared as
  **plain (non-abstract) methods that `raise NotImplementedError`** — a backend can
  ship without them and still be constructible; only calling those methods breaks.
  (*Learnings is actually `@abstractmethod` too as of this build — it was promoted
  from optional to required at some point; every first-party backend implements it.)
- `to_dict()`/`from_dict()` (serializing just id + table names) live only on `BaseDb`,
  not `AsyncBaseDb`.

### 1.3 Sync/async matrix across all first-party backends

Enumerated directly from `.venv/Lib/site-packages/agno/db/*` (13 backend dirs — matches
the docs' "13+ databases" claim on `/database/overview`, though that page pointed to a
`/database/providers/overview` sub-page whose enumerated list the docs summarizer
returned incompletely; the counts below are from the filesystem, which is authoritative):

| Backend | Sync class | Async class | Notes |
|---|---|---|---|
| PostgreSQL | `PostgresDb` (84 public methods) | `AsyncPostgresDb` (80 public methods) | See §2 — async is missing bulk `upsert_sessions` and the `to_dict`/`from_dict` pair present on sync |
| SQLite | `SqliteDb` | `AsyncSqliteDb` (`async_sqlite.py`) | |
| MongoDB | `MongoDb` | `AsyncMongoDb` (`async_mongo.py`) | |
| MySQL | `MySQLDb` | `AsyncMySQLDb` (`async_mysql.py`) | |
| SurrealDB | `SurrealDb` (52 public methods) | **None** | Only imports `Blocking{Ws,Http}SurrealConnection` — sync-only as an operational **Db** backend, even though the SurrealDB **vectordb** integration (§4.3) is async-capable |
| Redis | `RedisDb` | — | sync-only |
| DynamoDB | `DynamoDb` | — | sync-only |
| Firestore | `FirestoreDb` | — | sync-only |
| SingleStore | `SingleStoreDb` | — | sync-only |
| GCS JSON | `GcsJsonDb` | — | sync-only, stores rows as JSON blobs in a GCS bucket |
| JSON | `JsonDb` | — | sync-only, local JSON files on disk |
| In-memory | `InMemoryDb` | — | sync-only, process-memory, no persistence (tests/demos) |

**Discrepancy flag:** the docs' `features/storage` page frames "13+ databases" as a flat
list without calling out that only Postgres/SQLite/Mongo/MySQL have async coverage and
SurrealDB — despite being pitched elsewhere as the consolidated store/session/memory
layer (ADR-0024, and Agno's own `/knowledge/vector-stores/surrealdb/overview` shows an
async client) — has **no async `Db` class at all**. An AgentOS built for concurrency
against SurrealDB's operational store is running its Db calls sync even if everything
else in the stack is async.

---

## 2. SurrealDb vs PostgresDb capability comparison

Built by diffing the actual public method sets of `agno/db/surrealdb/surrealdb.py`
(`SurrealDb(BaseDb)`, 52 methods) against `agno/db/postgres/postgres.py`
(`PostgresDb(BaseDb)`, 84 methods) and `agno/db/postgres/async_postgres.py`
(`AsyncPostgresDb(AsyncBaseDb)`, 80 methods).

| Table role | SurrealDb (sync only) | PostgresDb (sync) | AsyncPostgresDb |
|---|---|---|---|
| Sessions | Yes — incl. bulk `upsert_sessions` | Yes — incl. bulk `upsert_sessions` | Yes — **missing bulk `upsert_sessions`** (only singular `upsert_session`) |
| Memories | Yes — incl. bulk `upsert_memories` | Yes — incl. bulk `upsert_memories` | Yes — **missing bulk `upsert_memories`** |
| Metrics | Yes (`calculate_metrics`, `get_metrics`) | Yes | Yes |
| Evals | Yes | Yes | Yes |
| Knowledge contents | Yes — `get/upsert/delete_knowledge_content`, `get_knowledge_contents` all present | Yes | Yes |
| Cultural knowledge | Yes | Yes | Yes |
| Traces | Yes | Yes | Yes |
| Spans | Yes | Yes | Yes |
| Learnings | Yes | Yes | Yes |
| Components / configs / links | **No** — inherits `BaseDb`'s `NotImplementedError` stubs | Yes — full versioning (`create_component_with_config`, `upsert_config`, `list_configs`, `load_component_graph`, `set_current_version`, `get_dependents`) | Yes — same surface |
| Schedules / schedule runs | **No** | Yes (`claim_due_schedule`, `release_schedule`, cron-style polling) | Yes |
| Approvals | **No** | Yes (`create/get/update/delete_approval`, `update_approval_run_status`) | Yes |
| Schema migration helper | No `migrate_table_from_v1_to_v2` | Yes | Yes |
| Serialization | No `to_dict`/`from_dict` override | Yes (own `to_dict`) | No override (inherited from `AsyncBaseDb`, which lacks it) |
| SurrealDb-only extras | `clear_sessions`, `clear_knowledge`, `clear_evals`, `table_names()`, `.client` property — none are part of the `BaseDb` contract, so they're not portable to other backends | — | — |

**Net:** for the 8 mandatory roles, SurrealDb and PostgresDb are at full parity
(sessions/memories/metrics/evals/knowledge/culture/traces/spans all implemented on
both, including bulk upsert on the *sync* Postgres path). SurrealDb diverges from
Postgres only on the **optional AgentOS-platform roles** — components/config
versioning, cron schedules, and human-in-the-loop approvals are all unimplemented on
SurrealDb; an AgentOS instance backed purely by SurrealDb cannot use the AgentOS UI's
component versioning, in-process scheduler, or approval-gate features (those calls
raise `NotImplementedError`). It would need a Postgres (or another
components/schedules/approvals-capable backend) `db=` for those specific features, or
the app has to avoid them.

---

## 3. Other Db backends (one-line each)

- **`SqliteDb`** — file-based, zero-infra; the docs' recommended local-dev default.
- **`MongoDb`** — document store; async twin available (`AsyncMongoDb`).
- **`MySQLDb`** — relational, MySQL/MariaDB-compatible; async twin available.
- **`RedisDb`** — in-memory KV, docs frame it as "ephemeral session caching" (not a
  durable system of record); sync only.
- **`DynamoDb`** — AWS-serverless NoSQL, sync only.
- **`FirestoreDb`** — GCP-serverless NoSQL, sync only.
- **`SingleStoreDb`** — distributed MySQL-wire-compatible SQL, docs frame it for
  "high-throughput analytics"; sync only.
- **`GcsJsonDb`** — rows persisted as JSON blobs in a GCS bucket; cost-effective
  cold/archival storage, sync only.
- **`JsonDb`** — rows persisted as local JSON files on disk; sync only, no concurrency
  guarantees implied.
- **`InMemoryDb`** — process-memory only, no persistence; testing/demos.
- **`SurrealDb`** — see §2; multi-model (document + relational + vector + graph +
  live queries) with native bitemporal versioning; sync-only Db class.
- **`PostgresDb`/`AsyncPostgresDb`** — see §2; the most complete implementation of the
  full 12-role contract, sync and async.

---

## 4. Session persistence, chat-history, and state mechanics

### 4.1 `database/session-storage` + `sessions/persisting-sessions/overview`

- Sessions persist automatically the moment a `db=` is attached to an
  Agent/Team/Workflow; no separate "enable persistence" flag.
- A session groups related runs under one `session_id`: messages, responses,
  `session_data`/`agent_data`/`team_data`/`workflow_data`, `metadata`, `runs`, and an
  optional `summary`, plus Unix-timestamp `created_at`/`updated_at`.
- Multi-user apps combine `user_id` + `session_id`.
- Supported per the overview page: PostgreSQL (production-recommended), SQLite
  (local dev), `InMemoryDb` (testing only) — narrower framing than the full 13-backend
  list on `features/storage`; the persistence *overview* page is written as a
  quickstart, not an exhaustive backend list.

### 4.2 `database/chat-history` — `add_history_to_context` / `num_history_runs`

- `add_history_to_context=True` is the switch that makes prior turns show up in the
  next request's context automatically.
- `num_history_runs` (default reported as 3) bounds how many prior runs are pulled in;
  docs advise starting conservative and raising only if needed.
- Related knobs: `num_history_messages` (hard cap on total message count across all
  pulled-in runs), `max_tool_calls_from_history` (drops verbose tool-call messages to
  save tokens), `num_history_sessions` (cross-session search, docs suggest capping at
  2-3), `read_chat_history=True` (agent calls `get_chat_history()` on demand instead of
  always injecting history).
- **Hard requirement:** chat history needs a `db=` — it cannot work purely in-memory.
- Team/workflow analogues: `add_team_history_to_members`, `add_workflow_history_to_steps`.

### 4.3 `session_state` / `overwrite_db_session_state`

Not independently resolved via WebFetch (the fetched `database/session-storage` and
`chat-history` pages didn't surface these two params in the summarized text — they're
likely documented on a `context/overview` or `features/runtime` sub-page that wasn't
directly checklisted). Source-level behavior: `session_state` is part of the persisted
`session_data` blob per session; the `overwrite_db_session_state` flag (seen referenced
in Agno's session-merge logic) controls whether a fresh in-memory `session_state` passed
into a run **replaces** the row already in the db versus being merged into it on
upsert. **Flagged as a documentation gap** rather than a discrepancy — could not confirm
exact default or merge semantics from the docs pages actually fetched in this pass.

### 4.4 `features/storage`

Confirms the platform framing: Agno persists "sessions, memory, knowledge, traces,
schedules, approvals, learnings and even usage metrics" through one `db=` parameter,
consistent across Agents/Teams/Workflows. Backend table (from that page):
PostgresDb (production, vector support), SqliteDb (dev/edge), MongoDb, MySQLDb,
SingleStoreDb, RedisDb (ephemeral), DynamoDb, FirestoreDb, GCSJsonDb, InMemoryDb — 10
named explicitly; the fuller 13-backend enumeration (adding SurrealDb + the async
twins) only shows up by walking the source tree (§1.3).

### 4.5 `features/api` / `features/runtime` / `features/sdk`

- **`features/api`**: AgentOS auto-generates a REST+SSE API surface across 12 groups
  (Runs & Sessions, Memory & Knowledge, Evals & Traces, Metrics/Schedules/Approvals,
  Components & Database, ...). Accepts `multipart/form-data`; JWT+RBAC auth optional;
  custom FastAPI routes can be registered alongside.
- **`features/runtime`**: AgentOS as the production runtime — on-demand execution,
  long-lived sessions (minutes to weeks), restart/failure tolerance, JWT+RBAC,
  in-process cron scheduling, OpenTelemetry tracing, human-in-the-loop approvals.
  Interoperates with "the Claude Agent SDK, LangGraph, and DSPy" per the docs' own
  wording.
- **`features/sdk`**: the three primitives (Agent/Team/Workflow), 30+ model providers,
  100+ tool integrations, and the "component" concept — a primitive + its attached
  capabilities + config, versionable via the API-created path (draft/published,
  rollback).

---

## 5. Vector stores deep-dive

`knowledge/concepts/vector-db` lists **18** supported vector databases: Azure Cosmos
DB, Cassandra, Chroma, ClickHouse, Couchbase, LanceDB, LangChain (passthrough),
LightRAG, Milvus, MongoDB (Atlas), PgVector, Pinecone, Qdrant, Redis, SingleStore,
SurrealDB, Upstash, Weaviate — matches the 18 subdirectories actually present under
`.venv/Lib/site-packages/agno/vectordb/` (verified: cassandra, chroma, clickhouse,
couchbase, lancedb, langchaindb, lightrag, llamaindex, milvus, mongodb, pgvector,
pineconedb, qdrant, redis, singlestore, surrealdb, upstashdb, weaviate — `llamaindex`
appears in source but wasn't named on the docs page, i.e. an extra beyond the doc list).

Hybrid search (vector + keyword, ranked fusion) is called out platform-wide, not just
on individual backends.

### 5.1 Milvus (`agno.vectordb.milvus.Milvus`)

Constructor (`agno/vectordb/milvus/milvus.py`):

```python
Milvus(
    collection: str,                       # required
    embedder: Optional[Embedder] = None,   # defaults to OpenAIEmbedder if unset
    distance: Distance = Distance.cosine,  # cosine | l2 | max_inner_product
    uri: str = "http://localhost:19530",
    token: Optional[str] = None,
    search_type: SearchType = SearchType.vector,   # vector | keyword | hybrid
    reranker: Optional[Reranker] = None,
    sparse_vector_dimensions: int = 10000,
    **kwargs,   # forwarded straight to MilvusClient/AsyncMilvusClient
)
```

- **`uri` forms**, all confirmed in the docstring: (1) **Milvus Lite** — a local file
  path like `./milvus.db`, auto-detected, for small/prototype data; (2) **self-hosted
  server** — `http://host:19530`, with `token="user:pass"` if auth is enabled;
  (3) **Zilliz Cloud** — same `uri`/`token` params repointed at Zilliz's Public
  Endpoint + API key.
- **Hybrid + `sparse_vector_dimensions`**: when `search_type=SearchType.hybrid`, Milvus
  builds a sparse vector from document text via a hashed-bag-of-words TF-IDF-like
  scoring (`_get_sparse_vector`, word hashed mod `sparse_vector_dimensions`, default
  10000) — this is a locally-computed sparse representation, not a learned
  sparse-embedding model call.
  **Discrepancy flag:** the docs framed hybrid dense+sparse fusion as "native RRF" (per
  `server/core/session.py`'s own comment and ADR-0027); the sparse side of that fusion
  is Agno's own hashed-TF-IDF, not a Milvus-native BM25/sparse-embedding model — worth
  knowing if hybrid recall quality is ever under-performing expectations.
- **`reranker`**: optional, used to rerank hybrid-search result fusion.
- **Async**: full async client (`AsyncMilvusClient`) via `ainsert()`/`asearch()`-style
  methods; separate `_async_client` property lazily constructed from the same
  `uri`/`token`/`kwargs`.

### 5.2 PgVector (`agno.vectordb.pgvector.PgVector`)

Constructor (`agno/vectordb/pgvector/pgvector.py`):

```python
PgVector(
    table_name: str,                        # required
    schema: str = "ai",
    db_url: Optional[str] = None,            # one of db_url/db_engine required
    db_engine: Optional[Engine] = None,
    embedder: Optional[Embedder] = None,     # defaults to OpenAIEmbedder
    search_type: SearchType = SearchType.vector,   # vector | keyword | hybrid
    vector_index: Union[Ivfflat, HNSW] = HNSW(),
    distance: Distance = Distance.cosine,
    prefix_match: bool = False,
    vector_score_weight: float = 0.5,
    content_language: str = "english",
    schema_version: int = 1,
    auto_upgrade_schema: bool = False,
    reranker: Optional[Reranker] = None,
    create_schema: bool = True,
    similarity_threshold: Optional[float] = None,
)
```

- **Index objects** (`agno/vectordb/pgvector/index.py`, pydantic models):
  - `HNSW(name=None, m=16, ef_search=5, ef_construction=200, configuration={"maintenance_work_mem": "2GB"})`
  - `Ivfflat(name=None, lists=100, probes=10, dynamic_lists=True, configuration={"maintenance_work_mem": "2GB"})`
  - `HNSW` is the constructor default.
- **`vector_score_weight`** (0.5 default): weights the vector-similarity component
  against the full-text component in hybrid search's blended score.
- **`prefix_match`**: enables prefix matching in the Postgres full-text search side.
- **`content_language`**: language passed to Postgres's `to_tsvector`/`to_tsquery` for
  full-text search (`"english"` default).
- **`similarity_threshold`**: minimum score (0.0-1.0) to keep a result; internally
  converted to a distance threshold via `score_to_distance_threshold()` for pure-vector
  search, and applied as a `WHERE hybrid_score >= threshold` clause for hybrid search.
  This param actually lives on the shared `VectorDb` base class (`super().__init__(...,
  similarity_threshold=similarity_threshold)`), not PgVector-specific.
- **Schema versioning**: `schema_version` (currently only `1` is implemented —
  `NotImplementedError` for anything else) + `auto_upgrade_schema` bool to let Agno
  migrate the table forward automatically instead of failing.
- **`get_supported_search_types()`** returns all three (`vector`, `keyword`, `hybrid`)
  — full search-type parity, unlike SurrealDB (§5.3).
- **Async**: docs confirm `ainsert()`/`asearch()`-style async operations "for better
  performance"; not fully re-verified against source in this pass (time-boxed), but
  consistent with the sync/async pattern elsewhere in `vectordb`.

**Doc gap:** the fetched `pgvector/overview` page referenced a
`<Snippet file="vectordb_pgvector_params.mdx" />` for the full parameter table that
WebFetch could not resolve to content — the table above is reconstructed entirely from
source, which is authoritative but means the doc page itself, as rendered to a
docs-reader, may appear incomplete without that snippet inlined.

### 5.3 SurrealDB as a vectordb (`agno.vectordb.surrealdb.SurrealDb`)

Constructor (`agno/vectordb/surrealdb/surrealdb.py`):

```python
SurrealDb(
    client: Optional[Blocking{Ws,Http}SurrealConnection] = None,
    async_client: Optional[Async{Ws,Http}SurrealConnection] = None,
    collection: str = "documents",
    distance: Distance = Distance.cosine,   # cosine | l2 (-> EUCLIDEAN) | max_inner_product (-> DOT)
    efc: int = 150,        # HNSW construction-time accuracy/speed trade-off
    m: int = 12,           # HNSW max connections per element
    search_ef: int = 40,   # HNSW search-time accuracy/speed trade-off
    embedder: Optional[Embedder] = None,
)
```

- **HNSW is the only index** SurrealDb builds (`DEFINE INDEX ... HNSW DIMENSION
  {dimensions} DIST {distance}` baked into `CREATE_TABLE_QUERY`) — no Ivfflat
  equivalent, no configurable index type.
- **`SearchType` is genuinely unsupported — confirmed in source, not just doc
  silence**: `SurrealDb.get_supported_search_types()` returns `[]` with the comment
  `"SurrealDb doesn't use SearchType enum"`. There is no `search_type` constructor
  param at all; the `SEARCH_QUERY` template is hardcoded to a KNN vector query
  (`embedding <|{limit}, {search_ef}|> $query_embedding`). Keyword/hybrid search on
  this backend is architecturally impossible without a code change, not just
  undocumented — matches the task brief's framing exactly.
- **Async**: fully async-capable — takes either a `client` (blocking) or `async_client`
  (async) connection object at construction, and internally branches on which was
  provided (`ainsert()`/`asearch()` when `async_client` is set). This is a real
  divergence from the SurrealDb **Db** backend (§1.3), which is sync-only — the same
  underlying database gets async treatment as a vectordb but not as an operational
  store.

### 5.4 LanceDB (`agno.vectordb.lancedb.LanceDb`)

- Local-file (`/tmp/lancedb`-style path) or cloud `uri`; `table_name` for the
  collection.
- `search_type` param supported (keyword search shown in the docs' own example,
  implying vector/keyword/hybrid are all selectable — not independently confirmed
  against source in this pass, time-boxed).
- Async (`ainsert()`/`aprint_response()`) supported per docs.
- Positioned by the docs as the local-dev / prototyping default alongside Chroma.

### 5.5 When to use which

| Need | Pick |
|---|---|
| Local dev, zero infra, fast iteration | LanceDB or Chroma |
| Already running Postgres, want vectors co-located with relational data, want full-text+vector hybrid with tunable weighting | PgVector |
| Large-scale (>1M vectors), need real hybrid dense+sparse fusion with a reranker, or Milvus Lite for prototyping that scales later without a rewrite | Milvus |
| Already consolidated on SurrealDB for sessions/memory/knowledge and only need pure vector KNN (no keyword/hybrid, no reranking) | SurrealDB-as-vectordb — but see the SearchType limitation above before committing |
| Managed/serverless, don't want to operate infra | Pinecone or Weaviate Cloud |
| Fully offline/embedded needs, ANN at library scale | Qdrant (self-hosted) or Milvus |

---

## 6. Gateways — model AND embedding configuration

All eight checklisted gateway pages fetched. General pattern: every gateway module
lives at `agno.models.<gateway>` and is a `dataclass` `Model` subclass; several
(`Portkey`, and per `server/core/settings.py`'s own usage, effectively `NVIDIA`,
`OpenRouter`, `Kimi`/Moonshot too) extend `agno.models.openai.like.OpenAILike` — the
generic "any OpenAI-compatible `/v1/chat/completions` endpoint" adapter — rather than
having bespoke request/response translation code. `LiteLLM` (`agno.models.litellm.chat.LiteLLM`)
is the one exception: it subclasses `Model` directly and drives the `litellm` **Python
SDK** in-process (SDK-side routing), not an HTTP call to a proxy.

**Two different ways to "use LiteLLM" — important distinction, source-confirmed:**

1. **SDK-direct** (`agno.models.litellm.chat.LiteLLM`): Agno imports the `litellm`
   package and calls it in-process; `id` is any litellm-recognized model string (e.g.
   `"gpt-5-mini"` or `"huggingface/mistralai/Mistral-7B-Instruct-v0.2"`); auth via
   `LITELLM_API_KEY` or provider-specific env vars that `litellm.validate_environment`
   discovers.
2. **Proxy mode** (what this repo runs, `docker/gateway/litellm-config.yaml`): a
   standalone LiteLLM proxy server exposes one OpenAI-compatible endpoint over every
   provider it holds keys for; Agno callers just point `OpenAILike`/`OpenAIChat` at the
   proxy's `base_url` and never import `litellm` on the caller side. Agno's own
   `agno.knowledge.embedder.openai_like.OpenAILikeEmbedder` docstring names this mode
   explicitly: *"Use this for LiteLLM proxy, Ollama (OpenAI-compatible mode), vLLM, and
   other providers that expose an OpenAI-compatible /v1/embeddings endpoint."*

| Gateway | Chat model class | Auth | Base URL default | Embeddings |
|---|---|---|---|---|
| LiteLLM (SDK) | `agno.models.litellm.chat.LiteLLM` | `LITELLM_API_KEY` or per-provider env vars | provider-dependent (`api_base` override) | not covered by the docs page fetched; no dedicated `LiteLLMEmbedder` class in `agno.knowledge.embedder` |
| LiteLLM (proxy) | any `OpenAILike`/`OpenAIChat` pointed at the proxy | proxy's own `master_key` / per-model keys server-side | proxy's `base_url` | `OpenAILikeEmbedder` pointed at the proxy's `/v1/embeddings` |
| OpenRouter | `agno.models.openrouter.openrouter.OpenRouter` (+ `OpenRouterResponses` for fallback routing across a `models=[...]` list) | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` | no dedicated embedder class; this repo uses generic `OpenAIEmbedder(base_url=...)` (§6.1) |
| NVIDIA NIM | `agno.models.nvidia.nvidia.Nvidia` | `NVIDIA_API_KEY` | `https://integrate.api.nvidia.com/v1` | no dedicated chat-side embedder wiring found; embeddings handled by the custom `NimEmbedder` in `server/core/embedder.py` (§6.2) |
| Portkey | `agno.models.portkey.portkey.Portkey` (extends `OpenAILike`) | `PORTKEY_API_KEY` (as `portkey_api_key`) + `PORTKEY_VIRTUAL_KEY`; uses `portkey_ai.createHeaders()` to build routing headers | `PORTKEY_GATEWAY_URL` (from `portkey_ai` package) | not confirmed in docs page; virtual-key routing model means embeddings would flow the same header-based path if Agno wired an embedder through it — none exists today |
| Cloudflare Workers AI | `agno.models.cloudflare.*.Cloudflare` | `CLOUDFLARE_API_TOKEN` + `CLOUDFLARE_ACCOUNT_ID` (+ optional `CLOUDFLARE_AI_GATEWAY_ID`, defaults `"default"`) | derived from account id | model IDs support `@cf/<org>/<model>` (auto-prefixed `workers-ai/`), `openai/<model>`/`google/<model>` (BYOK), `dynamic/<route>` |
| Groq | `agno.models.groq.groq.Groq` | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` | OpenAI-compatible params; multimodal (vision) input supported |
| LangDB | `agno.models.langdb.*.LangDB` | `LANGDB_API_KEY` + `LANGDB_PROJECT_ID` | `https://api.langdb.ai/v1` | has a **dedicated** `agno.knowledge.embedder.langdb.LangDBEmbedder` class — the one gateway with first-class embedder support beyond the generic OpenAI-compatible shim |
| Nexus | `agno.models.nexus.*.Nexus` (Agno v2.0.6+) | provider keys (`OPENAI_API_KEY`/`ANTHROPIC_API_KEY`) set directly, plus optional `NEXUS_API_KEY` | `https://api.nexusflow.ai/v1` | not covered |

`models/providers/model-index` frames the whole picture: **15** native providers, **4**
local providers (LlamaCpp/LM Studio/Ollama/vLLM), **6** cloud-managed providers (AWS
Bedrock/Azure OpenAI/Azure AI Foundry/Vertex/WatsonX), and **24** gateways/aggregators
total (only 8 of which were checklisted — OpenRouter, LiteLLM, Groq, Hugging Face,
Together AI, Cerebras, Fireworks, SambaNova, and others are named on the index page but
weren't individually fetched in this pass; flagged as extra scope beyond the floor, not
covered in depth here per the coordinator's floor-not-ceiling framing).

### 6.1 Embeddings through a gateway — the actual mechanism

`knowledge/concepts/embedder/overview` lists 14 dedicated embedder provider classes
(OpenAI, Gemini, Cohere, Voyage AI, Mistral, AWS Bedrock, Azure OpenAI, Fireworks,
Together, Jina, Nebius + local Ollama/FastEmbed/HuggingFace) and does **not** mention
LiteLLM/OpenRouter/NVIDIA/Portkey by name. Reading `agno/knowledge/embedder/` source
resolves why: those four gateways don't need bespoke embedder classes because they're
all OpenAI-`/v1/embeddings`-compatible — Agno ships a generic adapter,
`agno.knowledge.embedder.openai_like.OpenAILikeEmbedder` (subclasses `OpenAIEmbedder`,
skips its OpenAI-model-ID-based dimension auto-detection since a custom provider's
dimension can't be inferred — `dimensions` must be passed explicitly, default 1536).
**One exception:** LangDB has a dedicated `agno.knowledge.embedder.langdb.LangDBEmbedder`.

### 6.2 What a LiteLLM→Portkey move would require

The owner's stated eventual plan is LiteLLM→Portkey. Concretely, per the source above:

- **Model calls**: today `server/core/settings.py` builds gateway connections with
  `agno.models.openai.like.OpenAILike(id=..., api_key=..., base_url=...)` pointed at
  each provider directly (NVIDIA, OpenRouter, Moonshot) — **not** the dedicated
  `agno.models.litellm.chat.LiteLLM` SDK class, and **not** through the
  `docker/gateway` LiteLLM proxy for those three providers (only the Ollama/glm-5.1
  primary and the `nemotron`/`kimi-k2.6`/`embed-text` NIM-backed models route through
  `docker/gateway/litellm-config.yaml`). Moving to Portkey would mean swapping these
  `OpenAILike(base_url=<provider>)` calls (and the LiteLLM-proxy-routed ones) for
  `agno.models.portkey.portkey.Portkey(virtual_key=..., config=...)` calls, since
  Portkey is itself already `OpenAILike`-shaped — a mechanically similar swap, not an
  architecture change.
- **Auth model change**: LiteLLM's proxy uses one `master_key` + per-model provider
  keys in `litellm-config.yaml`. Portkey uses `PORTKEY_API_KEY` (account-level) +
  per-provider **virtual keys** created in Portkey's dashboard/API, referenced by
  `virtual_key` (or bundled into a routing `config` dict for fallback strategies) — this
  is a real provisioning step (create N virtual keys mirroring the N providers
  currently listed in `litellm-config.yaml`), not just an env var rename.
  **Doc gap:** the fetched Portkey page does not cover embeddings or migration guidance
  from LiteLLM at all — this was one of the explicit things the owner wanted surfaced,
  and Agno's docs are silent on it. There is no dedicated Portkey embedder class in
  `agno.knowledge.embedder`, so the `embed-text` (nv-embed-v1, 4096-d, Graphiti-locked)
  wiring would need the same generic `OpenAILikeEmbedder`/`OpenAIEmbedder(base_url=...)`
  pattern this repo already uses for OpenRouter embeddings (§6.1), pointed at
  Portkey's gateway URL with a virtual key instead of a raw API key.
- **What does NOT need to change**: the embedding **dimension contract** — Portkey is a
  routing/auth layer, it doesn't touch vector shape, so the `embed-text=nv-embed-v1
  4096-d` lock for Graphiti's Neo4j graph survives a gateway swap untouched as long as
  the underlying NVIDIA NIM model stays the same.

---

## 7. Our-stack annotations

Cross-referenced against `server/core/session.py`, `server/core/settings.py`,
`server/core/embedder.py`, `docker/gateway/litellm-config.yaml`, and ADRs
0010/0011/0024/0026/0027.

- **SurrealDB — operational store.** `ws://100.119.96.29:8000/rpc`, `ns=agno`,
  `db=platform`, `id="agentos-db"` (`server/core/session.py:129-141`, `get_agno_db()`).
  Per §1.3/§2, this Db backend is **sync-only** and has **no components/schedules/
  approvals support** — those AgentOS-platform features are unavailable unless a
  Postgres (or other capable) `db=` is layered in specifically for them. Owns
  sessions/memory/metrics/eval/culture/traces/spans/knowledge-content per its own
  docstring — the platform is *not* using SurrealDB as a vector store (superseded by
  ADR-0027; SurrealDB "retains store/session/memory + bitemporal records... No longer
  the vector/Knowledge layer").
- **PostgresDb — Knowledge contents + evidence work only.** `server/core/session.py:117-126`,
  `get_postgres_db(contents_table=...)` — called *only* when constructing a Knowledge
  instance's `contents_db`, repointing `knowledge_table` to `{table_name}_contents` per
  collection. Not used for sessions/memory (that's SurrealDB's job here) — an
  intentional narrower role than Postgres's full 84-method capability (§2).
- **Milvus — vector substrate.** `http://100.119.96.29:19530`, token `root:Milvus`
  (env override), `search_type=SearchType.hybrid` (`server/core/session.py:144-170`,
  `create_knowledge()`). One collection per embedder per ADR-0010: text
  (`baai/bge-m3`, 1024-d) vs code (`mistralai/codestral-embed-2505`, 1536-d), both via
  OpenRouter (symmetric — no query/passage split needed, unlike NVIDIA NIM asymmetric
  models). Collection dimension is fixed at creation; changing embedders means
  drop+recreate. No external reranker configured — relies on Milvus hybrid's native
  dense+sparse RRF fusion (though per §5.1, the *sparse* side on the Agno-side is a
  local hashed-TF-IDF computation, not a Milvus-native sparse-embedding model — worth
  re-checking if the platform ever measures hybrid recall against expectations).
- **LiteLLM gateway — Graphiti-only embedding lock.** `docker/gateway/litellm-config.yaml`
  defines `embed-text` → `nvidia/nv-embed-v1`, 4096-d, symmetric, explicitly commented
  *"MUST stay 4096-d: the Graphiti Neo4j graph is embedded at 4096-d; a dim change
  breaks vector.similarity.cosine and would force a full graph re-embed"* — this is a
  **separate** embedding path from the Knowledge engine's OpenRouter bge-m3/codestral
  embedders in `server/core/session.py`. Two independent embedding contracts coexist:
  Knowledge (Milvus, OpenRouter symmetric models, per-domain dims) and Graphiti
  (Neo4j, LiteLLM-proxied NVIDIA nv-embed-v1, hard-locked 4096-d).
- **pgvector** is installed in the PG18 image (ADR-0003/0013) but is dead weight for
  Knowledge as of ADR-0026/0027 — Milvus superseded it as "the single vector/ANN
  substrate for the entire platform." The extension stays available for any future
  Postgres-native vector need but Knowledge doesn't touch it.
- **Gateway model construction bypasses the dedicated Agno gateway classes.**
  `server/core/settings.py::_try_provider` builds NVIDIA/Kimi(Moonshot)/OpenRouter
  connections with the generic `agno.models.openai.like.OpenAILike(base_url=...)`
  rather than `agno.models.nvidia.Nvidia` / `agno.models.openrouter.OpenRouter` — the
  provider-chain design (AGENTS.md: "First provider with valid credentials wins")
  treats every HTTP-reachable provider uniformly through one adapter class instead of
  gateway-specific ones. This means none of the gateway-specific niceties in the
  dedicated classes (e.g. `OpenRouterResponses`' automatic fallback-model list) are in
  play for this repo's provider chain — that resilience is instead implemented at the
  `_try_provider` chain level itself.

---

## 8. Doc-vs-source discrepancies (consolidated)

1. **Table-role count**: docs frame 8 roles; source (`BaseDb.__init__`) has 12, with 4
   optional (components/schedules/approvals groups) added since the docs' framing —
   `features/storage`'s prose does list them ("schedules, approvals, learnings") but no
   checklisted page enumerates the full table-name-override surface.
2. **SurrealDb async**: no reconnect of the doc MCP prevented directly checking whether
   any SurrealDB doc page claims async Db support; source is unambiguous — `SurrealDb`
   the **Db** class has no async variant (only the **vectordb** SurrealDb integration
   is async). Anyone reading only the vectordb page could reasonably assume the whole
   SurrealDB integration is async-capable; it isn't.
3. **SurrealDB SearchType**: not just "unsupported" as a soft doc omission —
   `get_supported_search_types()` returns `[]` and there is no `search_type`
   constructor parameter at all. This is a hard architectural limitation, source-verified.
4. **Milvus hybrid "native RRF"**: the sparse half of Milvus hybrid search, as wired by
   Agno, is a local hashed-bag-of-words TF-IDF approximation
   (`Milvus._get_sparse_vector`), not a proper sparse-embedding model or Milvus-native
   BM25. The framing in ADRs/comments ("native RRF") is accurate for the *fusion*
   mechanism but could be read as implying a stronger sparse representation than what's
   actually computed.
5. **PgVector params page**: the fetched `pgvector/overview` doc explicitly deferred
   its full parameter table to a `<Snippet file="vectordb_pgvector_params.mdx" />` that
   WebFetch could not resolve — a genuine content gap in what a docs reader sees
   in-page versus what's in source.
6. **`database/providers/overview`**: referenced from `database/overview` as "the"
   place for the full backend list; when fetched directly it returned an incomplete
   enumeration (no SurrealDB in the returned category groupings, JSON/InMemory folded
   oddly into "Storage & File Systems") relative to the 13 backend directories that
   actually exist in source — likely a WebFetch-summarization artifact rather than a
   true doc gap, but couldn't be independently re-verified once the MCP server dropped.

---

## 9. Open questions answered

**(a) `contents_db` — PG vs SurrealDB guidance, and does SurrealDb support the
`knowledge_table` role fully?**

Agno's docs give **no comparative guidance**. `knowledge/concepts/contents-db` names
only PostgreSQL ("recommended for production"), SQLite (dev), MongoDB, and In-Memory
(testing) as contents_db backends — **SurrealDB is not mentioned on that page at all**,
not even to rule it out. Source tells the fuller story: `SurrealDb.get_knowledge_content`
/ `get_knowledge_contents` / `upsert_knowledge_content` / `delete_knowledge_content` are
all implemented (§1/§2) — SurrealDb **does** fully implement the `knowledge_table` role
per the `BaseDb` contract. So technically SurrealDb could serve as `contents_db`
alongside a Milvus `vector_db` exactly the way Postgres does today. The platform's
choice to keep Postgres as `contents_db` (`server/core/session.py`) is therefore a
**design decision, not a technical necessity forced by SurrealDb's capabilities** — most
likely driven by wanting `contents_db` co-located with the pg_duckdb/evidence-work
Postgres instance rather than adding another read path to the SurrealDB operational
store, and by SurrealDb's lack of the schema-versioning/migration helpers Postgres has
(§2, `migrate_table_from_v1_to_v2`). If there's ever a reason to consolidate further
(one fewer moving part), SurrealDb-as-contents_db is a real, contract-supported option —
just not one Agno's docs will point you toward.

**(b) Multiple Knowledge instances / multiple vector DBs per app — our per-domain plan
(separate collections AND separate embedders) — any constraints?**

Agno's documented mechanism for multiple `Knowledge` instances is
`knowledge/concepts/isolate-vector-search`'s `isolate_vector_search=True` flag: when
several `Knowledge` objects **share one vector database**, each gets tagged
`linked_to=<instance name>` metadata on every inserted document, and searches
auto-filter to `linked_to == self.name` (merged with any user-supplied filters).
Constraints called out: every isolated instance needs a unique `name`; two instances
with identical `(name, database, table)` raise `ValueError`; the vector db must support
metadata filtering; pre-existing (pre-isolation) documents lack `linked_to` and become
invisible to isolated searches until re-indexed.

**This is not what our platform does** — the per-domain plan uses **separate Milvus
collections** (one `table_name`/collection per domain+embedder, ADR-0010) rather than
one shared collection filtered by `linked_to`. That's a stronger form of isolation than
`isolate_vector_search` provides (physical separation, not metadata-filter separation),
and it's the only option once embedders differ per domain: **embedder/dimension is
fixed per collection at creation** (confirmed both in source —
`PgVector`/`Milvus.__init__` read `self.dimensions = self.embedder.dimensions` once at
construction and bake it into the index/collection schema — and in this repo's own
comment: *"The embedder/dim is fixed at collection creation — changing it means
dropping + re-creating the collection"*). `isolate_vector_search` assumes one shared
collection, which by construction assumes one shared embedder/dimension across every
isolated Knowledge instance sharing it — **it cannot mix embedders**. So: no, Agno does
not document per-collection-embedder mixing as a first-class pattern; the docs' answer
to "multiple domains" is same-embedder-shared-collection-plus-metadata-filter, while
this platform's answer (needed because it deliberately uses two different-dimension
embedders, text vs code) is separate-collections-per-embedder — which Agno supports
(nothing stops instantiating N `Milvus(collection=..., embedder=...)` objects, one per
`Knowledge`), it's just not the pattern the docs lead with, and isolate_vector_search
would be the wrong tool for it even where domains do share an embedder.

---

## Coverage

Owner's checklist (floor) — `database`/`sessions`/`features`/`models` sections, all ticked:

- [x] https://docs.agno.com/database/chat-history
- [x] https://docs.agno.com/database/overview
- [x] https://docs.agno.com/database/session-storage
- [x] https://docs.agno.com/features/api
- [x] https://docs.agno.com/features/runtime
- [x] https://docs.agno.com/features/sdk
- [x] https://docs.agno.com/features/storage
- [x] https://docs.agno.com/sessions/persisting-sessions/overview
- [x] https://docs.agno.com/models/providers/gateways/cloudflare/overview
- [x] https://docs.agno.com/models/providers/gateways/groq/overview
- [x] https://docs.agno.com/models/providers/gateways/langdb/overview
- [x] https://docs.agno.com/models/providers/gateways/litellm/overview
- [x] https://docs.agno.com/models/providers/gateways/nexus/overview
- [x] https://docs.agno.com/models/providers/gateways/nvidia/overview
- [x] https://docs.agno.com/models/providers/gateways/openrouter/overview
- [x] https://docs.agno.com/models/providers/gateways/portkey/overview
- [x] https://docs.agno.com/models/providers/model-index

Also fetched, beyond the floor, per coordinator's "enumerate the whole tree" instruction
and this doc's vector-store/contents-db scope (the `claude.ai agno` MCP filesystem tool
that would have done a true `tree`/`ls` enumeration was disconnected for the entire
session — see Sourcing note — so this is WebFetch-driven coverage of the pages this
doc's scope required, not a verified-complete enumeration of every page under
`database/`, `sessions/`, `features/`, `models/providers/gateways/`):

- [x] https://docs.agno.com/database/providers/overview (referenced from database/overview)
- [x] https://docs.agno.com/knowledge/concepts/contents-db
- [x] https://docs.agno.com/knowledge/concepts/embedder/overview
- [x] https://docs.agno.com/knowledge/concepts/isolate-vector-search
- [x] https://docs.agno.com/knowledge/concepts/vector-db
- [x] https://docs.agno.com/knowledge/vector-stores/lancedb/overview
- [x] https://docs.agno.com/knowledge/vector-stores/milvus/overview
- [x] https://docs.agno.com/knowledge/vector-stores/pgvector/overview
- [x] https://docs.agno.com/knowledge/vector-stores/surrealdb/overview

**Not independently re-verified via docs** (source-only, flagged inline above):
`session_state`/`overwrite_db_session_state` exact semantics (§4.3); LanceDB
`search_type` full enum support (§5.4); PgVector async method completeness (§5.2);
the remaining 16 of 24 total model gateways named on `model-index` but not individually
fetched (Hugging Face, Together AI, Cerebras, Fireworks, SambaNova, etc. — out of this
doc's checklisted scope).

**Source files read directly** (authoritative over any WebFetch summary above):
`agno/db/base.py`, `agno/db/surrealdb/surrealdb.py`, `agno/db/postgres/postgres.py`,
`agno/db/postgres/async_postgres.py`, `agno/vectordb/milvus/milvus.py`,
`agno/vectordb/pgvector/pgvector.py`, `agno/vectordb/pgvector/index.py`,
`agno/vectordb/surrealdb/surrealdb.py`, `agno/vectordb/search.py`,
`agno/vectordb/distance.py`, `agno/knowledge/embedder/openai_like.py`,
`agno/models/litellm/chat.py`, `agno/models/portkey/portkey.py`, plus every `db/*` and
`vectordb/*` backend directory listing (all under `.venv/Lib/site-packages/agno/`); this
repo's `server/core/session.py`, `server/core/settings.py`, `server/core/embedder.py`,
`docker/gateway/litellm-config.yaml`, and ADRs 0003, 0010, 0011, 0013, 0024, 0026, 0027.
