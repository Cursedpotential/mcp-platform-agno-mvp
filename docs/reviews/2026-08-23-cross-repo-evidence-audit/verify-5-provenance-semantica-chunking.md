# Claim Verification — Provenance, Semantica, Chunking, Projection Metadata, Deployment Truth

Repo: `E:/AI_Workspace/Projects/the-platform-workspace/Agno-MCP-Platform`
Verification date: 2026-08-23

---

## Part A — Provenance of the review itself

**Claim 1:** The gap-analysis document reviewed revision `1e38d3a61d86fe5bd4d94a549b7797380f8faa1c` on branch `main`, dated 2026-08-18.

```
$ git log --oneline -5
1e38d3a feat: ship governed conversations and native evidence desk
c0b8067 ops: add side-by-side Weaviate deployment
3a0f4d3 docs: persist standing subagent authorization
c835ce4 docs: checkpoint Surreal live core pass
ed55a75 fix: verify denied Surreal write postcondition

$ git cat-file -t 1e38d3a61d86fe5bd4d94a549b7797380f8faa1c
commit

$ git rev-parse HEAD
1e38d3a61d86fe5bd4d94a549b7797380f8faa1c

$ git log -1 --format="%H %ad %s" --date=iso
1e38d3a61d86fe5bd4d94a549b7797380f8faa1c 2026-08-18 10:22:03 -0400 feat: ship governed conversations and native evidence desk

$ git branch -a
* main
  sbv-swift-mvp-20260816
  sbv-swift-mvp-20260816-v2
  remotes/origin/HEAD -> origin/main
  remotes/origin/main
  ... (many other remote branches)
```

**Findings:**
- The commit exists locally (`git cat-file -t` returns `commit`, not an error).
- Its actual date is **2026-08-18 10:22:03 -0400**, matching the claimed date.
- Its message is `feat: ship governed conversations and native evidence desk`.
- The local checkout `HEAD` (on branch `main`) is **exactly at** this commit — `git rev-parse HEAD` returns the identical SHA. Not ahead, not behind.
- Caveat: the working tree is **dirty** — `git status --short` shows dozens of modified/deleted files (docs, `docker/surreal-phase1-runner/*`, etc.) on top of this commit. `HEAD` itself is correct, but anyone re-deriving "current state" from the working tree rather than from `git show HEAD:<path>` would see post-commit edits layered on top. This doesn't invalidate the review's premise (HEAD = claimed commit) but is a nuance worth flagging: some of the doc content used to verify Parts B–E below (docs/BUILD_PLAN.md etc.) may itself be part of the uncommitted, in-flight edits rather than pinned to the reviewed commit exactly. I did not attempt to isolate committed-vs-uncommitted state for every file checked below; all reads were of the live working tree.

**Verdict: CONFIRMED.** Commit exists, date and message match, and the local checkout is exactly at that commit (HEAD-equal), modulo an uncommitted, dirty working tree layered on top of it.

---

## Part B — Semantica claims

**Claim 2:** Vendored `semantica` supports "15 formats" (PDF, DOCX, HTML, email, JSON, CSV, XML, Excel, PPTX and more).

Located at `server/vendored/semantica/semantica/parse/`. Enumerated every format-specific parser module and what it declares it parses (from `parse/__init__.py` docstring + per-file headers):

| # | Format | Parser module |
|---|--------|----------------|
| 1 | PDF | `pdf_parser.py` (`PDFParser`) |
| 2 | DOCX | `docx_parser.py` (`DOCXParser`) |
| 3 | PPTX | `pptx_parser.py` (`PPTXParser`) |
| 4 | Excel/XLSX | `excel_parser.py` (`ExcelParser`) |
| 5 | HTML | `html_parser.py` (`HTMLParser`) |
| 6 | TXT (plain text) | `document_parser.py` (inline `.txt` branch) |
| 7 | JSON | `json_parser.py` (`JSONParser`) |
| 8 | CSV | `csv_parser.py` (`CSVParser`) |
| 9 | XML | `xml_parser.py` (`XMLParser`) |
| 10 | YAML | `structured_data_parser.py` (`yaml.safe_load` branch) |
| 11 | Email (EML) | `email_parser.py` (`EmailParser`, MIME) |
| 12 | Image (JPEG/PNG/GIF/BMP/TIFF) | `image_parser.py` (`ImageParser`, OCR) |
| 13 | Audio (MP3/WAV/FLAC/AAC) | `media_parser.py` |
| 14 | Video (MP4/AVI/MOV/MKV/WEBM) | `media_parser.py` |
| 15 | Code (multi-language source) | `code_parser.py` (`CodeParser`) |

