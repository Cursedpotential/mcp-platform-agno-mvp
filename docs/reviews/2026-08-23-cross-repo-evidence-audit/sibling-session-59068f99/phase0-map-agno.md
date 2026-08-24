> _Byline: Claude Code · Opus 5 · 2026-08-23_

# Agno-MCP-Platform — Document Handling, Search/Retrieval, Evidence Capability Map

Repo root: `E:\AI_Workspace\Projects\the-platform-workspace\Agno-MCP-Platform`
Phase 0 inventory only — no recommendations. Every claim below was read from source, not
inferred from filenames. `_stale/`, `to_be_deleted/`, `build/`, `vendored/`, `*.egg-info`,
`live-dumps/` were skipped except for the one-line abandonment notes in §6.

---

## 1. Ingest

### 1.1 Entrypoints

| Entrypoint | Path | Notes |
|---|---|---|
| HTTP upload | `POST /v1/ingest` — `server/api/ingest_routes.py:114-159` | multipart upload, streamed to disk (`_stage_upload`, ingest_routes.py:49-61), 50MB cap (`_MAX_UPLOAD_BYTES`, ingest_routes.py:24), bearer-auth via `OS_SECURITY_KEY` (`_authorize`, ingest_routes.py:28-40). Returns 202 + `run_id` immediately; ingest runs as a background `asyncio.Task` (ingest_routes.py:98-110). |
| HTTP staged-path | `POST /v1/ingest/path` — `ingest_routes.py:161-181` | ingests a file already on the staging filesystem, synchronous-ish (awaited via `asyncio.to_thread`), returns the full receipt (201). |
| HTTP read | `GET /v1/knowledge/items`, `GET /v1/knowledge/items/{artifact_id}` — `ingest_routes.py:183-202` | canonical-store reads via `server/ingest/query.py` (`list_items`, `get_item`). |
| CLI | `server/evidence/cli.py:87-112` (`python -m server.evidence …`) | subcommands `import` (workflow-based ingest), `tools` (list registered atomic tools), `workflows` (list named workflows), `verify` (re-hash a file against its custody row). |
| MCP tools | AgentOS `enable_mcp_server=True` — `server/api/main.py:452` | Mounted `/mcp` FastMCP app (agno-native since 2.8.0). No custom `@mcp.tool()` ingest tool found in this repo; ingest is reached via HTTP routes and the atomic tool registry (`server/tools/registry.py`), which a polyglot MCP "gateway" (`server/tools/gateway/`) can also front. |
| Folder-walk reindex | `POST /v1/knowledge/reindex` — `server/api/main.py:187-201` | calls `scripts.ingest_knowledge.ingest_all()`, writes to canonical PostgreSQL, independent of vector-store health. |

### 1.2 Orchestration & parsing

Core orchestrator: **`server/ingest/service.py:ingest_file()`** (ingest/service.py:264-520). Stages, each recorded to the run ledger (`seed_stages`, `stage_start`/`stage_finish`):
1. **custody** — `server.evidence.custody.ingest_artifact` (hash + dedupe + write-once blob copy).
2. **parse** — `_parse()` (ingest/service.py:185-236), dispatches to:
   - `_extract_document()` (service.py:143-182) for `.pdf/.docx/.pptx/.xlsx/.html/.htm` (`_DOCUMENT_SUFFIXES`, service.py:28) — tries `documents.extract-docling` then (PDF only) `documents.extract-text`.
   - `parse_chat_export()` (`server/analysis/chat_parse.py`) for chat/message exports, engine `go`/`python`/`auto` selected via `server/analysis/format_router.py` (signature-based detection, format_router.py:44-63) or an explicit `coverage_hint`/`format` override (`resolve_format_override`).
   - `_whole_file_text()` (service.py:127-140) fallback for `.md/.txt` — **forbidden for the evidence lane** (`ValueError` raised, service.py:131, per ADR-0044).
3. **store** — `server.evidence.store.store_record_batch` persists `NormalizedRecord`s + chunks to Postgres (`working.*`/`analysis.*`), with duplicate-artifact short-circuiting (service.py:342-389).
4. **projection** — optional vector projection to Weaviate via an injected `projector` (native outbox pattern, service.py:390-461); `message_corpus == "acquired_third_party"` always skips (awaiting approved `source_available_from`, service.py:393-400).

### 1.3 Supported document/file formats

