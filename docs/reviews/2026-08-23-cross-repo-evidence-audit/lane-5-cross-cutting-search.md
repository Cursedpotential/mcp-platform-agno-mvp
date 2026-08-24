# Lane 5 — Cross-Cutting Search & Retrieval Review

> Byline: Claude Code · Fable 5 · 2026-08-23
> Scope: Agno-MCP-Platform (A), Legal-Workspace (B), vendored/sbv (C)
> Method: static code/config trace only — no live probes executed. Every claim below is tagged VERIFIED (I read the actual code path, both writer and reader) or INFERRED (reasoning from structure without a confirmed caller).

## The question

*If a user asks "find me every document mentioning X and bundle it as an exhibit", what actually happens today?*

**Short answer: nothing, end-to-end.** No single code path in any of the three repos accepts a free-text query and returns a cross-corpus, bundle-ready result set. What exists is three separate, non-federated indexes, a narrow read-only identity/hash bridge between two of the repos, and an exhibit *labeling* feature in Legal-Workspace that only operates on material a human has already hand-picked and imported. Building the described feature requires new code in at least two of the three repos.

---

## 1. Storage inventory — where bytes actually live

| System | What | Where | Status |
|---|---|---|---|
| A (Agno-MCP-Platform) | Structured records, metadata, content-hashes, small inline text, embeddings | PostgreSQL 18 (`agentos-db`, custom image with pg_duckdb + PostGIS + pgvector) | VERIFIED — `compose.yaml`, `sql/bootstrap/schema_baseline.sql` |
| A | Raw file bytes (documents/images/code assets extracted from chat-export archives) | Cloudflare R2, reached via an **rclone FUSE mount at `/r2`** inside the container — NOT the boto3 S3 API for writes (`server/evidence/custody.py::blob_root`, `server/analysis/context_assets.py`) | VERIFIED — write path read directly |
| A | boto3/S3-style R2 env vars (`R2_BUCKET_NAME`, `R2_ACCESS_KEY_ID`, etc.) | Declared in `compose.yaml` for `agentos-api`, described as "S3-compatible reads" | VERIFIED present in config; INFERRED as a secondary/legacy read path since the primary write path is the rclone mount |
| A | Vector embeddings (evidence chunks, general "platform knowledge") | **Weaviate** (`get_weaviate_client()`), NOT Milvus | VERIFIED — `server/core/knowledge_handle.py` states outright: "investigated against Milvus, but the mechanism is store-agnostic and applies unchanged to the Weaviate store that replaced it — ADR-0040 cutover 2026-07-29" |
| B (Legal-Workspace) | All application state (matters, exhibit annotations, imported source packages, docket, work product) | **SQLite**, file-based, bind-mounted at `/data/workspace` | VERIFIED — `compose.yaml` comment block: "DATABASE: intentionally left on SQLite... Pointing DATABASE_URL at the live PG18 today would deploy a path that has never run." The ORM's own Postgres path is dead code today. |
| B | Evidence bytes | **None.** Legal-Workspace explicitly never stores evidence bytes — `services/agno_client.py` docstring: "Read-only Evidence Platform client. Agno is truth; never clone evidence." | VERIFIED |
| C (SBV) | Parsed SMS/MMS/call records | **SQLite** (`./data` bind mount, `DB_PATH_PREFIX=/data`) | VERIFIED — `compose.yaml` |
| C | Original backup XML the user uploads | Held only transiently for parsing (SBV is a parser/viewer, not an archive) | INFERRED from `sbv_upload` semantics in `server/agents/tools/sbv_tools.py` |

**Three separate physical stores, three separate schemas, zero shared storage.** A doc that both A and B "know about" is duplicated (see §4), and C's message store is a fourth, wholly separate SQLite database that neither A nor B queries directly (only through an HTTP hop, see §3).

---

## 2. Index inventory — what indexes exist, and are they real

