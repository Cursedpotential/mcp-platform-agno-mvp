# Lane 1b — Agno evidence: custody, hashing, search, bundling

> _Byline: Claude Code · Opus 5 · 2026-08-23_ · source: subagent af847d2cb6f204504

Scope: `server/evidence/` (all files), the API routes exposing it, `server/case_management/`.
Method: full reads of every named file + targeted greps across `server/`.

## 1. Custody & hashing

### Representation

Chain-of-custody is a real, append-only relational model:

- `evidence.evidence_hash` — one row per hash (H1/H2/H3), written only by `custody.py`
  (`server/evidence/custody.py:279-328`).
- `evidence.source` — file-level metadata (sha256, byte_size, mime, acquisition fields) (`custody.py:286-304`).
- `evidence.acquisition` — human-asserted acquisition event (method, authority, source_device,
  acquired_at, asserter identity) (`custody.py:141-170`, `_insert_acquisition`).
- `evidence.custody_event` — append-only chain-of-custody event log via `record_custody_event()`
  (`custody.py:396-426`).

Module-level guarantee (`custody.py:2,10-13`): this module is the ONLY writer of the `evidence`
schema; agent DB connections ride the read-only engine (ADR-0005) and physically cannot write here.

### Exact hash construction

- **H1** = plain `sha256` over raw file bytes, streamed in 1 MiB chunks (`custody.py:133-138`,
  `_sha256_file`), tag `h1-rawbytes-v1` (`:381`, used at insert `:314`).
- **H2** = per-record hash, **computed by the external Go service (SBV)**, not by Python. This module
  only STORES SBV's reported H2 digests (`:513-525`,
  `record_evidence_hash(level="H2", ..., computed_by="sbv:internal.custody.HashRecordH2")`).
  Tag `h2-rawelement-v1` (`:382`).
- **H3 (chain)**: genesis = empty string `""`; fold `chain_i = sha256(chain_{i-1} + "\n" + H2_i_hex)`,
  folded left-to-right in `record_locator->>'record_index'` order. Independently re-derivable by app
  code at `server/api/inspect_routes.py:630-660` (`_walk_h3_chain`), matching
  `vendored/sbv/internal/custody.go`. Tag `h3-chain-sbv-genesisempty-v1` (`:383`).
  A legacy, deliberately-disambiguated tag `h3-chain-v1` covers pre-2026-08-02 rows that used a
  DIFFERENT but equally valid H1-genesis construction from the Case Bible vault — explicitly never
  relabelled (`custody.py:374-384`, `inspect_routes.py:91-100`).
- A **separate, unrelated hash chain** exists in `derivation.py` for reproducible pass-corpus
  derivation: `corpus_hash = sha256(prev_hash || canonical_slice)`, genesis =
  `sha256(base_version || canonical_parameters)` (`derivation.py:155-184`). Not evidentiary custody.

### Enforcement before write — real, but partial

- **H1 is never trusted from a caller.** `ingest_artifact()` always computes its own SHA-256
  (`custody.py:207`), never accepts a caller-supplied digest.
- **Write-once blob integrity enforced at write time**: file copied to a temp name, the COPY is
  re-hashed, `RuntimeError` raised if it disagrees with the source hash, before the atomic
  `os.replace()` (`custody.py:262-270`). A crash cannot leave a partial file at a sha-named path.
- **`reconcile_sbv_import()` cross-validates before persisting** (`custody.py:483-546`): independently
  recomputes H1 via `ingest_artifact()` and compares to SBV's reported `sbv_file_hash`; only on match
  does it persist SBV's H2/H3 (tagged `verified`); on mismatch it records ONLY an
  `integrity_violation` custody_event and does NOT persist the untrustworthy H2/H3.
- **H2/H3 are NOT independently recomputed at write time** — this module trusts SBV for those levels.
  Independent H3-chain recomputation happens only at READ time via `POST /v1/verify/{sha256}`
  (`inspect_routes.py:663-753`).
- `verify_artifact()` (`custody.py:345-353`) is a read-time integrity check, used by the CLI `verify`
  command (`cli.py:79-84`) and the verify route — not invoked automatically before any write.

### DB constraints/triggers referenced (by name)

- `custody_event_chain` trigger — computes the hash-chained `event_digest`; app never sets it
  (`custody.py:404-405`).
