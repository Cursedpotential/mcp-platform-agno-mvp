# Verification: Gap-Analysis Absence Claims (10 items)

> Byline: Claude Code · Sonnet 5 · 2026-08-23
> Repo A: `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform`
> Repo B: `E:/AI_Workspace/Projects/the-platform-workspace/Legal-Workspace`
> Method: `Grep`/`grep` across `server/`, `sql/`, `scripts/`, `tests/`, `docs/`, `workbench/`, plus direct file reads of the implicated modules. Search terms are quoted per-claim below so each negative is auditable. `docs/planning/**` and `docs/wiki/**` are treated as design/proposal material, not implementation, unless stated otherwise.

---

## Claim 1 — No RAG citation-grounding validation system

**Verdict: CONFIRMED ABSENT (from implementation). Exists only as an unratified design draft.**

Searched (case-insensitive): `CONFIRMED_GROUNDED|HALLUCINATED|MISGROUNDED|AMBIGUOUS`, `grounding|groundedness|elusion|hallucinat|stratified|citation_check|provenance_check`, and the exact table names `generated_claim|claim_citation|grounding_check|validation_population|validation_sample|validation_release_gate`.

- `sql/` (30 real migration files): **zero matches** for any of the above.
- `server/` (real application code): **zero matches** for the vocabulary/tables; the only incidental hit was the string `"you're delusional"` in `server/analysis/config/behavioral_patterns.json` (an abuse-language detector phrase list — unrelated).
- The grounding vocabulary (`CONFIRMED_GROUNDED`, `elusion`, `stratified`, per-stratum rates, etc.) and the named tables appear **only** in `docs/planning/forensic-db-architecture/` (a 21-section design draft) — specifically `sections/13-confidence-review.md` and its siblings. That draft's own header states:
  > `## ⚠️ DRAFT — HUMAN-IN-THE-LOOP REVIEW REQUIRED ⚠️`
  > `**This is a DRAFT architecture for human review. It is NOT a ratified specification and NOT a court-facing artifact.**`
  and explicitly subordinates itself to the SSOT docs (`PROJECT_CANON.md` + ADRs).
- No table named `generated_claim`, `claim_citation`, `grounding_check`, `validation_population`, `validation_sample`, or `validation_release_gate` exists in `sql/bootstrap/schema_baseline.sql` (the live schema dump) or any numbered migration.

**Conclusion**: the claim is accurate. A citation-grounding validation vocabulary and pipeline were *designed* in a draft document but never implemented — not CREATED, not POPULATED, not QUERIED anywhere in real code or SQL.

---

## Claim 2 — No `context_thread_id` / `parent_thread_id` dual-granularity retrieval

**Verdict: CONFIRMED ABSENT. What exists instead is single-granularity chunk embedding with conversation/record linkage — described precisely below.**

Searched: `context_thread_id|parent_thread_id|context_thread|parent_thread|parent_span|projection_kind|atomic_fact|contextual_exchange|context_window`.

- No `context_thread_id`, `parent_thread_id`, `atomic_fact`, or `contextual_exchange` anywhere in `sql/`, `server/`, or `workbench/`.
- `projection_kind` **does** exist (`sql/0026_realization_event.sql`, `server/core/evidence_vector_store.py`, `server/evidence/vector_projection.py`, `server/evidence/native_activation.py`) but it means something unrelated: it is a two-value routing/decision-gate label (`first_party` vs `acquired_third_party`) used for message-provenance approval, not an embedding-granularity axis.
- `parent_span_id` exists only in `sql/bootstrap/schema_baseline.sql` line ~3146 as part of `ai.agno_spans` — Agno's own OpenTelemetry-style execution-tracing table (agent run spans), unrelated to citation/chunk parenting.

**What DOES exist for chunk/parent linkage** (read directly from `server/core/evidence_vector_store.py` lines 33–121 and `sql/0024_chat_conversation_and_message.sql`):
- One embedding per `chunk_id` (`EVIDENCE_VECTOR_COLLECTION` / `EvidenceChunkV1` in Weaviate), each chunk carrying `normalized_record_id` (parent record FK) and an optional `conversation_id` (parent conversation FK) — i.e., a single-vector-per-chunk scheme with simple foreign-key parentage, not a stable cross-referenceable "thread id" and not a second, context-enriched embedding alongside an isolated atomic-fact one.
- `sql/0024_chat_conversation_and_message.sql` defines `working.chat_chunk` (`conversation_id`, `chunk_index`), `working.chat_chunk_message` (chunk↔message join), and `working.chat_chunk_projection` (chunk↔sink/lane), which is a conventional one-chunk-one-embedding chunking/projection scheme, not dual-granularity retrieval.