Rule applied: an index is only "real" if all three are true — CREATED (migration/DDL), POPULATED (a writer inserts into it), QUERIED (a reader selects through it). Missing any leg is noted explicitly.

### A — PostgreSQL full-text (tsvector/GIN)

- `working.normalized_record.fts` (generated `tsvector` column) + `idx_normrec_fts` GIN index, and a parallel `idx_normrec_trgm` trigram index — this is the FTS index over the actual message/document content table.
- `public.memory_items` / `public.session_summaries` also carry generated `fts` + GIN indexes.
- Roughly 20 more trigram (`gin_trgm_ops`) indexes across `working.entity`, `working.attachment.ocr_text`, `analysis.timeline_event`, etc.
- **CREATED: yes** (`sql/bootstrap/schema_baseline.sql`, confirmed by `\d+`-style DDL).
- **POPULATED: yes, implicitly** — these are `GENERATED ALWAYS AS` computed columns, so any INSERT into the base table populates them automatically; no separate writer needed.
- **QUERIED: NOT FOUND.** A `Grep` across every `*.py` file in `Agno-MCP-Platform` for `tsvector`, `to_tsquery`, `plainto_tsquery`, `websearch_to_tsquery`, `idx_normrec_fts`, `idx_mem_fts` returned **zero matches**. Nothing in `server/` issues a Postgres full-text query.
- **Verdict: CREATED + auto-POPULATED, but NEVER QUERIED. The Postgres FTS layer is dead weight — a real index with no reader.** (VERIFIED via exhaustive grep, not just absence-of-evidence: the generated columns and GIN indexes exist and would populate on write, but no call site reads through `to_tsquery`/`plainto_tsquery`/`websearch_to_tsquery` anywhere in the Python tree.)

### A — pgvector

- `vector(...)` columns exist in `sql/bootstrap/schema_baseline.sql`, and `server/analysis/context_chat_ingest.py` writes real embeddings into `working.chat_chunk_embedding` (`CAST(:embedding AS vector)`), with a cache-read helper (`_load_cached_embedding`) that selects `embedding::text FROM working.chat_chunk_embedding`.
- **CREATED: yes. POPULATED: yes** (verified writer in `context_chat_ingest.py`). **QUERIED: only as a write-cache lookup by `chunk_id`+`embedder_id`, not as a similarity/kNN search** — no `<->`/`<=>` operator or `ORDER BY embedding <-> ...` pattern found in this file. This looks like a dedup/reuse cache for embedding computation, not a retrieval index.
- **Verdict: real writer, but the reader is a cache lookup, not semantic search. pgvector is not the platform's vector-search engine.**

### A — Weaviate (native evidence vector search)

This is the one fully real, three-legged index in the platform:
- **CREATED**: `server/evidence/native_activation.py::create_collection()` → `ensure_evidence_vector_collection(client)` + `validate_evidence_vector_collection(client)`. A whole resumable multi-phase activation workflow exists (collection create → frozen-watermark enqueue → drain/backfill → reconciliation/canaries → alias creation), explicitly designed so a crash mid-activation can resume.
- **POPULATED**: the drain/backfill path reads `working.normalized_record` (frozen watermark), chunks and embeds via `NativeEvidenceEmbedder` (NVIDIA NIM, 4096-d `nv-embed-v1`), and writes into the Weaviate collection.
- **QUERIED**: `server/api/native_evidence_search_routes.py` registers `POST /v1/evidence/search` (agent-facing, capability-gated to a bound walk/checkpoint) and `POST /v1/operator/evidence/search` (owner-only, bearer-token gated). Both call `native_evidence_search(store, embedder, query, ...)` against the same Weaviate collection, `mode: "near_vector" | "hybrid"`.
- **Verdict: genuinely real — CREATE, POPULATE, and QUERY all verified with actual call sites.**
- **BUT it is feature-flagged off by default.** `server/api/main.py`:
  ```
  _native_evidence_runtime = (
      create_native_evidence_runtime(validate_activation=True) if native_evidence_enabled() else None
  )
  ...
  if _native_evidence_runtime is not None:
      register_native_evidence_search_routes(app, native_runtime=_native_evidence_runtime)
  ```
  and `compose.yaml`: `NATIVE_EVIDENCE_ENABLED: ${NATIVE_EVIDENCE_ENABLED:-false}`. No `.env` file is present in the repo to check the actual deployed value, so whether this is currently switched on in production is **not verifiable from the repo alone — flag for live confirmation.** If it is off, the search routes are never registered and `/v1/evidence/search` does not exist on the running server at all.

