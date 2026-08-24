# Lane 1a — Agno ingest pipeline trace

> _Byline: Claude Code · Opus 5 · 2026-08-23_ · source: subagent a6fc1902ccc6366b2

Repo: `Agno-MCP-Platform`. Read-only. 22 files read in full + targeted greps.

## Headline: THREE parallel, non-converging ingest paths

1. `server/ingest/service.py::ingest_file` — the "canonical" path, wired to live HTTP routes
   `/v1/ingest` (`server/api/ingest_routes.py:114`) and `/v1/ingest/path` (`:161`),
   registered at `server/api/main.py:391`. Writes `working.normalized_record` /
   `working.normalized_record_chunk`.
2. `server/analysis/context_chat_ingest.py::ingest_chat_file` (+ `chat_archive.py::ingest_chat_archive`
   for ZIPs) — the richer PG-first chat path with conversation/message/chunk tables, multi-label lane
   classification, and a Weaviate/Graphiti projection outbox. **Reachable ONLY from
   `scripts/ingest_context_chat.py` (a CLI) and tests — no API route calls it.** Writes
   `working.chat_conversation` / `chat_message` / `chat_chunk` / `chat_chunk_lane` / `chat_chunk_projection`.
3. `server/core/session.py::create_knowledge` (`:380-430`) — builds Agno `Knowledge` objects and wires
   `chunking_policy.lane_chunker` (`server/analysis/chunking_policy.py:44`) onto Agno's own readers
   (text, markdown, pdf, json, csv, docx). A separate storage/query surface again.

These three share no chunkers and no tables. A chat export uploaded via the live `/v1/ingest`
HTTP endpoint gets NONE of the classification/lane-routing/chat-table treatment.

## 1. Types ingestible end-to-end today

Trace: `ingest_routes.py:114` or `:161` → `service.py::ingest_file:264` → `_parse:185` →
`_extract_document:143` OR `chat_parse.py::parse_chat_export:33` → `_whole_file_text:127` fallback
→ `server/ingest/chunking.py::chunk_records:85` → `server/evidence/store.py::store_record_batch`.

Routing (`service.py:26-28,143-237`):

- `_DOCUMENT_SUFFIXES = {.pdf,.docx,.pptx,.xlsx,.html,.htm}` → `_extract_document:143`, UNLESS
  `lane is evidence` or an explicit `coverage_hint` is given (`:197`).
- `_GO_SUFFIXES = {.xml,.eml,.mbox,.ndjson,.csv}` → SBV Go engine by default (`:26,204`).
- `.xml` sniffed for `<smses` / `<sms ` / `<mms ` → force-hint `smsbackuprestore-xml` (`:199-202`).
- else → `_parse_via_registry` → `parse_chat_export` → `_whole_file_text:127`, which only accepts
  `.md`/`.txt` (`_TEXT_SUFFIXES`, `:27`) and is FORBIDDEN for the evidence lane (`:130-131`, ADR-0044).

| Format | Extractor | Real today? |
|---|---|---|
| `.pdf` | `documents.extract-docling` then `documents.extract-text` (`:150-158`) | YES for text-layer PDFs. `pypdf==6.15.0`, `pdfplumber==0.11.10` in requirements.txt. OCR fallback (pytesseract/pdf2image, `server/tools/extractors/extract_text.py:1-20`) is an OPTIONAL `ocr` extra (`pyproject.toml:83`) NOT in requirements.txt → scanned PDFs do NOT OCR by default. |
| `.docx/.pptx/.xlsx/.html/.htm` | docling only; no fallback registered (`:155-158` only adds extract-text for .pdf) | **NOT FUNCTIONAL by default.** docling is gated behind the `document-ai` extra (`pyproject.toml:87`) and is ABSENT from requirements.txt. The extractors list is empty → `_extract_document:180-182` raises ValueError → the whole ingest fails, receipt status "failed" (`:485`). |
| `.md/.txt` | `_whole_file_text:127` or registry | Yes, trivially. |
| AI-chat exports (ChatGPT official JSON, Claude export, Perplexity contexts/GDPR/plugin/md, Gemini JSON/MD/Chrome, custom-GPT MD, share MD, Claude Code MD) | `server/tools/parsers/ai_chat/*.py`, 12 files, `capability="parse.transcript"` | Yes, real registered parsers. |
| SMS XML, .eml/.mbox, FB Messenger, Google Chat/Voice, iMessage, generic transcript, .ndjson, .csv | Go SBV engine, `GO_IMPORTER_FORMATS` (`server/analysis/format_router.py:65-79`) via `sbv_transcript.py` | **Real and built** — `build/swift-mvp-sbv/sbv.exe` exists on disk. |
| Bare images (.png/.jpg) | none — not in `_DOCUMENT_SUFFIXES`, no image branch in `_parse` | Not part of `ingest_file` at all. Images are only handled inside archive materialization (`context_assets.py::extract_asset_text:357`), a separate path. |