- **General documents**: PDF, DOCX, PPTX, XLSX, HTML/HTM — `_DOCUMENT_SUFFIXES` (ingest/service.py:28); extractor accept-list also includes PNG/JPG/JPEG/TIFF/WEBP (`_SUPPORTED`, `server/tools/extractors/docling_extract.py:16`).
  - **Docling** (`server/tools/extractors/docling_extract.py:20-40`, tool id `documents.extract-docling`) — optional dependency, lazily imported; layout/tables/reading-order/OCR, output = Markdown.
  - **Native text-layer + OCR** (`server/tools/extractors/extract_text.py:1-40`, tool id likely `documents.extract-text`) — tiered: (1) pypdf/pdfplumber native text layer (free), (2) Tesseract OCR (pytesseract+pdf2image, local/CPU), (3) escalation to a heavier provider is left to the caller (comment at extract_text.py:20-24; no in-repo provider call found).
- **Chat/message exports** (`server/tools/parsers/`, 20+ `@register`-decorated parsers, confirmed live): ChatGPT official export, ChatGPT share, ChatGPT custom-GPT markdown, Claude AI export, Claude Code (+ JSONL), Claude markdown, Gemini (Chrome/JSON/markdown), Perplexity (contexts/GDPR/markdown/plugin), generic markdown, whole-file fallback, Facebook Messenger (HTML/JSON), iMessage (HTML/TXT/PDF), SMS Backup & Restore XML, generic messaging CSV/transcript, SBV SMS.
  - Go-primary formats mirrored in `format_router.py:67-79` (`GO_IMPORTER_FORMATS`): `chatgpt-official-json`, `smsbackuprestore-xml`, `facebook-messenger-json/html`, `google-chat-json`, `google-voice-html`, `imessage-txt/html`, `messages-transcript`, `email-eml/mbox`, `ndjson`, `csv` — routed to the SBV Go engine (`vendored/sbv`) when a Go decoder exists, else Python (format_router.py:9-13).
- Text/markdown: `.md`/`.txt` via `_whole_file_text` (non-evidence lanes only).

### 1.4 Attachments/binaries

- `working.context_asset` (extended by migration 0024, `sql/0024_chat_conversation_and_message.sql:44-58`) is the multimodal attachment/generated-work table: `origin_kind` (`generated_work|attachment|export_asset|derived`), `modality` (`text|code|image|audio|video|binary`), `extracted_text`, `extraction_tool_id`, `extraction_confidence`, `extraction_status`. Linked to messages via `working.context_asset_message` (0024:59-58) and to lanes via `working.context_asset_projection`.
- Raw binary custody: **write-once blob copy** under `/r2/evidence/<sha256[:2]>/<sha256>/<original-name>` (`server/evidence/custody.py:103-107,254-270`), copy-verified by re-hashing before `os.replace` (custody.py:262-269) — a crash can never leave a partial file at the canonical path.

### 1.5 Manifest / receipt

Every ingest produces a durable **`IngestReceipt`** (`server/contracts/ingest.py:120-141`): `receipt_id`, `status`, `lane`, `matter_id`, `source_name/path`, `artifact_id`, `duplicate`, `parser_id`/`parser_engine`, `chunker_id`, `record_count`/`chunk_count`, `rejections[]`, `attempts[]` (per-extractor/parser try/fail log), `projections[]` (per-sink status), `started_at`/`completed_at`. Persisted to the workflow-run ledger (`analysis.workflow_run` / `analysis.workflow_run_stage`, migration `sql/0005_workflow_run_ledger.sql`) via `PostgresReceiptJournal` (ingest/service.py:53-101). Readable at `GET /v1/runs/{run_id}` and `GET /v1/runs/{run_id}/report` (`server/api/run_routes.py:528,538`).

---

## 2. Storage schema

30 numbered migrations, `sql/0001_init_extensions.sql` … `sql/0030_matter_case_foundation.sql`. **`0030` is drafted + static-validated but explicitly NOT applied** (see §6). Several migrations have timestamped `.backup_*` siblings from an in-repo repair pass (`0026`, `0027`, `0028`, `0029` — 2026-08-18); the numbered files are current.

Important: `evidence.source`, `evidence.file_node`, `evidence.custody_event` are **not created by any numbered migration** — they were applied out-of-band to production and are only captured (read-only, "evidence of what exists") in `sql/_manual/20260802_reconcile_evidence_ddl.sql:46-165`. Migration `0019_reconcile_evidence_hash.sql` promotes the `evidence.evidence_hash` 15-column shape into the numbered chain and wires FKs to those tables *only if they already exist* (0019:95-118).

