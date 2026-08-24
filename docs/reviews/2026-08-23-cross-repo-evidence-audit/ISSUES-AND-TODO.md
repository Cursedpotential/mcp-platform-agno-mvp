# Issues Register & Remediation Plan

> _Byline: Claude Code · Opus 5 · 2026-08-23_
>
> Scope: `Agno-MCP-Platform`, `Legal-Workspace`, `Agno-MCP-Platform/vendored/sbv`.
> Every issue below was **verified against code on disk**. Claims that failed verification are
> listed separately in §7 so they are not silently dropped.
>
> Evidence trail: `lane-1a`..`lane-5`, `verify-1`..`verify-7`, `CONSOLIDATED-CLAIM-VERIFICATION.md`,
> `sibling-session-59068f99/`.

**Status legend** — `VERIFIED` = read in code · `CORROBORATED` = two independent reads agree ·
`OWNER` = blocked on a decision, not on engineering.

---

## 1. P0 — Correctness defects (wrong output, silent data loss)

### ISS-001 · MCL 722.23 factor (j)/(k) names are inverted
- **Where:** `server/analysis/config/behavioral_patterns.json:59-66`
- **What:** `(j).name = "Domestic Violence"` with the facilitate-relationship description;
  `(k).name = "Willingness to Facilitate Relationship"` with the domestic-violence description.
  A clean swap of two `name` fields. Both `description` fields are individually correct.
- **Impact:** Any surface rendering `name` as a label prints domestic violence and
  relationship-facilitation **backwards**. Internally-correct codes, inverted human labels.
- **Status:** VERIFIED. All 12 letters (a)-(l) present.

### ISS-002 · Message evidence can land with NO custody hash on the default path
- **Where:** `server/tools/parsers/messaging/sbv_sms.py:323,376`; `sms_xml.py` (whole file)
- **What:** Two independent routes produce custody-free records:
  - **(a)** `accept=lambda …: hint.endswith(".xml") and _sbv_enabled()` — when SBV is unwired the
    SBV parser does not match, and resolution falls to `sms_xml.py`, which has **no custody path**
    (its only `sha256` is a base64-payload digest in `attrs`, never written to `evidence_hash`).
  - **(b)** `if not os.getenv("SBV_CUSTODY_ENABLED")` — no default, so unset = reconciliation skipped.
- **Impact:** Silent degradation. Neither route warns at record level.
- **Status:** VERIFIED. Note SBV *is* explicitly primary (`priority=100` vs 0) — it was never
  "demoted to shadow". The gap is the fallback and the flag, not precedence.

### ISS-003 · ContextForge JWT secret is a literal placeholder while `AUTH_REQUIRED=true`
- **Where:** `Legal-Workspace/docs/URGENT-TODO.md:26` (item B1)
- **What:** `CF_JWT_SECRET_KEY` / `JWT_SECRET_KEY` = the literal string `set CF_JWT_SECRET_KEY`;
  `AUTH_ENCRYPTION_SECRET` / `CF_AUTH_ENCRYPTION_SECRET` = literal `set CF_AUTH_ENCRYPTION_SECRET`.
  Someone pasted the shell command instead of its value.
- **Impact:** **SECURITY — HIGH.** Every service trusting a CF JWT is affected.
- **Status:** VERIFIED, already correctly triaged and escalated. **OWNER** — rotation invalidates every
  token platform-wide at once.

### ISS-004 · MMS multi-attachment loss is silent AND unrecoverable
- **Where:** `vendored/sbv/internal/parser.go:323-330`; hashing at `:918-922`
- **What:** Only the first media part is stored (`msg.MediaType`/`msg.MediaData`). Extra parts are
  discarded with **no counter, no log, no flag**. H2 covers the whole `<mms>` element, but the raw
  XML is discarded immediately after hashing — only `ContentHash` persists.
- **Impact:** The hash proves something was lost; it cannot reconstruct it. Recovery requires the
  original XML kept separately.
- **Status:** VERIFIED. This is **worse** than the sibling review stated (it believed parts were
  recoverable).

### ISS-005 · `DELETE /v1/calendar/events/{id}` raises an unhandled 500 on every call
- **Where:** `Legal-Workspace/api/legal_workspace/api/calendar_routes.py:166`
- **What:** Calls `UUID(event_id)`; `UUID` is never imported (imports at `:3-12`). `NameError` is not
  caught by the `except ValueError` / `except StopIteration` handlers below it.
- **Impact:** Route never returns its intended 400 — it 500s unconditionally.
- **Status:** VERIFIED. One-line fix.

### ISS-006 · H3 custody chain never spans import batches
- **Where:** `vendored/sbv/internal/engine.go:106`, sink construction `:498`, folds `:286,389,410`
- **What:** `chain string // incremental H3 fold (genesis "")`. The sink literal never seeds `chain`,
  so Go's zero value `""` applies. Every batch restarts at genesis.
- **Impact:** The chain proves ordering **within** a batch only. Deleting or reordering a whole batch
  is undetectable. `ChainH3(orderedH2s, prevChain)` accepts a prior chain; only a test ever passes one.
- **Status:** VERIFIED.

### ISS-007 · SBV dedup ignores the content hash
- **Where:** `vendored/sbv/internal/database.go:121` (and `:234` for per-user DBs)
- **What:** `idx_message_unique` keys on
  `(record_type, address, date, type, COALESCE(body,''), COALESCE(content_type,''),
  COALESCE(message_id,''), COALESCE(duration,0))` — **`content_hash` is not a member.**
- **Impact:** Deduplication decides identity by normalized field equality, not raw bytes. Records with
  differing bytes that normalize alike are collapsed; the survivor keeps whichever hash landed first.
  This inverts the guarantee the hash exists to provide.