- `evidence_hash_subject_ck` CHECK — every H1/H2 must carry `source_id` (or `file_node_id`); only H3
  may omit it (`custody.py:279-284`).
- `realization_event_approved_iff_timestamp` CHECK (`realization.py:183-186`).
- `evidence.custody_event`'s legacy trigger is independently RE-DERIVED at read time in
  `server/case_management/repository.py:1700-1737` — raw SQL `digest(...)` recomputation brute-forcing
  UTC-offset candidates (`-12:00`..`+14:00`, 15-min steps) because the legacy trigger hashed a
  session-rendered timestamp with unknown offset. Feeds `court_readiness`'s `event_chain_valid` gate.

**Verdict:** custody is a genuine layered gate — H1 self-computed and copy-verified at write time, and
cross-checked against SBV's file-level claim before any H2/H3 is trusted; but H2/H3 themselves are
stored trustingly at write time, with independent recomputation deferred to a read-time endpoint.

## 2. Search / retrieval surfaces

Three distinct, non-overlapping surfaces:

**(a) Substring search over normalized records — NOT full-text.**
`GET /v1/records?q=...` → `WHERE nr.content ILIKE :q` (`inspect_routes.py:262`, built `:259-264`,
executed `:270-339`). Grepping the whole lane for `tsvector|ts_query|to_tsquery|to_tsvector|GIN`
returns **zero hits** — no Postgres full-text search exists anywhere in this lane.

**(b) Entity name search.** `GET /v1/entities?q=...` → `ILIKE` against
`display_name`/`canonical_name`/alias text (`server/api/entity_routes.py:73-81`), over `working.entity`.

**(c) Vector search — two parallel implementations.**

*Legacy Agno path* — `server/evidence/retrieval.py::evidence_search()` (`:134-216`):
- `engine.async_search(query, max_results=fetch, filters={"case_id": case_id})` (`:185`) where
  `engine = resolve_knowledge(knowledge)` (`:176`).
- **Post-filters, not pre-filters**: over-fetches (`_OVERFETCH=5`, `_MAX_FETCH=100`, `:46-47,180`)
  then walks results in Python denying any doc whose `source_available_from`/`visible_from` is missing
  or in the future (`:189-198`). Docstring explains why (`:23-30`): the Agno Weaviate adapter can
  prefilter exact dict fields but stores metadata as JSON text, so missing range-prefilter support is
  an activation hold.
- Every call is audited via `server.core.audit.record_read` before returning (`:203-215`); a failed
  audit write is meant to fail the search (`:19-21`).

*Native path* — `native_evidence_search()` (`retrieval.py:62-123`):
- Requires a `NativeEvidenceVectorStore` (`:82-85`). Embeds the query, validates dimension against
  `EVIDENCE_EMBED_DIM` (`:90-93`), then `store.search(vector, query, mode, horizon, case_id,
  disclosure_tiers, limit)` (`:94-102`).
- Traced into `server/core/evidence_vector_store.py::NativeEvidenceVectorStore.search()` (`:344-409`):
  a real PRE-FILTERED Weaviate query — `Filter.all_of([case_id equal,
  source_availability_complete=True, authority_state='active', disclosure_tier in(...),
  source_available_from <= horizon])` executed via `.query.near_vector(...)` or `.hybrid(query=...,
  vector=..., alpha=0.75, query_properties=["content"])` (`:378-409`). Horizon, case and tier filtering
  happen BEFORE ranking here. Also audited (`retrieval.py:104-123`).

**`search_capability.py`** is just an HMAC token issuer (`issue_walk_search_capability`, `:16-24`)
binding one walk-run/step/checkpoint triple to a signed bearer token (`WALK_PASS_SIGNING_KEY`).
It performs no search — it's the authorization primitive consumed by
`native_evidence_search_routes.py:92-109`.

### Full call path, route → executed query

`POST /v1/evidence/search` (`server/api/native_evidence_search_routes.py:314-342`):
1. `_authenticate_walk_capability()` verifies bearer token (`:92-109`).
2. `_resolve_walk_context()` resolves case/actor/horizon/disclosure_tiers **from Postgres**
   (`working.walk_run`/`walk_checkpoint`/`walk_step`), never from client input (`:112-196`).
3. `executor(...)` → `_execute_native_search()` (`:199-239`) builds embedder + vector store and calls
   `retrieval.native_evidence_search()` (`:213,229`).