### 2.1 Evidence / custody tables
- `evidence.evidence_hash` (`sql/0002_schema.sql:59-66`, extended `sql/0003_normalized_records.sql:13-14`, `sql/0019_reconcile_evidence_hash.sql:45-56`) — `id, source_ref, algo, digest BYTEA(32), hashed_at, blob_key, meta JSONB, level ('H1'|'H2'|'H3'), source_id, file_node_id, md5_prefilter, record_locator JSONB, member_hash_ids UUID[], canon_version, computed_by`.
- `evidence.source` (`sql/_manual/20260802_reconcile_evidence_ddl.sql:131-165`, extended `sql/0008_temporal_clocks_and_provenance.sql:130+`) — `sha256, md5_prefilter, byte_size, mime_type, original_filename, source_type, source_platform, custodian, acquisition_source, acquisition_method, origin_device_id, acquired_at_utc, provenance_tier, r2_bucket/key, local_path, sensitivity_tier, custody_status, extraction_status, processing_status, review_status, export_status, original_metadata JSONB, acquisition_id`.
- `evidence.acquisition` (`sql/0008_temporal_clocks_and_provenance.sql:83-161`) — third-party/human-asserted acquisition events (method, authority, source_device, device_custodian, acquired_at, asserted_by/asserted_by_category).
- `evidence.custody_event` (`sql/_manual/...ddl.sql:46-70`) — append-only, hash-chained (`prev_event_digest`/`event_digest`, DB trigger), `event_type` CHECK set (`collected|sealed|in_processing|verified|disputed|released|re_hashed|integrity_violation|superseded|accessed`).
- `evidence.file_node` (`sql/_manual/...ddl.sql:107-129`) — sub-file structure (pages/frames/attachments/message units) with `sha256`, `byte_span_start/end`, `ai.ltree node_path`.
- `evidence.artifact_metadata` (`sql/0008_temporal_clocks_and_provenance.sql:162-...`).
- `evidence.ingest_run`, `evidence.raw_rejected` (`sql/0012_pipeline_visibility.sql:44,112`).

### 2.2 Records / normalization
- `analysis.normalized_record` (`sql/0003_normalized_records.sql:16`) — canonical parsed-record table.
- `analysis.record_observation`, `analysis.conversation_group(_member)`, `analysis.block_status`, `analysis.extraction_batch` (`sql/0009_raw_layer_and_derivation.sql`).
- `analysis.extraction_candidate` (`sql/0010_extraction_candidate_and_acquisition_reconcile.sql:59`).
- `analysis.entity_candidate`, `analysis.device_ownership` (`sql/0008...sql:314,416`).
- `analysis.corroboration_flag` (`sql/0007_curation_and_flags.sql:44`).

### 2.3 Chat / conversation / chunk / embedding (migration 0024, newest large-schema addition before 0030)
`sql/0024_chat_conversation_and_message.sql` — AI-chat landing + chunk routing + review register (BEGIN…COMMIT, one file):
- `working.chat_conversation` (0024:12-21) — `source, external_id UNIQUE(source,external_id), title, source_path, created_at`.
- `working.chat_message` (0024:24-36) — `conversation_id FK, message_index, role CHECK(user|assistant|system|tool|unknown), content, content_hash CHAR(64)`.
- `working.chat_chunk` (0024:103-116) — canonical chunk store: `content, content_hash UNIQUE, chunker_id, chunker_version, token_count, char_start/end`.
- `working.chat_chunk_message` (0024:120-129) — chunk↔message provenance mapping with ordinal.
- `working.chat_chunk_lane` (0024:131-148) — per-chunk lane classification (`platform|legal|personal_history|context`; evidence lane is deliberately excluded — populated only via custody workflow), `confidence`, `classifier_id`, `review_status`.
- `reference.knowledge_tag` / `working.chat_chunk_tag` (0024:159-179) — normalized tag taxonomy with provenance.
- `working.chat_chunk_embedding` (0024:190-201) — **idempotency/cache ledger, not the vector store itself**: `chunk_id, embedder_id, content_hash, embedding VECTOR, embedding_dimension, vector_ref, embedded_at`, PK `(chunk_id, embedder_id)`.
- `working.chat_chunk_projection` (0024:203-221) — per-sink projection status: `sink CHECK(weaviate|graphiti)`, `embedder_id`, `projection_ref`, `attempts`, `last_error`.
- `working.investigation_event(_source/_evidence_need/_evidence_link/_tag)` (0024:224-...) — human-curated investigation register, explicitly NOT evidence just because AI chat mentioned it.
- Event-sourcing tables: `chat_conversation_event`, `chat_message_event`, `chat_chunk_event`, `chat_chunk_lane_event`, `context_asset_event`, `chat_cdc_cursor`, `chat_projection_dead_letter` (0024:306-361).

