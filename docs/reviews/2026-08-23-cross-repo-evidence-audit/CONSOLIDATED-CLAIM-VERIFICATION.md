# Consolidated Claim Verification — gaps.md + mcp-platform-edisc-gap-analysis

> _Byline: Claude Code · Opus 5 · 2026-08-23_
> Verification of every checkable claim in the two supplied gap-analysis documents, against the
> local repos. Read-only; nothing was edited.

## Method and confidence

- **Doc A** = `gaps.md` (85 lines, 3 references, no line-level citations).
- **Doc B** = `mcp-platform-edisc-gap-analysis-2026-08-23.md` (350 lines, commit-pinned, line-cited).
- Ten subagent lanes: five repo-analysis lanes (Agno ingest, Agno evidence/custody, Agno docs/ADR,
  Agno SQL, Legal-Workspace, SBV, reference corpus, cross-cutting search) and five claim-verification
  lanes (dial-stack, MCL factors, absence claims, SBV/Legal-Workspace, provenance/semantica).
- **Rule applied throughout:** a table, config key, or doc assertion is NOT proof a feature works.
  Every CONFIRMED verdict rests on code read on disk. Every "absent" verdict names the search terms
  used, so the negative is auditable.
- **Not done:** no live database was queried, no running service was probed. Deployment state is
  reported only where the repo itself makes an explicit claim. That limit matters — see §6.

**Bottom line up front:** Doc B is substantially reliable (23 of 26 checkable claims stand). Doc A is
half-reliable — its "dial-stack" inventory is real and valuable, but its claims about SBV, the schema,
and Semantica are wrong in ways that would misdirect work.

---

## 1. Headline corrections — where the documents are wrong

### 1.1 Doc A's SBV section is materially wrong (4 of 6 claims refuted)

Doc A: SBV "stores media as base64 BLOBs inside a general-purpose `messages` table with **no
evidentiary hash field, no chain-of-custody column**… there is no visible bridge connecting SBV's
SQLite output to the Go `internal/custody.go` hashing module."

That claim is self-contradicting (it names `custody.go` while asserting no custody) and it is refuted
by source:

- `internal/custody.go` delegates to a decoupled `pkg/custodyhash` package implementing H1/H2/H3.
- `ensureCustodyColumns()` — called from `InitDB`/`InitUserDB` — migrates a `messages.content_hash`
  column and an `imports` table (`file_hash`, `chain_hash`, `canon_version`) into **every** SQLite DB.
- On the Python side, `server/evidence/custody.py::reconcile_sbv_import()` (`:470-546`) exists, is
  real, independently recomputes H1, cross-checks it against SBV's reported H1, and only on match
  records SBV's H2/H3 as `evidence_hash` rows. On mismatch it records an `integrity_violation`
  custody event and persists nothing.
- It is wired: called from `server/tools/parsers/messaging/sbv_sms.py::_reconcile_custody`, inside the
  live `parse()` path, gated by an opt-in `SBV_CUSTODY_ENABLED` env var.

Also refuted: "Android-only" (SBV also imports iMessage, Facebook Messenger, Google Voice, email,
Google Chat) and "browsing tool, not a pipeline component."

**Consequence:** Doc A's Opportunity #3 — "Build the SBV-to-custody bridge" — is proposing work that
already exists. Acting on it would be rebuilding a working system.

### 1.2 Doc A cites the wrong schema and the wrong migration range

Doc A: "The live bitemporal schema (`sql/0001`–`0018`) implements `analysis.normalized_record`."

- There are **30** numbered migrations, not 18.
- Migration `0014_split_analysis_into_working_reference_ops.sql` **moved** the spine out of `analysis`
  into a new `working` schema, explicitly with "NO COMPATIBILITY VIEWS, NO ALIASES" (`0014:34-36`).
- The correct current name is **`working.normalized_record`**.

Anyone writing a query or a migration against `analysis.normalized_record` today gets a hard
"relation does not exist."

### 1.3 Doc A's "Semantica has zero runtime call sites" is wrong as stated