Not counted as an additional/16th format: `mcp_parser.py` (`MCPParser`) parses **MCP protocol responses** (JSON/text/binary tool outputs), not a document/file format, and `docling_parser.py` (`DoclingParser`) is an **optional wrapper** re-parsing PDF/DOCX/PPTX/XLSX/HTML/images through a different backend, not a new format.

**Verdict: CONFIRMED.** Counting distinct format categories with dedicated parsing logic in `server/vendored/semantica/semantica/parse/`, the total is exactly **15**, matching the claim precisely, and the named examples (PDF, DOCX, HTML, email, JSON, CSV, XML, Excel, PPTX) are all present as claimed.

---

**Claim 3:** Vendored `semantica` "has no runtime caller anywhere outside its own vendored tree" / "zero runtime call sites."

Grep across the full repo (excluding `server/vendored/semantica/`, `.claude/worktrees/*`, `.research/*` which are upstream mirrors/copies of Semantica's own docs and cookbook examples, and `.venv`):

```
$ grep -rln "vendored\.semantica\|vendored/semantica\|from semantica\b\|import semantica\b" --include="*.py" .
  | grep -v "server/vendored/semantica/" | grep -v ".claude/worktrees" | grep -v ".research"

./.venv/Lib/site-packages/__editable___agent_platform_1_0_0_finder.py   # editable-install metadata, not a call site
./docs/wiki/project-docs/components/infrastructure/semantica/cookbook/advanced/snowflake_ingestion_examples.py  # Semantica's own vendored cookbook doc, not platform code
./server/analysis/semantica_worker.py     # <-- real production module
./tests/test_semantica_phase1_worker.py   # test
```

`server/analysis/semantica_worker.py` (325 lines) directly imports from the vendored package:
```python
from server.vendored.semantica.semantica.semantic_extract import event_detector as _event_module
from server.vendored.semantica.semantica.semantic_extract import methods as _methods
from server.vendored.semantica.semantica.semantic_extract.event_detector import Event, EventDetector
from server.vendored.semantica.semantica.semantic_extract.ner_extractor import Entity
```
This is a production module (`server/analysis/`, not `tests/` or `scripts/`) defining `class SemanticaPatternWorker` (ADR-0043 "governed extraction worker").

However, tracing **who calls `semantica_worker.py`**:
```
$ grep -rn "from server.analysis.semantica_worker\|semantica_worker import" --include="*.py" .
./scripts/run_semantica_fixture.py:21:from server.analysis.semantica_worker import SemanticaPatternWorker
./tests/test_semantica_phase1_worker.py:25:from server.analysis.semantica_worker import SemanticaPatternWorker
./tests/test_semantica_phase1_worker.py:83:    from server.analysis import semantica_worker as module
```
And checking `server/analysis/semantica_wiring.py` (which sits alongside it and looked like a possible caller): it only references `"server.analysis.semantica_worker.SemanticaPatternWorker"` as a **string value inside a config dict** (`worker_wiring()["runtime"]`) — it does not `import` the module at all. No route, Celery task, pipeline orchestrator, or API handler under `server/` instantiates `SemanticaPatternWorker` or imports `semantica_worker`.

**Verdict: REFUTED, as literally stated** — there IS a runtime call site outside the vendored tree: `server/analysis/semantica_worker.py` is production code (not a test) that directly imports and uses the vendored `semantica.semantic_extract` subpackage. The stronger, narrower claim that would be true is: *no production pipeline entry point (API route, orchestrator, scheduled job) currently invokes that call site* — its only current callers are a test file and a standalone manual fixture script (`scripts/run_semantica_fixture.py`). "Zero runtime call sites" overstates this; the correct characterization is "one production call site (semantica_worker.py) that itself has zero upstream production callers yet."

---

**Claim 4:** Wiring semantica into ingestion would close most "can't ingest this file type" risk without new parser code, given a prior finding that DOCX/PPTX/XLSX/HTML ingest fails today because `docling` is an optional extra absent from `requirements.txt`.

Checked main `requirements.txt`:
```
$ grep -in "docling\|pptx\|python-docx\|docx\|openpyxl\|beautifulsoup\|^lxml" requirements.txt
beautifulsoup4==4.15.0
lxml==6.1.1
openpyxl==3.1.5
```
Confirms the precondition: `docling` is absent, and `python-docx`/`python-pptx` are absent (only `beautifulsoup4`, `lxml`, `openpyxl` are present).

Checked vendored Semantica's own `pyproject.toml` (`server/vendored/semantica/pyproject.toml`):
- **Core (non-optional) dependencies** include: `beautifulsoup4`, `lxml`, `pypdf2`, `python-docx`, `openpyxl`, `pillow`. These back `docx_parser.py`, `excel_parser.py`, `html_parser.py`, `pdf_parser.py` directly — **none of these four formats require `docling`** in Semantica; Docling is a separate, optional (`parse-docling = ["docling>=1.0.0"]`) *enhancement* wrapper, not a requirement for basic DOCX/XLSX/HTML/PDF coverage.
- **Gap found in Semantica itself:** `pptx_parser.py` does `from pptx import Presentation` unconditionally (hard import, not try/except), yet `python-pptx` is **not declared anywhere** in Semantica's own `pyproject.toml` (core or optional extras) — grep for `pptx` in that file returns zero matches. This means importing `semantica.parse` (which unconditionally imports `pptx_parser` in `__init__.py`) will raise `ImportError` unless `python-pptx` happens to be installed via some unrelated transitive path. This is a real, independently-discovered dependency-declaration bug in the vendored package, not something the reviewed document flagged.
- Semantica's top-level `semantica/__init__.py` uses `importlib`/lazy patterns at module scope (no eager heavy imports of `torch`/`transformers` observed at that entry point), so importing just the `parse` subpackage does not obviously force-load the heavy ML core dependency stack — but Semantica's declared *core* dependency list (`numpy`, `torch`, `transformers`, `sentence-transformers`, `spacy`, `faiss-cpu`, `scikit-learn`, `umap-learn`, `gensim`, etc.) is still installed as a baseline requirement of the package regardless of which submodule is used, per the `[project] dependencies` section (not scoped per-submodule).

**Verdict: PARTIAL.** The factual precondition holds directionally: Semantica's DOCX/XLSX/HTML/PDF parsers do NOT require `docling` (they use lighter native libs already partly present in the platform's own `requirements.txt`), so wiring those four in would not require the `docling` extra. But this is not a clean, dependency-light win: (a) Semantica's own PPTX parser has an undeclared `python-pptx` dependency (a real bug), and (b) adopting any part of `semantica.parse` still pulls in Semantica's large core dependency footprint (torch/transformers/sentence-transformers/spacy/faiss-cpu/etc.) as a package-level install requirement, which is a nontrivial cost the claim's "without writing new parser code" framing elides. I do not assess the judgment ("would close most residual risk") — only the checked facts above.

