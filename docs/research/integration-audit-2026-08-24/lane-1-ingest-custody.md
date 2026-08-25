# Lane 1 — Ingest and Custody Path: Evidence-Only Inventory

> _Byline: lane-1 agent · Sonnet · 2026-08-24_

Scope: every ingest entrypoint, the custody module, the parser registry, and the
Temporal layer in `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform`.
Every claim below carries a `file:line` citation to code actually read in this repo
during this audit. Anything not directly verified is marked **UNKNOWN — not verified**.
No recommendations are included; this is inventory only.

---

## 0. Summary table — entrypoints

| # | Name | How called | Input | Lane(s) | Custody? | Evidence |
|---|---|---|---|---|---|---|
| 1 | `scripts/ingest_context_chat.py` | CLI: `uv run --no-sync python scripts/ingest_context_chat.py <path> [--dry-run] [--conversation-id ...] [--db-host ...]` | Single chat-export file (`.zip` or bare JSON/MD) | `context` (and platform/legal/personal_history via post-chunk multi-label classification) | No (AI-chat lane never enters evidence; explicit in module docstring) | `scripts/ingest_context_chat.py:1-24`, `server/analysis/context_chat_ingest.py:1-5` |
| 2 | `scripts/ingest_knowledge.py` (`ingest_all()`) | CLI: `docker exec agentos-api python -m scripts.ingest_knowledge`; also HTTP `POST /v1/knowledge/reindex` | Folder walk of 4 knowledge roots (`platform`, `legal`, `personal_history`, `relationship_timeline`→`personal_history`) | `platform`, `legal`, `personal_history` (never `evidence`; `context` explicitly excluded) | Yes — routes every file through `ingest_file` → `ingest_artifact` (custody) | `scripts/ingest_knowledge.py:7-8,43-53,64,93-109`, `server/api/main.py:187-201` |
| 3 | `POST /v1/ingest` (HTTP) | Multipart upload, async/backgrounded | `file` upload + form fields (`lane`, `matter_id`, `custody_tier`, etc.) | Caller-selectable `IngestLane` (`platform`\|`legal`\|`personal_history`\|`context`\|`evidence`) | Yes — via `ingest_file` → `server.evidence.custody.ingest_artifact` | `server/api/ingest_routes.py:114-159`, `server/ingest/service.py:287-309` |
| 4 | `POST /v1/ingest/path` (HTTP) | JSON body = `IngestRequest`, synchronous | Pre-staged server-side file path | Same `IngestLane` set | Yes — same `ingest_file` path | `server/api/ingest_routes.py:161-181` |
| 5 | `GET /v1/knowledge/items`, `GET /v1/knowledge/items/{artifact_id}` (HTTP) | Query params | n/a (read-only) | Filter by `IngestLane` | n/a (read) | `server/api/ingest_routes.py:183-202`, `server/ingest/query.py:37-114` |
| 6 | `POST /v1/evidence/import` (HTTP) | Multipart upload, synchronous | `file` upload + `workflow="chat-transcript"` + `domain` form field | `domain` param: `platform`\|`legal`\|`personal_history`\|`context`\|`evidence` | Yes — calls legacy `run_chat_transcript` → `ingest_artifact` | `server/api/evidence_routes.py:36-98`, `server/api/main.py:374-388` |
| 7 | `POST /v1/runs/...` (`register_run_routes`, `_execute_run`) | HTTP, backgrounded run with run-ledger tracking | `workflow` selects `run_chat_transcript` or `run_sms_xml` | via `domain` param | Yes — same `run_chat_transcript`/`run_sms_xml` | `server/api/run_routes.py:233-249` |
| 8 | `server/evidence/cli.py` (`python -m server.evidence import`) | CLI subcommand `_cmd_import` | Local file path | `--domain` arg | Yes — dispatches to `run_chat_transcript`/`run_sms_xml` | `server/evidence/cli.py:25-57` |
| 9 | Temporal `ChatTranscriptIngest` workflow (task queue `"evidence-pipeline"`, env `TEMPORAL_TASK_QUEUE`) + 4 activities + `P0DurabilityProbe` + worker | **Not started from any HTTP route, CLI script, or other code path found in this repo** — a `temporalio` client (`Client.connect` + `start_workflow`/`signal`/`query`) would have to be written from scratch; none exists today | `ChatTranscriptInput` dataclass: `path` (required), `source_meta`, `lane` (default `"context"`), `custody_tier` (default `"light"`), `parent_run_id`, `run_id`, `supervised` (bool) | `lane` field, any `IngestLane`-shaped string | Yes, inside `custody_activity` (calls the same `ingest_artifact`) | see §4 for full detail; `server/temporal/__init__.py:4-11` and `server/temporal/workflows.py:4-5` self-document as **INERT** |

Row 9 is the single most important fact for an n8n integration plan: the Temporal
layer exists as complete, working code (activities, workflow, signal, query, worker,
retry policies, gate logic, two swappable knowledge harnesses) but self-documents as
not dispatched from anywhere in this repository — starting it requires standing up a
Temporal client call that does not currently exist in the codebase. The callable, live
paths today are rows 1–8 (HTTP routes, CLI scripts, and the legacy in-process agno
`Workflow` in `server/evidence/workflows.py::run_chat_transcript`).

---

## 1. Ingest entrypoints — detail

### 1.1 `scripts/ingest_context_chat.py` (CLI)

- Docstring / usage block: `scripts/ingest_context_chat.py:1-24`.
- Invocation: `uv run --no-sync python scripts/ingest_context_chat.py <path> --dry-run`, or with `--conversation-id <id>` (repeatable), `--db-host <host>`, `--no-project` (`scripts/ingest_context_chat.py:9-21,46-107`).
- Full CLI flags (`scripts/ingest_context_chat.py:46-107`): `path` (positional), `--conversation-id` (repeatable, default all), `--dry-run` (no PG write, no projection), `--no-project` (write PG only, skip Weaviate/Graphiti), `--max-chars` (default 6000), `--chunker` (`message-window`\|`chonkie-semantic`\[default\]\|`teraflopai`), `--no-classify`, `--classify-mode` (`keyword`\|`cpu`\|`hybrid`\[default\]), `--classify-model`, `--engine` (`auto`\[default\]\|`python`\|`go`), `--format` (strict override, bypasses detection, exit 2 on mismatch — D-053), `--db-host`.
- Dispatch: if `path` ends in `.zip`, calls `server.analysis.chat_archive.ingest_chat_archive(...)`; otherwise calls `server.analysis.context_chat_ingest.ingest_chat_file(...)` (`scripts/ingest_context_chat.py:121-158`).
- On `ValueError`/`FileNotFoundError`, prints `error: <exc>` to stderr and exits 2 (`scripts/ingest_context_chat.py:159-161`); otherwise prints a JSON `IngestReport` to stdout and exits 0 (`:162-163`).
- Writes: PG-first. `working.chat_conversation`, `working.chat_message`, `working.chat_chunk`, `working.chat_chunk_message`, `working.chat_chunk_lane`, `working.chat_chunk_projection` (all in `server/analysis/context_chat_ingest.py:195-357`); optionally embeds and projects into Weaviate collections `platform_knowledge`/`legal_knowledge`/`personal_history_knowledge`/`platform_context` (`server/analysis/context_chat_ingest.py:43-48,478-529`) and/or Graphiti (`:532-543`), plus caches embeddings in `working.chat_chunk_embedding` (`:453-475`).
- Never writes to the evidence lane: "AI-chat material never enters the evidence lane" (`scripts/ingest_context_chat.py:7`, restated `server/analysis/context_chat_ingest.py:4-5`).
- Custody hashes: **not computed** in this path — only `content_hash` (SHA-256 of `conversation_id:indexes:content`, `server/analysis/context_chat_ingest.py:179-185`) and message-level `compute_content_hash` (`server/analysis/chat_normalizer.py`, referenced `context_chat_ingest.py:23,250`) — these are content-dedup hashes, not the `evidence.evidence_hash` custody chain.

### 1.2 `server/analysis/chat_archive.py` — ZIP front door (used by 1.1 for `.zip` input)

- Purpose: real chat exports arrive as ZIPs with `conversations*.json` + sidecar metadata + an `assets/` folder; this module inventories the archive without extracting everything, extracts only conversation logs, and hands each to `ingest_chat_file` (`server/analysis/chat_archive.py:1-22`).
- `inventory_archive(zip_path)` classifies every member into `conversation_logs`, `metadata_files` (fixed basename set: `users.json`, `user.json`, `projects.json`, `memories.json`, `message_feedback.json`, `model_comparisons.json`, `shared_conversations.json` — `chat_archive.py:42-52`), or `asset_files` (`chat_archive.py:94-111`).
- `ingest_chat_archive(zip_path, ...)` raises `ValueError` if zero conversation logs found (`chat_archive.py:166-171`); otherwise safely extracts each log (zip-slip guarded, `chat_archive.py:114-127`) to a temp dir and calls `ingest_chat_file` per log (`chat_archive.py:176-192`); also calls `materialize_archive(zip_path, ...)` from `server.analysis.context_assets` to persist assets/metadata (`chat_archive.py:197-199`, `dry_run=dry_run or not materialize_assets`).
- Recognized real-world shapes: Claude `data-*.zip` (conversations.json + users.json + projects.json + memories.json); ChatGPT/Perplexity `user_data_export_*.zip` (conversations-*.json + spreadsheet + `assets/`) (`chat_archive.py:7-11`).