### A — general AgentOS "platform knowledge" (agno's built-in Knowledge object)

- Also backed by Weaviate post-ADR-0040 (see `knowledge_handle.py`).
- **CREATED/POPULATED**: via agno's own `Knowledge` machinery, resolved once at boot (`server/core/knowledge_handle.py`).
- **QUERIED**: through agents' built-in knowledge-search tool and AgentOS's own `/knowledge*` routes — this is agent-facing RAG, not a user-facing document/exhibit search endpoint.
- Deliberately degrades gracefully: if Weaviate is unreachable at boot, `.instance` stays `None`, a background retry loop (60s interval) swaps it in once Weaviate recovers, but **agents/AgentOS internals built before the swap never get the live knowledge base for the life of that process** (documented, accepted limitation in the module's own docstring).

### C (SBV) — SQLite FTS5

- **CREATED**: `CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(...)` in `internal/database.go`.
- **POPULATED**: real INSERT/UPDATE/DELETE triggers keep `messages_fts` in sync with the `messages` table (verified in the same file, lines ~130-260).
- **QUERIED**: `SearchMessages(userDB, query, limit)` in `internal/database.go` runs `... FROM messages_fts JOIN messages ... WHERE messages_fts MATCH ?`, called by `HandleSearch` in `internal/handlers.go`, tested by `TestHandleSearch*` in `internal/handlers_test.go`.
- **Verdict: fully real, all three legs verified.** This is the only unconditionally-live FTS in the whole stack — but it only covers SBV's own SQLite `messages` table (SMS/MMS/calls from one imported backup), not documents, not evidence, not anything in Postgres.

### B (Legal-Workspace) — search

- No `tsvector`, `to_tsquery`, or FTS mechanism of any kind found in `api/legal_workspace/`. Legal-Workspace has **no search capability of its own** over its SQLite store. It relies entirely on receiving already-curated `LegalSourcePackage` objects.

---

## 3. The seam — how A, B, C actually exchange data

- **A ↔ C (Agno ↔ SBV): real, verified, HTTP, bidirectional in role but narrow in scope.**
  - Agno → SBV as an **agent tool**: `server/agents/tools/sbv_tools.py` wraps SBV's REST API (`SBV_BASE_URL`, default `http://platform-tools:8085`) with `@tool`-decorated functions including `sbv_search(query, limit)` → `_sbv().search(...)`, which calls SBV's FTS5-backed `/api/search`. An agent CAN invoke SBV's full-text search as one of its tools.
  - Agno → SBV as a **parse engine**: `server/analysis/sbv_transcript.py` hands SMS/MMS export files to the SBV Go service to parse (ADR-0049, "the universal, memory-safe decoder"), then reads the canonical records back and maps them into Agno's own `NormalizedRecord` shape, which is written into Postgres (`working.context_record`) and flows onward to Weaviate/Graphiti. This means a message parsed this way is **duplicated**: once inside SBV's SQLite (with SBV's own FTS5 index over it), and again inside Postgres/Weaviate under Agno's schema.
  - There is **no reverse channel** — SBV never reads from or writes to Postgres/Weaviate directly; it only serves HTTP requests from Agno.
  - **Crucially: `sbv_search` and `/v1/evidence/search` are two independent tools hitting two independent indexes.** An agent could call both and manually merge results, but there is no unified query, no shared relevance ranking, and no code that does this merge today.

- **A ↔ B (Agno ↔ Legal-Workspace): real, verified, HTTP, deliberately narrow and read-only.**
  - `Legal-Workspace/api/legal_workspace/services/agno_client.py` is the entire interface. Its own docstring: *"Read-only Evidence Platform client. Agno is truth; never clone evidence."*
  - Exactly three calls exist: `GET /health`, `GET /v1/matters` (identity projection only — matter id + display name, nothing else), `POST /v1/verify/{sha256}` (two-tier hash-verification verdict only).
  - **There is no call to `/v1/evidence/search` or any search/query endpoint anywhere in Legal-Workspace.** Confirmed by grep across `api/legal_workspace/` for the Agno base URL usage — only `probe_health`, `list_matters`, `verify_sha256`/`verify_package_hashes` exist.
  - Routed through a gateway in production: `EVIDENCE_PLATFORM_BASE_URL: http://contextforge:4444` (not directly to `agentos-api:8000`), with an optional `Authorization: Bearer <contextforge_gateway_token>` header.
  - **Verdict: the only thing Legal-Workspace can currently ask Agno is "what matters exist" and "does this hash check out." It cannot ask Agno "find documents mentioning X."**

- **B ↔ C (Legal-Workspace ↔ SBV): no evidence of any direct connection found.** Nothing in Legal-Workspace's code references SBV, `platform-tools`, or port 8085/8081.

**Conclusion on the seam: cross-corpus search is impossible by construction today.** A has one real vector index (Weaviate, evidence, flag-gated) and a dead-letter Postgres FTS layer; C has a real but isolated SQLite FTS5 index; B has no search of its own and no query access to either of the other two. There is no component anywhere that fans a query out to more than one of these stores.

---

## 4. Duplication — the same logical entity modeled independently

| Entity | A (Postgres/Weaviate) | B (SQLite) | C (SQLite) |
|---|---|---|---|
| A message/SMS record | `working.normalized_record`, `working.message`, `working.context_record`, (evidence-tier) `working.artifact_registry`; chunked+embedded into Weaviate | not modeled (Legal-Workspace never stores evidence) | `messages` table + `messages_fts` |
| A "document"/evidence item | `evidence.source`, `evidence.evidence_hash`, `working.attachment` (with OCR text + EXIF), R2 blob referenced by `content_hash`/`source_sha256` | `legal_core_source_package` (a **snapshot copy**, imported via `import_legal_source_package`, of items Agno already marked APPROVED) | not modeled |
| A "matter"/case | `analysis` / `case_management` schema (multiple tables — `evidence_item`, `finding`, `timeline_event`, etc.) | `legal_core_matter_ref`, `legal_core_court_case_ref` (identity-only projection from `/v1/matters`) | not modeled |
| Exhibit | comment-only mentions (`store.py`: "a conversation document bundles many records") — **no exhibit table or object in A** | `legal_core_exhibit_annotation` — label + Bates number attached to an already-imported item | not modeled |

**`legal_core_source_package` is the clearest duplication point**: it is an explicit, frozen copy of a subset of Agno's evidence metadata, imported once and then living independently in Legal-Workspace's SQLite with no live link back — `import_legal_source_package()` filters to `ReviewState.APPROVED` items and copies them in; nothing keeps this in sync with Agno afterward, and a later hash-only re-verify (`verify_sha256`) is the only feedback path.

---

## 5. The bundling/exhibit endpoint

- **Grep for `bundle`/`exhibit`/`production_set` across all of `Agno-MCP-Platform/server` found no bundling logic.** The only hits are: a code comment describing how a conversation *document* logically bundles several DB records (unrelated meaning), and unrelated matches in `providers.py`/`claude_code_agent.py`/vendored chatminer code. **Agno-MCP-Platform has no code that takes a search result set and emits an exhibit, production, or bundle. This capability does not exist in A.**
- **Legal-Workspace has a real exhibit *labeling* feature**, but it is not a search-to-bundle pipeline:
  - `domain/exhibits.py` defines `ExhibitCandidate`, `ExhibitAnnotation`, `ExhibitReadiness`.
  - `POST /v1/exhibits` (`annotate_exhibit`) attaches a label + readiness state to an item that is **already inside an imported, human-approved `LegalSourcePackage`** — it operates on pre-selected material, not on a live query.
  - `POST /v1/exhibits/{item_id}:bates` (`assign_exhibit_bates`) assigns sequential Bates numbers — real, owner-triggered, verified in `services/bates.py`.
  - There is no code path from "user types a search query" to "a `LegalSourcePackage` gets built" — `import_legal_source_package()` takes a fully-formed `LegalSourcePackage` object as input; nothing in the repo constructs one from a search result. How that package gets assembled today is not shown in either codebase — it is either a manual/external process or an as-yet-unbuilt integration.
  - No PDF/document assembly step was found beyond redaction/overlay utilities on an already-owner-produced PDF (`api/main.py` — explicitly noted as "Not Agno evidence").
- **Where it would have to live**: given the seam in §3, an actual "find X, bundle as exhibit" feature needs (a) a search endpoint in A that isn't capability/walk-gated the way `/v1/evidence/search` is (or a relaxed operator path), (b) a new call in B's `agno_client.py` to reach it (today deliberately absent by design — "never clone evidence" would need revisiting or a stream/reference-only response shape), and (c) new bundle-assembly code, most naturally in B next to the existing exhibit/Bates machinery, since B is the only repo with an exhibit domain model at all.

---

## Milvus / vector-store hard-dependency check

- Confirmed **no current code path in any of the three repos depends on Milvus.** `server/core/knowledge_handle.py` and `server/core/session.py` both state explicitly that the platform's vector store was cut over from Milvus to Weaviate on 2026-07-29 (ADR-0040); the only remaining Milvus references in the codebase are historical comments explaining the migration and the resilience design it motivated. `compose.yaml` in Agno-MCP-Platform declares no Milvus service.
- **The live dependency today is on Weaviate**, for both the native evidence search (`/v1/evidence/search`, flag-gated) and AgentOS's general knowledge/RAG lane (always-on when knowledge is configured). If Weaviate itself is down, the platform is designed to degrade gracefully at boot (background retry, `knowledge=None` fallback) rather than crash — but any agent/route that resolved a `None` knowledge handle before Weaviate recovered stays without a knowledge base for that process's lifetime, and `/v1/evidence/search` would 503 (`validate_evidence_vector_activation` raising) or simply not be registered.
- This is a **design gap in resilience documentation, not a currently-observed live outage** — I did not probe the running Weaviate instance; the memory context's Milvus-down note appears to concern a different, already-superseded dependency for this platform. **Recommend a live check of Weaviate reachability** if evidence search is expected to work today, since that is the actual current dependency, not Milvus.

---

## Summary verdict

Cross-corpus "find every document mentioning X and bundle it as an exhibit" **does not work today**, for concrete, traced reasons:
1. Postgres FTS is real but has no reader anywhere in the codebase.
2. The one real semantic search (Weaviate-backed evidence search in A) is capability/walk-gated for agents and feature-flagged off by default; its production-enabled status is unverified from the repo.
3. SBV's FTS5 search is real and live but scoped to one imported SMS backup's SQLite database, reachable only as an isolated agent tool call, never merged with A's results.
4. Legal-Workspace, the only repo with an exhibit/Bates concept, has zero search capability and zero query access to A's search — its `agno_client.py` is deliberately limited to health/matter-list/hash-verify.
5. No bundling/production-assembly code exists in any repo; Legal-Workspace's exhibit annotation only labels material a human already imported by hand.