**Conclusion**: claim is accurate as stated. The delta from what's asked (dual embeddings keyed by a stable context-thread id) to what exists (single embedding per chunk + record/conversation FKs) is real and precisely as above — this is not "basically the same thing under another name."

---

## Claim 3 — No relative-score cutoff / no overlap-dedupe / no diversity / no budget packing in native evidence search

**Verdict: CONFIRMED ABSENT. Read the full `search()` method and its only caller.**

`server/core/evidence_vector_store.py::NativeEvidenceVectorStore.search()` (lines 344–408, full method read):
- Builds an eligibility filter (`case_id`, `source_availability_complete`, `authority_state='active'`, `disclosure_tier` set, optional `source_kind`/`projection_kind`, optional `horizon` cutoff).
- Calls Weaviate `near_vector` or `hybrid` with that filter and a bare `limit` (default 10).
- Requests `MetadataQuery(distance=True, score=True, explain_score=True)` — i.e., raw distance/score is returned to the caller — but nothing in this method or its caller computes a threshold relative to the top hit, drops overlapping/nested windows, enforces source/custodian diversity, or does token-budget packing.

`server/evidence/retrieval.py` (full file read):
- `native_evidence_search()` calls `store.search(...)` and passes the response straight through (`documents = list(response.objects)`); no post-processing beyond an audit-log write.
- `evidence_search()` (the older/legacy Agno-`Knowledge`-backed path) over-fetches by a fixed `_OVERFETCH = 5` multiplier (capped at `_MAX_FETCH = 100`), then applies only two gates — `case_id` match and `visible_from <= horizon` — and finally truncates with `visible = kept[:limit]`. That is a hard slice, not a score-relative cutoff, and there is no dedupe/diversity/packing step here either.

**Conclusion**: claim is accurate. Both retrieval seams apply eligibility filtering + a bare `limit`; neither computes a relative-score deviation cutoff, overlap/parent-child dedupe, source diversity, or token-budget packing.

---

## Claim 4 — No EDRM / load-file production exports

**Verdict: CONFIRMED ABSENT in both repos. Legal-Workspace has Bates PDF stamping only — precisely scoped below, not an EDRM production capability.**

Searched: `Concordance|Opticon|load[_ -]?file|\.opt\b|\.lfp\b|EDRM|bates|exhibit|production[_ ]set|custodian|native file export|privilege log` (both repos), plus the literal DAT delimiter bytes `\x14 \xfe \xae` (no hits in either repo — checked via the same corpus scan, no file contains those control-byte sequences in a load-file context).

- **Zero** matches anywhere for `Concordance`, `Opticon`, `.opt`, `.lfp`, `EDRM`, or `.dat`-as-load-file in either repo's real code/SQL. The only "privilege log" / "exhibit-list" / "custodian" hits are Markdown **document templates** under `Legal-Workspace/docs/planning/original-context/skills/CURATED-custodyguide_v1/**` — attorney-facing drafting templates (`privilege-log.md`, `exhibit-list.md`), not export code, not wired to any database or file-production pipeline.
- **What Bates capability actually exists** (`Legal-Workspace/api/legal_workspace/services/bates.py`, full file read):
  - `stamp_bates_pdf()` uses `pypdf`/`pikepdf` to overlay a text footer (`{prefix}-{n:06d}`) onto every page of an **owner-produced PDF**.
  - The module docstring and the returned `BatesStampResult` are explicit about scope: `"Not Agno evidence."`, `"No evidence bytes."`, `"Not court-safe."`, and the result object hard-codes `court_safe: bool = False`, `exportable: bool = False`.
  - `legal_workspace/domain/exhibits.py::next_bates_number()` generates the next `{PREFIX}-{n:06d}` in a per-matter sequence, but only from a list the caller supplies (`existing: list[str]`) — there is no persistent Bates ledger table, no case-wide production-set concept, and Bates numbers on `ExhibitAnnotation`/`ExhibitCandidate` are explicitly **owner-entered free text** (`bates_number: str = ""`), "Owner-triggered sequence. Never auto-seeded."
- No custodian tracking, no native-file export, no privilege-log generation code, no production-set concept (a named, exportable batch of documents with a load file) anywhere in either repo.

**Conclusion**: claim is accurate. What exists is a single-PDF Bates-stamping overlay utility explicitly marked not court-safe/not exportable — a visual page-numbering convenience, not any part of an EDRM/Concordance/Opticon load-file production workflow (no `.dat`, no `.opt`, no image cross-reference file, no custodian/production-set metadata).

