# Lane 3 — Search and Vector State Inventory (Evidence-Only)

> _Byline: lane-3 agent · Sonnet · 2026-08-24_

Repo: `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform`
Live systems probed: Weaviate `100.91.190.107:8081` and `:8082`; PostgreSQL 18 `100.91.190.107:5432` db `ai` (read-only, `.env` creds).
Rule for this document: every claim is either a `file:line` citation or a live query/HTTP result recorded verbatim below. Anything not directly observed is marked **UNKNOWN — not verified**.

---

## 1. Full-text search on the spine

**Live confirmation** — `pg_indexes` query against `working.normalized_record` (PG18, db `ai`, run 2026-08-24):

```
idx_normrec_fts   CREATE INDEX idx_normrec_fts ON working.normalized_record USING gin (to_tsvector('english'::regconfig, COALESCE(content, ''::text)))
idx_normrec_trgm  CREATE INDEX idx_normrec_trgm ON working.normalized_record USING gin (content gin_trgm_ops)
```

Both indexes exist live, confirmed by direct `pg_indexes` query, not just by reading a migration file.

- **What populates it**: `idx_normrec_fts` is a plain **functional/expression GIN index** directly on `to_tsvector('english', COALESCE(content,''))` — there is **no** generated/stored `tsvector` column on `working.normalized_record` (confirmed via `information_schema.columns` — the table has no `fts` column) and **no trigger**. PostgreSQL maintains the expression index automatically on every INSERT/UPDATE of `content`; nothing application-level "populates" it. Compare this to `public.memory_items`/`public.session_summaries`, which DO use a generated stored column (`sql/bootstrap/schema_baseline.sql:6300`, `:6437`, `fts tsvector GENERATED ALWAYS AS (...) STORED`) — the spine table uses the older functional-index style, not that pattern.
- **Provenance gap**: `idx_normrec_fts` and `idx_normrec_trgm` do **not** appear in any numbered migration file under `sql/0001_*.sql`–`sql/0032_*.sql` (grepped all of them — zero hits). They exist only in `sql/bootstrap/schema_baseline.sql:11539` and `:11574`, which is a `pg_dump --schema-only` capture of the live database (header at `sql/bootstrap/schema_baseline.sql:1-5`, captured 2026-08-10 per `scripts/capture_bootstrap_ddl.py`). So these two indexes were applied to the live DB out-of-band (direct DDL), not through the tracked migration chain — confirmed live via `pg_indexes`, but their creation has no migration-file citation.
- **What the HTTP handler actually does instead**: `GET /v1/records?q=` does **not** use either index. It does a plain substring scan:
  `server/api/inspect_routes.py:262` — `where.append("nr.content ILIKE :q")`, with `params["q"] = f"%{q}%"` (`server/api/inspect_routes.py:263`). A leading-wildcard `ILIKE '%...%'` cannot use `idx_normrec_fts` (tsvector) or `idx_normrec_trgm` (trigram — trigram COULD accelerate this pattern via `%` operator but the route uses `ILIKE`, not `%`/`similarity()`, so the trigram index is also not engaged by this specific query). The GIN indexes exist and are live, but this specific handler bypasses both.
- **Row count**: `working.normalized_record` currently has **0 rows** live (`SELECT count(*)` → `0`), so today none of this — index or ILIKE — has any data to operate over.
- **pg_trgm fuzzy capability**: `pg_extension` confirms `pg_trgm` version `1.6` is installed (see §6). It is applied to `working.normalized_record.content` via `idx_normrec_trgm` (above), and to ~14 other columns across the schema (entity names, handles, locations, filenames, timeline titles — full list in §6), so trigram fuzzy matching capability exists broadly, independent of whether any current HTTP route calls it.

---

## 2 & 3. Weaviate live truth vs. the planned native `EvidenceChunkV1` collection

### Two reachable Weaviate instances, byte-identical content