`server/analysis/semantica_worker.py` (325 lines, production code, ADR-0043 "governed extraction
worker") **directly imports** `server.vendored.semantica.semantica.semantic_extract`. That is a real
runtime call site in production code.

The accurate, narrower statement: nothing in the live ingestion or orchestration pipeline currently
calls `semantica_worker` — its only callers are `tests/test_semantica_phase1_worker.py` and
`scripts/run_semantica_fixture.py`. It is deliberately approval-gated and candidate-only, writing
solely to `working.extraction_run` / `candidate_entity` / `candidate_fact` / `candidate_event`.

**Consequence:** the integration is **half-done, not greenfield.** Doc A's framing ("wiring it in
would close most residual risk without writing new parser code") understates what is already built
and overstates how easy the remaining step is — see §1.4.

### 1.4 Semantica's format coverage is real but carries a heavy dependency tail

Doc A's "15 formats" is **exactly right** — counted: PDF, DOCX, PPTX, XLSX, HTML, TXT, JSON, CSV, XML,
YAML, Email, Image, Audio, Video, Code.

But: Semantica's own PPTX parser has an undeclared `python-pptx` dependency, and using it at all pulls
in Semantica's full torch/transformers/spacy core stack. On a CPU-only box (a standing constraint here)
that is a material cost, not a free win.

### 1.5 Doc B: `evals/cases.py` is NOT empty

Doc B P1-10 states "`evals/cases.py` remains empty." The file is **145 lines with 8 real `Case`
entries** wired to a live Agent. None are grounding/citation cases, so Doc B's *underlying* point
(no grounding evaluation corpus) survives — but the specific factual claim is false.

Root cause worth noting: `docs/DEBT.md:119` still asserts `CASES: tuple[Case, ...] = ()`. Doc B
inherited stale doc drift rather than reading the file. **The debt register is wrong and should be
corrected.**

### 1.6 Doc B: per-event factor linkage DOES exist (and is applied live)

Doc B P1-3 claims factors are attributes of behavior categories only, with "no per-link rationale,
supporting span, confidence, reviewer, statute-version, or supersession record."

Refuted in part: **`analysis.factor_citation`** (`docs/planning/forensic-db-reconciliation/migrations/0005_forensic_reconciliation.sql:1543-1560`)
links an individual `evidence_item_id` to a `factor`, with `supporting_text`, `relevance_explanation`,
and `review_status`. And `STATUS.md:17-18` records it as **"✅ APPLIED to live PG — 2026-06-30…
psql exit 0, zero errors."**

Genuinely missing from it: an explicit character-offset span column and a per-row taxonomy-version
column. So Doc B's *recommendation* is still directionally right, but it should be framed as
"extend `analysis.factor_citation`," not "build `analysis.claim_factor_link` from scratch."

### 1.7 Doc A's `systemRouter.ts` tier description is wrong

The tiered router is real (`TrinityRouter`), but its tiers are Postgres + Neo4j + Directus (T1) /
Chroma (T2) / PGVector (T3). **LanceDB appears nowhere**, and there is no promotion mechanism.
Doc A's "Chroma → Postgres → LanceDB → Neo4j promotion" is invented detail on top of a real file.

### 1.8 Doc A's Tether model location is wrong

The models are real — genuine HuggingFace Hub IDs in working inference code, 16+2 = 18 labels,
237 phrase entries. But **no `utilities/` directory exists anywhere in dial-stack.** The real code
sits in an unrelated archive at `TheBigOne_SAFE_COPY/04_Utilities/Tether/app.py`. The repo's own
`EVIDENCE_MERGE_MAP.md` asserts a path that does not exist on disk — pre-existing doc drift that Doc A
propagated.

### 1.9 Doc A's vLex claim rests on an unsupported premise

Doc A recommends extending the vLex verification-status taxonomy (`VERIFIED_PRIMARY`, `MIRROR_ONLY`,
`BLOCKED`, `CONFLICTED`) from legal citations to factual claims. Grep finds **that taxonomy nowhere in
the codebase** — not in Legal-Workspace, not in Agno. There is nothing to extend. The idea may be
sound, but it is net-new work, not an extension.

---

## 2. Confirmed critical findings — act on these

### 2.1 The MCL 722.23 (j)/(k) label inversion is REAL, live, and uncorrected

**This is the single highest-stakes confirmed defect across both documents.**

In `Agno-MCP-Platform/server/analysis/config/behavioral_patterns.json`:

| Line | Letter | `name` on disk | `description` on disk | Correct per MCL 722.23 |
|---|---|---|---|---|
| 60-61 | `j` | "Domestic Violence" ❌ | facilitate-relationship text ✅ | (j) = willingness to facilitate the other parent-child relationship |
| 65-66 | `k` | "Willingness to Facilitate Relationship" ❌ | domestic-violence text ✅ | (k) = domestic violence |

It is a clean swap of the two `name` fields only; both `description` fields are individually correct.
**Any consumer that renders `name` as the factor label — a report header, a UI badge, an exhibit table
— prints domestic violence and relationship-facilitation backwards.** Consumers reading `description`
are fine. That split is what makes it dangerous: internally-correct codes rendered with inverted
human labels.

All twelve letters (a)–(l) ARE present in the file, including (i).

**`patterns.py` cannot catch it.** `patterns.py:41` defines `MCL_LETTERS = set("abcdefghijkl")` and
`:210-212` validates only set membership. It never reads `corpus["mcl_factors"]` name/description
at all. Two already-valid letters with swapped names pass validation cleanly.

Doc A's claim 3 (that category mappings use the letters correctly) is **only PARTIAL**: `j` is used as
a broad catch-all across 13 of 16 populated negative modules; `k` appears on only 4, none a dedicated
DV category; and `threats_intimidation` — the module most literally about violence — is tagged `j,l`,
not `k`. So the mapping layer is *also* imprecise, independently of the name swap.

### 2.2 The guidance document `edisc.md` omits factor (i)

Confirmed: `edisc.md:92` asserts "twelve" factors; its table at `:94-106` lists only eleven —
a,b,c,d,e,f,g,h,j,k,l. **Factor (i) — the child's reasonable preference — is genuinely absent.**

Note the asymmetry: `edisc.md`'s own j/k *content* is correct per statute. The inversion in §2.1 and
the omission here are two different defects in two different files. Implementing the guidance verbatim
would produce an incomplete statutory taxonomy.

### 2.3 Held migrations — confirmed, and worse than Doc B states

Doc B P0-5 is confirmed and understated. Migrations **0026, 0027, 0028, 0029, and 0030** — five
consecutive files, one-sixth of the numbered chain — each carry an explicit
`HELD FOR OWNER … NOT APPLIED` banner in the file's own header.

Three consequences the documents do not draw out:

1. **A load-bearing contradiction is live.** `0018_retrieval_axes.sql:114` filters on
   `row_knowledge_time <= p_horizon`. But `0008:246-250` explicitly disowns `knowledge_time` as
   row-write time, warning "Do not use for 'when did you know' questions." The fix — `0028`, which
   repoints the predicate at `visible_from()`/`source_available_from()` — is **unapplied.** So the
   horizon predicate very likely running in production filters on a clock its own predecessor
   migration declared invalid.
2. **The numbered chain does not replay from empty, and has not since 0008** (`sql/README.md:32-104`).
   Worse, `0014` does not *fail* on a fresh replay — it **silently no-ops**, because every table-move
   is guarded by `IF EXISTS (... table_schema='analysis' ...)`, false on a fresh DB. A migration that
   commits successfully having moved nothing is the most dangerous failure shape available.
3. **There are two separate migration series.** `sql/NNNN_*.sql` (30 files, 0026-0030 held) and
   `docs/planning/forensic-db-reconciliation/migrations/NNNN_*.sql` — the latter including
   `0005_forensic_reconciliation.sql`, recorded as **applied live 2026-06-30**. Neither document
   noticed this. Any statement of the form "migration NNNN is/isn't applied" is ambiguous until the
   series is named.

### 2.4 Evidence bundling does not exist anywhere — confirmed across all three repos

This is the strongest cross-lane negative. Searched `bundle|exhibit|production set|bates|packet|
disclosure|manifest|concordance|opticon|.dat|.opt|custodian|privilege log` across all three repos:

- **Agno:** zero. `bundle` hits are English prose ("a conversation document bundles many records");
  `disclosure` is the bitemporal `disclosure_tier` concept; `manifest` is a Postgres↔Weaviate
  reconciliation artifact. The one real committed artifact is `analysis.vw_court_export`, a
  **read-only readiness view** that reports pass/fail for **one item at a time** and produces no
  document.
- **Legal-Workspace:** has a real exhibit *labeling* layer (`domain/exhibits.py`, `services/bates.py`)
  — but `bates.py` overlays a footer on owner-produced PDFs and explicitly returns
  `court_safe=False, exportable=False` with the docstring "Not Agno evidence… Not court-safe."
  **No code path exists from a search result to a package being built.**
- **SBV:** three disconnected pieces — a `window.print()` browser dialog with no hash/custody data on
  the page, a custody-stamped JSON/CSV corpus export covering only the legacy tables, and a genuinely
  good self-verifying JSON attestation report (`/api/imports/:id/report`) that is an API response, not
  a document.

`analysis.evidence_item.exhibit_number` exists as a live schema column, unique per case — with
**zero application code reading or writing it.** A dead column.

**Doc B's P1-6/P1-7/P1-8 are all confirmed.** No EDRM load files, no complete courtroom matrix
renderer, no stable exhibit-ID service.

### 2.5 Cross-corpus search is impossible by construction

Neither document states this plainly. Traced end to end:

| | Agno | Legal-Workspace | SBV |
|---|---|---|---|
| Bytes | Postgres + R2 via rclone FUSE | **none** — never stores evidence bytes | SQLite |
| FTS | `working.normalized_record.fts` GIN/tsvector — CREATED + POPULATED, **zero readers** | none | `messages_fts` FTS5 — CREATED, POPULATED, QUERIED (fully real) |
| Vector | Weaviate — real, but flag-gated (`NATIVE_EVIDENCE_ENABLED=false`) and walk-capability gated | none | none |

- **Agno↔Legal-Workspace:** the client implements exactly three calls — health, `/v1/matters`
  (identity only), `/v1/verify/{sha256}` (hash only). Its own docstring: *"Agno is truth; never clone
  evidence."* **There is no call to any search endpoint anywhere in Legal-Workspace.**
- **Legal-Workspace↔SBV:** no connection at all.
- No component fans a query across more than one store.

So the question "find every document mentioning X and bundle it as an exhibit" fails at **both**
steps, in **all three** repos. Getting it working needs new integration code in at least two of three
— not a config flip.

### 2.6 A live full-text index with no readers

`working.normalized_record.fts` (GIN/tsvector) is created and auto-populated by trigger, and **nothing
in the Python tree queries it.** Meanwhile the actual record search endpoint,
`GET /v1/records?q=…`, runs `WHERE nr.content ILIKE :q` (`inspect_routes.py:262`) — an unindexed
substring scan. Entity search (`entity_routes.py:73-81`) does the same.

This is the cheapest real win in the whole analysis: the index already exists and is already current.

---

## 3. Findings neither document reported

These came out of the repo lanes, not from checking either doc. Several are more actionable than the
documents' own recommendations.

### 3.1 DOCX / PPTX / XLSX / HTML ingest fails on a default install — silently undocumented

`server/ingest/service.py` routes `.docx/.pptx/.xlsx/.html/.htm` to `_extract_document` (`:143`),
which registers only `documents.extract-docling` for those suffixes (`:155-158` adds the
`documents.extract-text` fallback for `.pdf` **only**).

`docling` is gated behind the `document-ai` extra (`pyproject.toml:87`) and is **absent from
`requirements.txt`**. With docling unimported the extractor list is empty, `_extract_document:180-182`
raises `ValueError`, and the whole ingest fails with receipt status `"failed"`.

There is **no `STUB:` marker and no `docs/URGENT-TODO.md` entry** for this — a direct violation of the
repo's own mandate at `server/contracts/AGENTS.md:60-61`. Doc B's P1-5 gets close (OCR/VLM deferred)
but misses that four common office formats are dead on arrival today.

Related: PDF **OCR** is also an optional `ocr` extra not in `requirements.txt` — scanned/image-only
PDFs do not OCR by default.

### 3.2 The evidence lane cannot ingest PDFs or DOCX at all

`service.py:197` skips the document-extraction branch entirely when `lane is evidence`. Combined with
`_whole_file_text` being forbidden for evidence (`:130-131`, ADR-0044) and two named parsers being
blocked (`:29,232-233`), the **evidence lane can only accept chat/transcript/Go-registry formats.**
A scanned court order or a PDF exhibit has no ingest path into the evidence lane.

### 3.3 Three parallel, non-converging ingest paths — and the good one is unreachable

1. `server/ingest/service.py::ingest_file` — the only path wired to live HTTP (`/v1/ingest`).
   Flat records, hardcoded `RecursiveChunker(1500 chars)`, no lane classification.
2. `server/analysis/context_chat_ingest.py::ingest_chat_file` — the mature one: conversation/message
   modeling, message-boundary-preserving semantic chunking, multi-label lane classification,
   per-lane Weaviate projection, Graphiti drain. **Reachable only from a CLI script and tests.**
3. `server/core/session.py::create_knowledge` — Agno's own `Knowledge.add_content` surface, the only
   consumer of the lane-aware `chunking_policy`.

Plus a fourth destination schema (`working.context_archive` / `context_asset`) reachable only via the
same CLI path.

**A user uploading a ChatGPT or Claude export through the documented, authenticated, live HTTP API
gets flat generic records** — no conversation grouping, no role-aware boundaries, no lane
classification, no per-lane projection. All the sophistication is bypassed.

### 3.4 Append-only enforcement is far less uniform than the docs imply

| Object | Actually enforced? |
|---|---|
| `evidence.evidence_hash.digest` correctness | **No.** Only `octet_length(digest)=32`. Nothing verifies the hash against source bytes. |
| `evidence.evidence_hash` append-only | **No trigger exists for this table at all.** |
| `evidence.raw_*` (6 tables) append-only | **No, by default** — `raw_no_mutate()` is gated on `app.evidence_live`, off unless armed. |
| derived-table write guard | **No, by default** — gated on `app.enforce_derived_guard`. |
| `evidence.source` immutability | **Yes** — but out-of-band, only in `bootstrap/schema_baseline.sql:782-807`. |
| `evidence.custody_event` hash chain | **Yes, DB-computed trigger** — the most rigorous chain in the schema, and **entirely invisible if you read only the numbered migrations.** |
| `working.source_provenance`, `review_decision`, `promotion`, `ops.audit_ledger` | **Yes, real, unconditional** (0017/0020/0025). |

And `0029_pass_grants.sql:11-19` documents its own inertness: the app connects as role `ai`, a
**superuser** (verified live 2026-08-14), which bypasses all grants and RLS. The grants are a schema
contract, not an enforcing guard.

### 3.5 Legal-Workspace has no document upload pipeline at all

Grepped all of `api/` for upload/UploadFile/multipart/s3/boto3 — **zero matches.** The "Document
viewer" (`web/src/components/PdfPane.tsx:14-20`) reads a file with `<input type="file">` and renders
it via a browser-local `URL.createObjectURL()` blob in an iframe. **It never calls `fetch()`.** The
only real ingestion path is `POST /v1/legal-source-packages:import`, which accepts pre-hashed JSON,
not files.

Also: the Postgres bootstrap has never been applied to any cluster; the SQLite "port" is a 1-table
stub; the actual 24-table runtime schema comes from SQLAlchemy `create_all()` and has already
diverged from the Postgres SQL.

### 3.6 Orphaned and dead code

- **`retrieval_axes` (migration 0018)** — grepping all of `server/` finds exactly one hit, a comment in
  `server/core/audit.py:361`. **No caller.**
- **`native_activation.py`** — complete, tested, resumable Weaviate cutover runbook. Grepping
  `server/` and `scripts/` finds **zero importers.** Exercised only by a contract test.
- **Root `iceberg`** — not a directory. `file` reports "DuckDB database file, version 64", 12,288
  bytes, `SHOW TABLES` returns `[]`. An empty stray DuckDB file with a misleading name.
- **`scripts.zip` (134KB) / `server/tools.zip` (408KB)** — same timestamp (2026-08-09 15:53), not
  referenced anywhere in `docs/`, sitting alongside the live unzipped directories. Unexplained.
- **`to_be_deleted/`** — empty.

### 3.7 Two parallel search implementations coexist

Legacy Agno `evidence_search()` (Python **post**-filtering after 5× over-fetch) vs native
`native_evidence_search()` (true Weaviate **pre**-filtering). The evidence *write* path has already
hard-fenced to native — `workflows.py:526-527` raises `TypeError` if an Agno `Knowledge` object is
passed for the evidence lane — but the legacy *read* path is still live code.

---

## 4. Full claim register — Doc A (`gaps.md`)

| # | Claim | Verdict | Note |
|---|---|---|---|
| A1 | dial-stack donor corpus exists | **CONFIRMED** | Real git-tracked project at `dev-resources/Archives/dial-stack/` |
| A2 | 11 OCR/doc engines | **CONFIRMED** | All 11 files in `document_intelligence/engines/` |
| A3 | `DocumentEngine`/`EngineRegistry` w/ cost-tier + locality fallback | **CONFIRMED** | `engine_registry.py` |
| A4 | 5 engines credential-free | **CONFIRMED** | All 5 declare `FREE`/`LOCAL` |
| A5 | `sqlite_wal_parser.py`, not ported | **CONFIRMED** | 575 lines; zero hits in live repo |
| A6 | `retrieval.ts` BM25 + hybrid + spans | **CONFIRMED** | All 4 functions present |
| A7 | Chroma+FAISS dual store; separate Qdrant/pgvector/Chroma TTL store | **CONFIRMED** | Two distinct files |
| A8 | ripgrep/ugrep forensic router + timeline | **CONFIRMED** | `text-miner.ts` |
| A9 | `systemRouter.ts` Chroma→PG→LanceDB→Neo4j promotion | **REFUTED** | Real `TrinityRouter`, but tiers are PG+Neo4j+Directus / Chroma / PGVector. **No LanceDB. No promotion.** |
| A10 | ~100-tool MCP catalog, unwrapped | **CONFIRMED** | 72 + 32 ≈ 104; none in live repo |
| A11 | Ed25519 custody + `verify_custody_chain`, not ported | **CONFIRMED** | SQL migration has it; live `custody.py` has zero Ed25519 refs |
| A12 | Tether models in dial-stack `utilities/` | **PARTIAL** | Models real (18 labels, 237 phrases); **location false** — no `utilities/` in dial-stack |
| A13 | `user_detection.py` is a placeholder | **CONFIRMED** | All 3 functions return hardcoded empty/zero |
| A14 | `behavior-service.ts` = 4 hardcoded regexes | **CONFIRMED** | Exactly 4 in `DEFAULT_PATTERNS` |
| A15 | Semantica = most complete parser, 15 formats | **CONFIRMED** | Counted exactly 15 |
| A16 | Semantica has zero runtime call sites | **REFUTED as stated** | `semantica_worker.py` is production code importing it; but no *pipeline* caller |
| A17 | SBV: base64 BLOBs, no hash/custody column | **PARTIAL/REFUTED** | Media-in-BLOB true (binary, not base64); no-hash claim **refuted** |
| A18 | SBV: no export path to normalized_record | **REFUTED** | Exports to `working.normalized_record`/`context_record` |
| A19 | SBV: no bridge to `custody.go` | **REFUTED** | Self-contradicting; wired end to end |
| A20 | SBV: 100k-message limit documented | **CONFIRMED** | `README.md:126` — a per-conversation *display* limit |
| A21 | SBV: Android-only | **REFUTED** | Also iMessage, FB Messenger, Google Voice, email, Google Chat |
| A22 | SBV: browsing tool, not pipeline component | **REFUTED** | Wired into automated ingest |
| A23 | `sql/0001-0018` implements `analysis.normalized_record` | **REFUTED** | 30 migrations; it's `working.normalized_record` since 0014 |
| A24 | `0006_behavior_seed.sql`, 9 iterations, "DRAFT / paper-only" | **CONFIRMED** | All parts, verbatim |
| A25 | Legal-Workspace has `eyecite_adapter.py` + `citation_gate.py` | **CONFIRMED** | |
| A26 | LW README says "Do not treat this as court-safe" | **CONFIRMED** | Verbatim, `README.md:17` |
| A27 | LW `PRIV` = "keyword-only hypothesized markers" | **CONFIRMED** | Near-verbatim |
| A28 | LW has Bates + redaction + DOCX export | **CONFIRMED** | All three exist |
| A29 | LW has no 8/9-column Best-Interest matrix export | **CONFIRMED** | |
| A30 | vLex taxonomy not extended to factual claims | **REFUTED (premise)** | The taxonomy exists **nowhere** in the codebase — nothing to extend |
| A31 | No live bridge SBV → custody schema | **REFUTED** | See A19 |
| A32 | LW explicitly disclaims court-safety | **CONFIRMED** | |

**Doc A scorecard:** 19 confirmed, 8 refuted, 2 partial, 3 premise-level errors.

## 5. Full claim register — Doc B (`mcp-platform-edisc-gap-analysis`)

| # | Claim | Verdict | Note |
|---|---|---|---|
| B0 | Reviewed commit `1e38d3a…` on `main`, 2026-08-18 | **CONFIRMED** | Exists locally; HEAD is exactly equal. Caveat: working tree dirty |
| B1 | P0-1 (j)/(k) name inversion | **CONFIRMED** | See §2.1. Real, live, uncorrected |
| B2 | P0-1 category mappings use letters correctly | **PARTIAL** | `j` is a 13-of-16 catch-all; `threats_intimidation` tagged `j,l` not `k` |
| B3 | P0-2 `edisc.md` omits factor (i) | **CONFIRMED** | `:92` says twelve; `:94-106` lists eleven |
| B4 | P0-3 no RAG grounding validation system | **CONFIRMED ABSENT** | Vocabulary/tables exist only in the disclaimed DRAFT |
| B5 | P0-4 court release is read-only, no release mutation | **CONFIRMED** | `BUILD_PLAN.md` quotes matched at cited lines |
| B6 | P0-5 0026-0029 held, 0030 unapplied | **CONFIRMED** | And understated — see §2.3 |
| B7 | P1-1 no `context_thread_id`/`parent_thread_id` | **CONFIRMED ABSENT** | `projection_kind`/`parent_span_id` exist but mean unrelated things |
| B8 | P1-2 no deviation cutoff / overlap dedupe / diversity / packing | **CONFIRMED ABSENT** | Both search paths apply filters + bare `limit` |
| B9 | P1-3 factors not a governed per-event relation | **PARTIAL — largely REFUTED** | `analysis.factor_citation` exists **and is applied live**; missing only span + version columns |
| B10 | P1-3 contradiction rules "UNHOMED" | **CONFIRMED** | `patterns.py:17-19`, verbatim |
| B11 | P1-3 newest ontology migration not applied | **CONFIRMED** | `0008_behavior_seed_pattern_analyzer.sql:10` |
| B12 | P1-3 some modules marked `needs_review` | **CONFIRMED** | Six modules, all with empty `mcl_factors` |
| B13 | P1-4 behavioral synthesis not calibrated | **CONFIRMED** | Debt register concurs |
| B14 | P1-5 OCR/VLM + forensic metadata not production-ready | **PARTIAL** | Real tiered OCR exists (native→Tesseract→optional Docling) but captures only `{method, ocr_used, char_count, low_confidence}`, **not persisted** into `artifact_metadata`, which has no OCR columns |
| B15 | P1-6 no EDRM/load-file exports | **CONFIRMED ABSENT** | Both repos |
| B16 | P1-7 no complete courtroom matrix renderer | **CONFIRMED** | |
| B17 | P1-8 no stable exhibit ID service | **PARTIAL** | `analysis.evidence_item.exhibit_number` exists as a **dead column** — zero readers/writers |
| B18 | P1-9 no closed-world generation contract | **CONFIRMED ABSENT** | No allowed-span manifest; agent instructions have zero citation language |
| B19 | P1-10 `evals/cases.py` empty | **REFUTED** | 145 lines, 8 real cases. Underlying point survives; the fact does not |
| B20 | P2-1 no corpus batch manifest | **PARTIAL** | `analysis.extraction_batch` lacks windows/bounds/overlap but **does** provide rerun identity via `input_hash` + status enum |
| B21 | P2-2 no factual-verification vocabulary | **CONFIRMED** | |
| B22 | P2-3 no automated revalidation on version change | **CONFIRMED** | Only a manual, unapplied `status='invalidated'` enum |
| B23 | P2-3 projection metadata records chunker/model/version/hashes | **CONFIRMED** | All present in `EvidenceVectorDocument`, plus extra hash fields |
| B24 | P2-4 backups remain planned | **CONFIRMED** | `DEBT.md:176` says "planned"; `backup_ovhdata_hot.sh` is a one-time local snapshot, skips Neo4j, **no R2 upload step at all** |
| B25 | P2-5 fresh-schema reproducibility open | **CONFIRMED** | And worse — 0014 silently no-ops rather than failing |
| B26 | P2-6 no NSRL/de-NISTing | **CONFIRMED ABSENT** | 2 grep hits, both false positives |
| B27 | P2-7 existence/pinpoint/characterization not separate | **CONFIRMED** | |
| B28 | P2-8 no machine-readable capability register | **CONFIRMED** | `TODO-SNAPSHOT-*.json` are session TODO lists, not deployment state |

**Doc B scorecard:** 23 confirmed, 1 refuted, 5 partial. Substantially reliable.

---

## 6. What neither document could establish — and neither should have claimed

Both documents are static source audits. Neither queried a live database or probed a running service.
Therefore **no statement about what is actually deployed can be verified from either document, or
from this one.**

The repo's own most current status statement (`docs/MASTER-TODO-2026-08-18.md`) is blunt:
**"No item is classified DONE+LIVE VERIFIED."** Custody, ingest, parsers, the normalized spine, the
evidence desk, human review and the Workbench/API are all "IMPLEMENTED LOCAL ONLY"; deployment is
"BLOCKED."

Doc B's P0-5 recommendation — treat *merged*, *migration applied*, *service deployed*, *projection
backfilled*, and *observed end-to-end* as five independent states in a machine-readable ledger — is
the correct response, and it is the one recommendation in either document I would raise in priority.

---

## 7. Reconciled priority list

Ordered by (confirmed-real × consequence × how cheap the fix is). Doc A's own priority list is not
reproduced because three of its top seven items rest on refuted claims.

**Tier 0 — correctness defects, fix before processing more evidence**

1. **Fix the (j)/(k) name inversion** in `behavioral_patterns.json`. Two string swaps. Then add a
   contract test asserting letter↔name↔description against official MCL 722.23 text, since
   `patterns.py` structurally cannot catch this class of error.
2. **Add factor (i)** to any `edisc.md`-derived spec or prompt, and stop forcing 1:1 event→factor —
   support `0..n` links plus `unmapped/review_required`.
3. **Correct `DEBT.md:119`** (`evals/cases.py` is not empty) and the `EVIDENCE_MERGE_MAP.md` Tether
   path. Doc drift propagated into both of these gap analyses; that is the actual cost of stale docs.

**Tier 1 — cheap wins on already-built machinery**

4. **Point record search at the existing FTS index.** `working.normalized_record.fts` is created,
   populated, and current, with zero readers, while `/v1/records?q=` does `ILIKE`. This is a one-query
   change.
5. **Add `docling` to `requirements.txt`** (or register a fallback extractor for the four office
   formats) and file the `STUB:` + `URGENT-TODO.md` entry the repo's own rules require. Four common
   document types currently fail ingest silently.
6. **Expose the mature chat ingest path over HTTP.** `context_chat_ingest.ingest_chat_file` already
   does conversation modeling, lane classification, and per-lane projection — it just has no route.

**Tier 2 — the real defensibility gaps (Doc B is right about all of these)**

7. Resolve the owner holds on 0026–0030 in order; prove fresh-schema build from empty; publish the
   five-state deployment ledger. Until this lands, nothing else can be claimed as working.
8. Build the citation-grounding layer: addressable span IDs, closed-world generation, and separate
   existence / pinpoint / characterization outcomes.
9. Build evidence bundling. It genuinely does not exist in any of the three repos. It most naturally
   belongs next to Legal-Workspace's existing exhibit/Bates machinery — but that requires first giving
   Legal-Workspace a search call into Agno, which it deliberately does not have today.
10. Extend `analysis.factor_citation` with span offsets and a taxonomy-version column — **extend, do
    not rebuild.**

**Tier 3 — inventoried but unwrapped (Doc A's genuine contribution)**

11. The dial-stack document-intelligence registry (11 engines, 5 credential-free) and Semantica
    (15 formats) are both real and both unwrapped. Weigh Semantica's torch/transformers/spacy tail
    against the CPU-only constraint before committing.
12. Port the Ed25519 signed custody chain — confirmed present in dial-stack, confirmed absent from
    live `custody.py`, which is SHA-256 integrity only. This matters if custody is ever challenged on
    authenticity rather than integrity grounds.

**Do NOT do**

- Do not "build the SBV-to-custody bridge" (A19/A31 refuted — it exists and is wired).
- Do not rename anything to `analysis.normalized_record` (A23 refuted).
- Do not plan to "extend the vLex taxonomy" as if it were present (A30 — it is nowhere in the code).