---

## Claim 5 — No stable human-usable exhibit ID service (e.g. `EX-2021-04-TEXT-01`)

**Verdict: PARTIAL — a schema column exists but is dead (created, never populated/queried); the Legal-Workspace Bates generator is the closest real thing and is scoped narrowly (see Claim 4).**

Searched: `exhibit_id|exhibit_number|bates|document_id|control_number|begdoc|enddoc` in both repos' `server/`, `sql/`, `scripts/`, `workbench/`, `api/`.

- **Agno-MCP-Platform**: `sql/bootstrap/schema_baseline.sql` defines `analysis.evidence_item.exhibit_number TEXT` (nullable) with a `UNIQUE (case_id, exhibit_number)` constraint (lines ~3430, ~8122–8126). This is a real, live-schema column — **CREATED**. Grepping `server/`, `scripts/`, `workbench/` for `exhibit_number` in application code returns **zero hits** — nothing writes to it, nothing reads it, no ID-generation function targets it. It is schema-only, unused by any code path — **not POPULATED, not QUERIED**.
- No `EX-2021-04-TEXT-01`-style generator, no `begdoc`/`enddoc`/`control_number` concept, anywhere in either repo.
- **Legal-Workspace** has the only working ID-generation logic — `next_bates_number()` (see Claim 4) — but it produces `{PREFIX}-{NNNNNN}` (e.g. `GENESEE-000001`), not a structured `EX-<year>-<month>-<type>-<seq>` exhibit ID, has no persistence layer (caller supplies `existing` values each call), and is scoped to owner-produced PDFs outside the Agno evidence system ("Not Agno evidence").

**Conclusion**: the claim is essentially accurate — there is no stable, system-generated, human-usable exhibit ID service distinct from internal UUIDs/content hashes. The one delta worth flagging precisely: `analysis.evidence_item.exhibit_number` is a real (if inert) schema slot that *could* hold such an ID; it currently does not.

---

## Claim 6 — No closed-world generation contract (span-ID citation, rejection of unknown sources)

**Verdict: CONFIRMED ABSENT.**

Searched: `retrieval manifest|allowed_span|span_id|citation validation|reject unknown|closed[- ]world`.

- `allowed_span`, `retrieval_manifest`, "reject unknown" pattern: **zero hits** anywhere in either repo.
- `span_id` appears exactly once as a real schema field: `sql/bootstrap/schema_baseline.sql` → `ai.agno_spans (span_id, parent_span_id, ...)`, with `PRIMARY KEY (span_id)` and an index on `parent_span_id`. This is Agno's built-in agent-execution/observability tracing table (OpenTelemetry-style run spans for debugging agent calls) — it has nothing to do with citation spans, retrieved-passage addressing, or generation constraints.
- `server/agents/instructions.py` (the file most likely to carry a prompt-level "cite only retrieved spans" instruction) has **zero** matches for `grounding`, `citation`, `cite`, or `hallucinat`.
- No backend parser/validator anywhere rejects a model response for citing an unknown/unaddressable source or span ID — there is no such validator to find.

**Conclusion**: claim is accurate. Nothing constrains generation to retrieved, addressable spans, and nothing rejects citations to unknown sources — at the prompt-instruction level or the backend-validation level.

---

## Claim 7 — `evals/cases.py` is empty

**Verdict: FOUND FALSE — the file is not empty.**

`evals/` directory listing and line counts:
```
__init__.py     0 lines
__main__.py   267 lines
cases.py      145 lines
dotenv.py      32 lines
fixtures/     (present)
```

`evals/cases.py` (full file read) defines a `Case` dataclass (judge + reliability-check fields) and a `CASES: tuple[Case, ...]` of **8 real cases** — 3 classification tests, 3 sentiment tests, 1 multi-provider comparison test, 1 batch-classification test — each wired to a live `Agent` instance (`OpenAILike(id="glm-5.1", ...)`) with `criteria` strings for LLM-judge scoring.

Important nuance for accuracy: the file's own docstring says *"The skeleton's web_search/code_search cases were removed... Cases for the v8.1 agents (routing, governance, boundaries) land with the evals phase — see docs/planning/BUILD_TODO.md Phase 12."* — i.e., the 8 cases present are generic classification/sentiment smoke tests, and there are **no eval cases here that test RAG citation-grounding, span-ID rejection, or any of the other claims 1/6 gaps.** So while the literal claim ("empty") is false, the *substance* — no grounding/citation eval coverage — is consistent with the rest of this report.