- `http://100.91.190.107:8081` — `GET /v1/meta` → HTTP 200, Weaviate `1.38.7`. This is `deploy/data-weaviate.yaml`, the app's live source.
- `http://100.91.190.107:8082` — also HTTP 200, same version. This is `deploy/data-weaviate-native-v1.yaml` ("blue" side-by-side instance; default `BIND_IP` in that file is `127.0.0.1`, but it answered on the tailnet IP, so the deployed instance's bind differs from the file's default — **UNKNOWN — not verified** whether that's an env override in Coolify or a stale file).
- `GET /v1/schema` on both ports returned the **same 7 classes with identical property definitions**, including identical Weaviate auto-schema generation timestamps down to the second (e.g. both show `Platform_context.filters` generated "Sat Aug 1 22:01:12 2026"). `GraphQL Aggregate{...{meta{count}}}` returned identical counts on both ports for every class.
- This is **documented, not a bug**: `docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md:6-30` records an owner-authorized "full legacy/custom instance clone to blue" — 8081 is the preserved live source, 8082 is a create-only replay copy built by `scripts/migrate_weaviate_instance.py`, done to stage a future cutover. The runbook's own recorded counts (`Platform_context` 2,790, `Legal_knowledge` 30, `Personal_history_knowledge` 1, `Platform_knowledge` 213, `Evidence_knowledge` 0, `Relationship_timeline_knowledge` 1, `Platform_code_knowledge` 0) match exactly what this audit's live GraphQL aggregate query returned on both ports today. The application still points only at 8081; no alias/cutover has happened.

### Live schema — all 7 classes, properties with types, object counts

Base properties on every class (Agno's Weaviate knowledge-doc shape): `name` (text, `word`), `content` (text, `lowercase`), `meta_data` (text, `word`), `content_id` (text, `word`), `content_hash` (text, `word`). All classes: `vectorizer: "none"` (self-provided/BYO vectors), `vectorIndexType: "hnsw"`, distance `cosine`. Raw schema JSON saved alongside this report: `docs/research/integration-audit-2026-08-24/_raw_weaviate_8081_schema.json` and `_raw_weaviate_8082_schema.json`.

| Class | Live count | Nested `filters` properties (name: type) | Relates to |
|---|---|---|---|
| `Platform_context` | **2,790** | `content_hash`:text, `disclaimer`:text, `source`:text, `conversation_id`:**uuid**, `conversation_title`:text, `chunk_index`:**number**, `message_count`:**number**, `tier`:text, `occurred_at_start`:**date**, `occurred_at_end`:**date**, `case_id`:text, `lane`:text, `doc_type`:text | chat/context knowledge |
| `Personal_history_knowledge` | 1 | `lane`:text, `doc_type`:text, `source`:text, `case_id`:text | personal-history knowledge |
| `Legal_knowledge` | 30 | `lane`:text, `doc_type`:text, `source`:text, `case_id`:text | legal reference knowledge |
| `Platform_knowledge` | 213 | `lane`:text, `doc_type`:text, `source`:text, `case_id`:text, `knowledge_actor`:text, `knowledge_time`:**date**, `knowledge_time_epoch`:**number**, `artifact_id`:**uuid**, `sha256`:text, `conversation_id`:text, `disclosure_tier`:text, `record_count`:**number** | platform/evidence-adjacent knowledge |
| `Evidence_knowledge` | 0 | *(none — auto-schema never generated a `filters` object; no evidence objects have ever been written)* | evidence (empty) |
| `Relationship_timeline_knowledge` | 1 | `case_id`:text, `lane`:text, `doc_type`:text, `source`:text | timeline knowledge |
| `Platform_code_knowledge` | 0 | *(none)* | code knowledge (empty) |

**Epoch-field finding (item 2's core question)**: numeric timestamp properties **do already exist live** — `Platform_knowledge.filters.knowledge_time_epoch` (`number`) alongside `Platform_knowledge.filters.knowledge_time` (`date`). No other class has an epoch/numeric-timestamp field: `Platform_context` has `occurred_at_start`/`occurred_at_end` as **date only** (no epoch companion), and `Relationship_timeline_knowledge` — despite its name — has **no date or epoch field of any kind** in its live schema (only `case_id`/`lane`/`doc_type`/`source`). `Evidence_knowledge` and `Platform_code_knowledge` have no `filters` object at all (never received a write with metadata beyond the base 5 properties).

### The planned native collection vs. live absence

Designed schema: `server/core/evidence_vector_store.py:130-187`, function `evidence_vector_properties()`. Key fields: `chunk_id` (uuid), `artifact_id` (uuid), `source_sha256`/`case_id`/`disclosure_tier`/`source_kind`/`projection_kind`/`authority_state` (text), `source_availability_complete` (bool), `occurred_at` (date), `source_available_from` (date, range-filterable), **`source_available_from_epoch` (INT, range-filterable — `server/core/evidence_vector_store.py:170-175`)**, `normalized_record_id` (uuid), `conversation_id`/`chunker_id`/`embed_model`/`embedder_version`/`projection_version`/`projection_hash`/`content_hash`/`source_content_hash` (text), `embed_dimension` (int), `content` (text, searchable). Collection name `EvidenceChunkV1` (`server/core/evidence_vector_store.py:22`), stable alias `EvidenceChunks` (`:23`), vectors self-provided (`Configure.Vectors.self_provided()`, `:204`), designed for `nvidia/nv-embed-v1` / 4096-d (`:24-25`).

Runbook status: `docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md:1-8` — filed as a **"HELD runbook"**: "Native `EvidenceChunkV1` is still held behind PostgreSQL migrations `0026`–`0029` and its separate evidence canaries."

**Confirmed live absence** (this audit, 2026-08-24):
- `GET /v1/schema/EvidenceChunkV1` → **HTTP 404** on both `:8081` and `:8082`.
- `GET /v1/aliases` on `:8081` → `{"aliases":[]}` — `EvidenceChunks` alias does not exist.
- Neither collection appears in the 7-class `/v1/schema` listing above.

**PostgreSQL-side readiness is further along than the runbook's "held" framing suggests** — confirmed live:
- `working.normalized_record_chunk` table: **exists** (0 rows).
- `working.evidence_vector_projection_job` table: **exists** (0 rows — nothing queued).
- Function `working.enqueue_evidence_vector_projection(uuid[],text)`: **exists**.
- Function `working.source_available_from(uuid)`: **exists**.

So migrations `0026`–`0029` (the tables/functions `server/evidence/vector_projection.py` depends on) are applied live, matching `sql/README.md`'s 2026-08-23 amendment that `0026`–`0029` were found already applied on live introspection. What remains undone per the runbook and confirmed by this audit: the Weaviate-side `EvidenceChunkV1` collection has not been created, no chunks exist in `working.normalized_record_chunk` to project, and the projection queue is empty — i.e., PG plumbing is live but nothing has been chunked or projected yet.

---

## 4. Embedder wiring (model/provider per write path — names and lengths only, no values)

Two independent write paths use the **same text-embedding model and dimension**:

- **Legacy Agno-knowledge pour** (the 7 classes above): `server/core/session.py:231-232` — `EMBED_TEXT_ID = getenv("EMBED_TEXT_ID", "nvidia/nv-embed-v1")`, `EMBED_TEXT_DIM = int(getenv("EMBED_TEXT_DIM", "4096"))`. Code path is symmetric OpenAI-compatible (`_embedder()`, `:237-251`) hitting NVIDIA NIM directly by default (`_NVIDIA_BASE_URL = getenv("NVIDIA_BASE_URL", "https://integrate.api.nvidia.com/v1")`, `:216`), not through the Portkey gateway (explicitly noted as a TODO at `:195-213`). A second, code-specific embedder exists: `EMBED_CODE_ID = getenv("EMBED_CODE_ID", "mistralai/codestral-embed-2505")`, dim 1536 (`:233-234`), routed to OpenRouter by default.
- **Native evidence-vector path** (designed, not yet live): `server/core/evidence_vector_store.py:24-25` — hardcoded constants `EVIDENCE_EMBED_MODEL = "nvidia/nv-embed-v1"`, `EVIDENCE_EMBED_DIM = 4096`, enforced by a hard `ValueError` in `EvidenceVectorDocument.properties()` (`:90-93`) if a caller supplies a different model/dim.
- An older asymmetric-NIM shim also exists (`server/core/embedder.py`, `NimEmbedder`, `:1-64`) for PgVector-specific query/passage-mode splitting — this is documented as NIM's asymmetric-embedqa behavior, not used by the two paths above (both of which are the symmetric `nv-embed-v1` model per the module's own comment at `server/core/session.py:240-242`, "Symmetric => the same vector space for documents and queries").

`.env` key names present (values not printed, character lengths only): `NVIDIA_API_KEY` (len 70), `NVIDIA_BASE_URL` (len 35), `NVIDIA_EMBED_TEXT_ID` (len 36), `NVIDIA_EMBED_TEXT_DIM` (len 4), `NVIDIA_EMBED_CODE_ID` (len 25), `NVIDIA_RERANK_ID` (len 27). **Note**: the code in `server/core/session.py:231-234` reads `EMBED_TEXT_ID`/`EMBED_TEXT_DIM`/`EMBED_CODE_ID` (no `NVIDIA_` prefix) — none of those exact names are set in `.env`, only the `NVIDIA_`-prefixed variants, which the code does not read. So the running config falls through to the hardcoded defaults (`nvidia/nv-embed-v1`, 4096; `mistralai/codestral-embed-2505`, 1536) rather than being driven by the `NVIDIA_EMBED_*` values in `.env` — **this is a live env-var-name mismatch, confirmed by reading both files side by side; not confirmed against the actually-running process's resolved env** (UNKNOWN whether Coolify injects a differently-named override at deploy time).

---

## 5. Chunking

- Chunker implementation: **Chonkie**, wrapped as an Agno `ChunkingStrategy` — `server/analysis/chonkie_chunkers.py:41-80`, class `ChonkieChunkingStrategy`. CPU-friendly chunkers (Semantic/model2vec, Recursive, Sentence, Token, Fast, Code, Table) run in-process; heavier chunkers (Neural/torch, Late, Slumber/LLM) are explicit stubs routed to a not-yet-existing remote MCP executor (`:16-22`).
- Chunk-level metadata produced by the chunker: `server/analysis/chonkie_chunkers.py:72-79` — `chunker` (label), `chunk_index`, `chunk_start`, `chunk_end`, `chunk_tokens`, merged into the Agno `Document.meta_data`.
- What actually lands in Weaviate today (legacy pour, confirmed by the live schema in §2/§3): Agno's Weaviate knowledge-doc writer flattens `meta_data` into the nested `filters` object — this is why `Platform_context.filters` shows `chunk_index` (number) and `message_count` (number) live, matching the chunker's emitted keys. Fields such as `chunk_start`/`chunk_end`/`chunk_tokens` are **not** present in any live class's `filters` schema today — **confirmed absent live**, meaning either they're dropped somewhere between the chunker and the Weaviate write, or no chunk carrying those specific keys has been ingested to trigger Weaviate's auto-schema on them (**UNKNOWN which** — not traced further; the insert call site itself was not located in this pass).
- For the native evidence path (not live): chunk rows are expected in `working.normalized_record_chunk` (confirmed to exist, §3) with `chunker_id`/`content`/`content_sha256`/`source_content_sha256` columns, read by `server/evidence/vector_projection.py:150-157`'s `_project()` SQL — that table has 0 rows live, so no native chunking has run yet.

---

## 6. pg_trgm / fuzzy capability — live

`pg_extension` (live query, 2026-08-24):

```
btree_gin 1.3, btree_gist 1.8, citext 1.8, fuzzystrmatch 1.2, hstore 1.8, ltree 1.3,
pg_duckdb 1.1.0, pg_stat_statements 1.12, pg_trgm 1.6, pgcrypto 1.4, postgis 3.6.4,
unaccent 1.1, vector 0.8.6, plpgsql 1.0
```

`pg_trgm` **1.6 is installed live**. `fuzzystrmatch` (Levenshtein/soundex family) is also installed. `vector` (pgvector) 0.8.6 is installed too — **UNKNOWN — not verified in this pass** whether anything currently writes vector columns via pgvector inside PG itself (this audit focused on Weaviate for vector storage; a separate check of `information_schema.columns` for a `vector` datatype column would be needed to confirm PG-side vector usage, not done here).

Trigram GIN indexes live today (`indexdef ILIKE '%gin_trgm_ops%'`, full list from live `pg_indexes` query): `analysis.evidence_item.idx_evitem_title_trgm`, `analysis.pattern_finding.idx_pattern_finding_matched_trgm`, `analysis.timeline_event.idx_event_title_trgm`, `evidence.source.idx_source_filename_trgm`, `public.memory_items.idx_mem_title_trgm`, `reference.detection_pattern.idx_detection_pattern_trgm`, `working.entity.idx_entity_dispname_trgm`, `working.entity.idx_entity_normname_trgm`, `working.entity_alias.idx_alias_trgm`, `working.entity_mention.idx_mention_trgm`, `working.handle.idx_handle_trgm`, `working.location.idx_location_name_trgm`, `working.normalized_record.idx_normrec_trgm` (the spine, see §1). None of this is currently exercised through an HTTP fuzzy-search endpoint in this audit's scope — `GET /v1/records?q=` uses `ILIKE '%...%'` only (§1); whether any other route calls `%`/`similarity()` against these indexes was **not checked** (out of scope for the routes reviewed).

---

## Summary (8 lines)

1. Full-text: `idx_normrec_fts` (GIN over `to_tsvector(content)`) and `idx_normrec_trgm` (trigram) both exist live on the spine `working.normalized_record`, confirmed by direct `pg_indexes` query — but neither traces to a numbered migration (only to the `sql/bootstrap/schema_baseline.sql` live-dump capture, meaning they were applied out-of-band).
2. Live handler `GET /v1/records?q=` (`server/api/inspect_routes.py:262`) bypasses both indexes and does a leading-wildcard `content ILIKE '%q%'` scan — no BM25/tsquery ranking, no trigram similarity call, and the spine table currently has 0 rows anyway.
3. Fuzzy/trigram capability (`pg_trgm 1.6`) is genuinely live across ~14 columns including the spine, but nothing observed in this pass exposes it through an HTTP fuzzy-search mode.
4. Semantic/vector search exists only in the legacy Agno-knowledge Weaviate pour (7 classes, `100.91.190.107:8081`, self-provided `nvidia/nv-embed-v1`/4096-d vectors) — no BM25/full-text mode inside Weaviate itself was exercised in this audit beyond schema/aggregate reads.
5. Hybrid search exists in code (`NativeEvidenceVectorStore.search(mode="hybrid")`, `server/core/evidence_vector_store.py:400-409`) but only against the **not-yet-live** `EvidenceChunkV1`/`EvidenceChunks` collection — confirmed absent on both Weaviate instances (`GET /v1/schema/EvidenceChunkV1` → 404 on `:8081` and `:8082`; `GET /v1/aliases` → empty).
6. Net: today, live, working end-to-end is exactly ONE mode — ILIKE substring scan over an empty table — plus a separate, disconnected semantic-search collection (7 legacy classes, 3,035 real objects) with no full-text/hybrid mode wired to it. The owner's four-mode (full-text, fuzzy, semantic, hybrid) requirement is met by pieces that exist in isolation, not as one integrated multi-query search surface.
7. Epoch-field finding: numeric epoch timestamps already exist live in exactly one place — `Platform_knowledge.filters.knowledge_time_epoch` (number) — while `Platform_context.filters.occurred_at_start/_end` are date-only (no epoch companion) and `Relationship_timeline_knowledge` has no date/epoch field of any kind despite its name.
8. The designed `EvidenceChunkV1` schema closes that gap by contract — `source_available_from` (DATE) plus `source_available_from_epoch` (INT) on every row (`server/core/evidence_vector_store.py:163-175`) — but PG-side plumbing (migrations 0026–0029, `working.normalized_record_chunk`, `working.evidence_vector_projection_job`) is applied and empty, and the Weaviate collection itself has not been created; the runbook (`docs/plans/WEAVIATE-NATIVE-EVIDENCE-CUTOVER-RUNBOOK-2026-08-18.md`) is explicitly HELD pending owner approval gates.