4. → `store.search(...)` → real Weaviate `near_vector`/`hybrid`.

`POST /v1/operator/evidence/search` (`:344-374`) — same executor, gated by static bearer secret
(`EVIDENCE_OPERATOR_SECURITY_KEY`), hard-capped to `_SAFE_TIERS` (never hindsight) (`:28-30,354-359`).

`evidence_routes.py` (`POST /v1/evidence/import`) is an INGEST route, not search.

### `retrieval_axes` (migration 0018) — ORPHANED

Grepping all of `server/` for `retrieval_axes` returns exactly ONE hit: a comment in
`server/core/audit.py:361`. **No caller** anywhere in `server/evidence/`, `server/api/`, or
`server/case_management/`. Horizon-gating in this lane is done by different mechanisms: Python
post-filtering (legacy), Weaviate metadata pre-filtering (native), and a Postgres function
`working.source_available_from(id)` (used at `derivation.py:194-197`, `vector_projection.py`,
`repository.py:313`).

## 3. Evidence bundling — DOES NOT EXIST

Grep (case-insensitive) for `bundle|exhibit|production|bates|packet|disclosure|manifest` in-lane:

| Term | Hits | Assessment |
|---|---|---|
| `bundle` | `store.py:651,656,662,719` | English usage only — "a conversation document **bundles** many records" (grouping chat messages into one markdown doc, `:645-728` `horizon_axes()`). Not an exhibit concept. |
| `exhibit` | none | Zero hits. |
| `bates` | none | Zero hits. |
| `packet` | none | Zero hits. |
| `production` | `derivation.py:100` | English usage — "production callers that need atomicity". |
| `disclosure` | `disclosure_tier(s)` throughout | A **metadata classification** (contemporaneous/discovered/hindsight) for horizon-gating access. Not legal-discovery production. |
| `manifest` | `native_activation.py:34,189-213,294-368` | A **reconciliation manifest** — JSON rows compared between Postgres and Weaviate to prove parity during vector-store cutover (`reconcile()`, `:182-219`). Internal data-integrity artifact. |

**Plain statement: NO evidence bundling capability exists in this lane.** No code path in
`server/evidence/`, `evidence_routes.py`, `native_evidence_search_routes.py`, `inspect_routes.py`,
`run_routes.py`, or `server/case_management/` assembles multiple evidence items into a deliverable.

Closest adjacent concept is `server/case_management/`'s **per-item** machinery:
- `promote_evidence()` — promotes ONE normalized record into `analysis.evidence_item` with full
  provenance re-verification (`repository.py:793-895`).
- `get_court_readiness()` — evaluates a SINGLE item against 9 named gates (content review, provenance,
  custody, authentication, confidence, assertion, redaction, sensitivity, court_export), returns
  pass/fail + blockers (`repository.py:386-485`, `:1574-1752`; contract
  `contracts/case_management.py:411-480`).
- `get_original_source_content()` — raw H1-verified byte span for ONE item (`repository.py:1306-1372`).
- `get_conversation_context()` — bounded message window around ONE item (`repository.py:1396-1571`).

None aggregate across items.

## 4. Run ledger / workflows — all real

- **`run_ledger.py`**: `create_run`, `seed_stages`, `stage_start`, `stage_finish`, `set_gate`,
  `read_gate`, `skip_remaining_stages`, `set_trace_id`, `record_review_action`, `list_review_actions`,
  `finish_run`, `get_run`, `list_runs` — all real SQL against
  `ops.workflow_run`/`workflow_run_stage`/`workflow_run_review_action` (`:60-499`). Every
  `record_review_action` also writes the global audit ledger (`:301-325`).