---

## Part C — Chunking and batching claims

**Claim 5:** The repo "chunks with versioned Chonkie policies and preserves conversation structure."

- `requirements.txt` confirms Chonkie is a real, pinned dependency: `chonkie==1.7.0`, `chonkie-core==0.10.2`.
- `server/analysis/chunking_policy.py` — the lane→chunker seam (ADR-0053) — imports Chonkie-backed chunkers from `server/analysis/chonkie_chunkers.py` for the "tuned" (default) path, with an explicit Agno-native `RecursiveChunking` fallback only when `tuned=False`. Docstring: "D-046 RUNTIME DEFAULT: knowledge lanes use Chonkie RecursiveChunker and transcript lanes use the semantic+fixed hybrid."
- `server/core/chunking_identity.py` provides explicit **versioning**:
  ```python
  CHONKIE_PIN = "1.7.0"
  def chunker_id(name: str, chunk_size: int | None = None) -> str:
      """Return the durable algorithm/version identifier stored in receipts."""
      ...
      return f"chonkie.{name}@{CHONKIE_PIN}{suffix}"
  ```
  producing identifiers like `chonkie.recursive@1.7.0:1500-chars`, explicitly described as "stored in receipts."
- Conversation-structure preservation: `chunking_policy.py` designates `TRANSCRIPT_LANES = {"context", "evidence"}` to use `TranscriptSemanticHybridChunking` from `chonkie_chunkers.py`, whose comment reads: "Chonkie SemanticChunker (model2vec, torch-free) groups meaning-coherent turns," and the policy docstring notes "chat chunks are classified only after their message-safe boundaries are formed."