- **Status:** VERIFIED.

### ISS-008 · Live horizon predicate filters on a clock its own schema disowned
- **Where:** `sql/0018_retrieval_axes.sql:114` vs `sql/0008…:246-250`; fix in unapplied `sql/0028`
- **What:** `working.horizon_visible()` filters `row_knowledge_time <= p_horizon`. `0008` explicitly
  states `knowledge_time` records row-write time and warns "Do not use for 'when did you know'
  questions." `0028` repoints the predicate at `visible_from()` — and is **HELD, not applied**.
- **Impact:** As-lived vs hindsight separation may be filtering on the wrong axis in production.
- **Status:** VERIFIED. **OWNER** — resolution requires the 0026-0030 cutover.

---

## 2. P1 — Missing capabilities (named gaps, nothing to fix — things to build)

### ISS-010 · Evidence bundling does not exist in any of the three repos
- Searched `bundle|exhibit|production set|bates|packet|concordance|opticon|.dat|.opt|custodian|
  privilege log` across all three. **Agno:** zero (all hits are English prose or the unrelated
  `disclosure_tier` concept). **Legal-Workspace:** `services/bates.py` overlays a footer on
  owner-produced PDFs and returns `court_safe=False, exportable=False`. **SBV:** a `window.print()`
  dialog with no custody data, plus a good JSON attestation report that is not a document.
- The only committed artifact is `analysis.vw_court_export` — a **read-only readiness view**, one item
  at a time, producing no output. **Status:** VERIFIED across all three.

### ISS-011 · DOCX / PPTX / XLSX / HTML ingest fails on a default install
- **Where:** `server/ingest/service.py:143,155-158,180-182`; `pyproject.toml:87`;
  `server/tools/extractors/docling_extract.py:31-34`
- `docling` is gated behind the `document-ai` extra and is **absent from `requirements.txt`**. The
  extractor list comes back empty and ingest dies with receipt status `"failed"`.
- **No `STUB:` marker, no `docs/URGENT-TODO.md` entry** — a direct violation of
  `server/contracts/AGENTS.md:60-61` and the standing LIVE ONLY policy. **Status:** VERIFIED.
- Same shape for PDF **OCR**: the `ocr` extra (pytesseract/pdf2image) is also absent from
  `requirements.txt`, so scanned PDFs do not OCR by default.

### ISS-012 · The evidence lane cannot ingest PDFs or DOCX at all
- **Where:** `server/ingest/service.py:197`
- The document-extraction branch is skipped entirely when `lane is evidence`. Combined with
  `_whole_file_text` being forbidden (`:130-131`) and two parsers blocked (`:29,232-233`), the
  evidence lane accepts only chat/transcript/Go-registry formats. A scanned court order has no path in.
- **Status:** VERIFIED.

### ISS-013 · A populated full-text index with zero readers
- `working.normalized_record.fts` (GIN/tsvector) is created and trigger-populated. Nothing in the
  Python tree queries it. `GET /v1/records?q=` runs `WHERE nr.content ILIKE :q`
  (`server/api/inspect_routes.py:262`); entity search does the same (`entity_routes.py:73-81`).
- **Status:** VERIFIED. Cheapest available capability win.

### ISS-014 · Cross-corpus search is impossible by construction
- Three isolated stores. `Legal-Workspace/api/legal_workspace/services/agno_client.py` implements
  exactly three calls — health, `/v1/matters` (identity), `/v1/verify/{sha256}` (hash). **No call to
  any search endpoint.** No connection at all between Legal-Workspace and SBV. No component fans a
  query across more than one store. **Status:** VERIFIED.

### ISS-015 · The mature chat-ingest path has no HTTP route
- `server/analysis/context_chat_ingest.py::ingest_chat_file` does conversation modeling,
  message-boundary chunking, multi-label lane classification, per-lane Weaviate projection and a
  Graphiti drain. It is reachable **only** from `scripts/ingest_context_chat.py` and tests.
- A user uploading a ChatGPT/Claude export via the documented live API gets flat generic records
  instead. **Status:** VERIFIED.

### ISS-016 · No citation grounding or closed-world generation
- No grounding vocabulary (`CONFIRMED_GROUNDED`/`HALLUCINATED`/`MISGROUNDED`/`AMBIGUOUS`), no
  `generated_claim`/`claim_citation`/`grounding_check` tables, no elusion sampling, no allowed-span
  manifest, no backend rejection of unknown span IDs. `server/agents/instructions.py` contains zero
  citation language. These exist only in the explicitly-disclaimed `FORENSIC_DB_ARCHITECTURE_DRAFT.md`.
- **Status:** VERIFIED ABSENT.

