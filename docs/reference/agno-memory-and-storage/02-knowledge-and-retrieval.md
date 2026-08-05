> _Byline: Claude Code · Sonnet (R1b) · 2026-07-11_

# Agno Knowledge & Retrieval — Expert Reference

Covers Agno's `Knowledge` subsystem as of `agno==2.6.13`: content ingestion,
readers, embedders, rerankers, vector DBs, contents DB, filters (static +
agentic), search types (vector/keyword/hybrid), agentic vs traditional RAG,
custom retrievers, and isolate-vector-search. Chunking is covered elsewhere —
see `docs/planning/agno-chunking-strategy.md` (pointer only, not restated here).

**Verification method**: the `claude.ai agno` docs MCP server (the assigned
primary source) was unreachable for the entire session — every `search_agno`
and `query_docs_filesystem_agno` call returned "MCP server not connected"
across many retries (confirmed dead for all sibling researchers too, per
coordinator). Fallback per coordinator instruction: (1) `curl
https://docs.agno.com/sitemap.xml` to enumerate the real page tree — this
revealed the `knowledge/` doc tree is **far larger than the 32-URL
checklist floor**: 19 vector-store backends (not 6), 14 embedder pages, 19
reader pages, 9+ filter examples, plus a large `examples/knowledge/*`
tree — see Coverage for the full enumeration; (2) `WebFetch` on ~20
highest-value pages (the core `concepts/*` pages, the agents/teams RAG
patterns, and Milvus/pgvector/LanceDB/SurrealDB/LangChain/LlamaIndex vector
store overviews); (3) everything else verified against installed source in
`.venv/Lib/site-packages/agno/knowledge/`, `agno/vectordb/`, `agno/agent/`,
`agno/filters.py`, and `agno/db/schemas/knowledge.py` (agno==2.6.13,
verified by direct `Read`/`Grep`, plus one dedicated sub-agent pass over
`agno/vectordb/*`). Every claim below is flagged as either doc-confirmed
(quoted from a fetched page) or source-only (not cross-checked against a
live page — the ~280 remaining sitemap URLs beyond what was fetched). The
one prior-precedent discrepancy (agno-chunking-strategy.md §7) is not
restated.

## Doc-vs-source discrepancies

Confirmed via `WebFetch` against the live `docs.agno.com` pages (quoted)
cross-checked with installed source, plus source-only findings not yet
doc-cross-checked (marked as such).