- **`run_report.py`**: `build_run_report()` (`:53-157`) — pure projection/formatting, no DB I/O.
- **`workflows.py`**: two named workflows (`NAMED_WORKFLOWS`, `:925-928`) — `chat-transcript` and
  `sms-xml`, each ordered `custody → parse → store → knowledge` (`:588-679`, `:682-825`) on Agno
  `Workflow`/`Step`, with per-stage ledger instrumentation (`_wrap_step_for_ledger`, `:160-214`),
  supervised-mode HITL gates + abort handling (`_wrap_step_for_run_control`, `:232-321`, polling
  `gate_state` every 2s, 24h ceiling), and real substitution/fallback in `parse_step` — for sms-xml it
  explicitly PAUSES rather than silently substituting on primary-parser failure unless
  `allow_fallback=True` (`:775-798`, "NO SILENT SUBSTITUTION", owner mandate cited `:702`).
  Documented production bug + fix: a full retry that dedupes at custody used to silently report
  `docs_ingested=0`; `_store_step_impl` (`:385-480`) now auto-routes to reload-from-Postgres when
  `parent_run_id` + parent's knowledge stage failed, with `run_knowledge_from_store()` (`:1024-1203`)
  wired from `run_routes.py:263-333`. Raises `TypeError` when the wrong knowledge backend is passed to
  the evidence lane (`:526-527`).
- **`realization.py`**: "realization" = a discrete atom marking WHEN a fact was actually discovered,
  distinct from when the raw source became available (`:1-24`). Lifecycle `propose_realization()` →
  `approve_realizations()` → `supersede_realization()` (`:89-234`) over
  `working.realization_event`/`realization_event_record`. `propose_realization()` REJECTS a
  realization proposed before a linked record's `source_available_from` boundary — "rejecting, not
  clamping" (`:130-138`).
- **`derivation.py`**: `derive_walk()` (`:220-368`) builds `working.walk_run`/`walk_step`, each step's
  visible slice from `working.vw_horizon_atom` filtered `visible_from <= horizon_at` and
  `disclosure_tier <> 'hindsight'` for as-lived walks (`:191-212`). Every step chain-hashed
  (`_step_corpus_hash`) and attested to `ops.audit_ledger` in the same transaction (`:339-354`).
  `verify_reproducibility()` (`:375-453`) re-derives the chain and asserts byte-identical reproduction.

## 5. Native search

"Native" = the direct PostgreSQL-outbox → Weaviate pipeline that bypasses Agno's `Knowledge`
abstraction entirely.

- **`vector_projection.py`** — `NativeEvidenceProjector` (`:70-269`) is the write side: durable
  outbox-drain worker claiming jobs from `working.evidence_vector_projection_job`
  (`SELECT ... FOR UPDATE SKIP LOCKED`, `:126-143`), re-evaluating `working.source_available_from()`
  authoritatively at drain time (never trusting a stale handoff timestamp, `:1-8`), embedding, then
  `NativeEvidenceVectorStore.replace()`. Fully wired: `workflows.py:511-525` checks
  `isinstance(knowledge, NativeEvidenceProjector)` and raises `TypeError` for an Agno `Knowledge`
  object in the evidence lane — a hard architectural fence.
- **`native_activation.py`** — a resumable ONE-TIME cutover runbook (create collection → frozen-
  watermark enqueue → drain → reconcile → canaries → alias creation, `:72-282`), each phase idempotent
  via a JSON state file. Grepping `server/` and `scripts/` for `native_activation` finds **ZERO
  importers** — orphaned, exercised only by
  `tests/test_exec_native_evidence_cutover_contract.py`. Appears to be a deliberately manual runbook.
- **`native_evidence_search_routes.py`** — fully wired and live (see §2). The only search surface with
  pre-ranking horizon/case/tier filtering.

## 6. Stubs — zero

Grep for `STUB:|TODO|FIXME|NotImplementedError|not implemented|unimplemented` across all 25 files in
this lane: **zero hits.** Every traced code path is a complete implementation.

## Summary of gaps

1. **H2/H3 trust boundary** — H1 self-computed and cross-verified; H2/H3 stored trustingly at write
   time, re-derived only at read time via `/v1/verify/{sha256}`.
2. **No full-text search** — all content "search" is `ILIKE` substring or vector. No tsvector/GIN.
3. **`retrieval_axes` (0018) is orphaned** in this lane — one comment reference, no caller.
4. **No evidence-bundling/exhibit/production/Bates capability exists anywhere in this lane.** Nearest
   analog is per-item `CourtReadiness` + promotion, one item at a time.
5. **`native_activation.py` has no caller** in `server/` or `scripts/` — complete, tested, unwired.
6. **Two parallel search implementations coexist** — legacy Agno post-filtering vs native Weaviate
   pre-filtering. The write path has hard-fenced to native; the legacy read path is still live code.
7. **Zero stub markers** — this lane holds to the no-stubs standard consistently.