### ISS-017 · No dual-granularity retrieval
- No `context_thread_id` / `parent_thread_id`. One embedding per `chunk_id` with
  `normalized_record_id`/`conversation_id` FKs. (`projection_kind` and `parent_span_id` exist but mean
  unrelated things — message-provenance routing and Agno's OTel tracing.) **Status:** VERIFIED ABSENT.

### ISS-018 · Retrieval has no cutoff, dedupe, diversity, or token budgeting
- Both search paths apply eligibility filters plus a bare `limit`. One over-fetches 5× then
  hard-slices. No score-relative cutoff, no overlapping-window dedupe, no source diversity, no packing.
- **Status:** VERIFIED (full read of `evidence_vector_store.py::search` and `retrieval.py`).

### ISS-019 · No EDRM / load-file production exports · ISS-020 · No stable exhibit-ID service
- No Concordance `.dat`, Opticon `.opt`, EDRM XML, custodian, or production-set concept anywhere.
- `analysis.evidence_item.exhibit_number` exists as a live schema column, unique per case, with
  **zero application code reading or writing it** — a dead column. **Status:** VERIFIED.

### ISS-021 · Legal-Workspace has no document upload pipeline
- Grep of all `api/` for upload/UploadFile/multipart/s3/boto3 → **zero matches**. `PdfPane.tsx:14-20`
  reads a file via `<input type="file">` and renders a browser-local `URL.createObjectURL()` blob in an
  iframe — it never calls `fetch()`. The only real ingest is `POST /v1/legal-source-packages:import`,
  which takes pre-hashed JSON, not files. **Status:** VERIFIED.

### ISS-022 · Legal-Workspace Postgres tables are never created
- `db/store.py:69` passes a non-null `store_dir`; `engine.py:27` makes that force the SQLite branch.
  `sql/0001` has never been applied; the live 24-table schema comes from SQLAlchemy `create_all()` and
  has already diverged. **Status:** VERIFIED (matches URGENT-TODO B2/B3).

### ISS-023 · Graphiti client is write-only
- `server/analysis/graphiti_case_client.py` — 165 lines. Full surface: `__init__`, `_headers`, `_post`,
  `_parse_sse_or_json`, `initialize`, `_ensure_init`, `call_tool`, `add_memory`. The only domain method
  is a **write**. No `search_*`, no `get_episodes`. **Status:** VERIFIED.

### ISS-024 · `verify_chain()` is never run automatically
- Defined `server/core/audit.py:514`. Only call site repo-wide: `scripts/audit_dump.py:199`. No startup
  hook, no schedule, no route. Audit-ledger tamper-evidence is only checked when a human runs a script.
- **Status:** VERIFIED.

### ISS-025 · SBV full-text search covers `body` only
- `messages_fts` (`database.go:124-132`) declares `message_id`, `address`, `contact_name`, `date` all
  `UNINDEXED`. **`body` is the only searchable column.** Call logs (`record_type=3`) have no body and
  are effectively unsearchable; contact-name and address search is impossible on any record type.
- **Status:** VERIFIED. Worse than the sibling review stated.

### ISS-026 · `InsertCallLogBatch` is dead and custody-less
- `vendored/sbv/internal/database.go:437` — zero call sites. Its INSERT omits `content_hash`
  (`:450-452`). Harmless today; would write custody-free rows if revived. **Status:** VERIFIED.

### ISS-027 · `extractGroupNameFromTrID` is live wrong code
- `vendored/sbv/internal/parser.go:394` — `return ""` with ~35 lines of real implementation commented
  out beneath. It **is** called on the live path (`:344`). Every MMS group name resolves to empty.
- **Status:** VERIFIED.

### ISS-028 · H2/H3 are never independently recomputed
- Agno re-derives H1 only, cross-checks it against SBV's reported file hash, then records SBV's H2 list
  and H3 chain **verbatim** (`computed_by="sbv:internal.custody.HashRecordH2"`). Agno holds the raw
  bytes and could re-derive. Independent H3 recomputation happens only at read time via
  `POST /v1/verify/{sha256}`. **Status:** CORROBORATED (two independent reads).

---

## 3. P2 — Structural / architectural debt

| ID | Issue | Evidence |
|---|---|---|
| ISS-030 | **Three parallel, non-converging ingest paths.** Only the flattest is HTTP-reachable. | `service.py`, `context_chat_ingest.py`, `session.py::create_knowledge` |
| ISS-031 | **Three independent chat/message schemas with zero cross-references.** `working.normalized_record` + `context_record` (0021) + `chat_conversation`/`chat_message` (0024). Grepped both directions: no FK, no shared key, no comment relating them. | `sql/0003`, `0021`, `0024` |
| ISS-032 | **Two candidate/staging systems, both live.** `extraction_candidate` marked SUPERSEDED by `candidate_entity/fact/event` via `COMMENT ON TABLE` only — never dropped. | `sql/0016:520-530` |
| ISS-033 | **`evidence.raw_*` append-only guards are inert by default.** `raw_no_mutate()` is gated on `app.evidence_live`; unset = pass-through no-op. Same for `derived_write_guard()`. | `sql/0009:163-200,281-295` |
| ISS-034 | **`evidence_hash.digest` correctness is never verified, and the table has no append-only trigger.** Only guarantee is `octet_length(digest)=32`. | `sql/0002:65`, `0019` |
| ISS-035 | **`0029_pass_grants` is inert by its own admission** — the app connects as role `ai`, a superuser, which bypasses all grants and RLS. | `sql/0029:11-19` |
| ISS-036 | **The numbered chain cannot replay from empty since 0008 — and `0014` silently no-ops** rather than failing, committing successfully having moved nothing. | `sql/README.md:32-104`; `sql/0014:71-157` |
| ISS-037 | **Two separate migration series exist.** `sql/NNNN` (0026-0030 held) and `docs/planning/forensic-db-reconciliation/migrations/NNNN` (0005 applied live 2026-06-30). "Migration NNNN" is ambiguous until the series is named. | `STATUS.md:17-18` |
| ISS-038 | **`retrieval_axes` (0018) is orphaned** — one comment reference in `server/core/audit.py:361`, no caller. | grep of `server/` |
| ISS-039 | **`native_activation.py` has zero importers** — complete, tested Weaviate cutover runbook, unwired. | grep of `server/`, `scripts/` |
| ISS-040 | **Semantica is half-wired.** `semantica_worker.py` is production code importing the vendored tree, but its only callers are a test and a fixture script. 15 formats supported; carries a torch/transformers/spacy tail. | `server/analysis/semantica_*.py` |
| ISS-041 | **`patterns.py` cannot catch ISS-001.** `MCL_LETTERS = set("abcdefghijkl")` at `:41`; `:210-212` validates letter membership only, never reads name/description. | VERIFIED |
| ISS-042 | **`sbv_sms.py` docstring misstates its own precedence mechanism** — claims alphabetical registration order; code uses `priority=100` resolved by `registry.py:87`. | `sbv_sms.py:14-20` |
| ISS-043 | **`DEBT.md:119` is stale** — claims `evals/cases.py` is `CASES = ()`; the file has 146 lines and 8 live Cases. **Both gap analyses inherited this error.** | VERIFIED |
| ISS-044 | **`EVIDENCE_MERGE_MAP.md` asserts a Tether path that does not exist on disk.** Real code is at `TheBigOne_SAFE_COPY/04_Utilities/Tether/app.py`. | VERIFIED |
| ISS-045 | **Contradiction rules are UNHOMED** — "the live schema has no contradiction table yet." | `patterns.py:17-19` |
| ISS-046 | **Six behavioral modules carry `needs_review: true` and empty `mcl_factors`** — guilt_trip, boundary_violation, triangulation, word_salad, hoovering, intermittent_reinforcement. | `behavioral_patterns.json:769-836` |
| **ISS-049** | **The behavioral-analysis mechanism over-flags and needs a full rework.** Owner ruling 2026-08-23: "that whole analysis is broken… the mechanism is bad, it over-flags everything, that whole process has to be reworked." Consistent with the standing project note that both prior detection passes over-flagged against an owner-labelled gold set. **Do not invest further in the custom ontology (ISS-045, ISS-046) until the mechanism is redesigned.** The ISS-001 label fix is independent and still valid — a correct label on an over-flagged finding is still an over-flagged finding. | OWNER, deferred |
| ISS-047 | **Backups do not reach R2 and skip Neo4j.** `scripts/backup_ovhdata_hot.sh` is a one-time local snapshot; `DEBT.md:176` says "planned". | VERIFIED |
| ISS-048 | **No machine-readable capability/deployment register.** `TODO-SNAPSHOT-*.json` are session TODO lists, not deployment state. | VERIFIED |

---

## 4. P3 — Hygiene

- **ISS-050** — Root `iceberg` is not a directory. `file` reports "DuckDB database file, version 64",
  12,288 bytes, `SHOW TABLES` returns `[]`. An empty stray file with a misleading name.
- **ISS-051** — `scripts.zip` (134 KB) and `server/tools.zip` (408 KB), same timestamp, referenced
  nowhere in `docs/`, sitting beside the live unzipped directories.
- **ISS-052** — `.backup_<timestamp>` proliferation: 9 in `sql/`, 3 for `AGENTS.md`, many across
  `server/tools/parsers/messaging/`. A pre-edit snapshot convention layered on top of git.
- **ISS-053** — `analytics/visit-locations` is a real, working Evidence.dev dashboard. Needs
  reconciling against the standing "Takeout Timeline = PARKED" rule. May be a pre-existing exception.

---

## 4b. Surfaced while applying Wave 0 (2026-08-23) — pre-existing, not introduced

- **ISS-054 · `Legal-Workspace` `tests/test_calendar.py::test_http_docket` fails 401.** At HEAD the
  test builds a bare `TestClient(app)` with no `Authorization` header and asserts 200. ContextForge
  JWT auth was added to the app after the test was written. Fix: add
  `client.headers = {"Authorization": "Bearer test-jwt-secret-for-testing"}` as
  `tests/test_api.py:43` does. **Attribution verified:** fails identically in isolation at an
  original line (`:58`), and the Wave 0 delta only appended tests below line 84.
- **ISS-055 · `Agno` `tests/test_workflow_ledger_wiring.py::test_ledger_failure_does_not_block_the_ingest`
  fails on schema drift.** `SmsXmlInput` now requires `source_principal` and
  `caller_owns_conversation` (the ADR-0059 governed-conversations work), but the test still posts
  `{'path': '/tmp/a.xml'}` → `ValidationError` at `server/api/workflow_registry.py:99`. Fix: update
  the test payload. **Attribution verified:** the Wave 0 `sbv_sms.py` edit was docstring-only
  (`git diff` confirms zero code lines changed).

## 5. OWNER — blocked on a decision, not on engineering

| ID | Decision needed | Age |
|---|---|---|
| ~~OWN-001~~ | ~~**JWT rotation plan** (ISS-003).~~ **RULED 2026-08-23 — owner: no rotation.** Closed by decision, not deferred. Rationale: rotation invalidates every token platform-wide at once (agentos, librechat, gateway, Legal-Workspace), and the surface is tailnet-fronted personal/internal infrastructure. **Standing consequence:** a ContextForge JWT is not a security boundary — do not introduce a service that treats one as proof of authorization without reopening this. ISS-003 is closed on the same basis. | **CLOSED** |
| OWN-002 | **Matter-MVP decision packet** — 15 decisions (P1-P5, R1-R6, A1-A4) unanswered; the "Recommended compact ruling" template at `:159` is unfilled. | 8 days |
| OWN-003 | **Migrations 0026-0030 cutover** — five consecutive files marked `HELD FOR OWNER / NOT APPLIED`. Gates ISS-008. | open |
| ~~OWN-004~~ | ~~**Custody policy:** mandatory at capture, or best-effort?~~ **RULED 2026-08-23 — owner: (a) mandatory at capture.** Evidence-lane ingest refuses when hashing is unavailable; silent degradation is not acceptable. Owner added the decisive follow-up: **extract hashing into a standalone process** callable by the SBV path, the fallback path, or anything else — "whether one fails or the other fails, they can call the hashing process." See TODO-207, which must land **before** (a) is enforced. | **RULED** |
| OWN-005 | **SurrealDB contradiction** — formally RETIRED (ADR-0043) yet `data-surreal-phase1-t0-r1` was ordered promoted 2026-08-20. | `URGENT-TODO` #14 |

---

## 6. Root-cause analysis — why this list regenerates

Three systems archetypes are producing the defect stream. Fixing items without addressing these
means the list rebuilds.

**Shifting the Burden** — a symptomatic solution keeps substituting for the fundamental one, and the
substitute removes pressure to build the real thing:
- custody hashing → opt-in flag + non-hashing fallback (ISS-002)
- schema DDL → applied out-of-band via `_manual/` (ISS-036)
- doc versioning → `.backup_*` snapshots instead of git (ISS-052)

**Growth and Underinvestment** — design capacity outran application capacity. Five migrations written
and unapplied (OWN-003), leaving a live contradiction (ISS-008). The binding constraint is **decision
throughput**, not engineering throughput: 17+ rulings are queued.

**Tragedy of the Commons** — many agent sessions edit one shared doc set; each snapshots for local
safety; the collective result is drift. **Proof of real cost:** `DEBT.md:119` was stale and *both*
independent gap analyses inherited the error without opening the file (ISS-043).

**Conclusion:** doc drift is not a hygiene problem. It is the primary defect generator, because status
claims are hand-written rather than derived.

---

## 7. Claims that FAILED verification — do not act on these

Recorded so they are not silently re-raised.

| Claim (source) | Verdict |
|---|---|
| "SBV has no evidentiary hash field, no chain-of-custody column" (gaps.md) | **REFUTED** — `pkg/custodyhash`, `ensureCustodyColumns()`, `messages.content_hash`, `imports` table |
| "No bridge from SBV to the custody schema" (gaps.md) | **REFUTED** — `reconcile_sbv_import()` exists and is wired via `sbv_sms.py::_reconcile_custody` |
| "SBV is Android-only" (gaps.md) | **REFUTED** — also iMessage, FB Messenger, Google Voice, email, Google Chat |
| "`sql/0001-0018` implements `analysis.normalized_record`" (gaps.md) | **REFUTED** — 30 migrations; it is `working.normalized_record` since 0014 |
| "Semantica has zero runtime call sites" (gaps.md) | **REFUTED as stated** — `semantica_worker.py` is production code that imports it |
| "vLex taxonomy not yet extended to factual claims" (gaps.md) | **PREMISE UNSUPPORTED** — the taxonomy exists nowhere in either codebase |
| "`systemRouter.ts` promotes Chroma→PG→LanceDB→Neo4j" (gaps.md) | **REFUTED** — real `TrinityRouter`, different tiers, no LanceDB, no promotion |
| "Tether models live in dial-stack `utilities/`" (gaps.md) | **PARTIAL** — models real, location false |
| "`evals/cases.py` is empty" (edisc gap analysis) | **REFUTED** — 146 lines, 8 Cases |
| "No governed per-event factor link exists" (edisc gap analysis) | **LARGELY REFUTED** — `analysis.factor_citation` is applied live; missing only span offsets + version column |
| "Custody parser demoted PRIMARY→SHADOW" (sibling F-02) | **REFUTED** — `priority=100` makes SBV primary. The *consequence* (ISS-002) still holds |
| "Dropped MMS parts are recoverable" (sibling F-05) | **REFUTED** — raw XML discarded after hashing |

**Also worth noting:** the two reviews examined **different copies of SBV**. The sibling session
shallow-cloned the standalone `sbv-forensic` remote; this session read
`Agno-MCP-Platform/vendored/sbv`, the subtree the platform actually builds. Divergence is the first
hypothesis for any remaining SBV disagreement.

---

# TODO — sequenced remediation plan

Ordering rule: **correctness before capability; verification capability before retrieval quality.**
That second constraint is not stylistic — see TODO-201.

## Wave 0 — Stop producing wrong output (hours)

**TODO-001 · Add the factor contract test, then fix the swap**
- Write a test asserting letter ↔ name ↔ description against official MCL 722.23 text for all 12
  letters. Watch it fail.
- Swap the two `name` values at `behavioral_patterns.json:60,65`. Watch it pass.
- **Why this order:** `patterns.py` structurally cannot catch a name/description swap (ISS-041). Fixing
  the data without the test fixes one instance, not the class — the next config edit re-breaks it.
- Blast radius: config only; ~12 modules reference the letters, none change.
- Closes ISS-001, mitigates ISS-041.

**TODO-002 · Fix the calendar DELETE crash**
- Add `from uuid import UUID` to `calendar_routes.py`.
- Add a test hitting `DELETE /v1/calendar/events/not-a-uuid`, asserting **400** (not 500).
- Closes ISS-005. One line, zero blast radius.

**TODO-003 · File the missing URGENT-TODO entries**
- Add entries for ISS-011 (docling/OCR extras absent → four office formats fail) and ISS-012 (evidence
  lane cannot ingest PDF/DOCX).
- Add `# STUB:` markers at `docling_extract.py:31` per `server/contracts/AGENTS.md:60-61`.
- **Why:** the standing LIVE ONLY policy requires every known-broken thing to be tracked. A silent gap
  is a defect by your own rule.

**TODO-004 · Correct the three stale doc claims**
- `DEBT.md:119` → `evals/cases.py` has 146 lines, 8 Cases (ISS-043).
- `EVIDENCE_MERGE_MAP.md` → real Tether path (ISS-044).
- `sbv_sms.py:14-20` → precedence is `priority=100` via `registry.py:87`, not alphabetical import
  order (ISS-042).
- **Why now:** ISS-043 already corrupted two independent audits. This is cheap and stops the bleeding.

## Wave 1 — Decide (blocks everything downstream)

**TODO-101 · ~~Rule on the custody policy~~ — RULED 2026-08-23: (a) mandatory at capture**

Evidence-lane ingest must refuse rather than silently produce custody-free records.

**Blocking caveat found while scoping (2026-08-23):** `_sbv_enabled()` is
`bool(os.getenv("SBV_SERVICE_PASS"))` (`sbv_sms.py:379-384`). Enforcing (a) as-is would make
evidence-lane SMS ingest **fail outright in every environment where that env var is unset** — an
availability cliff, not a safeguard. The owner's own follow-up dissolves this: build TODO-207 first,
and (a) becomes free.

**Sequencing: TODO-207 → then enforce (a).**

---

**TODO-207 · Extract custody hashing into a standalone callable process** _(owner directive, 2026-08-23)_

> "Separate process that gets called by SBV or by the backup … whether one fails or the other
> fails, they can call the hashing process."

**Why this is cheap.** `vendored/sbv/pkg/custodyhash/custodyhash.go` is **already decoupled and
dependency-free** — its only imports are `crypto/sha256`, `encoding/hex`, `io`. Public surface:

    HashBytes · HashReaderH1 · HashFileH1 · HashRecordH2 · ChainH3 · FoldChain · NewChain/Add/Value

That is a complete custody API with zero third-party dependencies. Go 1.26.7 is on PATH (verified
2026-08-23 — an earlier note claiming no Go toolchain was wrong for this environment).

**Shape:** compile `pkg/custodyhash` into a small standalone CLI binary. No HTTP service, no
credentials, no running daemon — callers shell out to it. That removes the dependency on SBV being
*up*, which is the entire failure mode behind ISS-002.

**Callers after this lands:**
- `sbv_sms.py` (SBV path) — unchanged behaviour, or switches to the CLI for consistency
- `sms_xml.py` (fallback path) — gains custody hashing for the first time, closing ISS-002 route (a)
- any future ingest path, without re-solving custody

**HARD CONSTRAINT — one implementation, never two.** Do **not** reimplement H1/H2/H3 in Python. This
project has already been burned by two valid-but-different H3 constructions colliding under a single
`h3-chain-v1` tag (see `custody.py:374-384`). A Python reimplementation risks exactly that again.
The Go package is the single source of truth; everything else calls it.

**Also unblocks:** TODO-202 (chain H3 across batches) and TODO-205 (independently recompute H2/H3 in
Agno) both become straightforward once hashing is callable outside the SBV service.

---

**TODO-208 · Change detection: record the change, then rebuild the affected walk** _(owner directive,
2026-08-23 — **deferred, not urgent**)_

> "Record changes… when something is updated or modified or changed, how it would change the horizon
> walk — so the change detection would have to then rebuild the derived index or view for that
> particular walk based on the new information. All that's been discussed."

**Owner notes this was already discussed previously** — find that prior design before rebuilding it
from scratch. Search the session logs (this is exactly the arbitration pass the owner described on
2026-07-29) before writing anything new.

**Two halves, in order:**

**(a) Record the change.** Today `working.message_projection_route` has **no immutability trigger** —
verified 2026-08-23. A message's classification can be flipped from acquired-third-party to
first-party after approval, with nothing recording that it happened. That silently moves the record's
awareness date from *when it was acquired* to *when it occurred*, rewriting what the owner knew and
when. `working.promotion` already has the pattern to copy: a revoke-only trigger permitting exactly
one shape of update and blocking everything else (`sql/0017_append_only_guards.sql:43-67`).

**(b) Rebuild what the change invalidated.** A changed classification, a new realization event, or a
corrected acquisition date all move `visible_from` — which means:

- the materialized cache row in `working.record_visible_from` is stale (the fast path in
  `sql/0028_horizon_repoint.sql`), and
- **any walk that already consumed that record was derived from now-wrong data.** Walks are
  version-pinned and hash-chained (`sql/0027_walk_ledger.sql`), so a stale walk is not just
  inaccurate — its reproducibility hash no longer matches what a re-derivation would produce.

So change detection must, at minimum: invalidate the cached availability, identify every walk step
that retrieved the affected record, and mark those walks for re-derivation rather than leaving them
silently wrong. `working.vw_walk_contamination` already detects a related condition (a record
retrieved whose availability is later than the step's horizon) and is the natural place to extend.

**Do not start this until the migrations are applied** — both halves sit on top of tables that do not
exist live yet.

**TODO-102 · Answer the Matter-MVP packet (OWN-002)** — 15 decisions, template at `:159`. Eight days
pending; gates the matter/case foundation.

**TODO-103 · Sequence the JWT rotation (OWN-001)** — needs a plan that rotates CF, then dependent
services, in an order that never locks you out. Not a patch.

**TODO-104 · Rule on the 0026-0030 cutover (OWN-003)** — gates ISS-008, the live horizon contradiction.

## Wave 2 — Make the custody chain mean what it claims

**TODO-201 · Point `/v1/records?q=` at the existing FTS index — with a guardrail**
- The GIN/tsvector index is already created and trigger-populated (ISS-013). Swap the `ILIKE` at
  `inspect_routes.py:262` for a `to_tsquery` match.
- **Mandatory pairing:** results must carry a visible "not grounded / not court-safe" marker until
  ISS-016 lands.
- **Why the pairing:** first-order, search gets real. Second-order, people rely on it. Third-order,
  they rely on it *before* citation-grounding exists, and unverified retrieval feeds legal work
  product. That is exactly the failure the Mary whitepapers describe.
- **Do NOT delete the index** — it is the cheapest path to a named gap, and deletion violates the
  never-delete rule.

**TODO-202 · Chain H3 across batches** — seed `engine.go`'s sink from the previous import's
`chain_hash` instead of `""` (ISS-006). **Requires a new canon tag** — the existing
`h3-chain-sbv-genesisempty-v1` names the genesis-empty construction, and a cross-batch chain is a
different construction. Never relabel existing rows.

**TODO-203 · Add `content_hash` to the SBV dedup key** (ISS-007). Changes dedup semantics — needs a
migration plan and a decision on existing collapsed rows.

**TODO-204 · Store all MMS parts, or record the loss** (ISS-004). Minimum viable: a `parts_total` /
`parts_stored` counter plus a rejection-ledger row, so the loss is signalled. Full fix: persist every
part.

**TODO-205 · Independently recompute H2/H3 in Agno** (ISS-028). Agno holds the raw bytes. Re-deriving
removes the trust dependency on SBV's own computation at write time.

**TODO-206 · Schedule `verify_chain()`** (ISS-024) — a startup check plus a cron, not just a manual
script.

## Wave 2b — Owner additions, 2026-08-23 evening (recorded verbatim intent, sequenced after ingest testing)

**TODO-210 · Apply bitemporal properties to the Neo4j entity/fact graph** _(owner directive)_

The graph Semantica's extractions build in Neo4j must carry the same two-clock awareness the
Postgres spine has: when a relationship was true vs when we learned it, with supersession instead
of overwrite. Today the graph has neither — facts land as timeless edges. Prerequisite thinking
exists (the spine's `occurred_at` / availability / realization model is the template); the work is
projecting those fields onto graph edges and teaching graph queries to filter by horizon the same
way `vw_spine_horizon` does. Sequenced AFTER ingest testing establishes real data flow.

**TODO-211 · Agent memory: explore engines, temporal awareness is the hard requirement** _(owner directive)_

> Owner: "there has to be some agent memory going on and right now I don't believe Surreal is the
> ticket but I'm not sure — maybe it is — but we do need agent memory, it should be temporally
> aware, so we need to explore that at some point."

**Hard requirements, owner 2026-08-23 (verbatim intent): "graph based and temporal with hybrid
search — I want all the features."** Judging order: self-hosted operability first (what killed
Graphiti), then feature completeness, then benchmarks.

**Likely frontrunner — Cognee.** This is almost certainly the system the owner remembers
("another memory system that's supposed to have all of those things and an SQLite database for
fast indexing"): Cognee's three-store architecture is exactly graph store + vector store +
**relational store (SQLite by default) for fast metadata indexing**, with 14 hybrid search modes
spanning all three, temporal/self-improving graph features (`memify`), and a fully customizable
ingest pipeline. It beat Mem0, Graphiti, and LightRAG on multi-hop reasoning (HotPotQA EM/F1).
Trade-off to test: heavier ingest-time processing — and per the LIVE ONLY policy this deploys and
gets tested **on the fleet, in place** (a Coolify app beside the data tier), never on the local
machine; embedding/LLM calls route through Portkey like everything else, so the fleet's
CPU-only constraint applies to Cognee's local processing stages, not its model calls.

Candidates to evaluate, all against the same bar (bitemporal belief tracking, cheap horizon
queries, CPU-friendly, fits the tailnet fleet):
- **Cognee** — the frontrunner above; graph+vector+SQLite, hybrid modes, self-hostable Python
- **Memgraph** — exploration already opened as ADR-0041 (2026-07-28), never concluded; in-memory
  graph, Cypher-compatible, would also bear on TODO-210's engine choice
- **SurrealDB** — the ruled analytical surface (D-061); owner is unconvinced it fits the *agent
  memory* role specifically — evaluate, don't assume
- **Postgres-native** — the run ledger + walk checkpoints already persist run-scoped state; with
  Temporal keeping live workflow state, the residual "memory" need may be smaller than it looks
- **Graphiti** — the incumbent for exactly this role; write-only client, zero rows drained.
  **Owner's stated retirement rationale (2026-08-23, verbatim intent): the self-hosted MCP server
  never worked like Zep's hosted version** — the custom image exists only because upstream drops
  the Neo4j database field, the case-lane read path never functioned, and it "keeps getting
  fucked and not functioning properly, so I just gave up." The retirement is OPERATIONAL, not
  conceptual — the temporal-KG idea was sound, the self-hosted implementation was not. Two
  consequences for the bake-off: (1) any candidate must be judged on operability-as-self-hosted
  first, features second — that is the failure mode that actually killed the incumbent;
  (2) Zep's HOSTED service technically remains an option if the memory involved is never case
  evidence, but that conflicts with keeping case-adjacent data on owned infrastructure — treat
  hosted-Zep as excluded unless the owner explicitly says otherwise.

Explicitly sequenced: **after ingest testing** produces real corpus data to evaluate against.
Not before.

**TODO-213 · Consolidate the knowledge-timing name: `disclosure_horizon` vs `disclosure_tier`**
_(owner-flagged 2026-08-23; verified live the same night)_

The owner flagged the old `disclosure_tier` enum collision (public/restricted/sealed vs the
temporal values). Live introspection shows that ORIGINAL collision was resolved by `sql/0008` —
the misnamed enum is gone; the access concept lives correctly as `sensitivity_tier`
(public/restricted/sealed). **But the same check exposed the surviving cousin:** the
knowledge-timing concept (contemporaneous/hindsight/discovered) exists live under TWO names and
TWO typings — `disclosure_horizon` as a proper enum on `analysis.time_assertion` /
`analysis.timeline_event`, and `disclosure_tier` as plain TEXT+CHECK on
`working.normalized_record` and its views (`vw_spine_horizon`, `vw_horizon_atom`,
`vw_record_disclosure`). Same three values, different clothes; a join across timeline and spine
must simply *know* they're the same concept.

Consolidation direction: one name (`disclosure_horizon` — "tier" is what caused the original
collision with sensitivity), one enum type, everywhere. The spine-side rename is a breaking
change under the no-compatibility-aliases policy, so it is owner-gated, sequenced with the next
deliberate schema wave — not a late-night patch. Until then: any new table takes
`disclosure_horizon` (the enum), never a new `disclosure_tier` column.

**TODO-212 · Framework roles under Temporal — ruled by discussion, 2026-08-23 evening**

| Job | Handled by |
|---|---|
| Sequencing, retries, gates, durability | Temporal (workflows) |
| Classification & extraction model calls | **DSPy programs** — compiled against owner-labeled gold sets, schema-enforced JSON via Portkey, run inside Activities. Owner named DSPy for this slot; it operationalizes the debt register's own demands (human-labeled eval, LLM challenger, sampled audit) and gives a systematic recompile-and-compare answer when models change. Cost to plan: the gold set is the real work — a few hundred labeled chunks to start lane classification; substantially more before the behavioral-analysis rework leans on it. |
| Tool-rich single agents, knowledge/RAG | Agno (as today — no rip-out; ingest barely touches agents) |
| Multi-agent deliberation (investigation/analysis) | AG2, per the existing 08-15 coordination lane — review that handoff against the Temporal plan before restarting it, since it predates the Temporal ruling |
| Visual pipeline driving | Workbench (deployment already a Temporal-P2 prerequisite) |

LangGraph: benched — its durable-graph niche is Temporal's job here, and deliberation is AG2's;
revisit only if a concrete in-step graph appears that neither covers. Dify: struck — was a
misreading of the owner's "DSPy" and would have been a parallel platform anyway.

## Wave 3 — Build the missing capabilities

Ordered by dependency, not by size:

1. **TODO-301 · Addressable spans + closed-world citations** (ISS-016). Canonical span IDs for message,
   page, paragraph, image region, context window. Backend rejects any span ID outside the retrieval
   manifest. **This gates everything court-facing.**
2. **TODO-302 · Dual-granularity projections** (ISS-017) — `projection_kind = atomic_fact |
   contextual_exchange`, `parent_span_id`, deterministic context hash.
3. **TODO-303 · Retrieval assembly** (ISS-018) — score-relative cutoff, overlap dedupe, source
   diversity, token budgeting. Calibrate empirically; do not hard-code the 25% heuristic.
4. **TODO-304 · Grounding validation** (ISS-016) — separate existence / pinpoint / characterization
   outcomes. Stratified sampling with confidence intervals.
5. **TODO-305 · Exhibit identity layer** (ISS-020) — activate the dead `exhibit_number` column or
   replace it. Reservation, aliases, supersession. Never derive numbering from mutable sort order.
6. **TODO-306 · Evidence bundling** (ISS-010) — belongs beside Legal-Workspace's existing exhibit/Bates
   machinery. **Prerequisite:** Legal-Workspace needs a search call into Agno, which it deliberately
   does not have (ISS-014).
7. **TODO-307 · EDRM load-file export** (ISS-019) — a separate target from the courtroom chronology.
8. **TODO-308 · Courtroom matrix renderer** (ISS-019) — blocked until ISS-017 and ISS-020 exist.

## Wave 4 — Remove the defect generator

**TODO-401 · Build the derived capability ledger** (ISS-048)

Five independent, separately-verifiable states per capability:

- merged
- migration applied
- service deployed
- projection backfilled
- observed end-to-end

**Derive it, do not hand-write it.** A hand-maintained doc drifts the moment reality moves.
`MASTER-TODO-2026-08-18.md` is honest today and wrong by default tomorrow.

**This is the highest-leverage item in the plan.** On Meadows' ladder, patching defects is a parameter
change — the weakest intervention. Contract tests are rules — stronger. An information flow that makes
drift structurally impossible sits above both.

**TODO-402 · Retire the `.backup_*` convention** (ISS-052) — it was a fix for multi-agent doc
collisions. Second-order effect: readers can no longer tell which file is live. The fix now causes the
confusion it prevented. Move existing ones to `_stale/`; never delete.

**TODO-403 · Quarantine the hygiene items** — root `iceberg` (ISS-050), the two zips (ISS-051) to
`_stale/`. Reconcile `analytics/visit-locations` against the Timeline-parked rule (ISS-053).

## Wave 5 — Consolidate the parallel structures

Do **not** start these until Waves 0-2 are done and the migration cutover has landed.

- **TODO-501** — collapse the three ingest paths (ISS-030); expose the mature chat path over HTTP
  (ISS-015).
- **TODO-502** — reconcile the three chat/message schemas (ISS-031). Decide whether `0024` supersedes
  `0021`/`0022` or coexists; the SQL says neither.
- **TODO-503** — retire `extraction_candidate` / `record_observation` properly (ISS-032). They are
  marked superseded by comment only.
- **TODO-504** — arm the append-only guards (ISS-033) once the schema stops churning.
- **TODO-505** — resolve the superuser connection model (ISS-035) so `0029` grants become enforcing.
- **TODO-506** — bring the out-of-band custody DDL into the numbered chain (ISS-036), and disambiguate
  the two migration series (ISS-037).