**Conclusion**: claim as literally stated is **FALSE**; `evals/cases.py` has 145 lines and 8 working cases. If the gap-analysis document meant "empty of grounding-relevant cases," that narrower claim would be accurate, but "empty" is not.

---

## Claim 8 — No NSRL / de-NISTing

**Verdict: CONFIRMED ABSENT.**

Searched: `NSRL|de-nist|denist|de_nist|known-file filter|hashset` across the whole Agno-MCP-Platform tree.

- Only 2 raw hits, both false positives on inspection: a base64 blob inside `workbench/web/package-lock.json` (an npm integrity hash string that happens to contain the substring) and binary image data inside a test fixture `vendored/sbv/backend/testdata/sample_backup.xml`. Neither is related to NSRL, de-NISTing, or hash-set filtering.
- No known-file-filter / NSRL-hashset logic anywhere in `server/`, `sql/`, or `scripts/`.

**Conclusion**: claim is accurate — no NSRL/de-NIST capability exists.

---

## Claim 9 — No OCR production pipeline with receipts

**Verdict: PARTIAL — a tiered OCR pipeline exists and reports lightweight stats, but none of the specific receipt fields claimed (engine+version, page confidence, bounding boxes, EXIF, access-time preservation, append-only OCR-correction) are captured or persisted.**

- `server/tools/extractors/extract_text.py` (full file read) implements a real 2-tier pipeline: native text layer (`pypdf` → `pdfplumber` fallback) → Tesseract OCR fallback (`pytesseract` + `pdf2image`/`PIL`) for sparse/scanned PDFs and images. It returns `stats: {method, ocr_used, page_count, char_count, low_confidence, ext}`.
- `server/tools/extractors/docling_extract.py` (full file read) adds a third, optional tier (IBM Docling, structured layout+table+OCR) returning `stats: {method: "docling", ocr_used, page_count, char_count, low_confidence, structured}`.
- **What's missing, confirmed by reading both files line-by-line:**
  - No recorded OCR **engine version** (e.g., Tesseract binary version, Docling model version) — only the string `"tesseract"`/`"docling"`/`"pypdf"`/`"pdfplumber"` as `method`.
  - No **page-level confidence** score (Tesseract can emit per-word confidence via `image_to_data`, but this code calls `image_to_string` only — confidence is never captured).
  - No **bounding boxes** anywhere.
  - No **EXIF extraction** — neither extractor reads or stores EXIF metadata.
  - No **access-time preservation** — not addressed by these modules.
  - No **OCR correction as append-only supersession** workflow specific to OCR. A *generic* append-only supersession primitive does exist at the raw-derivation layer (`sql/0009_raw_layer_and_derivation.sql`: `superseded_by`/`supersede_note` columns plus a trigger that only permits setting `superseded_by` on an otherwise-immutable row), but nothing in the codebase wires an OCR-correction flow through it.
  - These `stats` dicts are **return values from stateless tool calls**; grepping `server/` for where `ocr_used`/`low_confidence` from these two files get persisted turns up no write into `evidence.artifact_metadata` or any other table — the OCR stats are not currently stored anywhere as a durable receipt.

**What `evidence.artifact_metadata` CAN store vs. what's written** (`sql/bootstrap/schema_baseline.sql` lines 4431–4467, full `CREATE TABLE` read): columns are `fs_original_path, fs_filename, fs_size_bytes, fs_mtime, fs_ctime, fs_birthtime, fs_observed_at, embedded (jsonb), embedded_export_at, export_set_id, export_kind, record_count_claimed, filename_export_at, resolved_export_at, resolved_source, layer_disagreement`. This is a **filesystem/export-metadata** table (three competing timestamp layers: filesystem, filename-embedded, chat-export-embedded) for detecting export truncation and clock disagreement — it has no OCR-specific columns (no `ocr_engine`, `ocr_confidence`, `bbox`, `exif`) at all, so even if the extractor stats were wired up, this table has nowhere to put them today.