### 1.3 `server/analysis/chat_parse.py` — engine/format routing (used by 1.1/1.2)

- `parse_chat_export(path, source_meta=None, *, engine="auto", format=None)` (`server/analysis/chat_parse.py:33-85`): validates `engine in VALID_ENGINES = ("auto","python","go")` (`:17,43-44`); if `format` is explicitly given, resolves via `server.analysis.format_router.resolve_format_override(format, engine)` and dispatches strictly to Go SBV (`server.analysis.sbv_transcript.parse_via_sbv`) or a pinned Python tool from the registry, with **no fallback** on failure (`:48-57,116-136`). If `engine=="auto"` (default), calls `detect_format(path)` and tries Go first (best-effort, falls through on exception) then the detected Python parser, then the full registry-resolution fallback (`:66-85`).
- Underlying Python-registry path calls `server.tools.registry.registry.resolve("parse.transcript", media_hint=path.name.lower(), size_bytes=...)` and tries candidates in order, logging each attempt (`server/analysis/chat_parse.py:88-113`).

### 1.4 `scripts/ingest_knowledge.py` — `ingest_all()` (CLI + HTTP-triggered)

- Signature: `async def ingest_all(_knowledge=None, bases: dict | None = None) -> int` (`scripts/ingest_knowledge.py:64`); `_knowledge`/`bases` are accepted only for source-compatibility and are ignored (`:66-68,73`).
- Knowledge roots walked (`scripts/ingest_knowledge.py:46-53`): `platform` → env `KNOWLEDGE_BASE_PATH` default `/app/knowledge/platform`; `legal` → `KNOWLEDGE_LEGAL_PATH` default `/app/knowledge/legal`; `personal_history` → `KNOWLEDGE_PERSONAL_HISTORY_PATH` default `/app/knowledge/personal_history`; `relationship_timeline` → `KNOWLEDGE_RELATIONSHIP_TIMELINE_PATH` default `/app/knowledge/relationship_timeline` (folded into the `personal_history` lane at ingest time).
- Deliberately absent roots: `evidence` has no folder-walk root ("its only writer is the custody path"); `context` ingests via `server/analysis/context_chat_ingest.py`, not this walker (`scripts/ingest_knowledge.py:43-45`).
- Allowlist: `ALLOWED_EXT = {".md", ".txt", ".json", ".csv", ".pdf", ".docx"}`; `MAX_SIZE = 50 MB` (skip + log if exceeded) (`scripts/ingest_knowledge.py:37-38,81-86`).
- Per file, calls `asyncio.to_thread(ingest_file, IngestRequest(staged_path=str(path), lane=lane, matter_id="primary", custody_tier="light", source_identity={...}))` — the SAME `ingest_file` used by the HTTP ingest routes (`scripts/ingest_knowledge.py:93-109`).
- Invocation 1 (documented CLI): `docker exec agentos-api python -m scripts.ingest_knowledge` (`scripts/ingest_knowledge.py:7-8`), via `if __name__ == "__main__": asyncio.run(main())` (`:123-124`).
- Invocation 2 (HTTP, on demand — NOT at process startup): `POST /v1/knowledge/reindex` (`server/api/main.py:187`), handler body `from scripts.ingest_knowledge import ingest_all; count = await ingest_all(); return {"indexedDocumentCount": count, "status": "completed", "store": "postgresql"}` (`server/api/main.py:198-201`). No `_authorize`-style call is visible on this specific route in `main.py` (unlike `ingest_routes.py`'s routes) — **UNKNOWN — not verified** whether any outer middleware gates it.

### 1.5 `POST /v1/ingest` — multipart upload (HTTP, async/backgrounded)

- Registration: `@app.post("/v1/ingest", status_code=202)` (`server/api/ingest_routes.py:114`), registered from `server/api/main.py:391` (`register_ingest_routes(app, native_projector)`).
- Auth: `_authorize(request)` (`server/api/ingest_routes.py:28-40`) — fail-closed: if env `OS_SECURITY_KEY` is unset, `HTTPException(503, "ingest authorization is not configured")`; else requires header `Authorization: Bearer <token>` matched via `secrets.compare_digest` against `OS_SECURITY_KEY`, else `401` (`:29-40`).
- Request is `await request.form()` (raw multipart), NOT a bound Pydantic model on the wire; handler manually builds `IngestRequest` from form fields (`server/api/ingest_routes.py:117-145`): `file` (required upload), `source_identity` (JSON object string), `message_corpus`, `source_principal`, `caller_owns_conversation` (bool-coerced), `acquisition` (JSON object string, forced `asserted_by="owner"`/`asserted_by_category="human"`), `coverage_hint`, `lane` (default `"platform"`), `matter_id` (default `"primary"`), `engine` (default `"auto"`), `allow_fallback` (bool-coerced, default false), `custody_tier` (default `"light"`); `staged_path` is server-computed, not client-supplied.
- Upload staging: `_stage_upload` (`server/api/ingest_routes.py:49-61`) streams the upload in 1 MiB chunks to `_staging_root()` (env `INGEST_STAGING_ROOT`, default `/tmp/horizon-ingest-staging`, `:43-46`) under `f"{uuid4()}-{safe_upload_name(...)}"` (`:51`); enforces `_MAX_UPLOAD_BYTES = 50 MB` (`:24`), renaming overflow files to `<name>.rejected-too-large` and raising `413` (`:57-60`).
- On success: response is submitted asynchronously via `_submit_ingest` (`:98-110`) — reserves a receipt via `PostgresReceiptJournal().start(...)` in a thread, then schedules `_run_reserved_ingest` as a tracked background `asyncio.Task` (`:107-109`) — **the HTTP response returns BEFORE ingest work completes.** Response body: `{"run_id": receipt_id, "workflow": "framework-neutral-ingest", "mode": "auto", "status": "running"}` (`:154-159`).
- Full `IngestRequest` model field list, `AcquisitionAssertion` fields, and the five `IngestLane` values are given once in §1.7/§1.8 below (shared by all `IngestRequest`-based routes).

### 1.6 `POST /v1/ingest/path` — staged-path (HTTP, synchronous)

- Registration: `@app.post("/v1/ingest/path", status_code=201)` (`server/api/ingest_routes.py:161`).
- Takes `payload: IngestRequest` directly as a JSON body (FastAPI-validated against the model) plus `request: Request` for auth (`:162-163`); same `_authorize` gate as §1.5.
- Same `acquisition` force-override (`asserted_by="owner"`, `asserted_by_category="human"`) as §1.5 (`:164-171`).
- **Synchronous:** `await asyncio.to_thread(ingest_file, payload, projector=native_projector)` is awaited directly (`:173`) — blocks until ingest completes or fails, unlike `/v1/ingest`.
- On success: `201`, body from `_receipt_response(receipt)` = `{"run_id": receipt.receipt_id, "workflow": "framework-neutral-ingest", "mode": "auto", "receipt": receipt.model_dump(mode="json")}` — the full `IngestReceipt` embedded (`:76-82`).
- On failure: catches `(FileNotFoundError, IngestError)` → `HTTPException(422, detail)` (`:174-180`).
- Caller supplies `staged_path` directly (a path that must already exist on the server, resolved via `Path(payload.staged_path).resolve(strict=True)` inside `ingest_file`, `server/ingest/service.py:275`) — no upload staging step (`INGEST_STAGING_ROOT` is not consulted by this route).

### 1.7 `IngestRequest` / `IngestLane` / `AcquisitionAssertion` contracts (`server/contracts/ingest.py`)

`IngestLane` enum (`server/contracts/ingest.py:23-28`) — five values, name == string value:
```
platform | legal | personal_history | context | evidence
```
Cross-reference: `server/ingest/service.py:30-36` and `server/ingest/query.py:19-25` both map each lane to a Postgres `domain` string: `platform`→`platform_design`, `legal`→`legal`, `personal_history`→`behavioral`, `context`→`context`, `evidence`→`evidence`.

`IngestRequest` fields (`server/contracts/ingest.py:65-79`): `staged_path: str`, `source_identity: dict[str, Any] = {}`, `message_corpus: Literal["first_party","acquired_third_party"] | None = None`, `source_principal: str | None = None`, `caller_owns_conversation: bool = False`, `acquisition: AcquisitionAssertion | None = None`, `coverage_hint: str | None = None`, `lane: IngestLane = IngestLane.platform`, `matter_id: str = "primary"`, `engine: Literal["auto","go","python"] = "auto"`, `allow_fallback: bool = False`, `custody_tier: Literal["full","light"] = "light"`.

Validation (`server/contracts/ingest.py:81-106`): `staged_path`/`matter_id` must be non-blank; `source_principal` if given must be non-blank; `message_corpus=="first_party"` requires `caller_owns_conversation=True` AND `source_principal` set; `message_corpus=="acquired_third_party"` requires `acquisition` set AND `source_principal` set.

`AcquisitionAssertion` fields (`server/contracts/ingest.py:31-62`): `acquired_at: datetime`, `method: Literal["own_device","household_device","voluntary_third_party","legal_process","public_source","unknown"] = "unknown"`, `authority: Literal["device_owner","parent_guardian","account_holder","consent_given","court_order","unclear"] = "unclear"`, `source_device: str|None`, `device_custodian: str|None`, `notes: str|None`, `asserted_by_category: Literal["human"]="human"`, `asserted_by: str="owner"` (non-blank).

### 1.8 `ingest_file` (`server/ingest/service.py`) — the shared write path for §1.4/1.5/1.6

- Composes "existing custody, parser, and PostgreSQL writers" (`server/ingest/service.py:3`).
- Stage 1 (custody): `from server.evidence.custody import ingest_artifact` (default, override-able via a `custody` callable param), called as `custody_fn(path, request.source_identity, tier=request.custody_tier, acquisition=request.acquisition.model_dump(...) if request.acquisition else None)` (`server/ingest/service.py:287-309`); records `{"artifact_id", "sha256", "duplicate"}` on success.
- `Artifact` protocol returned: `artifact_id: str`, `sha256: str`, `duplicate: bool`, `acquisition_id: str | None`, `acquired_at: datetime | None` (`server/ingest/service.py:39-45`). `artifact.sha256` surfaces as `IngestReceipt.source_sha256` (`:470,507`).
- Document extraction stage: `_extract_document` (`server/ingest/service.py:143-182`) lazily imports `server.tools.extractors.docling_extract.extract_docling`; for `.pdf` only, also chains `server.tools.extractors.extract_text.parse` as a second-chance extractor; iterates extractors in order, raising only if all fail (`:148-182`).
- No Temporal reference anywhere in `server/api/ingest_routes.py` or `server/ingest/service.py` — confirmed by direct grep (no matches for `temporal|Temporal|signal\(|workflow\.`); the only "workflow" occurrences are the literal label string `"framework-neutral-ingest"` and the unrelated `server.evidence.run_ledger` labeling call (`server/ingest/service.py:54,59-61`).

### 1.9 `GET /v1/knowledge/items` / `GET /v1/knowledge/items/{artifact_id}` (read-only)

- `GET /v1/knowledge/items` (`server/api/ingest_routes.py:183-192`): params `matter_id: str="primary"`, `lane: IngestLane|None=None`, `limit: int=100` (1–500, else `422`); delegates to `server.ingest.query.list_items(...)`.
- `list_items` (`server/ingest/query.py:37-64`): joins `working.normalized_record` (`r`) → `evidence.evidence_hash` (`e`) on `e.id = r.artifact_id`, left join `working.normalized_record_chunk` (`c`) on `c.normalized_record_id = r.id`; filters `r.case_id` + optional `r.domain`; one row per distinct `artifact_id` with `record_count`/`chunk_count`, ordered by earliest `created_at` desc, limited.
- `GET /v1/knowledge/items/{artifact_id}` (`server/api/ingest_routes.py:194-202`): delegates to `get_item(artifact_id, matter_id=...)` (`server/ingest/query.py:67-114`), which returns source rows + chunk rows for that artifact, or `404` if none found.

### 1.10 `POST /v1/evidence/import` — chat-transcript workflow (HTTP)

- Registration: `@app.post("/v1/evidence/import")` (`server/api/evidence_routes.py:64`), registered via `register_evidence_routes(app, _knowledge_handle)` at `server/api/main.py:388` (called from `_build_app()`, confirmed active — not dead code).
- Fields: `file: UploadFile`, `workflow: str = "chat-transcript"` (only allowed value; `_ALLOWED_WORKFLOWS = {"chat-transcript"}`, `evidence_routes.py:44`), `domain: str = "context"` (must be in `_ALLOWED_DOMAINS = {"platform","legal","personal_history","context","evidence"}`, `:35-41`), `source_meta: str = "{}"` (JSON) (`evidence_routes.py:65-70`).
- Validates `workflow`/`domain`/`source_meta` JSON, then writes the upload to a temp dir and calls `await run_chat_transcript(str(tmp_path), source_meta=meta, domain=domain, knowledge=resolve_knowledge(knowledge))` (`evidence_routes.py:79-98`) — the legacy in-code agno workflow (see §5).
- Returns the workflow's summary dict directly: `{workflow, status, artifact_id, sha256, duplicate, parser, parse_attempts, records_stored, step_log}` (per its own docstring, `evidence_routes.py:73-75`).
- Module note: this route was "ported verbatim from `main`" onto a branch that previously had no REST evidence-import route at all (`evidence_routes.py:9-14`) — i.e. its presence here is deliberate and current, not leftover.

### 1.11 `POST /v1/runs/...` and `server/evidence/cli.py` — other `run_chat_transcript` callers

- `server/api/run_routes.py:233-249` (`_execute_run`, inside `register_run_routes`): `runner = run_chat_transcript if workflow == "chat-transcript" else run_sms_xml`, then `await runner(str(tmp_path), source_meta=meta, domain=domain, ...)` — a second, run-ledger-tracked HTTP path to the same legacy workflow.
- `server/evidence/cli.py:25-57` (`_cmd_import`): `runners = {"chat-transcript": run_chat_transcript, ...}`; `asyncio.run(runners[args.workflow](args.path, ...))` — CLI entrypoint `python -m server.evidence import`.
- Both confirmed as production (non-test) callers of `run_chat_transcript` alongside `/v1/evidence/import`. `tests/test_run_ledger.py` also calls it directly, but only from test functions.

---

## 2. Custody module — `server/evidence/custody.py`

### 2.1 Public functions

| Function | Signature | What it does |
|---|---|---|
| `blob_root()` | `() -> Path` | Returns `Path(getenv("EVIDENCE_BLOB_ROOT", "/r2/evidence"))` — root of the write-once blob store (`custody.py:103-106`) |
| `ingest_artifact()` | `(src: str\|Path, source_meta: dict\|None=None, *, tier: str="full", acquisition: dict\|None=None) -> ArtifactRef` | Takes custody of one file: streaming SHA-256 (`custody.py:207`); checks `evidence.evidence_hash` for an existing row with that digest (dedupe); if found, returns the existing `ArtifactRef` with `duplicate=True`; else copies write-once to `blob_root()/<sha[:2]>/<sha>/<name>` with re-hash verification, inserts `evidence.source` + `evidence.evidence_hash` (level `H1`), returns a new `ArtifactRef` with `duplicate=False` (`custody.py:173-342`) |
| `verify_artifact()` | `(artifact_id: str, file_path: str\|Path) -> bool` | Re-hashes `file_path` and compares against the stored `evidence.evidence_hash.digest` for `artifact_id` — integrity check (`custody.py:345-353`) |
| `utcnow_iso()` | `() -> str` | `datetime.now(timezone.utc).isoformat()` (`custody.py:356-357`) |
| `record_custody_event()` | `(source_id, event_type, actor, detail=None, evidence_hash_id=None, file_node_id=None) -> str` | Inserts one row into `evidence.custody_event`; a DB trigger (`custody_event_chain`) computes the hash-chained `event_digest` — this function never sets that column itself (`custody.py:396-426`) |
| `record_evidence_hash()` | `(*, level, digest_hex, canon_version, computed_by, source_id=None, file_node_id=None, record_locator=None, meta=None) -> str` | Inserts one row into `evidence.evidence_hash` (digest stored as bytes via `bytes.fromhex`) (`custody.py:429-467`) |
| `reconcile_sbv_import()` | `(src, source_meta, *, sbv_file_hash, sbv_record_hashes=None, sbv_chain_hash=None, actor="server.tools.parsers.messaging.sbv_sms") -> dict` | Calls `ingest_artifact` to independently derive H1; compares against SBV's asserted `sbv_file_hash`; records a `verified`/`integrity_violation` custody event; on match, records each `sbv_record_hashes[i]` as an `H2` row and `sbv_chain_hash` (if given) as an `H3` row; returns `{verified, event, artifact_id, our_h1, sbv_h1, source_id, h2_hash_ids, h3_hash_id, record_count}` (`custody.py:470-546`) |

### 2.2 Hash canons

- **H1** (`H1_CANON = "h1-rawbytes-v1"`, `custody.py:381`): plain streaming SHA-256 over raw file bytes, 1 MiB chunks (`_sha256_file`, `custody.py:133-138`), invoked from `ingest_artifact` (`:207`) and again as a copy-verification re-hash (`:264-269`).
- **H2** (`H2_CANON = "h2-rawelement-v1"`, `custody.py:382`): **not computed in this module** — supplied externally by SBV (`sbv_record_hashes` param) and merely recorded via `record_evidence_hash(level="H2", computed_by="sbv:internal.custody.HashRecordH2", ...)` per record (`custody.py:512-525`). Comment: "H1/H2 match `vendored/sbv/internal/custody.go`" (`custody.py:374`) — the H2 algorithm itself lives in the SBV Go codebase (**UNKNOWN — not verified**, out of this repo's Python tree as read).
- **H3** (`H3_CANON = "h3-chain-sbv-genesisempty-v1"` current; `H3_CANON_LEGACY = "h3-chain-v1"` pre-2026-08-02, "ambiguous, read-only", `custody.py:383-384`): also supplied externally (`sbv_chain_hash`) and recorded via `record_evidence_hash(level="H3", computed_by="sbv:internal.custody.ChainH3", ...)` (`custody.py:527-534`). Comment block explains the legacy tag is ambiguous because the Case Bible vault writes an equally-valid H1-genesis chain under the same tag, and legacy rows are never relabelled (`custody.py:374-380`). Exact fold formula: **UNKNOWN — not verified** (lives in `vendored/sbv/internal/custody.go` / `vendored/sbv/CUSTODY.md`, not read in this audit).
- Verification cross-check: `verified = bool(sbv_h1) and sbv_h1 == our_h1.lower()` (`custody.py:492`).

### 2.3 `ArtifactRef`

`@dataclass(frozen=True)` at `server/evidence/custody.py:109-131`:

| Field | Type |
|---|---|
| `artifact_id` | `str` |
| `sha256` | `str` (hex) |
| `source_ref` | `str` (original path/object key) |
| `blob_key` | `str` (relative to blob root) |
| `size_bytes` | `int` |
| `duplicate` | `bool` |
| `ingested_at` | `str` (ISO timestamp) |
| `source_id` | `str \| None = None` |
| `acquisition_id` | `str \| None = None` |
| `acquired_at` | `datetime \| None = None` |
| `custody_tier` | `str = "full"` |

No other `ArtifactRef` definition exists; it is imported into `server/evidence/workflows.py:88` and `server/evidence/store.py:52`.

### 2.4 `server/evidence/store.py` — writes

Direct SQL INSERTs inside `store_record_batch()` → `_do_insert()` (`store.py:441-473`, transactional via `_get_engine().begin()`):

1. `working.normalized_record` (`store.py:443-455`).
2. `working.normalized_record_chunk`, only if chunk rows present (`store.py:456-467`).
3. Message-projection tables, via `write_message_projections(conn, records, record_ids, artifact, projection_request)` imported from `server.evidence.message_projection`, in the same transaction (`store.py:468-471`). Confirmed by direct read of `server/evidence/message_projection.py` (not originally in the delegated agent's scope, verified directly in this session): `write_message_projections` (`message_projection.py:309-332`) writes, per record, into `working.message_projection_route` (`_insert_route`, `:125-152`) and then either `working.conversation` + `working.message` + `working.message_participant` (first-party, `_write_first_party`, `:153-223`) or `working.third_party_conversation` + `working.third_party_message` + `working.third_party_message_participant` + `working.third_party_conversation_acquisition` (acquired third-party, `_write_third_party`, `:224-307`).
4. Indirect: `link_duplicate_artifact_acquisition()` (`store.py:477-512`) calls `link_duplicate_acquisition` (`message_projection.py:335+`, writes `working.third_party_conversation_acquisition`) and, if linked, `audit_record(...)` from `server.core.audit` against `object_schema="working.third_party_conversation_acquisition"` (**UNKNOWN — not verified** which literal table `audit_record` targets; `server/core/audit.py` not read).
5. Knowledge-engine sink (non-Postgres): `ingest_into_knowledge()` (`store.py:759-831`) writes derived markdown to disk (`store.py:801`) and calls `await knowledge.ainsert(...)` — targets the Weaviate collection `Platform_knowledge` per the module docstring (`store.py:7-8`); the actual Weaviate write is inside the externally-supplied `knowledge` object, outside this file.

Doc/code disagreement found: `server/evidence/README.md:14` describes `store.py` as persisting to an "`analysis` schema + knowledge engine," but no `analysis` schema name appears anywhere in `store.py`'s actual SQL (`working.*` throughout). `server/evidence/AGENTS.md:14` names the SBV cross-check function `verify_sbv_import`, but the actual function is `reconcile_sbv_import` (`custody.py:470`) — no `verify_sbv_import` exists.

### 2.5 `server/evidence/derivation.py` — walk derivation (sole-writer, ADR-0045)

- `derive_walk(*, case_id="primary", agent_id, horizon_policy, horizon_schedule, bound_lane=None, model_id=None, prompt_version=None, parameters=None, custom_horizon_ceiling=None, connection=None) -> uuid.UUID` (`derivation.py:220-232,245-367`). Validates `horizon_policy in ("ignorant","hindsight","custom")`; acquires advisory lock `pg_advisory_xact_lock(hashtext('working.walk_ledger'))` (`:261`); computes `base_version` from `working.vw_walk_base_version_input` and `genesis_hash = sha256(base_version || canonical(parameters))`; inserts one row into `working.walk_run`, then per horizon step queries `working.vw_horizon_atom`, computes `corpus_hash = sha256(prev_hash + slice_canonical)`, inserts into `working.walk_step`, `working.walk_step_retrieval`, `working.walk_step_realization_retrieval`, and attests via `audit_record(...)` to `ops.audit_ledger`; finalizes `working.walk_run.status='completed'`.
- `verify_reproducibility(*, walk_run_id, connection=None) -> dict` (`derivation.py:375-379,390-453`) — read-only re-derivation that recomputes the same hash chain and reports whether it still reproduces byte-for-byte.
- This module is entirely downstream of the normalized-record store (`working.normalized_record` + `working.realization_event`), not an ingest entrypoint itself.

---

## 3. Parser registry — `server/tools/parsers/`

### 3.1 Registration mechanism

- Package docstring: sub-packages `messaging`, `ai_chat`, `generic` self-register on import via `@register`; `registry.load_builtin_tools()` walks the tree recursively; modules starting with `_` are skipped as shared helpers (`server/tools/parsers/__init__.py:1-7`).
- `register(*, id, capability, description, accept=None, provenance="", execution_policy="manual_or_auto", side_effect="read_only", priority=0)` (`server/tools/registry.py:107-136`) wraps a function into a `FunctionTool` and calls `registry.register(...)` (`:65-69`), which raises `ValueError` on duplicate `id`.
- Detection is per-tool, not centralized: each tool supplies its own `accept: Callable[[str,int], bool]` (media-hint + size) at registration (`server/tools/registry.py:36,48,54-55`). `ToolRegistry.resolve(capability, media_hint, size_bytes)` (`:79-87`) filters by capability + `accepts(...)`, sorts by `priority` descending, with registration order as the stable tie-break. Most `accept` predicates are filename/extension checks; content-shape sniffing (DOM shape, JSON keys, regex markers) happens inside each parser's `parse()` body, which raises to defer to the next candidate.
- Only one explicit non-default priority in this tree: `messages.sms-xml-sbv` (SBV Go-backed) at `priority=100` (`server/tools/parsers/messaging/sbv_sms.py:393`); every other parser defaults to `priority=0` (`server/tools/registry.py:52`).
- Auto-discovery: `load_builtin_tools()` (`server/tools/registry.py:139-188`) recursively walks `server.tools` via `pkgutil.walk_packages`, skipping `_`-prefixed leaf modules, the `gateway` sub-package, and `__init__` modules; memoized via `_BUILTINS_LOADED`.
- Shared output contract: `records_out(records, **stats)` (`server/tools/_common.py:27-32`) → `{"records": [...], "stats": {"record_count": ..., **stats}}`.
- Canonical record model `NormalizedRecord` (`server/contracts/records.py:73-96`): `record_type` (enum `message|call|event|media`, default `message`), `source`, `conversation_id`, `role`, `participants`, `sender`, `recipients` (`MessageParticipant` list), `message_corpus`, `content`, `occurred_at`, `knowledge_time`, `disclosure_tier` (enum `contemporaneous|hindsight|discovered`), `attrs`.

### 3.2 Messaging parsers (`server/tools/parsers/messaging/`)

| File | Tool id | Capability | Detection | Priority | Input format |
|---|---|---|---|---|---|
| `sbv_sms.py` | `messages.sms-xml-sbv` | `parse.sms-xml` | `.xml` ext AND `SBV_SERVICE_PASS` env set (`sbv_sms.py:392,379-384`) | 100 (`:393`) | Android SMS Backup & Restore XML, via external SBV Go service |
| `sms_xml.py` | `messages.sms-xml` | `parse.sms-xml` | `.xml` ext (`:310`); content-verified for `<smses`/`<calls`/`<sms `/`<call ` in first 4096 chars (`:315-317`) | 0 | Same XML, pure-Python fallback |
| `imessage_html.py` | `messages.imessage-html` | `parse.imessage` | `.html`/`.htm` ext (`:391`); DOM sniff `div.message > div.sent|received` w/ `span.timestamp`/`span.sender`, or `div.announcement` (`:82-92`), plus an owner-custom bubble variant (`:316-319`) | 0 | imessage-exporter HTML export |
| `imessage_txt.py` | `messages.imessage-txt` | `parse.imessage` | `.txt` ext (`:476`); regex header-grammar sniff (`:459-469`) | 0 | imessage-exporter TXT export |
| `imessage_pdf.py` | `messages.imessage-pdf` | `parse.imessage` | `.pdf` ext (`:56`); extracts text layer, reuses the TXT sniff (`:61-66`) | 0 | Print-to-PDF of a TXT/HTML export, native text layer |
| `facebook_messenger_html.py` | `messages.facebook-html` | `parse.facebook` | `.html`/`.htm` ext (`:123`); structural extraction (`div.message` or `div._a6-g`) raises if neither found (`:136-142`) | 0 | Facebook DYI HTML export, legacy or card layout |
| `facebook_messenger_json.py` | `messages.facebook-json` | `parse.facebook` | `.json` ext (`:123`); requires `"messages"`+`"participants"` keys (`:136-138`) | 0 | Facebook DYI JSON export |
| `messaging_csv.py` | `messages.messaging-csv` | `parse.messages-csv` | `.csv` ext (`:319`); column-alias sniff requiring timestamp+text+sender/direction/service-ish columns (`:208-215`) | 0 | Column-flexible messaging CSV |
| `messaging_transcript.py` | `messages.transcript-marker` | `parse.messages-transcript` | `.txt`/`.csv` ext (`:154`); regex marker `^[YYYY-MM-DD HH:MM AM/PM] Speaker:$` in first 40 non-empty cells (`:52,163-168`) | 0 | Owner-vault transcript-marker grammar |

All nine emit `NormalizedRecord` directly (not via chatminer) and route through the shared `enrich_message_parties` helper before `records_out(...)`.

`_source_parties.py` (excluded from auto-discovery, leading `_`): exports `enrich_message_parties(records, payload)` (`_source_parties.py:56-137`), re-deriving `sender`/`recipients`/`message_corpus` from an explicitly supplied `source_principal` — never inferring the case owner — and flagging `source_party_review_required` when unresolved (`:114-125`). Confirmed used by `sms_xml.py:37,323`, `imessage_html.py:53,409,447`, and 6 other messaging parsers plus `server/tools/_chatminer_adapter.py:25,106`.

### 3.3 AI-chat parsers (`server/tools/parsers/ai_chat/`)

All 14 register under capability `parse.transcript`. Ten are thin wrappers around a vendored `chatminer` library via `server/tools/_chatminer_adapter.py:85-109`; four (`chatgpt_custom_gpt_md.py`, `claude_ai_export.py`, `gemini_md.py`, `perplexity_contexts.py`) implement their own parsing directly.

| File | Tool id | Detection | Input format |
|---|---|---|---|
| `chatgpt_official.py` | `transcripts.chatgpt-official` | `.json` ext + chatminer detector | ChatGPT official `conversations.json` |
| `chatgpt_share.py` | `transcripts.chatgpt-share` | `.md`/`.txt` + chatminer | ChatGPT "Share" markdown export |
| `chatgpt_custom_gpt_md.py` | `transcripts.chatgpt-custom-gpt-md` | `.md`/`.txt`; regex `"You asked:"`/`"ChatGPT Replied:"` (`:96-97`) | Custom GPT markdown, own-built record (`:107-116`) |
| `claude_ai_export.py` | `transcripts.claude-ai-export` | `.json`; first item dict with `"chat_messages"` key (`:30-31`) | claude.ai `conversations.json`, own-built (`:47-58`) |
| `claude_code.py` | `transcripts.claude-code` | `.jsonl`/`.json` + chatminer | Claude Code simple JSONL |
| `claude_code_jsonl.py` | `transcripts.claude-code-jsonl` | `.jsonl`; per-line `type in ("user","assistant")` (`:55-59`) | Claude Code session JSONL, own-built (`:60-71`) |
| `claude_md.py` | `transcripts.claude-md` | `.md`/`.txt` + chatminer | Claude markdown copy-paste |
| `gemini_chrome.py` | `transcripts.gemini-chrome` | `.md`/`.txt` + chatminer | Gemini Chrome-extension markdown |
| `gemini_json.py` | `transcripts.gemini-json` | `.json` + chatminer | Gemini JSON export |
| `gemini_md.py` | `transcripts.gemini-md` | `.md`/`.txt`; regex `**You:**`/`**Gemini:**`/`**Model:**` (`:110-111`) | Gemini markdown, own-built (`:120-132`) |
| `perplexity_contexts.py` | `transcripts.perplexity-contexts` | `.json`; requires `conversations[0].context_uuid` + `entries[0].query/answer` (`:31-42`) | Perplexity "contexts" export, own-built, 2 records per Q/A (`:76-101`) |
| `perplexity_gdpr.py` | `transcripts.perplexity-gdpr` | `.json` + chatminer | Perplexity GDPR export |
| `perplexity_md.py` | `transcripts.perplexity-md` | `.md`/`.txt` + chatminer | Perplexity generic markdown |
| `perplexity_plugin.py` | `transcripts.perplexity-plugin` | `.md`/`.txt` + chatminer | Perplexity plugin markdown |

Chatminer-adapted shape: `message_to_record()` (`server/tools/_chatminer_adapter.py:32-69`) builds `NormalizedRecord` with `attrs` = `message_id`, `message_hash`, `content_type`, `sender`, `source_file`, `source_format`, `source_index`, `confidence`, optional `language`/`message_metadata`/`conversation_title`. `run_chatminer_parser()` hard-fails below `min_confidence` (default 0.5, `:29,88`; `generic_md.py` lowers to 0.25) or on zero parsed messages (`:103-104`).

### 3.4 Generic / document parsers (`server/tools/parsers/generic/`)

| File | Tool id | Capability | Detection | Output |
|---|---|---|---|---|
| `generic_md.py` | `transcripts.generic-md` | `parse.transcript` | `.md`/`.txt` + chatminer `min_confidence=0.25` (`:27`) | chatminer-adapted |
| `whole_file_fallback.py` | `transcripts.markdown` | `parse.transcript` | `.md`/`.txt`, no content sniff, accepts any non-empty file (`:29,35-36`) | ONE `NormalizedRecord` per file: `source="markdown-transcript"`, `role="transcript"`, `content`=whole file, `attrs={"original_name": ...}` (`:37-46`) |

`whole_file_fallback.py`'s module name is deliberately chosen so alphabetical auto-discovery import order places it last among same-priority `parse.transcript` candidates (`:6-12`).

### 3.5 `docling_extract` — NOT in the parsers tree

`docling_extract` is defined at `server/tools/extractors/docling_extract.py` — a **sibling** package (`server/tools/extractors/`), not under `server/tools/parsers/`. Registered `id="documents.extract-docling"`, `capability="extract.text"` (a different capability namespace than any `parse.*` used above), `accept` for `.pdf,.docx,.pptx,.xlsx,.html,.htm,.png,.jpg,.jpeg,.tiff,.webp` (`docling_extract.py:32,35-41`). Lazily imports `docling.document_converter.DocumentConverter`; raises `RuntimeError` if the optional `document-ai` extra is absent (`:46-49`); returns Markdown via `export_to_markdown()` (`:51-64`). Docstring flags a known gap: no fallback extractor for `.docx/.pptx/.xlsx/.html/.htm` if Docling is unavailable — tracked as `URGENT-TODO #17` (`:6-17`). Consumed by `server/ingest/service.py:143-182` (`_extract_document`), a document-ingest path distinct from the chat/messaging parser resolution in §3.1–3.4, though both register into the same process-wide `registry` object.

---

## 4. Temporal layer — `server/temporal/`

**Headline fact, stated by the code itself:** `server/temporal/__init__.py:4-11` — "Nothing in the platform imports this package, and nothing dispatches to it. ... The live path stays exactly where it is — agno's `Workflow.arun` driven by `server/evidence/workflows.py::run_chat_transcript` (:940)." `server/temporal/workflows.py:4-5` repeats: "INERT: nothing dispatches to this." This section inventories the Temporal skeleton as it exists in code, which is real and complete as a standalone module, but is not wired to any live entrypoint in this repo.

### 4.1 The four activities (`server/temporal/activities.py`)

| Activity | Decorator | Params dataclass (fields) | Result dataclass (fields) | Body |
|---|---|---|---|---|
| `custody_activity` | `@activity.defn(name="custody_activity")` (`:149`, sync `def` `:150`) | `CustodyParams` (`:61-67`): `path: str`; `source_meta: dict[str,Any] = {}`; `custody_tier: str = "full"` | `CustodyResult` (`:70-82`): `artifact_id: str`; `sha256: str`; `source_ref: str`; `blob_key: str`; `size_bytes: int`; `duplicate: bool`; `ingested_at: str`; `custody_tier: str` | Pure call-through to `server.evidence.custody.ingest_artifact(params.path, {**params.source_meta,"workflow":"chat-transcript"}, tier=params.custody_tier)` (`:166-182`) — no custody logic reimplemented |
| `parse_activity` | `@activity.defn(name="parse_activity")` (`:185`, sync `def` `:186`) | `ParseParams` (`:86-88`): `path: str`; `source_meta: dict[str,Any] = {}` | `ParseResult` (`:91-109`): `parser_id: str\|None`; `record_count: int`; `records: list[dict] = []`; `attempts: list[dict] = []`; `stats: dict = {}` | Calls `server.tools.registry.registry.resolve("parse.transcript", media_hint=..., size_bytes=...)`, tries each candidate's `.run()`, raises `ValueError` if all fail or none match (`:206-238`) — same registry used by the live path |
| `store_activity` | `@activity.defn(name="store_activity")` (`:253`, sync `def` `:254`) | `StoreParams` (`:112-120`): `artifact_id: str`; `records: list[dict] = []`; `parser_id: str\|None`; `parent_run_id: str\|None`; `message_corpus: str\|None = "first_party"`; `caller_owns_conversation: bool = True`; `source_principal: str\|None` | `StoreResult` (`:123-129`): `stored: int`; `record_count: int`; `dedupe_noop: bool`; `detail: str`; `attempts: list[dict] = []` | Calls `server.evidence.store.load_artifact_ref` + `server.evidence.workflows._store_step_impl(ctx)` — reuses the SAME internal helper the legacy agno workflow uses (`:271-292`) |
| `knowledge_activity` | `@activity.defn(name="knowledge_activity")` (`:295`, `async def` `:296`) | `KnowledgeParams` (`:132-141`): `artifact_id: str`; `lane: str = "context"`; `run_meta: dict[str,Any] = {}` | `KnowledgeResult` (defined in `server/temporal/knowledge_harness/__init__.py:71-87`, not `activities.py`): `docs_ingested: int`; `skipped: bool`; `detail: str`; `harness: str`; `lane: str`; `attempts: list[dict] = []` | Pure dispatcher: `harness_name = os.getenv("KNOWLEDGE_HARNESS","agno")`; `harness = get_harness(harness_name)`; `return await harness(RecordsRef(artifact_id=...), params.lane, dict(params.run_meta))` (`:314-320`) |

`ALL_ACTIVITIES = [custody_activity, parse_activity, store_activity, knowledge_activity]` (`activities.py:323`).

### 4.2 `ChatTranscriptIngest` workflow (`server/temporal/workflows.py`)

- `@workflow.defn(name="ChatTranscriptIngest")` class at `workflows.py:172-173`. `__init__` sets `self._gate: str|None=None`, `self._stage: str="pending"`, `self._aborted_at: str|None=None` (`:184-187`).
- **Signal:** `@workflow.signal(name="gate_decision")` → `gate_decision(self, decision: str) -> None` (`:191-192`). Normalizes and, if `decision` equals `GATE_APPROVE="approve"` or `GATE_ABORT="abort"` (`:88-89`), sets `self._gate`; otherwise logs a warning and ignores (a raising handler would fail the whole workflow task) (`:206-210`).
- **Query:** `@workflow.query(name="status")` → `status(self) -> dict[str,Any]` returns `{"stage": self._stage, "gate": self._gate, "aborted_at": self._aborted_at}` (`:212-215`).
- **Run method** `@workflow.run async def run(self, params: ChatTranscriptInput) -> ChatTranscriptOutput` (`:219-220`), four sequential stages, each an `await workflow.execute_activity(...)` call with its own timeout + retry policy:
  1. `custody` (`:223-233`) — `execute_activity(custody_activity, CustodyParams(path, source_meta, custody_tier), start_to_close_timeout=_CUSTODY_TIMEOUT, retry_policy=_CUSTODY_RETRY)`; gated (if `params.supervised`) via `_gate_open("custody")` (`:239-240`).
  2. `parse` (`:242-248`) — same pattern with `ParseParams`; gated at `"parse"` (`:253-254`).
  3. `store` (`:256-267`) — `StoreParams(artifact_id=custody.artifact_id, records=parse.records, parser_id=parse.parser_id, parent_run_id=params.parent_run_id)`; gated at `"store"` (`:269-270`).
  4. `knowledge` (`:274-288`) — `KnowledgeParams(artifact_id=custody.artifact_id, lane=params.lane, run_meta={"run_id":...,"parent_run_id":...,"dedupe_noop": store.dedupe_noop})`; **never gated** — comment states this is deliberately the final, non-interruptible stage (`:272-273`).
  5. Completion (`:291-304`): `self._stage="completed"`; returns `ChatTranscriptOutput(status="completed", artifact_id=custody.artifact_id, sha256=custody.sha256, duplicate=custody.duplicate, parser_id=parse.parser_id, records_parsed=parse.record_count, records_stored=store.stored, docs_ingested=knowledge.docs_ingested, knowledge_harness=knowledge.harness, knowledge_skipped=knowledge.skipped, step_log=step_log)`.
- **Gate mechanism** `_gate_open(self, stage) -> bool` (`:308-334`): resets `self._gate=None`; loops `await workflow.wait_condition(lambda: self._gate is not None, timeout=_GATE_NOTIFY_AFTER)` where `_GATE_NOTIFY_AFTER = timedelta(days=7)` (`:133`); on `asyncio.TimeoutError`, logs and loops again — **never auto-aborts on timeout**; returns `False` (setting `self._aborted_at=stage`) if `self._gate==GATE_ABORT`, else `True`.
- **Retry policies** (`:97-124`): `_CUSTODY_RETRY`/`_STORE_RETRY` = initial 2s, backoff coefficient 4.0, max interval 60s, `maximum_attempts=4`; `_PARSE_RETRY` = same but `maximum_attempts=2`; `_KNOWLEDGE_RETRY` = initial 2s, coefficient 4.0, max interval 5 min, `maximum_attempts=6`.
- **Timeouts** (`:126-129`): custody/parse/store = 30 min each; knowledge = 2 hours.

**`ChatTranscriptInput` — exact params required to start this workflow** (`workflows.py:136-151`, a `dataclasses.dataclass`):

| Field | Type | Required/default |
|---|---|---|
| `path` | `str` | **required** |
| `source_meta` | `dict[str, Any]` | optional, `{}` |
| `lane` | `str` | optional, default `"context"` |
| `custody_tier` | `str` | optional, default `"light"` |
| `parent_run_id` | `str \| None` | optional, `None` |
| `run_id` | `str \| None` | optional, `None` |
| `supervised` | `bool` | optional, default `False` |

**`ChatTranscriptOutput`** (`workflows.py:154-169`): `status: str`; `artifact_id/sha256/parser_id: str|None`; `duplicate/knowledge_skipped: bool|None`; `records_parsed/records_stored/docs_ingested: int`; `knowledge_harness: str|None`; `aborted_at: str|None`; `step_log: list[str]`.

**Naming/queue discrepancies found (fact, not opinion):**
- `workflows.py:86` defines `TASK_QUEUE = "evidence-ingest"` and exports it, but `worker.py` never imports or reads `workflows.TASK_QUEUE` anywhere — confirmed by a full read of `worker.py`. The task queue actually used at runtime is a *different* string (see §4.3).
- `server/api/workflow_registry.py:51-64` defines its OWN `ChatTranscriptInput` (a pydantic `BaseModel`, fields `path`/`domain`/`custody_tier`(default `"full"`)/`mode`) — same class name, different type, different field set and different `custody_tier` default than the Temporal `ChatTranscriptInput` dataclass (default `"light"`, field `lane` not `domain`) described above. The two are unrelated types that happen to share a name.

### 4.3 `server/temporal/worker.py`

- Task queue: `TASK_QUEUE_DEFAULT = "evidence-pipeline"` (`worker.py:42`); actual value `task_queue = os.environ.get("TEMPORAL_TASK_QUEUE", TASK_QUEUE_DEFAULT)` (`worker.py:52`) — corroborated by the module docstring at `worker.py:7,18`. This is the literal string actually polled, and it differs from `workflows.py:86`'s unused `"evidence-ingest"` (see discrepancy above).
- Registered workflows: `from server.temporal.workflows import ChatTranscriptIngest, P0DurabilityProbe` (`worker.py:38`); passed as `workflows=[ChatTranscriptIngest, P0DurabilityProbe]` to the `Worker` constructor (`worker.py:63`).
- Registered activities: `from server.temporal.activities import (custody_activity, knowledge_activity, parse_activity, store_activity)` (`worker.py:32-37`); passed as `activities=[custody_activity, parse_activity, store_activity, knowledge_activity]` (`worker.py:64`).
- Entrypoint: `if __name__ == "__main__": asyncio.run(main())` (`worker.py:71-72`); `async def main()` (`worker.py:45-68`) connects via `Client.connect(address, namespace=namespace)` (`:56`), builds a `ThreadPoolExecutor(max_workers=threads)` (`:59`), constructs the `Worker(...)` (`:60-66`), and runs `await worker.run()` (`:68`).
- Env vars read (`worker.py:50-53`): `TEMPORAL_ADDRESS` (default `"temporal-server:7233"`), `TEMPORAL_NAMESPACE` (default `"default"`), `TEMPORAL_TASK_QUEUE` (default `TASK_QUEUE_DEFAULT`), `TEMPORAL_ACTIVITY_THREADS` (default `"8"`).

### 4.4 `P0DurabilityProbe`

- `@workflow.defn(name="P0DurabilityProbe")` class (`workflows.py:367-379`). `async def run(self, ticks: int = 6, tick_seconds: int = 10) -> list[str]` (`:374`): loops `await workflow.sleep(tick_seconds)` `ticks` times, appending a log line each tick, returns the log (`:375-379`). No activities, no I/O — a pure timer.
- Stated purpose (`workflows.py:359-363`): "P0 exit-test probe (`deploy/temporal/README.md` 'P0 exit test'): a trivial, deterministic workflow that takes ~a minute across several timer ticks so an operator can `docker restart` the worker mid-run and watch it resume from history."
- Registered in `worker.py:38,63,67` (including the boot log line naming it). **No other file in the repository references `P0DurabilityProbe`** — confirmed by a repo-wide grep. `deploy/temporal/README.md:78-86` describes the "P0 exit test" procedure in prose (start a trivial workflow, restart the worker mid-run, confirm resume-from-history) but does not name `P0DurabilityProbe` by identifier and contains no literal start command. **UNKNOWN — not verified**: no discoverable CLI command, script, or API call that actually starts this workflow exists in this repository as of this audit.

### 4.5 `server/api/workflow_registry.py` — HTTP-to-agno wiring (NOT Temporal)

This file wires HTTP/AgentOS `WorkflowFactory` objects to the **agno** workflow builders in `server/evidence/workflows.py` (`build_chat_transcript_workflow`, `build_sms_xml_workflow`) — confirmed by a full read finding zero imports of `temporalio` or `server.temporal.*` anywhere in the file.

- `build_workflow_factories(db, knowledge, native_projector=None) -> List[WorkflowFactory]` (`workflow_registry.py:102-201`) builds two factories:
  - `id="chat-transcript"`: `_chat_factory(ctx)` (`:159-167`) builds `args = _input_of(ctx, ChatTranscriptInput)` (the pydantic one, §4.2 discrepancy), calls `build_chat_transcript_workflow(path=args.path, domain=args.domain, knowledge=knowledge, custody_tier=args.custody_tier)`, wraps with `_ledgered(...)`.
  - `id="sms-xml"`: `_sms_factory(ctx)` (`:169-182`) builds `args = _input_of(ctx, SmsXmlInput)` (fields: `path`, `source_principal` required, `caller_owns_conversation: Literal[True]` required, `domain="evidence"` default, `custody_tier="full"` default, `mode="auto"` default — `:66-76`), calls `build_sms_xml_workflow(...)`.
  - `_ledgered(workflow_id, args, wf, wf_ctx)` (`:122-157`) creates an `ops.workflow_run` row via `server.evidence.run_ledger.create_run(...)` and attaches it via `server.evidence.workflows.attach_ledger(...)`; any exception is caught/logged non-fatally so the workflow still runs unledgered.
- `registered_workflows(db, knowledge, native_projector=None)` (`:204-218`) wraps the above in try/except, returning `[]` on any error rather than raising — registration never crashes boot.

### 4.6 `server/api/run_routes.py` — confirmed: no Temporal client calls

Full read of this 797-line file found **zero** occurrences of `client.start_workflow`, `handle.signal(...)`, or `handle.query(...)`. Every route (`GET /v1/health/deps`, `POST /v1/runs`, `GET /v1/runs`, `GET /v1/runs/{run_id}`, `GET /v1/runs/{run_id}/report`, `POST /v1/runs/{run_id}/review-actions`, `POST /v1/runs/{run_id}/continue`, `POST /v1/runs/{run_id}/abort`, `POST /v1/runs/{run_id}/retry`) dispatches to the live agno runners in `server/evidence/workflows.py` (`run_chat_transcript`, `run_sms_xml`, `run_knowledge_from_store`) and to Postgres via `server/evidence/run_ledger.py` functions (`create_run`, `seed_stages`, `list_runs`, `get_run`, `set_gate`, `record_review_action`, `build_run_report`). `POST /v1/runs/{run_id}/continue` and `/abort` (`run_routes.py:566-614`) write `ops.workflow_run.gate_state` directly via `set_gate(...)` — a Postgres column, not a Temporal signal.

`POST /v1/runs`, `status_code=202` (`run_routes.py:453`): accepts multipart `file`, `workflow` (`"chat-transcript"`\|`"sms-xml"`), `domain`, `mode` (`"auto"`\|`"supervised"`), `custody_tier`, `source_meta` (JSON) — the same field surface used across §1.11; internally schedules `_execute_run(...)` as a background `asyncio.Task`, which resolves `runner = run_chat_transcript if workflow=="chat-transcript" else run_sms_xml` (`run_routes.py:235`) — the legacy agno path, confirmed not Temporal.

### 4.7 Knowledge harnesses (`server/temporal/knowledge_harness/`)

Both harnesses implement the identical public signature `async def run_knowledge_step(records_ref: RecordsRef, lane: str, run_meta: dict[str, Any]) -> KnowledgeResult`, and both are reached only through `knowledge_activity`'s `get_harness(harness_name)` selector (`activities.py:314-320`; selector logic in `knowledge_harness/__init__.py:93-114`) — neither is imported by name directly from `activities.py`.

- **`agno_harness.py`** (`HARNESS_NAME = "agno"`, `:32`): loads records via `server.evidence.store.load_records_for_artifact(records_ref.artifact_id)` (`:61,64`), builds a `ctx` dict, gets a knowledge handle via `server.analysis.context_chat_ingest.create_lane_knowledge(lane)`, and calls `_knowledge_step_impl(ctx, knowledge)` from `server.evidence.workflows` (`:62,83`) — the SAME internal helper the legacy `run_chat_transcript` workflow calls in its own `knowledge_step`. Raises `RuntimeError` if records exist but no knowledge handle resolves, or if the step reports failure (`:77-85`). Returns `KnowledgeResult(docs_ingested, skipped, detail, harness="agno", lane, attempts)` (`:87-94`).
- **`pydantic_ai_harness.py`** (`HARNESS_NAME = "pydantic_ai"`, `:37`): requires env var `KNOWLEDGE_BAKE_MODEL` (raises `RuntimeError` if unset, `:90-95`); lazily imports `pydantic_ai.Agent`, raising `RuntimeError` naming the `temporal-bake` extra if not installed (`:70-79`); constructs a pydantic-ai `Agent` with one tool, `project_records`, which queries `SELECT count(*) FROM working.normalized_record WHERE artifact_id=:artifact_id` for confirmation, then calls the SAME `_knowledge_step_impl` from `server.evidence.workflows` (`:118,145`) that `agno_harness.py` calls, and returns a `KnowledgeResult` tagged `harness="pydantic_ai"`.
- `server/temporal/knowledge_harness/BAKE.md:5` self-describes status: "open. Neither side has won. Both are shipped INERT behind one env var" — consistent with neither harness module being imported anywhere outside `server/temporal/`.

---

## 5. Legacy in-code workflow — `server/evidence/workflows.py::run_chat_transcript`

### 5.1 Signature

```python
async def run_chat_transcript(
    path: str,
    source_meta: dict[str, Any] | None = None,
    domain: str = "platform_design",
    knowledge=None,
    run_id: str | None = None,
    mode: str = "auto",
    custody_tier: str = "full",
    parent_run_id: str | None = None,
) -> dict[str, Any]
```
(`server/evidence/workflows.py:940-949`; `knowledge` has no type annotation in source.)

### 5.2 What it does (read from the body, `workflows.py:968-1021`)

1. Starts a timer; if `run_id` given, logs a start line (`:968-970`).
2. Calls `build_chat_transcript_workflow(path, source_meta, domain, knowledge, custody_tier=custody_tier, parent_run_id=parent_run_id)` → `(wf, ctx)` (`:971-973`). This builds an `agno.workflow.Workflow` named `"chat-transcript"` with four `Step`s, each `on_error=OnError.fail` (`:588-679`):
   - **`custody_step`** (`:621-630`): `ingest_artifact(ctx["path"], {**ctx["source_meta"], "workflow": "chat-transcript"}, tier=ctx["custody_tier"])` from `server/evidence/custody.py` → `ctx["artifact"]`.
   - **`parse_step`** (`:632-657`): resolves parser candidates via `registry.resolve("parse.transcript", ...)` (`server/tools/registry.py`), tries each, sets `ctx["raw_records"]`, `ctx["parse_stats"]`, `ctx["parser_id"]`.
   - **`store_step`** (`:659-660`): calls `_store_step_impl(ctx)` (`:385-480`), which builds `NormalizedRecord`s via `finalize()` and calls `store_records(...)` from `server/evidence/store.py`, setting `ctx["stored"]`.
   - **`knowledge_step`** (`:662-663`): calls `_knowledge_step_impl(ctx, knowledge)` (`:483-533`) — drains the native vector-projection outbox (`NativeEvidenceProjector`) or, on the legacy path, calls `ingest_into_knowledge(knowledge, ...)` from `store.py`, setting `ctx["knowledge_docs"]`.
3. If `run_id is not None`, wraps every step for the run ledger and gate control via `attach_ledger(wf, ctx, run_id, mode)` (`:974-978`) — writes `ops.workflow_run_stage` rows (`server/evidence/run_ledger.py`'s `stage_start`/`stage_finish`) and applies gate/abort logic against `ops.workflow_run.gate_state`.
4. `result = await wf.arun(input=f"ingest transcript: {path}")` (`:984`).
5. Returns a summary dict: `workflow`, `status`, `artifact_id`, `sha256`, `duplicate` (from `ctx["artifact"]`), `parser` (`ctx["parser_id"]`), `parse_attempts` (`ctx["attempts"]`), `records_stored` (`ctx["stored"]`), `step_log` (`:986-997`).
6. On exception, records `exc_message` and re-raises; `finally` block computes `duration_ms`, and if `run_id` given, calls `finish_run(...)` from `run_ledger.py` with the terminal status, summary, error, sha256, artifact_id (`:998-1021`).

### 5.3 How it's invoked today (repo-wide grep, all files, not just docstrings)

Three confirmed production call sites (plus test-only calls):

1. **`server/api/run_routes.py:233-249`** — inside `_execute_run`: `runner = run_chat_transcript if workflow == "chat-transcript" else run_sms_xml`, then `await runner(str(tmp_path), source_meta=meta, domain=domain, ...)`.
2. **`server/api/evidence_routes.py:88-98`** — inside the `POST /v1/evidence/import` handler: `from server.evidence.workflows import run_chat_transcript` then `return await run_chat_transcript(str(tmp_path), source_meta=meta, domain=domain, knowledge=resolve_knowledge(knowledge))`.
3. **`server/evidence/cli.py:25-38,57`** — `runners = {"chat-transcript": run_chat_transcript, ...}`; `asyncio.run(runner(args.path, ...))` inside `_cmd_import`.
4. **`tests/test_run_ledger.py`** — multiple direct calls (`:233,521,1053,1074`) — test-only.

Non-calls (grep matched the string but these are comments, not invocations): `server/temporal/workflows.py:1-5` states explicitly "INERT: nothing dispatches to this. The live path remains `server/evidence/workflows.py::run_chat_transcript` (:940)." `server/temporal/__init__.py:8-13` states "The live path stays exactly where it is — agno's `Workflow.arun` driven by `server/evidence/workflows.py::run_chat_transcript` (:940). The seam that flips between the two ... is a single dispatch switch inside `run_chat_transcript` and is deliberately NOT part of this commit." `sql/0005_workflow_run_ledger.sql:4` is a SQL comment referencing the function name, not a call.

**Conclusion:** `run_chat_transcript` is the live, callable evidence-ingest workflow today, reachable via two HTTP routes (`/v1/evidence/import`, and the run-ledger-tracked route in `run_routes.py`) and one CLI. The `server/temporal/` package exists as code but self-documents as not wired to this dispatch.

---

## 6. File-intake expectations

Per-entrypoint accepted forms, gathered from §1 above:

- `scripts/ingest_context_chat.py` / `server.analysis.chat_archive` accept: a bare chat-export file (any format the parser registry or SBV Go service recognizes — JSON, JSONL, MD, TXT) **or** a `.zip` archive containing `conversations*.json` + sidecar metadata + an `assets/` folder (`server/analysis/chat_archive.py:1-22,36-53`). ZIP is required for "real" exports per the module's own claim; bare JSON/MD/TXT is accepted directly by `ingest_chat_file`.
- `scripts/ingest_knowledge.py` accepts a directory tree under each knowledge root, walked recursively (`rglob("*")`), filtered to `.md/.txt/.json/.csv/.pdf/.docx`, ≤ 50 MB (`scripts/ingest_knowledge.py:37-38,80-86`).
- `POST /v1/ingest` accepts a raw multipart file upload, any extension/content the downstream parser/extractor registry can handle, ≤ 50 MB (`server/api/ingest_routes.py:24,57-60`).
- `POST /v1/ingest/path` and `POST /v1/evidence/import` / `run_chat_transcript` accept a server-local file path (already staged or freshly written from an upload) — same downstream parser resolution as above.
- `docling_extract` (document path) accepts `.pdf,.docx,.pptx,.xlsx,.html,.htm,.png,.jpg,.jpeg,.tiff,.webp` (`server/tools/extractors/docling_extract.py:32`).

### Container path assumptions

Direct repo-wide grep for the literal strings `/data/ingest` and `/data/r2-sorted` across `server/`, `scripts/`, and `deploy/` found:

- **No occurrences in `server/` or `scripts/`** (verified via `grep -rln "/data/ingest|/data/r2-sorted" server/ scripts/` — zero files matched).
- **`deploy/exec.yaml:66-71`** (the OVH-1 exec-tier Coolify compose file for `agentos-api`) mounts:
  ```yaml
  volumes:
    - r2-nexus:/r2
    - r2-casebible-sorted:/data/r2-sorted:ro
    - /srv/ingest:/data/ingest
  ```
  Comment at `deploy/exec.yaml:66-69`: "Ingest surfaces (owner order 2026-08-24): the sorted evidence bucket (read-only) + a host drop-dir, so data can be moved into the system and workflows triggered without any copy step. Mirrors the temporal-worker mounts on ovh-files (`/data/ingest` + `/data/r2-sorted` there)." This confirms `/data/ingest` and `/data/r2-sorted` are **deployment-level container mount points on the `agentos-api` container**, not paths referenced anywhere in the application code read for this audit — no Python source under `server/` or `scripts/` reads from either path directly (**UNKNOWN — not verified**: whether any code added after this audit's file list, or the SBV Go service, reads from these mounts; not found in the Python tree covered here).
  - The comment additionally claims a "temporal-worker" service on a host named "ovh-files" has equivalent mounts — this repo's `deploy/` tree does not contain that compose definition (only `deploy/temporal/compose.temporal.yaml` was found, not read in this audit) — **UNKNOWN — not verified** whether/how a Temporal worker actually consumes `/data/ingest` or `/data/r2-sorted`.
- Other container paths confirmed in code: `EVIDENCE_BLOB_ROOT` default `/r2/evidence` (`server/evidence/custody.py:103-106`); `INGEST_STAGING_ROOT` default `/tmp/horizon-ingest-staging` (`server/api/ingest_routes.py:44`); `KNOWLEDGE_BASE_PATH` default `/app/knowledge/platform`, `KNOWLEDGE_LEGAL_PATH` default `/app/knowledge/legal`, `KNOWLEDGE_PERSONAL_HISTORY_PATH` default `/app/knowledge/personal_history`, `KNOWLEDGE_RELATIONSHIP_TIMELINE_PATH` default `/app/knowledge/relationship_timeline` (`scripts/ingest_knowledge.py:47-51`).

---

## Files read in full or in cited excerpt for this audit

`scripts/ingest_context_chat.py`, `scripts/ingest_knowledge.py`, `server/analysis/context_chat_ingest.py`, `server/analysis/chat_archive.py`, `server/analysis/chat_parse.py`, `server/api/ingest_routes.py`, `server/api/evidence_routes.py`, `server/api/main.py` (excerpts), `server/contracts/ingest.py`, `server/ingest/service.py`, `server/ingest/query.py`, `server/evidence/custody.py`, `server/evidence/workflows.py`, `server/evidence/store.py`, `server/evidence/derivation.py`, `server/evidence/message_projection.py` (excerpts), `server/evidence/README.md`, `server/evidence/AGENTS.md`, `server/evidence/cli.py`, `server/tools/parsers/__init__.py` and all 24 files under `server/tools/parsers/{messaging,ai_chat,generic}/`, `server/tools/registry.py`, `server/tools/_common.py`, `server/tools/_chatminer_adapter.py`, `server/tools/extractors/docling_extract.py`, `server/contracts/records.py`, `deploy/exec.yaml` (excerpt), `docs/plans/TEMPORAL-INTEGRATION-PLAN-2026-08-23.md` (excerpt, context only — not cited as code evidence), `server/temporal/activities.py`, `server/temporal/workflows.py`, `server/temporal/worker.py`, `server/temporal/__init__.py`, `server/temporal/knowledge_harness/agno_harness.py`, `server/temporal/knowledge_harness/pydantic_ai_harness.py`, `server/temporal/knowledge_harness/__init__.py`, `server/temporal/knowledge_harness/BAKE.md`, `server/api/workflow_registry.py`, `server/api/run_routes.py` (full file).