Evidence-lane restrictions: `_whole_file_text` forbidden (`:130-131`); `_EVIDENCE_FORBIDDEN_PARSERS =
{"transcripts.markdown","documents.text-v1"}` (`:29,232-233`); AND the document-extraction branch is
skipped entirely when `lane is evidence` (`:197`) — meaning **the evidence lane cannot ingest
PDF/DOCX at all through this router**, only chat/transcript/Go registry routes.

## 2. Where ingest starts and terminates

Entry: `POST /v1/ingest` (`ingest_routes.py:114`) multipart, staged to disk (`_stage_upload:49`,
`INGEST_STAGING_ROOT`, default `/tmp/horizon-ingest-staging`), then run as a **fire-and-forget asyncio
task** (`_submit_ingest:98`), returning 202 + receipt_id; the caller must poll
`/v1/knowledge/items/{artifact_id}`. `POST /v1/ingest/path` (`:161`) is synchronous, returns 201.
Registration is unconditional at startup (`main.py:378,391`), not flag-gated.

Four journaled stages — custody → parse → store → projection — via `server/evidence/run_ledger.py`
(`PostgresReceiptJournal`, `service.py:53-101`).

Termination:

1. **Custody**: `server/evidence/custody.py::ingest_artifact` (`service.py:288`) — hashes, write-once
   blob, returns `Artifact(artifact_id, sha256, duplicate, acquisition_id)`.
2. **Chunk**: `chunking.py:85` Chonkie `RecursiveChunker(tokenizer="character", chunk_size=1500)`
   HARDCODED — never consults `chunking_policy.lane_chunker`.
3. **Store**: `store_record_batch` (`service.py:294,360-375`) → `working.normalized_record` +
   `working.normalized_record_chunk` (confirmed via `server/ingest/query.py:47-100`).
4. **Projection**: best-effort outbox drain to Weaviate via
   `server/evidence/vector_projection.py::NativeEvidenceProjector` when a `native_projector` is passed
   (`main.py:336-339,391`); can be `None` → silently reports "skipped" (`service.py:401-430`).

Receipt: `IngestReceipt` (`server/contracts/ingest.py:120-142`). Read-back:
`GET /v1/knowledge/items[/{artifact_id}]` (`ingest_routes.py:183-202`).

## 3. Stubs

Greps: `STUB:` → 0 in code (3 hits in `server/contracts/AGENTS.md` policy text).
`TODO` → 1 (`server/analysis/detection.py:32`, a DB-index note; the guard it refers to is already
implemented at `:253-261`).
`raise NotImplementedError` → 1 (`server/analysis/chonkie_chunkers.py:203`, `_RemoteChunkerStub.chunk`,
backing the neural/late/slumber remote chunkers at `:207-211`; unreachable — `chunking_policy` only
ever selects `cpu_chunker("recursive")` or `TranscriptSemanticHybridChunking`). Benign/by-design.

**Highest-impact undocumented gap:** `server/tools/extractors/docling_extract.py:31-34` raises
`RuntimeError("Docling is unavailable; install the document-ai extra")`. DOCX/PPTX/XLSX/HTML ingest is
dead-on-arrival in a default install, with NO `STUB:` marker and NO `docs/URGENT-TODO.md` entry —
violating the repo's own mandate at `server/contracts/AGENTS.md:60-61`.

No bare `pass`, no `...` bodies, no fake return values found.

## 4. Chunking — not orphaned, but split across two call graphs that never merge

- `server/ingest/chunking.py::chunk_records` — called ONLY by `service.py:321-323`. Hardcodes
  `RecursiveChunker` (1500 chars), bypasses `chunking_policy` entirely.
- `chunking_policy.lane_chunker` — called by `session.py:421-425` in `create_knowledge`, wiring Agno's
  own readers. A real live call site, but on Agno's `Knowledge.add_content` surface, not the HTTP path.
- `chonkie_chunkers.cpu_chunker` / `semantic` / `TranscriptSemanticHybridChunking` — called from
  `chunking_policy.lane_chunker:64-73`. The REMOTE half is unreachable.
- `chunk_chat_messages` (`context_chat_ingest.py:159-192`) — a THIRD chunking implementation,
  message-boundary-preserving, Chonkie `SemanticChunker` (`:121-131`) or a `message-window` fallback.

Net: all three modules have real callers, none dead — but the one reachable from `/v1/ingest` never
uses lane-aware selection, and the chat-tuned chunker is invisible to HTTP uploads.