**Conclusion**: claim is accurate on every specific receipt field named. There is a working, tiered OCR pipeline (a real capability the claim doesn't quite acknowledge), but it captures only coarse method/ocr_used/confidence-boolean stats, does not persist them, and `artifact_metadata` has no schema surface for OCR receipts regardless.

---

## Claim 10 — Backups (Postgres/Neo4j → R2) remain "planned"

**Verdict: FOUND TRUE — confirmed directly in `docs/DEBT.md`, and the existing script proves the narrower point.**

`docs/DEBT.md` line 176 (debt ledger table):
```
| Backups (pg_dump + neo4j dump → R2) | planned | P5 |
```
`docs/DEBT.md` lines 119–122 (explicit prose caveat):
> `evals/cases.py` still `CASES: tuple[Case, ...] = ()`, and Backups (pg_dump + neo4j dump → R2) still has no recurring implementation — `scripts/backup_ovhdata_hot.sh` exists but is a one-time host-retirement snapshot (Postgres/SurrealDB/Weaviate only, explicitly skips Neo4j/Milvus to a cold-copy phase), not the recurring R2 lane this row tracks.

(Note: DEBT.md's own line 119 appears to assert `evals/cases.py` is `()` — that is now stale/incorrect per Claim 7's direct read of the current file, which has 8 real cases. Flagging this as a doc-drift point, not part of claim 10's own verdict.)

`scripts/backup_ovhdata_hot.sh` (full file read, 207 lines) confirms the caveat precisely:
- Backs up Postgres (`pg_dumpall`), SurrealDB (`surreal export`), and Weaviate (typed schema + paginated object/vector export) — all **hot**, all written to a **local staging directory** (`STAGE="/data/backup-ovhdata-20260801"`), gzip'd, with a `SHA256SUMS` manifest.
- Explicitly **skips Neo4j and Milvus** ("file-backed with no online export on the community edition, so they are COLD-copied in phase 1b via the Coolify stop/start API").
- Contains **no R2 upload step** anywhere in the script — no `rclone`, `aws s3`, `r2`, or any remote-transfer command; everything lands in the local `$STAGE` dir only.
- Its own header states this is "PHASE 1a" of a one-time host-retirement migration (ovh-data → ovh-files), not a recurring backup job — there is no cron/scheduled-task wiring for it (also checked: no `CronCreate`/scheduled-task references to this script).

**Conclusion**: claim is accurate. A recurring Postgres+Neo4j→R2 backup lane does not exist; `DEBT.md` itself says so and is the authoritative source. The one script that does exist is a one-time, local-staging, Postgres/SurrealDB/Weaviate-only snapshot that explicitly does not cover Neo4j and does not push to R2.

---

## Confidence summary

| # | Claim | Verdict |
|---|---|---|
| 1 | No RAG citation-grounding validation | CONFIRMED ABSENT (design-draft only) |
| 2 | No context_thread_id/parent_thread_id dual-granularity | CONFIRMED ABSENT |
| 3 | No relative-score cutoff / dedupe / diversity / budget packing | CONFIRMED ABSENT |
| 4 | No EDRM/load-file production exports | CONFIRMED ABSENT (Bates PDF stamping only, explicitly not court-safe/exportable) |
| 5 | No stable human-usable exhibit ID service | PARTIAL (dead schema column; Bates generator exists but narrowly scoped) |
| 6 | No closed-world generation contract | CONFIRMED ABSENT |
| 7 | `evals/cases.py` is empty | **FALSE** — 145 lines, 8 real cases (none grounding-related) |
| 8 | No NSRL/de-NISTing | CONFIRMED ABSENT |
| 9 | No OCR pipeline with receipts | PARTIAL (real tiered OCR pipeline exists; none of the named receipt fields are captured or persisted) |
| 10 | Backups to R2 remain "planned" | FOUND TRUE (confirmed by DEBT.md + script read) |

**High-confidence (verified by full-file reads of the implicated modules, not just grep hit-counts):** 1, 2, 3, 4, 5, 6, 7, 9, 10.

**Would benefit from a second pass:**
- Claim 8 (NSRL) — this was a pure-negative grep with no positive code to read against; a second pass should also check any third-party/vendored dependency manifests (`requirements*.txt`, `pyproject.toml`) for a hash-set library (e.g., `hashdb`, `nsrl`) that might be present but unused/uncalled, which a content grep alone would miss if the dependency name doesn't literally contain "nsrl".
- Claim 9's "access-time preservation" sub-clause — confirmed absent from the two extractor modules, but I did not exhaustively check every ingest/upload code path (`server/ingest/service.py`, `workbench/api/app/runtime/upload.py`) for an unrelated place that might separately capture `atime`/`fs_atime` outside the OCR extractors. `artifact_metadata` does capture `fs_mtime`/`fs_ctime`/`fs_birthtime` but has no `fs_atime` column, which is strong (not conclusive) evidence access-time isn't tracked.
- Claim 2 — I did not check the Legal-Workspace repo for `context_thread_id`/dual-granularity retrieval since the claim's context (RAG evidence chunking) is Agno-MCP-Platform-specific; if the gap-analysis document intended this claim to also cover Legal-Workspace, that repo wasn't searched for it.