1. **[DOC-CONFIRMED, most important] The `hybrid-search` concept page
   describes RRF as *the* hybrid-search fusion mechanism used across
   backends — but pgvector's actual fusion is NOT RRF.** The live page
   (`knowledge/concepts/search-and-retrieval/hybrid-search`) states hybrid
   search works via "Fusion merges the results using Reciprocal Rank Fusion
   (RRF)" with formula `RRF(d) = Σ 1/(k + rank)`, and lists **"PgVector,
   ChromaDB, LanceDB, Weaviate, Milvus, and Pinecone"** as the backends that
   "explicitly support this feature." Source
   (`agno/vectordb/pgvector/pgvector.py::hybrid_search`) shows pgvector's
   hybrid search is a completely different mechanism: a SQL-computed
   **weighted linear combination** —
   `hybrid_score = vector_score_weight * vector_score + (1 - vector_score_weight)
   * text_rank` (normalized `ts_rank_cd` + normalized distance score,
   `vector_score_weight` default `0.5`) — there is no RRF anywhere in
   pgvector's search code. Milvus, by contrast, genuinely does use
   `RRFRanker(k=60)` (hardcoded, matches the doc's "default 60" claim). So
   the doc's fusion-mechanism explanation is accurate for Milvus but
   **wrong for pgvector** — a reader following this page to reason about
   pgvector hybrid-search ranking behavior would draw the wrong conclusion
   about how scores combine. If this platform ever adds pgvector as a
   secondary knowledge backend, tune `vector_score_weight`, not a `k`
   parameter — RRF's `k` doesn't exist there.
2. **[DOC-CONFIRMED] `insert()` is already the doc-canonical method —
   `add_content()` is source-only-deprecated, not doc-visible at all.**
   Contrary to this task's own framing (which named `add_content`/async
   variants as part of the "Knowledge API" to document), every fetched
   quickstart/agents page (`knowledge/quickstart`,
   `knowledge/agents/agentic-rag-pgvector`,
   `knowledge/agents/traditional-rag-pgvector`) uses `knowledge.insert(...)`
   exclusively — `add_content` doesn't appear in any fetched doc page.
   Source confirms why: `add_content()`/`add_content_async()`
   (`knowledge.py` ~3448-3540) are deprecated wrappers around
   `insert()`/`ainsert()` with a literal `"DEPRECATED: Use insert() instead.
   This method will be removed in a future version."` docstring. Net: no
   actual doc-vs-source conflict here — the docs and source agree that
   `insert()`/`ainsert()`/`insert_many()`/`ainsert_many()` are current,
   `add_content` is legacy-only. (Flagging this only because it corrects an
   assumption baked into this task's own brief.)
3. **[SOURCE-ONLY, not doc-cross-checked] Milvus does not support `SearchType.keyword`** despite it being a valid
   enum member you can pass to the constructor without error.
   `Milvus.get_supported_search_types()` returns `[vector, hybrid]` only;
   `search()`'s branch logic is a plain `if hybrid: hybrid_search() else:
   vector_search()`, so constructing `Milvus(..., search_type=SearchType.keyword)`
   silently degrades to plain dense-vector search rather than raising or
   behaving as documented "keyword search."
4. **[SOURCE-ONLY] Milvus hybrid search is dense + Agno's own hashed
   pseudo-TF-IDF, not dense + real BM25.** `_get_sparse_vector()`
   lowercases/splits on whitespace, buckets each word into
   `hash(word) % sparse_vector_dimensions` (default 10000 —
   collision-prone), and scores by `count * log(1 + total_word_count)`.
   Milvus 2.5+/2.6 has a native BM25 full-text function; Agno's Milvus
   integration does not use it. The RRF fusion mechanism itself is
   genuinely Milvus-native (`RRFRanker(k=60)`, hardcoded) and matches what
   the doc-confirmed `hybrid-search` page describes for Milvus specifically
   — it's only the *sparse-side input quality* (pseudo-TF-IDF, not BM25)
   that's a gap the docs don't surface anywhere fetched this session.
5. **[SOURCE-ONLY] `FilterExpr` (`EQ`/`AND`/`OR`/etc. from `agno.filters`)
   is effectively a pgvector-only feature for search**, not a
   backend-agnostic DSL as its module docstring implies. Milvus, LanceDB,
   SurrealDB, and LlamaIndex all detect `isinstance(filters, list)` and
   `log_warning(...)` + drop the filter to `None` rather than applying or
   raising. Only plain `Dict[str, Any]` equality filters are universally
   supported across backends. The doc-confirmed `filters/overview` page
   lists "ChromaDB, LanceDB, Milvus, MongoDB, PgVector, Pinecone, Qdrant,
   and Weaviate" as supporting filtering generally, **without
   distinguishing which of those accept `List[FilterExpr]` vs. dict-only**
   — a reader could reasonably assume `FilterExpr` composition
   (`AND(EQ(...), GT(...))`) works on Milvus/LanceDB from that page alone;
   source shows it silently no-ops there. **For Milvus (our backend),
   always pass filters as a plain `Dict[str, Any]`.**
6. **[SOURCE-ONLY] LanceDB filters client-side, after `.limit()` truncates
   the candidate set** — opposite of the predicate-pushdown behavior most
   readers assume from a columnar store. A filtered LanceDB query can
   return fewer than `limit` results (or zero) even when more matching rows
   exist beyond the pre-filter top-`limit` window, because metadata lives
   inside an opaque `payload` JSON blob column, not a queryable field. Not
   mentioned on the doc-confirmed `lancedb/overview` page (which only shows
   `SearchType.keyword` in its example and doesn't discuss filter mechanics
   at all in the fetched excerpt).
7. **[DOC-CONFIRMED, refines a source-only finding] `isolate_vector_search`'s
   `linked_to` metadata is unconditionally written on every insert, but
   only enforced as a search filter when the flag is `True` — and the live
   doc's own warning is about a real, narrower failure mode than a naive
   reading suggests.** Source: `_prepare_documents_for_insert()` sets
   `document.meta_data["linked_to"] = self.name or ""` on **every**
   document regardless of the `isolate_vector_search` setting; the flag
   only controls whether `search()`/`asearch()` inject `linked_to` into the
   filter. The live `isolate-vector-search` doc page states this exact
   warning verbatim: *"Enabling `isolate_vector_search=True` with vector
   databases that don't have existing `linked_to` metadata will cause those
   documents to disappear from search results."* Reconciling the two:
   since stamping is unconditional in 2.6.13 regardless of the flag, the
   realistic failure mode is narrower than "any pre-existing data" — it's
   specifically data inserted under an **older Agno version** that
   predates the `linked_to`-stamping code entirely, or data inserted via a
   **different `Knowledge` instance** with a different `.name` (which would
   carry the wrong `linked_to` value, not a missing one). Either way:
   re-index before flipping the flag on for a collection with pre-existing
   data of uncertain provenance, exactly as the doc warns.
8. **[DOC-CONFIRMED, genuine doc gap] The LangChain and LlamaIndex
   vector-store overview pages are literal "TBD" stub pages** on the live
   site (`knowledge/vector-stores/langchain/overview` and
   `knowledge/vector-stores/llamaindex/overview` — both fetched, both
   return placeholder "TBD" content, no constructor details or examples).
   Everything in Part 12's LangChain/LlamaIndex subsection is source-only;
   there is currently no live doc content to cross-check it against.

## Open questions answered

### (a) Does Milvus metadata filtering push down (server-side enforcement of knowledge_filters/domain)?

**Yes, for plain `Dict[str, Any]` filters** (which is what our
`metadata={"domain": ...}` ingestion + `knowledge_filters={"domain": ...}`
search use). `Milvus._build_expr(filters)` translates the dict into a native
Milvus boolean filter-expression string (`meta_data["domain"] == "legal_strategy"`
for equality, `json_contains_any(meta_data["domain"], [...])` for list values,
`meta_data["domain"] is null` for `None`) and passes it as `filter=` to
`client.search()` / `client.query()` / `client.delete()` — genuine server-side
enforcement, not a Python post-filter. **`List[FilterExpr]` filters
(`EQ`/`AND`/`OR`/etc.) are NOT supported on Milvus** — `search()`/
`async_search()` detect a list, log a warning
(`"Filters Expressions are not supported in Milvus. No filters will be
applied."`), and drop the filter entirely (the search runs unfiltered). Since
our `create_knowledge()` never sets `isolate_vector_search=True` and our
domain filters are always plain dicts (`server/evidence/store.py`'s
`metadata={"domain": domain, ...}`), we're already on the supported path —
but any future code that switches to `agno.filters.EQ`/`AND` composition for
Milvus queries would silently stop filtering. Stick to dict filters for Milvus.

### (b) What does Agno's Milvus collection schema look like (fields it creates)?

**It differs by `search_type`, which matters because our stack always uses
`SearchType.hybrid`:**

- **Non-hybrid (`vector`)**: created via the Milvus quickstart convenience
  call `client.create_collection(collection_name, dimension, metric_type,
  id_type="string", max_length=65535)` — no explicit field schema. Milvus
  auto-creates `id` (VARCHAR PK) + `vector` (FLOAT_VECTOR); every other
  attribute (`name`, `content`, `content_id`, `content_hash`, `meta_data`,
  `usage`) is inserted as a **dynamic field** per row, with `meta_data` and
  `usage` stored as **JSON-encoded strings** (`json.dumps(...)`), not native
  Milvus JSON-typed values.
- **Hybrid (our config)**: built via `_create_hybrid_schema()` with an
  explicit `MilvusClient.create_schema(auto_id=False,
  enable_dynamic_field=True)`. Fields: `id` (VARCHAR 128, PK), `name`
  (VARCHAR 1000), `content` (VARCHAR 65535), `content_id` (VARCHAR 1000),
  `content_hash` (VARCHAR 1000), `text` (VARCHAR 65535 — a duplicate of
  `content`), `meta_data` (VARCHAR 65535, **still JSON-string-encoded, not a
  native JSON field**), `usage` (VARCHAR 65535, JSON-string-encoded),
  `dense_vector` (FLOAT_VECTOR, dim = `embedder.dimensions` — 1024 for our
  bge-m3 text collection, 1536 for the codestral-embed code collection),
  `sparse_vector` (SPARSE_FLOAT_VECTOR, Agno's own hashed pseudo-TF-IDF, see
  discrepancy #4). Index: `dense_vector` → IVF_FLAT (metric per `distance`
  param — default `cosine`), `nlist=1024`; `sparse_vector` →
  SPARSE_INVERTED_INDEX, metric IP, `drop_ratio_build=0.2`.

Because `meta_data` is a VARCHAR holding a JSON *string* rather than a native
JSON field even in the hybrid schema, the `meta_data["domain"] == "..."`
filter-expression syntax Milvus's expr language uses for JSON subscripting
relies on Milvus parsing that string as JSON at query time — this works in
practice (Milvus's `create_collection`/dynamic-field JSON handling supports
it), but it's worth a live smoke test if domain filtering ever behaves
unexpectedly, since it's a less obvious path than a genuinely JSON-typed
column.

### (c) Is isolate-vector-search (`linked_to`) a better fit than metadata domains for our per-domain isolation?

**No — keep the metadata `domain` approach; `linked_to` solves a different
problem. This is now doc-confirmed, not just source-inferred.** The live
`knowledge/concepts/isolate-vector-search` page states the problem it solves
verbatim: *"When multiple `Knowledge` instances share the same vector
database, searches return results from all instances by default"* — i.e.
it's explicitly a **multi-instance-sharing-one-collection** isolation tool,
not a multi-domain-within-one-instance filter tool. Mechanism, confirmed on
both source and the doc page: *"Each document gets `linked_to` metadata set
to the Knowledge instance's `name`"* on insert (unconditional, see
discrepancy #7), and *"A `linked_to` filter is automatically injected"* on
search when `isolate_vector_search=True`. It's a single-value,
single-Knowledge-instance partition key — one `Knowledge` object, one
`linked_to` value, all-or-nothing isolation from other `Knowledge`
instances on the shared collection. The live `knowledge/teams/overview`
page corroborates the same framing for teams: `isolate_vector_search` is
recommended *"particularly relevant when sharing a vector database across
teams or tenants."*

**Further corroboration from the live `distributed-rag-lancedb` example**:
Agno's own official distributed-RAG-across-a-team pattern does **not** use
`isolate_vector_search`/`linked_to` at all — it uses **separate LanceDB
tables per team member** (`recipes_primary` for the primary retriever,
`recipes_context` for the context-expander agent, connected via two
distinct `Knowledge`/`LanceDb` constructions). That is exactly the
**per-domain-collection** pattern this platform's planned next build
already intends (separate Milvus collections per domain/embedder), which
independently validates the direction without needing `linked_to` at all.

Our actual requirement is different: **one single `Knowledge` instance**
(`platform`/`platform_knowledge`) whose documents span **four domains**
(`timeline_relationship | personal_history | platform_design |
legal_strategy`), where individual agents need to filter to *one or more* of
those domains per query — not a fixed 1:1 instance-to-partition mapping.
`linked_to` only carries one string value per `Knowledge` instance (set once,
at `Knowledge(name=...)` construction) — it cannot represent "this agent
wants `legal_strategy` OR `platform_design`" the way our existing
`metadata={"domain": ...}` + `knowledge_filters={"domain": ...}` (or
`IN("domain", [...])` if it worked on Milvus — it doesn't, see (a)) approach
can. The domain metadata pattern we already have (ADR-0027,
`server/evidence/store.py`) is the correct primitive here; `linked_to` would
only become relevant if the **planned per-domain vector DB split** (separate
Milvus collections per domain/embedder) later needed *multiple Knowledge
instances sharing one collection* for some other reason — which the planned
design (separate collections, not a shared collection with instance-level
partitioning) doesn't call for either. Net: no action needed, `linked_to` is
not a fit for either the current single-collection-domain-tagged design or
the planned per-domain-collection design.

### (d) Where can a reranker hook into the Milvus hybrid path vs native RRF?

Two distinct, stackable mechanisms exist and don't conflict:

1. **`RRFRanker(k=60)`** — always used internally by Agno's `Milvus.
   hybrid_search()`/`async_hybrid_search()` whenever `search_type=hybrid`.
   This is Milvus's native reciprocal-rank fusion across the two
   `AnnSearchRequest`s (dense + sparse), built via
   `pymilvus.AnnSearchRequest`/`RRFRanker` and executed server-side inside
   `client.hybrid_search(reqs=[...], ranker=RRFRanker(60), limit=limit)`.
   `k=60` is **hardcoded** in the installed source — not exposed as a
   `Milvus(...)` constructor kwarg, so tuning it would require subclassing or
   a source patch.
2. **`Milvus(..., reranker=<Reranker instance>)`** — a separate, **optional**
   constructor param (same shape/contract as pgvector's and LanceDB's
   `reranker=`). If set, `self.reranker.rerank(query=query,
   documents=search_results)` runs **after** Milvus returns the RRF-fused
   hybrid results (or after plain vector search, in the non-hybrid path) —
   i.e. it's an additional Python-side rerank pass (e.g.
   `CohereReranker`/`SentenceTransformerReranker`/`InfinityReranker`/
   `AwsBedrockReranker`) layered on top of, not instead of, the native RRF
   fusion. Our `create_knowledge()` currently passes no `reranker=` to
   `Milvus(...)` — consistent with `server/core/session.py`'s own comment
   ("Milvus hybrid search fuses dense+sparse natively (RRF) — no external
   reranker"). If retrieval quality on the sparse side ever becomes a problem
   (plausible given discrepancy #4 — the sparse vector is a weak hashed
   pseudo-TF-IDF, not real BM25), the lowest-risk lever is adding a
   `reranker=SentenceTransformerReranker(...)` (or Cohere/Infinity) to the
   `Milvus(...)` call in `create_knowledge()` — it hooks in exactly at this
   post-RRF point without touching the fusion logic itself.

---

## Part 1 — Knowledge overview & mental model

`agno.knowledge.Knowledge` (dataclass, `agno/knowledge/knowledge.py`) is the
single ingestion + retrieval class for Agno's RAG system. Core fields:
`name`, `description`, `vector_db`, `contents_db`, `max_results` (default
10), `readers` (lazy-loaded dict), `content_sources` (list of
`BaseStorageConfig` for cloud sources), `isolate_vector_search` (bool,
default `False`). It inherits from `RemoteKnowledge`, which itself inherits
from five provider-specific loader mixins (`S3Loader`, `GCSLoader`,
`SharePointLoader`, `GitHubLoader`, `AzureBlobLoader`) — this is how cloud
storage ingestion is composed in rather than being a separate subsystem.

`__post_init__` auto-creates the vector DB collection if it doesn't exist
(`self.vector_db.create()` when `not self.vector_db.exists()`) and calls
`construct_readers()` (initializes an empty lazy-loading readers dict — no
readers are instantiated until first use, via `ReaderFactory`).

`Knowledge` itself implements `KnowledgeProtocol` (see Part 11) —
`build_context()`, `get_tools()`/`aget_tools()`, `retrieve()`/`aretrieve()` —
which is what lets an `Agent(knowledge=Knowledge(...))` wire it in without any
glue code. `agno.knowledge.protocol.KnowledgeProtocol` is a
`@runtime_checkable Protocol` documenting the **minimal** interface a custom
knowledge implementation needs (`build_context`, `get_tools`, `aget_tools`
required; `retrieve`/`aretrieve` optional, only needed for
`add_knowledge_to_context`/traditional RAG) — this is the extension point for
building a knowledge base that isn't `agno.knowledge.Knowledge` at all (e.g.
a hand-rolled SQL-query knowledge base with custom tools like "grep" or
"list_files" instead of "search").

## Part 2 — Knowledge API

### Insert (write path)

- `insert(name=, description=, path=, url=, text_content=, metadata=, topics=,
  remote_content=, reader=, include=, exclude=, upsert=True,
  skip_if_exists=False, auth=)` / `ainsert(...)` (async) — the primary
  ingestion entrypoint. Exactly one of `path` / `url` / `text_content` /
  `topics` / `remote_content` must be given (validated; logs a warning and
  no-ops otherwise). Internally dispatches to `_load_from_path` /
  `_load_from_url` / `_load_from_content` / `_load_from_topics` /
  `_load_from_remote_content` (or the async equivalents) based on which arg
  was set.
- `insert_many(...)` / `ainsert_many(...)` — two calling conventions: pass a
  `List[ContentDict]` as the first positional arg, or pass plural kwargs
  (`paths=`, `urls=`, `text_contents=`, `topics=`, `remote_content=`) that
  fan out into repeated `insert()`/`ainsert()` calls.
- `add_content()` / `add_content_async()` — **deprecated** thin wrappers
  around `insert()`/`ainsert()` (see discrepancy #2). Do not use in new code.
- `content_hash` + `id` are computed before load (`_build_content_hash`,
  `generate_id(content_hash)`) — this is the basis for `skip_if_exists`
  (checks `vector_db.content_hash_exists(content_hash)` before doing any
  reading/embedding work) and for `upsert` (re-embeds and replaces).
- `path` insert on a **directory** recurses over every file in the dir
  (non-recursive — `path.iterdir()`, not `rglob`), applying `include`/
  `exclude` glob patterns per file (matched against both the full path and
  the basename, so bare patterns like `*.go` work against nested paths too).
- `url` insert: validates URL format, downloads the body only if the URL path
  has a file extension (skipped entirely when a custom URL-aware reader like
  `LLMsTxtReader` is supplied and declares `ContentType.URL` in
  `get_supported_content_types()` — the reader fetches the URL itself
  instead), selects a reader by extension or falls back to `website_reader`,
  and — notably — **groups documents by source URL** when a single reader
  call returns pages from multiple URLs (e.g. `WebsiteReader` crawling
  multiple links), processing/deduping each source URL's `content_hash`
  independently rather than treating the whole crawl as one content item.
- Every prepared `Document` gets `document.meta_data["linked_to"] =
  self.name or ""` stamped in `_prepare_documents_for_insert` — unconditional
  regardless of `isolate_vector_search` (see discrepancy #7).
- **LightRAG special case**: if `vector_db.__class__.__name__ == "LightRag"`,
  path/URL insert routes to `_process_lightrag_content()` instead of the
  normal reader→chunk→vector_db.insert pipeline — LightRAG's `VectorDb.
  insert()`/`upsert()` are no-ops; real ingestion happens via LightRAG's own
  HTTP upload endpoints.

### Search (read path)

- `search(query, max_results=None, filters=None, search_type=None) ->
  List[Document]` / `asearch(...)`. `filters` accepts `Dict[str, Any]` OR
  `List[FilterExpr]`. `search_type` (string) can override the vector db's
  configured `SearchType` per-call if the vector db exposes a
  `search_type` attribute.
- **`isolate_vector_search` injection happens here**: if
  `self.isolate_vector_search and self.name`, a `linked_to` constraint is
  merged into whatever `filters` were passed — `{"linked_to": self.name}`
  merged into a dict, or `EQ("linked_to", self.name)` prepended to a list.
- `asearch()` tries `vector_db.async_search()` first and falls back to the
  sync `vector_db.search()` on `NotImplementedError` (not every backend
  implements true async search).
- Errors inside `search`/`asearch` are caught and logged, returning `[]`
  rather than raising — a search failure degrades gracefully to "no results"
  rather than crashing the agent turn.

### Content management (contents_db-backed)

- `get_content(limit=, page=, sort_by=, sort_order=) -> Tuple[List[Content],
  int]` / `aget_content(...)` — paginated listing, **automatically scoped to
  `linked_to=self.name`** (so even without `isolate_vector_search` enabled
  for search, content listing is already partitioned by Knowledge name at
  the contents_db layer).
- `get_content_by_id(content_id)` / `aget_content_by_id(...)`.
- `get_content_status(content_id) -> Tuple[Optional[ContentStatus],
  Optional[str]]` — status is one of `ContentStatus.PROCESSING / COMPLETED /
  FAILED` (str Enum), plus an optional `status_message` (e.g. the exception
  text on failure).
- `patch_content(content)` / `apatch_content(content)` — update a `Content`
  row (thin wrapper over `_update_content`/`_aupdate_content`).
- `remove_content_by_id(content_id)` / `aremove_content_by_id(...)` — deletes
  from both `vector_db` (`delete_by_content_id`, or LightRAG's
  `delete_by_external_id` special case) and `contents_db`
  (`delete_knowledge_content`).
- `remove_all_content()` / `aremove_all_content()` — lists then deletes every
  content item one at a time (no bulk-delete short-circuit).
- `remove_vector_by_id(id)`, `remove_vectors_by_name(name)`,
  `remove_vectors_by_metadata(metadata)` — vector-db-only deletes, bypass
  `contents_db` (useful for cleaning up orphaned vectors without a matching
  content row).
- **Sync methods raise `ValueError` if `contents_db` is an `AsyncBaseDb`**
  (e.g. `get_content()` explicitly checks `isinstance(self.contents_db,
  AsyncBaseDb)` and tells you to use `aget_content()` instead) — a real
  footgun if you mix sync/async `Db` instances.

### Filters API (validation, not just search-time)

- `get_valid_filters() -> Set[str]` / `aget_valid_filters()` — walks every
  content row's `metadata` dict and unions all keys seen. **Without a
  `contents_db`, this returns an empty set and logs "all filter keys
  considered valid"** — i.e. filter validation is silently disabled if you
  don't wire a contents DB.
- `validate_filters(filters) -> Tuple[filters, invalid_keys]` /
  `avalidate_filters(...)` — validates a dict or `List[FilterExpr]` against
  `get_valid_filters()`. For dict filters: unknown keys are stripped with a
  warning (both flat keys and dotted `meta_data.key`-style prefixed keys are
  checked against the base key). For list filters: only leaf `FilterExpr`
  instances with a `.key` attribute are checked; `AND`/`OR`/`NOT` composites
  are passed through unvalidated (their nested leaves aren't recursively
  checked) — non-`FilterExpr` list items are dropped with a warning.
- This validation path is what `search_knowledge_base_with_filters` (the
  agentic-filters tool, see Part 11) calls with `validate_filters=True` —
  it's specifically there to stop the LLM from inventing filter keys that
  don't exist in the knowledge base.

## Part 3 — Readers

**19 readers in source.** 18 are registered in `ReaderFactory`
(`agno/knowledge/reader/reader_factory.py`) with lazy class-level caching
(`_reader_cache`); the 19th (`S3Reader`, `agno/knowledge/reader/s3_reader.py`)
is a standalone reader tied to the legacy `agno-aws`/`textract`/`pypdf` extras
path, not registered in the factory.

**[DOC-CONFIRMED]** The live `knowledge/concepts/readers/overview` page's
own listing table only names 15 of the 19 (`PDFReader`, `DoclingReader`,
`TextReader`, `MarkdownReader`, `CSVReader`, `FieldLabeledCSVReader`,
`JSONReader`, `PPTXReader`, `ArxivReader`, `WikipediaReader`,
`YouTubeReader`, `WebsiteReader`, `WebSearchReader`, `FirecrawlReader`,
`LLMsTxtReader`) — it omits `ExcelReader`, `DocxReader`, `TavilyReader`, and
(expectedly, since it's not factory-registered) `S3Reader` from its
narrative table, though the sitemap does show a much larger
`examples/knowledge/readers/*` tree (30+ pages) with dedicated
excel/docx-adjacent examples (`excel-reader`, `excel-legacy-xls`) — so the
omission looks like the *overview* page's table being non-exhaustive rather
than those readers being undocumented site-wide. The doc confirms the
auto-selection mechanism exactly matches source: *"reader =
ReaderFactory.get_reader_for_extension(".pdf")  # PDFReader"* and *"reader =
ReaderFactory.get_reader_for_url("https://youtube.com/watch?v=...")  #
YouTubeReader"*, stating *"When using `knowledge.insert()`, this happens
automatically."*

| Key | Class | Formats / notes |
|---|---|---|
| `pdf` | `PDFReader` | PDF text extraction; optional OCR for embedded images via `rapidocr_onnxruntime` (`_ocr_reader`); `_sanitize_pdf_text()` rejoins pypdf's word-per-line extraction artifacts into flowing paragraphs (disable via `sanitize_content=False`) |
| `csv` | `CSVReader` | Custom delimiter support |
| `excel` | `ExcelReader` | `.xlsx`/`.xls`, sheet filtering, row-based chunking |
| `field_labeled_csv` | `FieldLabeledCSVReader` | Converts each CSV row into a field-labeled text document (`"Field: value"` per line) instead of a flat row dump; **chunking is disabled** (`get_supported_chunking_strategies() -> []`) — each row is already the logical unit |
| `docx` | `DocxReader` | `.docx`/`.doc` |
| `pptx` | `PPTXReader` | `.pptx` |
| `json` | `JSONReader` | Nested object handling |
| `markdown` | `MarkdownReader` | Header-aware chunking, formatting preservation |
| `text` | `TextReader` | Plain text, configurable encoding; **the universal fallback** for unrecognized extensions |
| `website` | `WebsiteReader` | BeautifulSoup-based crawl; `max_depth=3`, `max_links=10`, `timeout`, `proxy`, `allowed_hosts` (SSRF guard via `is_host_allowed`/redirect guards) |
| `firecrawl` | `FirecrawlReader` | JS-rendering crawl via Firecrawl API (`api_key` from `FIRECRAWL_API_KEY` env), `mode="crawl"` default |
| `tavily` | `TavilyReader` | Tavily Extract API (`TAVILY_API_KEY`), `extract_format="markdown"`, `extract_depth="basic"` defaults |
| `youtube` | `YouTubeReader` | Transcripts + metadata for videos/playlists |
| `arxiv` | `ArxivReader` | Downloads + PDF-parses arXiv papers, extracts metadata |
| `wikipedia` | `WikipediaReader` | Section-aware chunking, link resolution |
| `web_search` | `WebSearchReader` | Executes a web search and reads the results |
| `llms_txt` | `LLMsTxtReader` | Reads an `llms.txt` file, discovers linked doc URLs, fetches each — declares `ContentType.URL` support so URL insert skips the pre-download step and lets the reader own the fetch |
| `docling` | `DoclingReader` | IBM Docling — the broadest-format reader: PDF/DOCX/XLSX/PPTX/Markdown/HTML/AsciiDoc/LaTeX/CSV documents, PNG/JPEG/TIFF/BMP/WEBP images, WAV/MP3/M4A/AAC/OGG/FLAC audio, MP4/AVI/MOV video, plus WebVTT/JSON/XML — converts everything to a unified `DoclingDocument`, exports to `output_format` (`markdown` default, or `text`/`json`/`yaml`/`html`/`html_split_page`/`doctags`/`vtt`) |
| `s3` (standalone) | `S3Reader` | Legacy path requiring `agno-aws` + `textract` + `pypdf`; not in `ReaderFactory` — cloud ingestion normally goes through `remote_content`/`RemoteKnowledge` loaders instead (Part 13) |

`ReaderFactory.get_reader_for_extension(extension)` maps file extensions to
readers (`.pdf`→pdf, `.csv`→csv, `.xlsx`/`.xls`→excel, `.docx`/`.doc`→docx,
`.pptx`→pptx, `.json`→json, `.md`/`.markdown`→markdown, `.txt`/`.text`→text,
anything else→text fallback). `get_reader_for_url(url)` special-cases
`youtube.com`/`youtu.be` domains → `youtube`, else → `website`.
`ReaderFactory.get_all_reader_keys()` orders URL-capable readers
(`website`/`firecrawl`/`tavily`/`youtube`) first, rest alphabetically.
`ReaderFactory.register_reader(...)` lets you register a brand-new reader key
at runtime by attaching a `_get_{key}_reader` classmethod.

Base `Reader` dataclass (`agno/knowledge/reader/base.py`) fields: `chunk`
(bool, default `True` — if `False`, chunking is deferred to
`Knowledge._chunk_documents_sync`/async path instead of happening inline in
the reader), `chunk_size` (default 5000), `separators` (list, used by the
default `FixedSizeChunking` fallback), `chunking_strategy`
(`Optional[ChunkingStrategy]` — see Part 6 pointer), `name`, `description`,
`max_results` (default 5, relevant to search-style readers like
`WebSearchReader`), `encoding`. `chunk_document()`/`achunk_document()`
lazily default to `FixedSizeChunking(chunk_size=self.chunk_size)` if no
`chunking_strategy` was set.

## Part 4 — Embedders

Base `Embedder` dataclass (`agno/knowledge/embedder/base.py`): `dimensions`
(default 1536), `enable_batch` (bool, default `False`), `batch_size`
(default 100). Four methods every embedder implements (or leaves
`NotImplementedError`): `get_embedding`, `get_embedding_and_usage`,
`async_get_embedding`, `async_get_embedding_and_usage`.

**Providers present**: `openai` (`OpenAIEmbedder`), `openai_like`
(`OpenAILikeEmbedder`), `azure_openai`, `cohere`, `google`, `mistral`,
`voyageai`, `jina`, `fireworks`, `together`, `nebius`, `langdb`, `vllm`,
`ollama`, `huggingface`, `fastembed`, `aws_bedrock`, `sentence_transformer`
— 18 total in source. **[DOC-CONFIRMED, partial gap]** The live
`knowledge/concepts/embedder/overview` page's narrative list names only 14:
*"OpenAI, Gemini, Cohere, Voyage AI, Mistral, Ollama, FastEmbed,
HuggingFace, AWS Bedrock, Azure OpenAI, Fireworks, Together, Jina, and
Nebius"* — omitting `openai_like`, `langdb`, `vllm`, and
`sentence_transformer` from the overview narrative (though
`sentence-transformer` and other providers do have dedicated
`reference/knowledge/embedder/*` pages per the sitemap, so — same pattern
as the readers overview gap — this reads as the overview page's list being
a non-exhaustive highlight reel rather than a real absence of docs).
Doc-confirmed on dimensions/batching: *"Ensure your embedder's output
dimensions match what your vector database expects"* and batch processing
*"Process multiple texts in a single API call to reduce requests and
improve performance"* via `enable_batch=True, batch_size=100` — both match
source exactly (Part 14).

### `OpenAIEmbedder` (`agno/knowledge/embedder/openai.py`) — the base our stack uses directly

`id="text-embedding-3-small"`, `dimensions=None` (resolved in
`__post_init__`: `3072` if `id == "text-embedding-3-large"`, else `1536` —
**only for the two known OpenAI model IDs**; for anything else the field
stays whatever you passed), `encoding_format="float"|"base64"`, `user`,
`api_key`, `organization`, `base_url`, `request_params`, `client_params`.

**Dimensions-in-request gotcha (source-verified, relevant to our stack)**:
`response()`/`async_get_embedding()`/`async_get_embeddings_batch_and_usage()`
all gate sending the `dimensions` param to the API with:
```python
if self.id.startswith("text-embedding-3") or self.base_url is not None:
    _request_params["dimensions"] = self.dimensions
```
i.e. `dimensions` is sent to **any** endpoint reached via a custom
`base_url` (not just OpenAI's own `text-embedding-3-*` models) — this is
exactly the condition our OpenRouter-backed embedder hits (see below), and
it's the mechanism that keeps our request payload honest about the vector
size the third-party model should return.

`async_get_embeddings_batch_and_usage(texts) -> (List[List[float]],
List[Optional[Dict]])` batches in chunks of `self.batch_size`, with a
per-batch fallback to individual `async_get_embedding_and_usage` calls if the
batch request errors — this is the method that actually gets used when
`enable_batch=True` on the embedder (see Part 14, performance tips).

### `OpenAILikeEmbedder` (`agno/knowledge/embedder/openai_like.py`)

Subclasses `OpenAIEmbedder`, purpose-built for LiteLLM proxy / Ollama
OpenAI-compatible mode / vLLM / any OpenAI-compatible `/v1/embeddings`
endpoint. Defaults: `id="not-provided"`, `dimensions=1536`,
`api_key="not-provided"`. **Overrides `__post_init__` to a no-op** —
explicitly skips `OpenAIEmbedder`'s model-ID-based dimension inference,
because a third-party model ID can't be matched against OpenAI's known
model list; the docstring is explicit that dimensions must be set manually
for custom providers.

**Our stack does not use `OpenAILikeEmbedder`** — `server/core/session.py`'s
`_embedder()` helper instantiates the base `OpenAIEmbedder` directly with
`api_key=_OR_API_KEY, base_url=_OR_BASE_URL, dimensions=dimensions` for both
the text (`bge-m3`, 1024-d) and code (`codestral-embed-2505`, 1536-d) lanes.
This works because `OpenAIEmbedder`'s own dimensions-gate logic already
covers "any `base_url`" (see gotcha above), so `OpenAILikeEmbedder`'s only
real value-add (skipping the OpenAI-model-ID inference) isn't needed when you
pass `dimensions=` explicitly anyway, which our `_embedder()` always does.
Functionally equivalent either way for our case; using the base class
directly is fine and matches current code.

## Part 5 — Rerankers

Base `Reranker` (Pydantic `BaseModel`, `agno/knowledge/reranker/base.py`):
one method, `rerank(query, documents) -> List[Document]`
(`NotImplementedError` in the base). All four concrete implementations
follow the same shape: fetch scores, set `doc.reranking_score`, sort
descending, truncate to `top_n` if set, and **swallow exceptions** —
`rerank()` wraps `_rerank()` in a `try/except` that logs and returns the
**original, unreranked** documents on any error rather than raising, so a
reranker outage degrades to "no reranking" not "search failure."

- **`CohereReranker`** (`reranker/cohere.py`): `model="rerank-multilingual-v3.0"`,
  `api_key`, `top_n`. Uses `cohere.Client.rerank()`.
- **`InfinityReranker`** (`reranker/infinity.py`): `model="BAAI/bge-reranker-base"`,
  `host="localhost"`, `port=7997`, `url` (parsed into host/port if given),
  `top_n`, `api_key`, `verify_ssl`. Talks to a self-hosted
  [Infinity](https://github.com/michaelfeil/infinity) rerank server via
  `infinity_client`; has a genuine async path (`arerank`), unlike Cohere/
  SentenceTransformer which are sync-only in this install.
- **`SentenceTransformerReranker`** (`reranker/sentence_transformer.py`):
  `model="BAAI/bge-reranker-v2-m3"`, `model_kwargs`, `top_n`. Local
  cross-encoder inference via `sentence_transformers.CrossEncoder` —
  no network call, runs on whatever hardware is available (relevant given
  our "no GPU / local LLMs ≤4B" constraint — this is a *cross-encoder*
  scoring pass, not a generative model, so it's much cheaper, but a
  `bge-reranker-v2-m3`-class model is still nontrivial CPU work per call).
- **`AwsBedrockReranker`** (`reranker/aws_bedrock.py`): `model` (Literal
  `"amazon.rerank-v1:0"` or `"cohere.rerank-v3-5:0"`, default Cohere),
  `top_n`, `aws_region`, `aws_access_key_id`, `aws_secret_access_key`,
  `session` (boto3 `Session`), `additional_model_request_fields`. Calls the
  unified Bedrock `bedrock-agent-runtime` Rerank API. Two convenience
  subclasses: `CohereBedrockReranker`, `AmazonReranker`. Note: Amazon Rerank
  1.0 is unavailable in `us-east-1`.

**Where rerankers hook in**: they are a constructor param on the **vector
db** itself (`Milvus(..., reranker=...)`, `PgVector(..., reranker=...)`,
`LanceDb(..., reranker=...)`), not on `Knowledge`. When set, the vector db's
`search()`/`hybrid_search()` methods call `self.reranker.rerank(query=query,
documents=search_results)` **after** the backend's own similarity search
(and, for Milvus hybrid, after native RRF fusion) returns results — a
strictly additional, optional Python-side pass. See open question (d) above
for the Milvus-specific detail.

## Part 6 — Chunking (pointer only)

Fully covered in `docs/planning/agno-chunking-strategy.md` — every strategy
Agno 2.x ships, cost/latency of embed-at-chunk-time strategies, a hybrid
semantic+fixed configuration sketch tuned for transcripts, tuning knobs, and
3 doc-vs-source bugs already found there (§7). Not restated here. One
integration note relevant to *this* doc: `Reader.chunk_document()` defaults
to `FixedSizeChunking(chunk_size=self.chunk_size)` when no
`chunking_strategy` is set on the reader — so every reader has a working
chunking fallback even if you never touch the chunking config directly.

## Part 7 — Filters

Two unrelated filter concepts live side by side and are easy to conflate:

### `agno.filters` — the `FilterExpr` DSL (`agno/filters.py`)

`FilterExpr` base class with operator overloads (`|`→`OR`, `&`→`AND`,
`~`→`NOT`) plus `to_dict()`/`from_dict()` round-tripping (JSON-API-safe, with
a `MAX_FILTER_DEPTH=10` recursion guard on deserialization). Concrete leaf
classes: `EQ(key, value)`, `NEQ(key, value)`, `GT(key, value)`,
`GTE(key, value)`, `LT(key, value)`, `LTE(key, value)`,
`IN(key, values: List[Any])`, `CONTAINS(key, value: str)`,
`STARTSWITH(key, value: str)`. Composites: `AND(*expressions)`,
`OR(*expressions)`, `NOT(expression)`.

**Backend support is uneven** (see discrepancy #5 and open question (a)) —
only `PgVector._dsl_to_sqlalchemy()` genuinely consumes `List[FilterExpr]`
for search, and even there the supported op subset is smaller
(`EQ, IN, GT, LT, NOT, AND, OR` — no `NEQ`/`GTE`/`LTE`/`CONTAINS`/
`STARTSWITH`, which raise `ValueError: Unknown filter operator` if passed).
Milvus/LanceDB/SurrealDB/LlamaIndex detect a list and drop it with a warning;
LangChain delegates dict filters only to the wrapped vectorstore's
`search_kwargs`. **For Milvus (our backend), always pass filters as a plain
`Dict[str, Any]`.**

A second, separate `FilterExpr` consumer exists at
`agno/db/filter_converter.py` (`filter_expr_to_sqlalchemy`) for **named
table columns** (e.g. trace/session tables, not knowledge metadata) — don't
confuse it with `PgVector`'s JSONB-`meta_data`-specific converter; they
support different (and differently-sized) operator sets.

### `KnowledgeFilter` — the agentic-filter tool-arg shape (`agno/knowledge/types.py`)

```python
class KnowledgeFilter(BaseModel):
    key: str
    value: Any
```
A tiny Pydantic model, unrelated to `FilterExpr` — it's the **shape the LLM
is asked to emit** when calling the agentic `search_knowledge_base` tool with
filters (a `List[KnowledgeFilter]`), which then gets converted to a plain
`Dict[str, Any]` internally before being merged with any static
`knowledge_filters` (via `get_agentic_or_user_search_filters()`,
`agno/utils/knowledge.py`) and handed to `Knowledge.search()`.

### Agentic filters (`enable_agentic_knowledge_filters`)

`Agent(enable_agentic_knowledge_filters=True)` (or the equivalent on `Team`)
swaps the plain `search_knowledge_base(query)` tool for
`search_knowledge_base(query, filters: Optional[List[KnowledgeFilter]] =
None)` — see `create_knowledge_search_tool()` in
`agno/agent/_default_tools.py`. When enabled:

- `Knowledge.build_context(enable_agentic_filters=True)` appends
  `_AGENTIC_FILTER_INSTRUCTION_TEMPLATE` (a hardcoded, fairly verbose
  few-shot prompt block) to the system prompt, listing every currently-valid
  metadata key (from `get_valid_filters()`) and giving the model 3 worked
  examples of filter dict shapes to emit.
- Filter merge precedence (`get_agentic_or_user_search_filters`): if the
  agent-emitted filters and a static `knowledge_filters=` are **both**
  present, the **static/user-passed filters win** (agent's are discarded)
  — this is a deliberate "user override always wins" policy, not a merge.
  Merging a dict (agentic) with a `List[FilterExpr]` (static) raises
  `ValueError` — mixing filter shapes across the two sources isn't supported.
- The search call always runs through `get_relevant_docs_from_knowledge()`
  with `validate_filters=True` when agentic filters are on — invalid keys
  the LLM invents get stripped with a warning rather than sent to the vector
  db, protecting against a hallucinated filter key silently returning zero
  results.

Note the discovery/instructions cost: `get_valid_filters()` (no
`contents_db` → empty set, silently disabling the whole agentic-filter
prompt injection) does a full **`get_content()` scan and re-derives keys from
every content row's metadata on every `build_context()` call** — for a large
knowledge base this is a real per-turn cost worth knowing about (see Part
14).

## Part 8 — Isolate vector search (`linked_to`)

Covered in depth under Open Question (c) above — short version: opt-in
per-`Knowledge`-instance partitioning (`isolate_vector_search: bool = False`
on `Knowledge`) for the case where multiple `Knowledge` instances share one
physical vector collection. `linked_to = self.name` is stamped on every
inserted document unconditionally (`_prepare_documents_for_insert`,
regardless of the flag); the flag only controls whether `search()`/
`asearch()`/`get_content()` filter by it. It is a single-value partition key
per `Knowledge` instance, not a general-purpose multi-value tag — it cannot
express "any of domains X, Y" the way our existing `metadata={"domain":
...}` tagging does. Requires re-indexing content that predates the
`linked_to`-stamping code path if you flip isolation on for old data.

## Part 9 — Contents DB

`contents_db: Optional[Union[BaseDb, AsyncBaseDb]]` on `Knowledge` is a
**bookkeeping/metadata store, not a document/vector store.** It persists one
row per inserted content item (`KnowledgeRow`,
`agno/db/schemas/knowledge.py`): `id`, `name`, `description`, `metadata`
(`Dict[str, Any]` — the same dict later used for filter-key discovery via
`get_valid_filters()`), `type`, `size`, `linked_to`, `access_count`,
`status`/`status_message` (`ContentStatus.PROCESSING/COMPLETED/FAILED`),
`created_at`/`updated_at`, `external_id` (used by the LightRAG special case
to map back to the external doc ID for deletion).

**It does not store**: the chunked document text, the embedding vectors, or
per-chunk metadata — all of that lives in `vector_db` only. The distinction
in practice: `contents_db` answers "what source files/URLs/text blobs have I
ingested, and what's their status/size/metadata?" (one row per `insert()`
call, used by `get_content()`/`get_content_status()`/`patch_content()`/
content-management UI-style operations); `vector_db` answers "what are the
actual searchable chunks and their vectors?" (many rows per `insert()` call,
one per chunk). Deleting a content item deletes from **both**
(`remove_content_by_id` calls `vector_db.delete_by_content_id()` +
`contents_db.delete_knowledge_content()`).

**[DOC-CONFIRMED — exact match, no discrepancy]** The live
`knowledge/concepts/contents-db` page states the identical distinction —
*"Vector DB: Stores embeddings for search functionality"* vs. *"Contents
DB: Stores metadata about each piece of content — what it is, when you
added it, and its processing status"* — and its schema field table is a
byte-for-byte match to `KnowledgeRow`: `id, name, description, metadata,
type, size, linked_to, access_count, status, status_message, created_at,
updated_at, external_id`. Delete semantics also match: *"Removes the
content metadata from Content DB"* + *"Deletes associated vectors from the
vector database."* This is the one section of this doc with zero
doc-vs-source drift found.

**Our stack**: `contents_db=get_postgres_db(contents_table=f"{table_name}_contents")`
— a `PostgresDb` instance scoped to a `{collection}_contents` table per
Milvus collection (`server/core/session.py:144-170`). This is a deliberate
Postgres-for-contents / Milvus-for-vectors split (ADR-0026/0027) — `Knowledge`
supports this split natively (`vector_db` and `contents_db` are entirely
independent constructor args, no requirement they be the same backend).

## Part 10 — Search types (vector/keyword/hybrid) per backend

`SearchType` (`agno/vectordb/search.py`) — plain `str, Enum`: `vector`,
`keyword`, `hybrid`. No companion config dataclass; the enum value alone is
what backends branch on.

| Backend | `get_supported_search_types()` | Hybrid mechanism | Filter push-down |
|---|---|---|---|
| **Milvus** (ours) | `[vector, hybrid]` — **no keyword**; passing `search_type=keyword` silently degrades to plain vector search | Native: 2× `AnnSearchRequest` (dense IVF_FLAT + sparse SPARSE_INVERTED_INDEX) fused via `RRFRanker(k=60, hardcoded)`. Sparse side is Agno's own hashed pseudo-TF-IDF, not BM25 | Server-side via `_build_expr()` → native Milvus filter-expression string, **dict filters only** (`List[FilterExpr]` dropped with a warning) |
| **pgvector** | `[vector, keyword, hybrid]` — all three | NOT RRF: a SQL-computed **weighted linear combination** — normalized `ts_rank_cd` (full-text) + normalized distance-derived similarity, combined via `hybrid_score = vector_score_weight * vector + (1 - vector_score_weight) * text` (`vector_score_weight` default 0.5, tunable) | Server-side both ways: dict → JSONB `@>` containment; `List[FilterExpr]` → `_dsl_to_sqlalchemy()` against `meta_data[key].astext` (smaller op set: `EQ, IN, GT, LT, NOT, AND, OR`) |
| **LanceDB** | `[vector, keyword, hybrid]` — all three | LanceDB's own native `query_type="hybrid"` (`.vector(emb).text(query)`); keyword uses LanceDB FTS over the whole opaque `payload` JSON blob (auto-creates an FTS index on it) | **Client-side, after `.limit()`** — metadata lives inside an opaque `payload` string column (not queryable), so Agno runs the search unfiltered up to `limit`, then Python-filters by exact match on `doc.meta_data` — can silently return fewer than `limit` results (discrepancy #6) |
| **SurrealDB** (vectordb) | `[]` — no `SearchType` concept at all | N/A — vector-only via SurrealQL's native `<|k, ef|>` KNN operator + `vector::distance::knn()` | Server-side, parametrized SurrealQL (`AND meta_data.{key} = ${key}`) — dict filters only |
| **LangChain adapter** | `[]` | Delegates entirely to the wrapped LangChain vectorstore's own retriever/search_kwargs | Delegated (dict → `search_kwargs`); backend-opaque to Agno |
| **LlamaIndex adapter** | `[]` | Delegates entirely to the wrapped LlamaIndex `BaseRetriever.retrieve()` | **Unsupported** — filters (dict or list) are dropped with a warning regardless |

Every backend implements the same abstract `VectorDb` interface
(`agno/vectordb/base.py`): `create()`/`async_create()`, `name_exists()`,
`id_exists()`, `content_hash_exists()`, `insert()`/`async_insert()`,
`upsert()`/`async_upsert()`, `search()`/`async_search()`, `drop()`,
`exists()`, `delete()`, `delete_by_id()`/`delete_by_name()`/
`delete_by_metadata()`/`delete_by_content_id()`,
`get_supported_search_types()`. Non-abstract defaults: `upsert_available()`
→ `False` unless a backend overrides it; `update_metadata()` → a no-op that
just logs a warning unless overridden; `optimize()` → raises
`NotImplementedError` if actually called. Base `__init__` takes `id`, `name`
(defaults to the class name), `description`, `similarity_threshold`
(validated to `0.0`–`1.0`).

## Part 11 — Agentic RAG vs traditional RAG; custom retriever; update_knowledge

### The two RAG modes are independent Agent flags and can both be on at once

- **Agentic RAG** — `Agent(search_knowledge=True)` (the default when
  `knowledge` is set). Adds a `search_knowledge_base` tool the LLM decides
  when to call (`create_knowledge_search_tool()`,
  `agno/agent/_default_tools.py`). `add_search_knowledge_instructions=True`
  (default) also injects a short system-prompt nudge
  (`_SEARCH_KNOWLEDGE_INSTRUCTIONS`: *"You have a knowledge base you can
  search... Search before answering... For ambiguous questions, search first
  rather than asking for clarification."*). This is the LLM-in-the-loop /
  "agent decides to search" pattern.
- **Traditional RAG** — `Agent(add_knowledge_to_context=True)`. On every user
  message, `get_relevant_docs_from_knowledge()` runs **unconditionally**
  (once per turn, keyed on the user message text as the query) and the
  results get appended directly into the user message content as an
  `<references>...</references>` block **before** the LLM ever sees the
  turn — no tool call, no LLM decision involved. This is the classic
  "always retrieve then generate" RAG pattern.
- Both flags route through the **same unified function**,
  `get_relevant_docs_from_knowledge()`/`aget_relevant_docs_from_knowledge()`
  (`agno/agent/_messages.py`), which is also where the custom retriever hook
  lives (next section) — so a custom `knowledge_retriever` transparently
  covers both agentic and traditional RAG without separate wiring.

### Custom retriever (`knowledge_retriever`)

`Agent(knowledge_retriever: Optional[Callable[..., Optional[List[Union[Dict,
str]]]]] = None)` — **when set, this function REPLACES both the default
`search_knowledge_base` tool logic AND the traditional-RAG retrieve path**;
`Knowledge.search()` is never called. `get_relevant_docs_from_knowledge()`
checks `agent.knowledge_retriever is not None and callable(...)` first,
before falling back to the knowledge protocol's `retrieve()`.

Signature is introspected via `inspect.signature()` and called with whatever
subset of these params the function actually declares (duck-typed, not a
fixed signature):

```python
def knowledge_retriever(
    agent: Agent,             # included only if "agent" is a param name
    query: str,                # always passed
    num_documents: Optional[int],  # always passed
    filters: ...,               # included only if "filters" is a param name
    run_context: RunContext,    # included only if "run_context" is a param name
    # OR, for backward compat:
    dependencies: ...,          # included only if "run_context" absent but "dependencies" present
    **kwargs,
) -> Optional[List[Union[Dict[str, Any], str]]]:
    ...
```

Async support: the async path (`aget_relevant_docs_from_knowledge`) calls the
same retriever and, if the return value `isawaitable()`, awaits it — so one
retriever function can serve both sync and async agent runs as long as it
returns a coroutine when called from async context. Exceptions inside a
custom retriever are logged and **re-raised** (unlike `Knowledge.search()`,
which swallows errors and returns `[]`) — a custom retriever failure is
treated as a real failure, not a soft "no results."

### `update_knowledge` — write-back tool

`Agent(update_knowledge: bool = False)`. When `True` (and a `knowledge` is
resolved), adds `agent.add_to_knowledge` as a tool
(`agno/agent/_tools.py`, gated on `resolved_knowledge is not None and
agent.update_knowledge`). Implementation
(`agno/agent/_default_tools.py::add_to_knowledge`):

```python
def add_to_knowledge(agent: Agent, query: str, result: str) -> str:
    document_name = query.replace(" ", "_")...  # sanitized
    document_content = json.dumps({"query": query, "result": result})
    insert_fn(name=document_name, text_content=document_content, reader=TextReader())
    return "Successfully added to knowledge base"
```

Lets the LLM **write new content back into its own knowledge base** —
literally `{"query": ..., "result": ...}` JSON blobs inserted as text
content via `TextReader`. This is a self-updating-knowledge / "remember what
I just learned or looked up" pattern, distinct from `Knowledge.insert()`
being called by application code — here the *agent itself* decides what's
worth persisting. Worth flagging for anyone building an agent with
`update_knowledge=True`: there's no dedup/upsert-by-semantic-similarity
here, just a fresh `insert()` per call — repeated similar queries will
create near-duplicate knowledge entries over time unless the caller adds its
own guardrails.

## Part 12 — Vector DB backends (deep detail)

See Part 10's table for the search-type/filter-pushdown summary; this
section is constructor-level and schema-level detail, gathered via a
source-reading sub-agent pass over `agno/vectordb/*` plus my own spot-checks
of `agno/vectordb/milvus/milvus.py`.

**[DOC-CONFIRMED] The sitemap shows 19 vector-store backends** (not the 6
the checklist listed): Azure Cosmos DB MongoDB vCore, Cassandra, Chroma,
ClickHouse, Couchbase, LanceDB, LangChain, LightRAG, LlamaIndex, Milvus,
MongoDB, PgVector, Pinecone, Qdrant, Redis, SingleStore, SurrealDB, Upstash,
Weaviate — each with its own `overview` + one-or-more `usage/*` pages (see
Coverage for the full URL list). The live `knowledge/vector-stores` index
page's one-line descriptions were fetched but are shallow (e.g. *"Milvus
open-source vector database"*) and don't cover schema/search-type/filter
mechanics — **every backend overview page fetched this session
(Milvus/pgvector/LanceDB/SurrealDB) referenced a separate, not-included
`vectordb_*_params.mdx` snippet file for full constructor parameters**, and
none of the fetched overview pages discussed collection schema, fusion
mechanism detail (beyond the separate `hybrid-search` concept page, see
discrepancy #1), or filter push-down mechanics in the returned excerpts.
This is a genuine, confirmed doc-depth gap for exactly the internals this
platform most needs (Milvus schema/filter/rerank-hook specifics) — the
detail in this section is source-only and fills that gap; it was not
possible to confirm or contradict it against doc prose beyond the
constructor-level basics shown below.

### Milvus (`agno/vectordb/milvus/milvus.py`) — our production backend

`Milvus(collection, name=None, description=None, id=None, embedder=None,
distance=Distance.cosine, uri="http://localhost:19530", token=None,
search_type=SearchType.vector, reranker=None, sparse_vector_dimensions=10000,
**kwargs)` — `**kwargs` pass straight through to `MilvusClient`/
`AsyncMilvusClient`. `distance` maps `cosine→COSINE, l2→L2,
max_inner_product→IP`. Our `create_knowledge()` passes `search_type=
SearchType.hybrid` explicitly (the constructor default is plain `vector`).

Schema details, hybrid mechanism, filter push-down, and reranker hook: see
Open Questions (a)/(b)/(d) above — not repeated here. `[DOC-CONFIRMED,
constructor-level only]` the live `milvus/overview` and
`milvus/usage/milvus-db-hybrid-search` pages confirm `collection`, `uri`
(supports Milvus Lite local-file mode like `"./milvus.db"`, a server
address, or Zilliz Cloud), `token`, and `search_type=SearchType.hybrid` as
shown constructor usage, plus *"Milvus also supports asynchronous
operations"* (`ainsert()`/async agent runs) — consistent with source, no
conflict, just doesn't go deeper than this in the fetched excerpts.

### pgvector (`agno/vectordb/pgvector/pgvector.py`)

`PgVector(table_name, schema="ai", name=None, description=None, id=None,
db_url=None, db_engine=None, embedder=None, search_type=SearchType.vector,
vector_index=HNSW(), distance=Distance.cosine, prefix_match=False,
vector_score_weight=0.5, content_language="english", schema_version=1,
auto_upgrade_schema=False, reranker=None, create_schema=True,
similarity_threshold=None)` — requires `db_url` or `db_engine`. Table (v1):
`id` (PK), `name`, `meta_data` (JSONB), `filters` (JSONB — a second,
separate JSONB column from `meta_data`), `content` (TEXT), `embedding`
(`Vector(dimensions)`), `usage` (JSONB), `created_at`/`updated_at`,
`content_hash`, `content_id`; indexes on `id`/`name`/`content_hash`/
`content_id`. `create()` also issues `CREATE EXTENSION IF NOT EXISTS
vector`. Keyword search: `to_tsvector(content_language, content)` vs.
`websearch_to_tsquery` (or `to_tsquery ... :*` per token when
`prefix_match=True`), ranked by `ts_rank_cd`. Not our production backend
(session.py's docstring: "pgvector remains in the PG image but is NO LONGER
the Knowledge store") but relevant as the only backend with full
`FilterExpr` support and true server-side hybrid scoring. `[DOC-CONFIRMED]`
live `pgvector/overview` confirms `table_name`/`db_url`/`search_type`
constructor usage and async support (`ainsert()`); does not discuss the
weighted-combination-vs-RRF distinction (that's covered separately by the
`hybrid-search` concept page — see discrepancy #1) or filter mechanics in
the fetched excerpt.

### LanceDB (`agno/vectordb/lancedb/lance_db.py`)

`LanceDb(uri="/tmp/lancedb", name=None, description=None, id=None,
connection=None, table=None, async_connection=None, async_table=None,
table_name=None, api_key=None, embedder=None, search_type=SearchType.vector,
distance=Distance.cosine, nprobes=None, reranker=None, use_tantivy=False,
on_bad_vectors=None, fill_value=None)` — supports LanceDB Cloud (`db://...`
URI + `api_key`). Table has only 3 columns: `vector`, `id`, `payload`
(single JSON blob holding `name`/`meta_data`/`content`/`usage`/
`content_id`/`content_hash` — see discrepancy #6 for the filtering
implication). `[DOC-CONFIRMED]` live `lancedb/overview` confirms
`table_name`/`uri`/`search_type` constructor usage — its own example uses
`SearchType.keyword` specifically (not hybrid) — and async support; filter
mechanics not discussed in the fetched excerpt.

### SurrealDB — two unrelated integrations, don't conflate

`agno/db/surrealdb/surrealdb.py` is the **session/memory/operational `Db`
backend** (what our stack uses via `get_agno_db()` for sessions, memory,
metrics, culture, traces/spans — see `server/core/session.py`).
`agno/vectordb/surrealdb/surrealdb.py` is a **separate, genuine `VectorDb`
implementation** — `SurrealDb(client=None, async_client=None,
collection="documents", distance=Distance.cosine, efc=150, m=12,
search_ef=40, embedder=None, name=None, description=None, id=None)`, no
`search_type` param at all (vector-only, via SurrealQL's native `<|k,ef|>`
KNN operator + an HNSW index), no `reranker` param. Our stack does not use
this vectordb variant (Milvus is the vector substrate; SurrealDB is
operational-only per ADR-0026/0027). `[DOC-CONFIRMED]` live
`surrealdb/overview` shows `client`/`async_client`/`collection`/`efc`/`m`/
`search_ef` constructor params — matches source; doesn't show a
`search_type` param either (consistent with source's finding that SurrealDB
has no `SearchType` concept at all).

### LangChain / LlamaIndex adapters

**[DOC-CONFIRMED, genuine doc gap]** Both `knowledge/vector-stores/
langchain/overview` and `knowledge/vector-stores/llamaindex/overview` are
literal **"TBD" stub pages** on the live site — no constructor details,
code examples, or NotImplementedError caveats are documented anywhere for
either adapter. Everything below is source-only.

`LangChainVectorDb` (`agno/vectordb/langchaindb/langchaindb.py`) wraps a
LangChain `vectorstore`/retriever; `create/insert/upsert/drop/delete*` all
raise `NotImplementedError` — ingestion must happen outside Agno directly
against the LangChain vectorstore, Agno only wraps `search()` (builds a
`BaseRetriever` via `vectorstore.as_retriever(search_kwargs={"k": limit,
**filters})`). `LlamaIndexVectorDb` (`agno/vectordb/llamaindex/
llamaindexdb.py`) wraps a LlamaIndex `BaseRetriever` directly (constructor
requires `knowledge_retriever` — note: same param name as `Agent`'s custom
retriever hook but an unrelated concept here, just a constructor arg name
collision); same `NotImplementedError` pattern for all write ops, `search()`
is `retriever.retrieve(query)` sliced to `limit` in Python, filters entirely
unsupported. Both adapters exist for "I already have a LangChain/LlamaIndex
vector store, let Agno read from it" migration scenarios, not for new Agno-
native knowledge bases.

### LightRAG (`agno/vectordb/lightrag/lightrag.py`)

Not a schema/search vector database in the usual sense — an HTTP client
shim to an external LightRAG server (`DEFAULT_SERVER_URL =
"http://localhost:9621"`, optional API key header). `insert`/`upsert` on the
`VectorDb` interface are **no-ops**; real ingestion happens via LightRAG's
own file-upload endpoints (which is why `Knowledge._load_from_path`/
`_load_from_url` special-case `vector_db.__class__.__name__ == "LightRag"`
and route to `_process_lightrag_content()` instead of the normal reader→
chunk→insert pipeline, as noted in Part 2).

## Part 13 — Cloud storage sources

`RemoteContent = Union[S3Content, GCSContent, SharePointContent,
GitHubContent, AzureBlobContent]` (`agno/knowledge/remote_content/
remote_content.py`) — passed to `Knowledge.insert(remote_content=...)`.
Each has a small typed constructor with mutual-exclusivity validation (e.g.
`S3Content` requires exactly one of `key`/`object`/`prefix`, and exactly one
of `bucket_name`/`bucket`).

`content_sources: Optional[List[BaseStorageConfig]]` on `Knowledge` holds
**pre-registered, reusable connection configs** (`S3Config`,
presumably `GCSConfig`/`SharePointConfig`/`GitHubConfig`/`AzureBlobConfig`
siblings under `agno/knowledge/remote_content/`), each with a `list_files()`
method supporting pagination against the provider's native API (S3's example
uses continuation-token pagination, fetching only the objects needed for the
requested page rather than loading the whole bucket listing into memory).
`RemoteKnowledge` (the mixin `Knowledge` inherits) composes five
provider-specific `*Loader` mixins (`S3Loader`, `GCSLoader`,
`SharePointLoader`, `GitHubLoader`, `AzureBlobLoader`) that implement the
actual fetch-and-load-into-`insert()` glue per provider.

Our stack does not currently use any `RemoteContent`/cloud-storage source —
ingestion goes through local file paths written by
`server/evidence/store.py` (`render_conversations_markdown()` writes derived
`.md` files under `knowledge/platform/transcripts/`, then `knowledge.
ainsert(path=str(doc_path), ...)`), not direct cloud reads. Worth knowing
this exists if R2-direct ingestion is ever considered instead of the
write-local-then-insert pattern.

## Part 14 — Performance tips

**[DOC-CONFIRMED]** The live `knowledge/concepts/performance-tips` page
gives concrete guidance beyond what's inferable from source alone:

- **Vector DB selection by scale**: *"LanceDB/ChromaDB"* for dev (zero
  setup), *"PgVector"* for production up to ~1M documents needing SQL,
  managed/auto-scaling services (e.g. Pinecone) beyond that. Not a
  head-to-head benchmark, just a rough sizing heuristic — doesn't cover
  Milvus explicitly in the fetched excerpt (our backend is presumably in
  the "needs to scale past what a single Postgres box handles well"
  bucket, consistent with ADR-0026/0027's stated rationale for choosing
  it).
- **"Filter first, then search"** — apply metadata filters to narrow scope
  *before* the vector search runs, not as a post-filter. This matches how
  Milvus (server-side `_build_expr`) and pgvector (server-side SQL WHERE)
  actually execute it — but is the opposite of what happens on LanceDB
  (discrepancy #6, filters applied *after* `.limit()` truncation client-side)
  — worth knowing the tip doesn't hold uniformly across backends.
- **Chunking strategy tradeoffs**: fixed-size for speed on uniform content,
  semantic for quality on complex documents, recursive as a balance between
  the two — consistent with, and a shorter restatement of,
  `docs/planning/agno-chunking-strategy.md`'s own recommendations (not
  contradicted).
- **Reduce embedding dimensions for faster search with minimal quality
  loss** — directly relevant if our 1024-d bge-m3 / 1536-d codestral-embed
  collections ever need a speed/storage tradeoff; not something we've
  tuned.
- **Async batch operations via `asyncio.gather()`** to load multiple
  sources concurrently — consistent with, not contradicting, the
  source-derived async-everywhere point below.

Source-derived tips (not covered on the fetched doc page, or covered only
partially):

- **Batch embeddings on bulk ingestion.** `Embedder.enable_batch` (default
  `False`) gates whether the async insert path uses
  `embedder.async_get_embeddings_batch_and_usage()` (chunks of
  `embedder.batch_size`, default 100) instead of one embedding API call per
  document/chunk — confirmed wired into `Milvus`'s async insert/upsert paths
  (`if self.embedder.enable_batch and hasattr(self.embedder,
  "async_get_embeddings_batch_and_usage")`). **Our `_embedder()` helper in
  `server/core/session.py` does not set `enable_batch=True`** — for bulk
  ingestion jobs like `scripts/ingest_knowledge.py`, adding
  `enable_batch=True` (and tuning `batch_size`) to the embedder construction
  would collapse N per-chunk OpenRouter calls into N/100 batch calls, a
  meaningful latency/cost win with no data-shape changes required.
- **`skip_if_exists` short-circuits before reading/chunking/embedding.**
  `Knowledge._should_skip()` checks `vector_db.content_hash_exists()`
  *before* any reader/chunker/embedder work happens on the path/URL/content
  branches — re-running an ingestion script over a directory that's mostly
  already indexed is cheap if `skip_if_exists=True`, expensive (re-embeds
  everything) if left at the `upsert=True` default.
- **`get_valid_filters()` is O(all content) per call, and gets called on
  every `build_context()` when agentic filters are enabled** (Part 7) — for
  a knowledge base with many content rows, this re-scans all of them via
  `get_content()` on every agent turn that builds a system prompt with
  agentic filters on. Not currently a problem at our content volumes, but
  worth remembering as a scaling concern before agentic filters get enabled
  broadly.
- **Async everywhere it's available.** `ainsert`/`ainsert_many`/`asearch`
  are the async-first paths and are what `server/evidence/store.py`'s
  `ingest_into_knowledge()` already uses (`await knowledge.ainsert(...)`
  per conversation) — consistent with the async-batch-embedding point above.
- **Milvus non-hybrid insert has no explicit schema** (Part 12/Open Question
  b) — irrelevant to us since we always use hybrid, but worth remembering if
  a future collection is ever created with `search_type=vector` instead:
  dynamic-field inserts have less validation than the explicit hybrid
  schema.
- **`remove_all_content()` deletes one item at a time**, no bulk-delete
  path — a full knowledge-base wipe-and-reingest is O(n) individual delete
  calls against both `vector_db` and `contents_db`, not a single `DROP`/
  `TRUNCATE`. For a full rebuild, `vector_db.drop()` +
  `vector_db.create()` (or dropping the Milvus collection directly) is
  faster than `remove_all_content()` if the contents_db rows can be
  wiped separately (e.g. `TRUNCATE {table_name}_contents`).

## Part 15 — Agents/teams-with-knowledge; distributed RAG

**[DOC-CONFIRMED]** `knowledge/agents/overview` (live page) lays out the
same three integration methods as Part 11, in the docs' own words:

1. **"Search-Based (Default)"** — `search_knowledge=True` adds a
   `search_knowledge_base()` tool.
2. **"Context-Based"** — `add_knowledge_to_context=True` implements
   "traditional RAG, automatically injecting relevant knowledge references
   into agent context based on user messages."
3. **"Custom Retrieval"** — a `knowledge_retriever` function with the
   signature `knowledge_retriever(agent: Agent, query: str, num_documents:
   Optional[int], **kwargs) -> Optional[list[dict]]` (doc's simplified
   published signature omits `filters`/`run_context`/`dependencies` as
   named params, but source's `inspect.signature()`-driven introspection
   supports all of them by name when declared — the doc shows the minimal
   form, source supports a richer one via `**kwargs` and introspection, not
   a contradiction). Also confirms *"Both synchronous and async retrievers
   are supported."*

It also restates the contents-db/vector-db split (Part 9) and the
insert-time pipeline: *"Parse the content, Chunk the information, Embed
each chunk."*

`knowledge/teams/overview` (live page) confirms teams use knowledge
"identically to agents," and calls out `isolate_vector_search` specifically
for *"sharing a vector database across teams or tenants"* — consistent
with Open Question (c)'s finding that `linked_to` is a multi-instance
sharing tool.

**`knowledge/teams/distributed-rag-lancedb` (live page, fetched) —
concrete evidence for the per-domain-collection direction**: Agno's own
official distributed-RAG team example is a **4-agent pipeline** (primary
retriever → context expander → answer synthesizer → quality validator)
where isolation between the two knowledge-bearing agents is achieved via
**two separate LanceDB tables** (`recipes_primary`, vector search;
`recipes_context`, hybrid search) — **not** `isolate_vector_search`/
`linked_to` on a shared table. Only the two retrieval-role agents get
`search_knowledge=True`; the synthesizer and validator have no direct
knowledge access and only process the upstream agents' outputs
sequentially. This is the strongest available confirmation (official
example, not inference) that "separate collections per partition" is
Agno's own preferred pattern for exactly the kind of split this platform
is planning next (legal/code/timeline vector DBs) — reinforcing Open
Question (c)'s conclusion.

---

## Our-stack summary (annotations consolidated)

We run **one `Knowledge` instance** per collection
(`server/core/session.py::create_knowledge(name, table_name,
use_code_embedder)`), called for the platform-wide `platform_knowledge`
Milvus collection:

- **Vector DB**: `Milvus(collection=table_name, uri=MILVUS_URI,
  token=MILVUS_TOKEN, search_type=SearchType.hybrid, embedder=embedder)` —
  hybrid = native RRF (dense IVF_FLAT + Agno's hashed-pseudo-TF-IDF sparse),
  `k=60` hardcoded, no `reranker=` set.
- **Contents DB**: `PostgresDb(knowledge_table=f"{table_name}_contents")` —
  metadata/status bookkeeping only, separate from the Milvus vectors
  (ADR-0026/0027 split).
- **Embedder**: `OpenAIEmbedder` (base class, not `OpenAILikeEmbedder`)
  pointed at OpenRouter (`base_url=https://openrouter.ai/api/v1`),
  symmetric models only. Text lane: `baai/bge-m3`, 1024-d. Code lane:
  `mistralai/codestral-embed-2505`, 1536-d, **separate collection**
  (ADR-0010: one collection per embedder — dimension is fixed at Milvus
  collection creation, changing embedder = drop + recreate).
  `enable_batch` is not set (Part 14 performance gap).
- **Domain isolation**: plain metadata tagging
  (`metadata={"domain": "timeline_relationship"|"personal_history"|
  "platform_design"|"legal_strategy", ...}` at insert,
  `server/evidence/store.py::ingest_into_knowledge`), filtered at query time
  via dict `knowledge_filters` — this is the **correct** mechanism given
  Milvus only supports dict filters server-side (Open Question a) and
  `linked_to`/`isolate_vector_search` can't express multi-domain queries
  (Open Question c). `isolate_vector_search` is not (and should not be) set.
- **Ingestion shape**: transcripts re-rendered to per-conversation markdown,
  written to `knowledge/platform/transcripts/`, then `await knowledge.
  ainsert(path=..., metadata={"domain": ..., ...})` — local-file-then-insert,
  not `RemoteContent`/cloud-source ingestion (Part 13).
- **Planned next build** (per this task's framing): per-domain vector DBs
  (legal/code/timeline) with specialized embedders + hybrid semantic+fixed
  chunking. Given Open Question (c)'s finding, the natural mechanism for
  that split is **separate Milvus collections per domain** (new
  `create_knowledge()` calls with different `table_name`/`embedder`), each
  with its own `contents_db` table — not `linked_to`/`isolate_vector_search`
  on a shared collection, and not a switch away from the existing dict-based
  domain metadata pattern for any domain that still needs sub-filtering
  within its own collection.

---

## Coverage

### Sourcing method

The `claude.ai agno` docs MCP (assigned primary tool) never connected this
session despite many retries — confirmed dead platform-wide (all sibling
researchers hit the same failure, per coordinator). Fallback used instead:
`curl https://docs.agno.com/sitemap.xml | grep '/knowledge/'` to enumerate
the real page tree (below), then `WebFetch` on the highest-value subset,
then source verification for everything else.

### Floor checklist (`_url-checklist.md` `knowledge` section, 32 URLs)

- [x] https://docs.agno.com/knowledge/agents/agentic-rag-lancedb — not fetched, source-only (Part 11/15)
- [x] https://docs.agno.com/knowledge/agents/agentic-rag-pgvector — **fetched**, quoted in Part 15/discrepancy #2
- [x] https://docs.agno.com/knowledge/agents/overview — **fetched**, quoted in Part 15
- [x] https://docs.agno.com/knowledge/agents/traditional-rag-lancedb — not fetched, source-only
- [x] https://docs.agno.com/knowledge/agents/traditional-rag-pgvector — **fetched**, quoted in Part 15/discrepancy #2
- [x] https://docs.agno.com/knowledge/concepts/chunking/fixed-size-chunking — pointer, intentionally not read (agno-chunking-strategy.md is authoritative)
- [x] https://docs.agno.com/knowledge/concepts/chunking/overview — pointer, intentionally not read
- [x] https://docs.agno.com/knowledge/concepts/chunking/semantic-chunking — pointer, intentionally not read
- [x] https://docs.agno.com/knowledge/concepts/cloud-storage — **fetched**, quoted in Part 13
- [x] https://docs.agno.com/knowledge/concepts/contents-db — **fetched**, quoted in Part 9 (exact match, zero drift)
- [x] https://docs.agno.com/knowledge/concepts/embedder/overview — **fetched**, quoted in Part 4
- [x] https://docs.agno.com/knowledge/concepts/filters/overview — **fetched**, quoted in Part 7/discrepancy #5
- [x] https://docs.agno.com/knowledge/concepts/isolate-vector-search — **fetched**, quoted in Part 8/Open Question (c)/discrepancy #7
- [x] https://docs.agno.com/knowledge/concepts/performance-tips — **fetched**, quoted in Part 14
- [x] https://docs.agno.com/knowledge/concepts/readers/overview — **fetched**, quoted in Part 3
- [x] https://docs.agno.com/knowledge/concepts/search-and-retrieval/agentic-rag — **fetched**, quoted in Part 11
- [x] https://docs.agno.com/knowledge/concepts/search-and-retrieval/custom-retriever — **fetched**, quoted in Part 11/15
- [x] https://docs.agno.com/knowledge/concepts/search-and-retrieval/hybrid-search — **fetched**, quoted in discrepancy #1 (most important finding this session)
- [x] https://docs.agno.com/knowledge/concepts/search-and-retrieval/keyword-search — not fetched, source-only (Part 10)
- [x] https://docs.agno.com/knowledge/concepts/search-and-retrieval/overview — **fetched**, quoted in Part 10/11
- [x] https://docs.agno.com/knowledge/concepts/search-and-retrieval/vector-search — not fetched, source-only (Part 10)
- [x] https://docs.agno.com/knowledge/concepts/vector-db — **fetched**, quoted in Part 12 intro
- [x] https://docs.agno.com/knowledge/overview — **fetched**, quoted in Part 1
- [x] https://docs.agno.com/knowledge/quickstart — **fetched**, quoted in Part 2/discrepancy #2
- [x] https://docs.agno.com/knowledge/teams/distributed-rag-lancedb — **fetched**, quoted in Part 15/Open Question (c) (key corroborating evidence)
- [x] https://docs.agno.com/knowledge/vector-stores — **fetched**, quoted in Part 12 intro
- [x] https://docs.agno.com/knowledge/vector-stores/lancedb/overview — **fetched**, quoted in Part 12
- [x] https://docs.agno.com/knowledge/vector-stores/langchain/overview — **fetched** — TBD stub, discrepancy #8
- [x] https://docs.agno.com/knowledge/vector-stores/llamaindex/overview — **fetched** — TBD stub, discrepancy #8
- [x] https://docs.agno.com/knowledge/vector-stores/milvus/overview — **fetched**, quoted in Part 12 (thin — see gap note)
- [x] https://docs.agno.com/knowledge/vector-stores/pgvector/overview — **fetched**, quoted in Part 12
- [x] https://docs.agno.com/knowledge/vector-stores/surrealdb/overview — **fetched**, quoted in Part 12

**22 of 32 fetched** (3 chunking pointers intentionally skipped; 7 not
fetched — 2 lancedb agent-pattern pages, 2 search-type detail pages,
1 agentic-rag-lancedb — all source-covered but not doc-cross-checked).

### Extras beyond the floor list — full sitemap enumeration

`curl https://docs.agno.com/sitemap.xml | grep '/knowledge/'` returned
**~300 URLs** under `/knowledge/`-adjacent paths — the 32-URL checklist was
indeed a floor, not the ceiling, confirmed. Full breakdown by section
(fetched pages marked; the rest are enumerated-but-not-read this session —
listing every one of ~280 remaining URLs individually would not be a good
use of remaining budget, so they're grouped):

- **`knowledge/vector-stores/*`** — **19 backends**, not 6: Azure Cosmos
  MongoDB vCore, Cassandra, Chroma, ClickHouse, Couchbase, LanceDB
  (fetched), LangChain (fetched, TBD stub), LightRAG, LlamaIndex (fetched,
  TBD stub), Milvus (fetched), MongoDB, PgVector (fetched), Pinecone,
  Qdrant, Redis, SingleStore, SurrealDB (fetched), Upstash, Weaviate. Each
  has an `overview` + 1-3 `usage/*` pages (async variant, hybrid-search
  variant where applicable) — ~45 URLs total in this subtree, 6 fetched.
- **`knowledge/agents/*`** — 5 URLs (all on the 32-checklist, 3 fetched).
- **`knowledge/teams/*`** — 4 URLs: `overview` (fetched, not on checklist),
  `team-with-knowledge` (not fetched), `distributed-rag-lancedb` (fetched),
  `distributed-rag-pgvector` (not fetched, not on checklist).
- **`knowledge/concepts/chunking/*`** — 10 URLs (pointer territory, not
  read — `agno-chunking-strategy.md` is authoritative).
- **`knowledge/concepts/embedder/*`** — 7 URLs: `overview` (fetched) +
  6 per-provider pages (cohere/gemini/mistral/ollama/openai/voyageai) not
  fetched.
- **`knowledge/concepts/readers/*`** — 9 URLs: `overview` (fetched) + 8
  per-reader pages (csv/docling/json/llms-txt/markdown/pdf/website/youtube)
  not fetched.
- **`knowledge/concepts/search-and-retrieval/*`** — 6 URLs, 4 fetched (all
  but keyword-search, vector-search).
- **`examples/knowledge/*`** — a large parallel tree (**~150+ URLs**) of
  runnable code examples: `chunking/*` (13), `cloud/*` (5), `custom-retriever/*`
  (4), `embedders/*` (19 — one per provider, confirms 19 embedder examples
  exist even though the concepts overview narrative only named 14),
  `filters/*` (10, including `vector-dbs/filtering-{chroma,lance,milvus,
  mongo,pgvector,pinecone,qdrant,surrealdb,weaviate}-db` — 9 backend-specific
  filter examples), `os/*` (2, incl. `multiple-knowledge-instances`),
  `protocol/*` (2 — the `KnowledgeProtocol` custom-implementation examples),
  `quickstart/*` (16, incl. `isolate-vector-search`, `batching`,
  `skip-if-exists-contentsdb`), `readers/*` (30+), `search-type/*` (3),
  `vector-db/*` (30+, organized per-backend like the main vector-stores
  tree). **None of this example tree was fetched this session** — it's the
  single biggest remaining gap for a follow-up pass, since runnable
  examples are usually the most reliable source of exact current API usage.
- **`reference/knowledge/*`** and **`reference-api/schema/knowledge/*`** —
  API-reference-generated pages (chunking strategies, embedders, readers,
  reranker, remote-content) — not fetched, lower priority since source
  already gives exact signatures.
- **`agent-os/knowledge/*`** and **`api-reference/knowledge/*`** — AgentOS
  product surface (REST endpoints for knowledge management: upload,
  search, filter, manage) — out of scope for this doc (covered by a
  different researcher lane per the platform's doc split, presumably).

### Follow-up priority if this doc gets revisited

1. `examples/knowledge/vector-db/milvus-db/*` (3 URLs) — actual runnable
   Milvus code, would directly confirm/refute the schema and RRF details in
   Part 12/Open Questions (a)/(b)/(d), which are currently source-only.
2. `examples/knowledge/filters/vector-dbs/filtering-milvus` — would
   directly confirm/refute discrepancy #5 (Milvus `List[FilterExpr]`
   silently dropped) with an actual doc example rather than source-only.
3. `knowledge/concepts/search-and-retrieval/{keyword-search,vector-search}`
   — the only two checklist-floor pages not yet fetched.
4. `examples/knowledge/os/multiple-knowledge-instances` — would likely be
   the canonical `isolate_vector_search` worked example, strengthening
   Open Question (c).