### 2.4 Context records
- `working.context_record` (`sql/0021_context_record.sql:51`), `working.context_archive`/`context_asset` (`sql/0022_context_assets.sql:31,44`) — pre-date and are extended by the 0024 chat schema.

### 2.5 Workflow / audit / ledger
- `analysis.workflow_run`, `analysis.workflow_run_stage` (`sql/0005_workflow_run_ledger.sql:18,36`) — the ingest-receipt backing store (§1.5).
- `ops.audit_ledger` (`sql/0020_audit_ledger.sql:58`) — hash-chained read/write audit log (see §5).
- `ops.workflow_run_review_action` (`sql/0025_durable_run_reports.sql:43`).
- `working.walk_run`, `working.walk_step`, `working.walk_step_retrieval`, `working.walk_checkpoint`, `working.walk_step_realization_retrieval` (`sql/0027_walk_ledger.sql`) — resumable "walk" state that the native evidence-search agent surface authenticates against (§4.2).
- `working.record_visible_from` (`sql/0028_horizon_repoint.sql:61`) — horizon/visibility clock.
- `working.realization_event`, `working.realization_event_record`, `working.evidence_vector_projection_job` (`sql/0026_realization_event.sql:258,302,482`) — the native Weaviate outbox job table driving §1.2 stage 4.
- `working.third_party_conversation`, `working.third_party_message(_participant)`, `working.third_party_conversation_acquisition` (`sql/0026...sql:167-257`) — acquired third-party message review/approval pipeline joined into `GET /v1/records` (§4.1).
- `working.message_projection_route`, `working.normalized_record_chunk` (`sql/0026...sql:83,107`).

### 2.6 Case management (newest applied migration = 0029; 0030 held)
- `sql/0029_pass_grants.sql` — applied.
- `sql/0030_matter_case_foundation.sql` (**NOT APPLIED**, see §6): `analysis.matter`, `analysis.court_case`, `analysis.matter_knowledge_partition`, `analysis.knowledge_evidence_promotion` (0030:17-151+).
- Repository/service code already exists and is routed: `server/case_management/repository.py`, `service.py`, exposed at `GET/POST /v1/matters`, `/v1/matters/{matter_id}`, etc. (`server/api/case_management_routes.py:55-182`) — **this is code ahead of schema**: routes reference tables the migration that creates them has not been applied (flagged for §6, verify at runtime).

---

## 3. Chunking & embedding

- **Chunk policy seam**: `server/analysis/chunking_policy.py:lane_chunker()` (44-71) — per-lane `ChunkingStrategy`. Five lanes: `platform, legal, personal_history, context, evidence` (`LANES`, chunking_policy.py:31). `context`/`evidence` are "transcript lanes" (turn-structured) using `TranscriptSemanticHybridChunking` (semantic 400-token chunks, 2000-char hard cap — `_TRANSCRIPT_SEMANTIC_TOKENS/_TRANSCRIPT_HARD_CAP_CHARS`, chunking_policy.py:38-39); other lanes use Chonkie's `cpu_chunker("recursive")`. A `tuned=False` rollback path uses Agno-native `RecursiveChunking(chunk_size=1500, overlap=150)` (`_BASELINE_CHUNK_CHARS/_BASELINE_OVERLAP_CHARS`, chunking_policy.py:35-36) — explicit non-default rollback only.
- Ingest-path default chunker: `CHUNKER_ID = chunker_id("recursive", 1500)` (`server/ingest/service.py:25`), applied via `server/ingest/chunking.py:chunk_records()`.
- **Chonkie** implementations: `server/analysis/chonkie_chunkers.py` (torch-free, CPU-only; "remote executor is not wired yet" comment at line 192 — see §6).
- **Embedders**:
  - `NimEmbedder` (`server/core/embedder.py:26-63`) — NVIDIA NIM asymmetric embedqa wrapper subclassing Agno's `OpenAIEmbedder`; documents embed with `input_type=passage`, queries with `input_type=query` (fixes a previously-silent retrieval-quality bug, documented in the module docstring).
  - **Evidence-lane embedder**: `nvidia/nv-embed-v1`, **4096 dimensions** — pinned constants `EVIDENCE_EMBED_MODEL`/`EVIDENCE_EMBED_DIM` (`server/core/evidence_vector_store.py:24-25`); query-side embedder is `NativeEvidenceEmbedder` (`server/core/native_evidence_runtime.py`).
  - Platform-wide vector contract mirrors this: `EMBED_PLATFORM_ID="nvidia/nv-embed-v1"`, `EMBED_PLATFORM_DIM=4096` (`server/analysis/semantica_wiring.py:41-42`).