**Verdict: CONFIRMED.** Chonkie is a real pinned dependency, chunking policies are versioned via `chunker_id()`/`CHONKIE_PIN` and stored in receipts, and a dedicated transcript-hybrid chunker exists specifically to preserve message/turn boundaries.

---

**Claim 6:** No first-class corpus batch manifest encoding chronological month/quarter windows, page/message bounds, overlap, source completeness, and rerun identity.

Found `analysis.extraction_batch` (defined in `sql/0009_raw_layer_and_derivation.sql`, lines 520-556, also referenced in `sql/0010` and `sql/bootstrap/schema_baseline.sql`):
```sql
CREATE TABLE IF NOT EXISTS analysis.extraction_batch (
  id                UUID PRIMARY KEY DEFAULT uuidv7(),
  scope_query       TEXT,
  scope_note        TEXT,
  record_count      INT NOT NULL DEFAULT 0,
  input_hash        TEXT,
  input_canon       TEXT NOT NULL DEFAULT 'extraction-batch-v1',
  input_ref         TEXT,
  extractor         TEXT NOT NULL,   -- 'semantica'
  extractor_version TEXT,
  prompt_version    TEXT,
  ontology_version  TEXT,
  model_id          TEXT,
  status            TEXT NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','running','completed','failed','superseded')),
  error_note        TEXT,
  started_at        TIMESTAMPTZ,
  completed_at      TIMESTAMPTZ,
  created_at        TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

Field-by-field against the claim's list:
- **Chronological month/quarter windows** — NOT present as structured columns. `scope_query`/`scope_note` are free text; there is no `window_start`/`window_end`/`period` column.
- **Page/message bounds** — NOT present as structured columns.
- **Overlap** — NOT present.
- **Source completeness** — NOT present as a structured field (no completeness/coverage percentage or check).
- **Rerun identity** — PARTIALLY present: `input_hash` ("the reproducibility anchor," per the inline comment) plus the `status` enum including `'superseded'` gives batch-level rerun/reproducibility tracking, though not a dedicated "rerun of run X" foreign-key/lineage field.

**Verdict: PARTIAL.** The specific claim is mostly accurate — `analysis.extraction_batch` does NOT encode chronological windows, page/message bounds, or source-completeness as first-class structured fields, so the document's core point stands for those three. But it overstates the gap on "rerun identity": `input_hash` + `input_canon` + the `status` enum (including `superseded`) constitute a real, working reproducibility/rerun mechanism at the batch level, just not a dedicated structured field named for it.

---

## Part D — Projection metadata claims

**Claim 7:** "Projection metadata records chunker, embed model, embedder version, projection version, and hashes."

`server/evidence/vector_projection.py` builds an `EvidenceVectorDocument` per chunk (lines ~188-211) with these fields, read straight from the write call:
```python
document = EvidenceVectorDocument(
    chunk_id=..., artifact_id=..., source_sha256=..., case_id=...,
    disclosure_tier=..., source_kind=..., projection_kind=...,
    authority_state="active", source_available_from=...,
    normalized_record_id=...,
    chunker_id=str(row["chunker_id"]),
    embed_model=self._embed_model,
    embed_dimension=self._embed_dimension,
    embedder_version=self._embedder_version,
    projection_version=EVIDENCE_PROJECTION_VERSION,
    projection_hash=projection_hash,
    content_hash=str(row["content_hash"]),
    source_content_hash=str(row["source_content_hash"]),
    content=..., vector=..., occurred_at=..., conversation_id=...,
)
```
`projection_hash` is computed (`_projection_hash`, lines 272-291) as a SHA-256 over a payload including `content_hash`, `chunker_id`, `embed_model`, `embedder_version`, `projection_version`, and availability/timestamp fields.

**Verdict: CONFIRMED.** All five named items are present and more: `chunker_id`, `embed_model`, `embedder_version`, `projection_version`, and three distinct hashes (`content_hash`, `source_content_hash`, `projection_hash`), plus `source_sha256` (custody hash) — the claim slightly undersells the actual field count.

---

**Claim 8:** No automated dependency graph that invalidates prior grounding/evaluation approval when a relevant version changes.

- Repo-wide grep for `invalidat`/`revalidat` (excluding vendored/worktrees/research/`.venv`) found only: `docs/planning/forensic-db-reconciliation/migrations/0006_behavior_seed.sql`, `sql/0027_walk_ledger.sql`, `sql/drafts/walk_ledger.postgres-draft.HOLD.sql`, `tests/test_surreal_phase1_workspace.py`.
- `sql/0027_walk_ledger.sql` (part of the **0026-0029 range BUILD_PLAN.md explicitly says is "unapplied," not cut over** — see Part E) defines `working.walk_run.status` with an allowed value `'invalidated'` and a `base_version`/`genesis_hash` version-pinning scheme, plus an `invalidated_reason` column. This is a **manual status value**, not an automated trigger: I found no `CREATE TRIGGER` or function in that file (or anywhere in `sql/*.sql`) that automatically flips a row's status to `invalidated` when `prompt_version`/`ontology_version`/`embedder_version`/`model_id` changes.
- Full inventory of every `CREATE TRIGGER` across applied migrations (`sql/0008`, `0009`, `0010`, `0017`, `0020`, `0024`, `0025`, `0026`, `0030`) shows only: no-mutate guards, append-only guards, `updated_at` triggers, and outbox/enqueue triggers on chat and vector-projection tables. None implement cross-table, version-change-triggered invalidation of a prior approval/grounding decision.
- `provenance.lineage_edge` (applied, `sql/0014`) is a real lineage/DAG table linking artifacts to parents/runs, but it is a passive edge table, not an active invalidation mechanism — nothing reads it to cascade-invalidate approvals on version bumps.
- The only places "dependency DAG" / automated invalidation of approvals is discussed at length as a **design concept** are planning drafts (`docs/planning/forensic-db-architecture/FORENSIC_DB_ARCHITECTURE_DRAFT.md` and its `sections/*`), which are design documents, not applied schema or running code.

**Verdict: CONFIRMED.** No automated dependency-graph/trigger mechanism exists anywhere in applied (or even unapplied-but-written) SQL or Python that invalidates a prior grounding/evaluation approval when a relevant version changes. The closest thing (`walk_run.status = 'invalidated'`) is a manually-settable enum value in a migration BUILD_PLAN.md says is explicitly not cut over, and even there nothing automatically triggers it on a version delta.

---

## Part E — Deployment-truth claim

**Claim 9:** The repo has no machine-readable capability register recording deployment state (built/held/not-deployed), despite being explicit about it in prose scattered across handoffs/debt/build-plan/migration comments.

- Found `docs/TODO-SNAPSHOT-2026-08-02.json`, `-08-03.json`, `-08-07.json`, `-08-12.json`, `-08-14.json` — real, machine-readable JSON files. Inspected `TODO-SNAPSHOT-2026-08-14.json`:
  ```json
  {"_meta": {"generated_by": "PreCompact hook precompact_handoff.py",
             "byline": "Claude Code / Fable 5",
             "note": "Open (non-completed) tasks captured at each compaction, keyed by session id. Latest capture wins per session."},
   "snapshots": {"32008b72-...": [...]}}
  ```
  This is a **session-keyed open-TODO tracker** written by a PreCompact hook, not a deployment/capability status register — it records "what's still on someone's todo list," not "what's built/held/not-deployed" per feature or migration.
- Searched `docs/` (depth 2) and repo root (depth 2) for other JSON/YAML/TOML status/capability/feature-flag/build-status/deploy-status files: none found (only the TODO-SNAPSHOT files matched any structured-status naming pattern).
- No `capabilities.yaml`, `STATUS.json`, `feature_flags.*`, or similar found anywhere outside vendored/worktree/research paths.

**Verdict: CONFIRMED**, with a nuance worth surfacing: TODO-SNAPSHOT JSON files exist and are machine-readable, so "no machine-readable [file] at all" would be false — but they are session task-lists, not a capability/deployment-state register, so the claim's substantive point (no machine-readable registry of what's built/held/deployed per feature or migration) holds. The actual deployment-truth ledger genuinely lives only in prose (BUILD_PLAN.md, DEBT.md, handoffs, migration file comments), as verified directly in Claim 10 below.

---

**Claim 10:** `docs/BUILD_PLAN.md` states migrations 0026-0029 "must not be cut over yet," 0030 is unapplied, and the court-export feature is a "read-only court-export/readiness explanation ... performing no release mutation."

Direct quotes from `docs/BUILD_PLAN.md` (current working-tree content):

Line 24:
> "1. Preserve and audit the unapplied Wave-1 tree; do not cut over migrations `0026–0029`."

Lines 55-59 ("Locally built and held" section):
> "Migration `sql/0030_matter_case_foundation.sql` and focused tests exist, but the migration is **unapplied** and no deployment/live claim is made. Commit `be286a8` adds exact canonical-record and H1 custody inspection before human review; it changes no schema and is pushed to `main` but remains undeployed."

Lines 60-63:
> "Commit `7b6aaf6` adds a read-only court-export/readiness explanation: actual `analysis.vw_court_export` membership is shown separately from stricter content-review, exact-provenance, custody, authentication, confidence, hypothesis, redaction, and sensitivity checks. It performs no release mutation."

Lines 67-70 (current-state correction, corroborating):
> "Wave 1 has implementation files in the working tree (`sql/0026_realization_event.sql` through `sql/0029_pass_grants.sql`, `server/evidence/realization.py`, and `server/evidence/derivation.py`), but they are **pushed to `main` and not recorded as applied to the live database**."

**Verdict: CONFIRMED.** All three sub-claims are directly and near-verbatim supported by BUILD_PLAN.md: migrations 0026-0029 explicitly "do not cut over," migration 0030 is explicitly "unapplied," and the court-export feature is described almost word-for-word as "a read-only court-export/readiness explanation ... It performs no release mutation."

---

## Summary Verdict Table

| # | Claim | Verdict |
|---|-------|---------|
| 1 | Commit `1e38d3a6...` on `main`, dated 2026-08-18, is what the review covers | CONFIRMED — commit exists, date/message match, local HEAD is exactly at it (working tree is dirty on top) |
| 2 | Semantica supports 15 formats (PDF/DOCX/HTML/email/JSON/CSV/XML/Excel/PPTX + more) | CONFIRMED — counted exactly 15 distinct format-specific parsers |
| 3 | Zero runtime call sites outside the vendored tree | REFUTED (as stated) — `server/analysis/semantica_worker.py` is a production module that imports vendored semantica directly; its only callers, however, are a test and a manual fixture script, not a production pipeline entry point |
| 4 | Semantica's parser set covers the docling-blocked formats without needing docling | PARTIAL — true for DOCX/XLSX/HTML/PDF (native libs, no docling needed), but Semantica's own PPTX parser has an undeclared `python-pptx` dependency, and adopting semantica.parse still pulls Semantica's full core ML dependency stack |
| 5 | Chunks with versioned Chonkie policies, preserves conversation structure | CONFIRMED — `chonkie==1.7.0` pinned, `chunker_id()`/`CHONKIE_PIN` versioning stored in receipts, dedicated transcript-hybrid chunker for message boundaries |
| 6 | No first-class batch manifest for chronological windows/page-message bounds/overlap/completeness/rerun identity | PARTIAL — `analysis.extraction_batch` lacks windows/bounds/overlap/completeness as structured fields (claim holds there), but does provide real rerun/reproducibility identity via `input_hash`+`status` |
| 7 | Projection metadata records chunker, embed model, embedder version, projection version, hashes | CONFIRMED — all present in `EvidenceVectorDocument`/`vector_projection.py`, plus additional hash fields |
| 8 | No automated dependency graph invalidating prior approvals on version change | CONFIRMED — no trigger/function found anywhere; only a manual, unapplied `status='invalidated'` enum value exists |
| 9 | No machine-readable capability/deployment-state register | CONFIRMED (substantively) — TODO-SNAPSHOT JSON files exist but are session task-lists, not a capability/deployment register |
| 10 | BUILD_PLAN.md: 0026-0029 not cut over, 0030 unapplied, court-export is read-only/no release mutation | CONFIRMED — near-verbatim quotes match at cited lines |