## 5. Semantica — parallel, NOT wired into ingest

`semantica_worker.py` / `semantica_contracts.py` / `semantica_candidates.py` / `semantica_wiring.py`
form a credential-free, governed candidate-extraction subsystem.

- `SemanticaPatternWorker.extract` (`semantica_worker.py:120-159`) takes custody-approved
  `working.normalized_record` snapshots (content-hash-verified, `semantica_contracts.py:17-36`), runs
  three deterministic pattern extractors from vendored `server.vendored.semantica` (`:33-36`), and emits
  Entity/Fact/EventCandidate (`semantica_contracts.py:78-123`). It explicitly REFUSES Semantica's
  fabricating `related_to` RelationExtractor fallback (`:227-235`).
- Writes ONLY `working.extraction_run` / `candidate_entity` / `candidate_fact` / `candidate_event`
  (allowlist `submitted_tables()`, `semantica_candidates.py:324-333`). No custody/Neo4j/Weaviate/
  Surreal/promotion write.
- `semantica_wiring.py` builds config DICTS only, no I/O (`:26-27`); `worker_wiring():133-149` states
  `deploy: "APPROVALS-gated; fixture/in-process adapter only"`.

Callers (grep): only `tests/test_semantica_phase1_worker.py`, `tests/test_semantica_wiring.py`, and
`scripts/run_semantica_fixture.py`. **No production code calls any semantica module.**
Orphaned from live ingest by explicit design (candidate-only, approval-gated), but not functioning as
part of ingest for gap-analysis purposes.

## 6. Chat ingest — parallel path, different destination schema

ZIP detection (`chat_archive.py:36-53`): `conversations*.json` as the log; a fixed set of sidecar
basenames (users.json, projects.json, memories.json, message_feedback.json, model_comparisons.json,
shared_conversations.json) inventoried but never parsed as transcripts.

Signature detection (`format_router.py::detect_format:97`): only 3 hardcoded head-byte signatures —
chatgpt-official ("mapping"+"create_time"), perplexity-contexts, claude-ai-export ("chat_messages")
(`:49-57`). Everything else → the full registry (`chat_parse.py:88-113`).

Non-AI-chat formats (SMS XML, .eml/.mbox, FB, Google Chat/Voice, iMessage) are NOT part of this
chat-archive path — they go through the Go SBV engine on the OTHER path.

Destination divergence, confirmed by direct comparison:

- `ingest_file` → generic NormalizedRecords → `_enrich:239-261` → flat `chunk_records` →
  `working.normalized_record[_chunk]`. No conversation modeling, no lane classification, no per-lane
  Weaviate routing.
- `ingest_chat_file` → `normalize_many` (`chat_normalizer.py:125`) → ChatConversation+ChatMessage →
  `chunk_chat_messages` → `lane_classifier.classify_chunks` into {platform, legal, personal_history,
  context} (never `evidence` — Pydantic-enforced, `records.py:231-236`) → `working.chat_*` tables
  (`:195-357`) → optional Weaviate per-lane (`LANE_COLLECTIONS`, `:43-48`) + Graphiti drain.

**Consequence:** a user uploading a ChatGPT/Claude export through the documented, authenticated, live
HTTP API gets flat generic records — no conversation grouping, no role-aware boundaries, no lane
classification, no per-lane projection. Grep confirms no HTTP route and no `service.py` call into
`context_chat_ingest.py` / `chat_archive.py` anywhere.

Bonus: `chat_archive.ingest_chat_archive:197-205` also calls `context_assets.materialize_archive`
for every non-log ZIP member → a FOURTH destination schema, `working.context_archive` /
`working.context_asset` (`context_assets.py:251-353`), content-addressed, deduped by sha256, blobs
written to an R2 mount (`context_blob_root()`, `:145-149`, default `/r2/context-assets`). CLI-only.

## Reachability from the live `POST /v1/ingest`

| Component | Reachable? |
|---|---|
| `service.py::ingest_file` | Yes (entry point) |
| `chunking.py::chunk_records` | Yes |
| PDF text extraction (pypdf/pdfplumber) | Yes |
| PDF OCR (Tesseract) | No — optional extra not installed |
| DOCX/PPTX/XLSX/HTML (docling) | No — extra not installed; ingest FAILS for these types |
| AI-chat Python parsers | Yes, but only flat NormalizedRecords |
| Go SBV engine | Yes |
| `chunking_policy.py` lane-aware chunking | No |
| `context_chat_ingest.py` (chat_* tables) | No |
| `chat_archive.py` (ZIP + asset materialization) | No |
| `context_assets.py` (archive asset store) | No |
| `semantica_*` (candidate extraction) | No — approval-gated, script/test only |