- **Vector stores**:
  - **Weaviate** is canonical (ADR-0040 cutover, per comments at `server/api/inspect_routes.py:596` and `run_routes.py:436,449` — "milvus": deprecated compatibility alias only).
  - Agno-native lane knowledge: `agno.vectordb.weaviate.Weaviate`, wrapped by `VerifiedWeaviate` (`server/core/knowledge_vectordb.py:146-...`) which fixes/guards three documented upstream agno×weaviate-client bugs (silent-COMPLETED-with-zero-vectors; async client hardcoded to `localhost:8080`; `update_metadata`'s `where=` vs `filters=` kwarg mismatch; missing `Document.id` on search results) — see §6 for detail, all now fixed in-repo.
  - **Native evidence-only collection**: `EvidenceChunkV1` aliased `EvidenceChunks` (`EVIDENCE_VECTOR_COLLECTION`/`_ALIAS`, `evidence_vector_store.py:21-22`) — a hand-built Weaviate collection (not an Agno `Knowledge` object) with typed properties for horizon/disclosure filtering, managed by `NativeEvidenceVectorStore` (evidence_vector_store.py:282-411).
  - Embedder↔collection pairing is enforced by pinned dimension checks (`if len(vector) != EVIDENCE_EMBED_DIM: raise ValueError`, `evidence_vector_store.py:365-366`) and by `working.chat_chunk_embedding`'s `(content_hash, embedder_id)` UNIQUE constraint (idempotency ledger, §2.3) plus `working.chat_chunk_projection.sink CHECK(weaviate|graphiti)`.
  - **Milvus**: still running for `memsearch` only per `semantica_wiring.py:14` comment ("SIDELINED (ADR-0040): stays up for memsearch only — no new platform writers"); per user's own memory notes, `Milvus DOWN deliberately 2026-08-10` (6th etcd corruption) — external to this repo's scope but corroborates the deprecation.

---

## 4. Search / retrieval

| Path | Type | Route/Tool | Reranking | Provenance returned |
|---|---|---|---|---|
| Agent evidence search | vector (near_vector or hybrid) | `POST /v1/evidence/search` — `server/api/native_evidence_search_routes.py:271-289` | no (see below) | `audit_id, kept, denied, case_id, horizon, horizon_policy` in response meta (native_evidence_search_routes.py:245-261) |
| Operator evidence search | vector (near_vector or hybrid) | `POST /v1/operator/evidence/search` — `native_evidence_search_routes.py:291-311` | no | same shape |
| Agno-native knowledge search | vector, per-lane | Agno's built-in `/knowledge/search` (mounted by `AgentOS`, not a route defined in this repo) | via `NvidiaReranker` if wired into the Knowledge instance | agno's own `VectorSearchResult` shape; `get_search_results` override backfills `document.id` (`knowledge_vectordb.py`, "Fix" section) |
| Keyword/SQL search | SQL `ILIKE` over `working.normalized_record.content` | `GET /v1/records` — `server/api/inspect_routes.py:249-...` | n/a | rich inline provenance: `source_kind` (first_party/third_party_acquired), `projection_kind`, `source_available_from`, `normalized_lineage`, `third_party_conversation`/`third_party_review` (approval-gated), `realization_events` — all joined in one query (inspect_routes.py:270-330) |
| Direct Weaviate inspection | n/a | `GET /v1/inspect/weaviate/{collection_name}` — `inspect_routes.py:603` | n/a | raw object dump for ops debugging |
| Graph write (Graphiti) | episode ingestion only | `server/analysis/graphiti_case_client.py:GraphitiCaseClient.add_memory()` (143-165), called from `server/tools/ingest/context_drain.py` (a registered tool) via `sync_pending_context` | n/a | n/a |
| Graph **search/query** | **not implemented** | — | — | — |

### 4.1 Native evidence-search seam (`server/evidence/retrieval.py`)
`evidence_search()` (retrieval.py:134-216) is documented as **the only sanctioned read path into the evidence knowledge base** (ADR-0050 §4, module docstring lines 8-16): no bypass parameter, deny-undated-by-default, every call audited via `server.core.audit.record_read` — **if the audit write fails, the search fails** (retrieval.py:19-21,171-174). `native_evidence_search()` (retrieval.py:62-123) is the newer native-Weaviate variant used by the HTTP routes; it type-checks the store is a `NativeEvidenceVectorStore`, requires a permission-derived `disclosure_tiers` set (no `allow_hindsight` convenience flag — retrieval.py:76-79), and validates the query vector is exactly 4096-d before searching.

### 4.2 Horizon / disclosure gating
`NativeEvidenceVectorStore.search()` (`evidence_vector_store.py:344-410`) builds a compound Weaviate filter (`case_id`, `source_availability_complete=True`, `authority_state=active`, `disclosure_tier IN (...)`, optional `source_available_from <= horizon`) **before** ranking — supports both `near_vector` and `hybrid` (alpha-weighted, `query_properties=["content"]`) modes. Callers on the agent surface must present a `walk_run_id/walk_step_id/checkpoint_id` that resolves (via `working.walk_run`/`walk_step`/`walk_checkpoint`, `native_evidence_search_routes.py:126-197`) to a server-derived `case_id/actor/horizon/disclosure_tiers` — the caller cannot self-assert permission. Operator route is capped to `_SAFE_TIERS = (contemporaneous, discovered)` — hindsight is agent/walk-only.

### 4.3 Reranking
`NvidiaReranker` (`server/core/reranker.py:32-71`) — direct HTTP client to NVIDIA NIM's native ranking endpoint (`nvidia/rerank-qa-mistral-4b`, `ai.api.nvidia.com`), subclassing `agno.knowledge.reranker.base.Reranker` because Agno ships no NVIDIA reranker and its Cohere reranker ignores `base_url`. On any failure it returns documents unranked rather than failing retrieval (reranker.py:69-71). **Wiring not verified in this pass** — grep for the Knowledge-instance construction that passes `reranker=NvidiaReranker(...)` would confirm; not found in the files read (candidate for follow-up, not claimed wired or orphaned here).

### 4.4 MCP tool exposure
`enable_mcp_server=True` on `AgentOS` (`server/api/main.py:452`) exposes Agno's standard MCP surface (agent/team run, knowledge search) at the mounted `/mcp`. No custom MCP `@tool` was found wrapping `/v1/evidence/search` or `/v1/records` directly; those are plain HTTP routes. The atomic-tool mesh (`server/tools/registry.py`, `server/tools/gateway/`) is a separate polyglot tool-calling layer (parsers, extractors, repair tools) — not itself an MCP server in this repo (a "gateway" abstraction, `server/tools/gateway/mcp_chain.py`/`toolfinder.py`, exists to front MCP-shaped tool calls, not independently verified as live in this pass).

---

## 5. Evidence / custody

### 5.1 Hashing construction (quoted from source)

Custody is **sole-writer gated**: `server/evidence/custody.py` docstring (lines 10-13) — *"This module is the ONLY writer of the `evidence` schema (chain-of-custody guarantee). Agent DB connections ride the read-only engine (ADR-0005) and physically cannot write here."*

- **H1** (`H1_CANON = "h1-rawbytes-v1"`, custody.py:381) — plain `sha256` over raw file bytes, computed streaming (`_sha256_file`, custody.py:133-138), 1MB chunks.
- **H2** (`H2_CANON = "h2-rawelement-v1"`, custody.py:382) — per-record hash, computed by the Go SBV engine (`sbv:internal.custody.HashRecordH2`), reconciled/cross-checked here (never generated by `ingest_artifact` itself).
- **H3** (`H3_CANON = "h3-chain-sbv-genesisempty-v1"`, custody.py:383) — chain hash over the H2 sequence, computed by SBV (`sbv:internal.custody.ChainH3`). **Deliberately diverges from a legacy tag**: `H3_CANON_LEGACY = "h3-chain-v1"` (custody.py:384) — quoted rationale (custody.py:374-380): *"the bare `h3-chain-v1` tag is ambiguous — the Case Bible vault writes an equally-valid H1-genesis chain under the SAME tag... Legacy rows are never relabelled (that would be tampering); disambiguate legacy rows by writer."*
- Cross-check flow: `reconcile_sbv_import()` (custody.py:470-546) independently recomputes H1 via `ingest_artifact()`, compares to SBV's reported H1; on mismatch emits only an `integrity_violation` custody event and **deliberately does not record SBV's H2/H3** ("they cannot be trusted if the file itself disagrees", custody.py:485-487).

### 5.2 Chain-of-custody / immutability
- `evidence.custody_event` is append-only and **hash-chained** by a DB trigger (`prev_event_digest`/`event_digest`, `sql/_manual/...ddl.sql:46-61`) — event types: `collected, sealed, in_processing, verified, disputed, released, re_hashed, integrity_violation, superseded, accessed`.
- Blobs are write-once with post-copy re-hash verification before atomic `os.replace` (custody.py:254-270) — never overwritten.
- Dedupe-by-digest: re-ingesting identical bytes returns the existing `ArtifactRef` (`duplicate=True`), never rewrites (custody.py:180-252).
- Independent operational audit ledger: `ops.audit_ledger` (`sql/0020_audit_ledger.sql:58`), hash-chained, written by `server/core/audit.py:record_read()`. `verify_chain()` (audit.py:514-...) walks the ledger re-deriving every `entry_hash`, raising `AuditChainError` on the first mismatch — **documented as "not wired"** into startup or the backup cycle (audit.py:520-521); only callable via `scripts/audit_dump.py:199` (§6).

### 5.3 Export / bundle
No dedicated "evidence bundle export" endpoint or function was found in `server/api/` or `server/evidence/` in this pass (`evidence.source.export_status` column exists as a status field, `sql/_manual/...ddl.sql`, but no writer of it or bundling code was located). `evidence/run_report.py` produces per-run reports (`GET /v1/runs/{run_id}/report`, `run_routes.py:538`), which is receipt/manifest-level, not an evidentiary export bundle.

### 5.4 Two-tier custody
`ingest_artifact(..., tier: str = "full")` (custody.py:173-201) accepts `"full"|"light"`; both tiers currently execute an identical write path (sha256 + dedupe + blob + H1 row) — `tier` is stamped into `meta['custody_tier']` for future branching (a per-record H2/H3 hook that does not yet exist at this call site, per the docstring, custody.py:184-199) but has **no behavioral effect today** beyond the stamp.

---

## 6. Known-broken / disabled / stubbed

| Item | Location | Status |
|---|---|---|
| Migration 0030 (`analysis.matter`, `court_case`, `matter_knowledge_partition`, `knowledge_evidence_promotion`) | `sql/0030_matter_case_foundation.sql:5-7` | **Drafted, static-validated, NOT applied to any database** — explicit owner hold, "apply only after 0026-0029 review". Case-management routes/repository code already exist and reference this shape (`server/api/case_management_routes.py`, `server/case_management/repository.py`) — verify against the live DB before trusting `/v1/matters*`. |
| `server/api/mcp_main.py` (whole file) | mcp_main.py:1-57 | **DEPRECATED 2026-07-23**, "retired, kept for historical reference only" — standalone MCP ASGI workaround for a bug fixed upstream in agno 2.8.0. Not imported by any live code path; the mounted `/mcp` on the main AgentOS app (`main.py:452`) is the live surface. |
| `server/evidence/normalize.py` | normalize.py:1 | **DEPRECATED shim** — "Import from `server.contracts.records` instead" (ADR-0035). |
| `record_approval()` audit helper | `server/core/audit.py:33-47` | Implemented, **zero callers** anywhere in the repo — "documented here for S6, not wired" into the native `/approvals` resolve path. |
| `verify_chain()` audit-chain verification | `server/core/audit.py:514-...` | Implemented, **only called from `scripts/audit_dump.py:199`** (a manual CLI script) — not run at API startup or on any backup schedule, contrary to its own docstring's stated intent (audit.py:520-524). |
| Semantica worker/extraction pipeline | `server/analysis/semantica_worker.py`, `semantica_candidates.py`, `semantica_contracts.py`, `semantica_wiring.py` | **Config-only / orphaned from any route, agent, or tool** — grep across `server/api`, `server/agents`, `server/tools`, `scripts` found exactly one caller: `scripts/run_semantica_fixture.py` (a standalone fixture runner). `semantica_wiring.py` builds config dicts only, "performs NO writes and bakes NO secrets... deployment and all projection activation remain approval-gated" (semantica_wiring.py:26-27). |
| Chonkie remote executor | `server/analysis/chonkie_chunkers.py:192` | Comment: *"not on this CPU-only box (DECISION_LOG D-046). The remote executor is not wired yet"* — a documented gap, chunking falls back to local CPU chunkers. |
| OCR escalation to a heavy provider | `server/tools/extractors/extract_text.py:20-24` | Docstring describes a 3rd OCR tier (Docling/Cloud Vision/Document AI/Textract) but the module itself is stateless — "a stateless tool can't call a remote provider here, so when the result is low_confidence the CALLER escalates" — no in-repo caller performing that escalation was located in this pass. |
| Graph **search/query** capability | `server/analysis/graphiti_case_client.py` (165 lines total) | Only `add_memory()` (write/episode-queue) is implemented; no query/search method exists in this client. Graph retrieval is not available through this repo's code today — only ingestion into the external Graphiti/Neo4j `memory` database. |
| Milvus | referenced as `"deprecated compatibility alias"` at `server/api/inspect_routes.py:596` and `server/api/run_routes.py:436,449` | Superseded by Weaviate (ADR-0040 cutover); kept only for the separate `memsearch` product per `semantica_wiring.py:14`. |
| `evidence.source.export_status` column | `sql/_manual/20260802_reconcile_evidence_ddl.sql` | Column exists in the captured live DDL; no writer or export/bundle code found referencing it in this pass. |

### 6.1 Abandoned-attempt directories (noted, not read in depth per task scope)
- `_stale/00_analysis_graph.surql.SUPERSEDED` — a SurrealDB graph schema; SurrealDB was abandoned platform-wide (Postgres-first flatten, per repo history), this is that abandonment's artifact.
- `_stale/compose.browser.yaml.SUPERSEDED`, `compose.data.yaml.SUPERSEDED`, `compose.ui.yaml.SUPERSEDED` — earlier Docker Compose service-split attempts, superseded by the current compose layout.
- `_stale/gen_validate_0008.py.SUPERSEDED`, `_stale/validate_0008_working_schema.sql.SUPERSEDED` — an earlier validation pass for migration 0008, superseded.
- `_stale/sbv_sms_map_message_legacy.py` — a legacy SBV SMS message-mapping implementation, replaced by the current `server/tools/parsers/messaging/sbv_sms.py`.
- `to_be_deleted/` — empty at inspection time.
- `live-dumps/ontology_20260708T130849Z.json` — a captured ontology snapshot from an earlier pass (2026-07-08), left as a dump rather than wired into any live path.
- `docs/reports/_stale/recovery-run1-203756` — an earlier recovery-run report, superseded.

---

## Summary of WIRED vs ORPHANED (verified by caller-search, not inference)

**WIRED** (reachable from a route/CLI/tool, callers confirmed):
- Ingest: `POST /v1/ingest`, `/v1/ingest/path`, `POST /v1/knowledge/reindex`, CLI `server/evidence/cli.py`.
- Custody: `evidence.custody.ingest_artifact`/`reconcile_sbv_import`/`record_custody_event` — sole writer, called from `ingest_file()`.
- Chunking: `lane_chunker()` — called from KB creation and `chunk_records()`.
- Vector search: `POST /v1/evidence/search`, `POST /v1/operator/evidence/search`, Agno's mounted `/knowledge/search`.
- Keyword/provenance search: `GET /v1/records`.
- Graph write: `GraphitiCaseClient.add_memory()` — called from `context_chat_ingest.sync_pending_context()`, called from the registered tool `server/tools/ingest/context_drain.py`.
- Audit read logging: `server.core.audit.record_read()` — called from both `evidence_search()` and `native_evidence_search()`.

**ORPHANED** (defined, no caller found outside tests/fixtures/self-reference):
- `server.core.audit.record_approval()` — zero callers.
- `server.core.audit.verify_chain()` — only a manual CLI script.
- Semantica worker/candidate pipeline — only a fixture script.
- Graph search/query — not implemented at all (distinct from orphaned; the capability does not exist).
- `server/api/mcp_main.py` — explicitly retired, zero imports.
