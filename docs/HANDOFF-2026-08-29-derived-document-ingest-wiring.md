# HANDOFF — Derived-document ingest wiring (AI work products → context → timeline/vectors/graphs) (2026-08-29)

> _Byline: Claude Code · Opus 5 · 2026-08-29_
STATUS: COMPLETE (audit + handoff only — no code changes were in scope)
BUILD_STATUS: UNKNOWN (no tests run this session; `PHASE-0-FREEZE` itself records BUILD_STATUS UNKNOWN)

## Scope

Owner supplied four markdown files (AI-assistant outputs containing case chronologies, events,
entities, legal strategy, and a long-form research guide) and asked: **is there a parser that
will handle them, where should they land, and are they searchable?** Then: write the handoff +
TODO to get documents of this class through the Temporal/n8n path, into the right tables, so
change detection can drive them to timeline, vectors, and graphs.

Answer up front: **no parser handles them structurally, they are not semantically searchable
once ingested, and the downstream timeline/graph machinery is built but has no producer.**
Nearly every missing piece already exists in-tree and is unwired.

## The four files (content class)

They are **not chat transcripts** — zero role markers in any of them. They are *derived
analytical work products*: a NotebookLM case chronology ("FULL CASE EXTRACTION — ALL
TIMELINES, EVENTS, STRA", 17.6KB), a courtroom-framing strategy memo (3.8KB), a long-form
Michigan digital-evidence practitioner guide (56.4KB), and statute analysis with NotebookLM
`[span_N](start_span)` citation markers still embedded (5.0KB).

This class has no representation in the parser registry or the format router.

## Verified-live state (do not re-derive)

> **⚠ LINE NUMBERS ARE VOLATILE.** Codex is running ~6 concurrent subagents against this repo
> (owner, 2026-08-29); HEAD moved twice during the audit that produced this document. Every
> `file:line` below was verified at the HEAD named in the first row — **anchor on the symbol
> name, not the line number**, and re-locate before acting. Findings are about *symbols and
> behavior*, which are stable; line numbers are not.

| Thing | State |
|---|---|
| Repo / HEAD | `Agno-MCP-Platform` `main` @ **`312d302`** "PHASE-0.2-SECURITY: Critical security fixes for STOP gates" (2026-08-29 11:34). Audit was performed at `54de3f0` "PHASE-0-FREEZE" (11:10); re-verified against `312d302` where noted |
| Working tree at time of writing | Dirty and moving — `engine/activities/hashing.go`, `engine/stagegraph/`, `engine/uiw/`, `workbench/api/app/runtime/auth.py`, `server/ingest/service.py` modified; `deploy/authentik.yaml` untracked. **Codex in-flight — do not touch.** |
| In-flight change to an audited file | `server/ingest/service.py` has **+130 uncommitted lines** adding `recover_incomplete_ingests()` — startup recovery scanning `ops.workflow_run` for stuck `framework-neutral-ingest` runs, replacing the `_INGEST_TASKS` asyncio-only path lost on restart. **Orthogonal to this handoff** (touches durability, not parser routing / lane / chunking) — the work packages below are not redundant with it, but expect line drift in that file |
| Migrations on disk | through `sql/0046_agno_app_role.sql`; `0041`–`0046` all post-date the 2026-08-23 audit |
| Parser registry | 25 `@register` parsers; **16 accept `.md`/`.txt`** |
| Format router | `server/analysis/format_router.py` — `SIGNATURES` has **3 entries, all JSON marker matches** (`chatgpt-official`, `perplexity-contexts`, `claude-ai-export`). **Zero markdown signatures.** |
| Router wiring | `detect_format()` IS wired — `server/analysis/chat_parse.py:68`. Returns `format_id=None` for all `.md` → falls to `_parse_via_registry` with no preferred tool (`chat_parse.py:84`) |
| Detection is advisory | On a hit, `preferred_tool_id` only **sorts** the candidate first (`chat_parse.py:99`); on exception it still walks every other candidate |
| Parser precedence | **Only `sbv_sms.py:393` declares `priority=100`.** Every `.md` parser is priority 0, so order is decided by `pkgutil.walk_packages` alphabetical traversal (`registry.py:140`) — `ai_chat/` < `generic/` is load-bearing by accident |
| `.md` terminal fallback | `transcripts.markdown` (`generic/whole_file_fallback.py:25`) — one flat whole-file record |
| Evidence-lane guard | `_EVIDENCE_FORBIDDEN_PARSERS = {transcripts.markdown, documents.text-v1}` (`service.py:29`); enforced at `service.py:131`. The guard at `:232` is **dead** — it raises inside a `try` whose `except` reroutes into `:131` |
| Temporal parse path | `server/temporal/activities.py:196 parse_activity` resolves via `registry.resolve()` directly and has **no lane guard at all** — its docstring states it is deliberately not the ingest facade's path |
| Ingest lane default | **`platform`** (`server/contracts/ingest.py:75`, `server/api/ingest_routes.py:138`). No auto-classifier on the canonical path |
| Lane semantics | **ADR-0053** governs (supersedes ADR-0050): `legal` = law/procedure/strategy/created legal work; `personal_history` = personal/relationship history (absorbed retired `relationship_timeline`); `context` = general/ambiguous; `evidence` = custody-approved only |
| Canonical chunker | `server/ingest/chunking.py::chunk_records()` (`service.py:321-323`) — Chonkie `RecursiveChunker(tokenizer="character", chunk_size=1500)`, **no overlap, lane-blind**. `chunking_policy.lane_chunker()` is NOT on this path (only caller `server/core/session.py:426`) |
| Chonkie | **1.7.0 installed, `requirements.txt:23-24`** — in production. Chunkers available: Recursive, Semantic, Sentence, Token, Fast, Code, Table, Late, Neural, Slumber |
| Chonkie markdown recipe | **`RecursiveRules.from_recipe("markdown")` FAILS live** — attempts a network download of `markdown_en`. Default `RecursiveRules` levels are `['\n\n','\r\n','\n','\r']` → sentences → punctuation. **No heading delimiters.** A 56KB record → ~37 chunks with section structure destroyed |
| Docling | Declared `pyproject.toml:87` (`document-ai` extra). **NOT in `requirements.txt`; NOT installed by the root `Dockerfile` (`RUN uv pip sync requirements.txt --system`) nor `docker/tools/Dockerfile`.** Not present in any deployed image |
| Docling failure mode | `.pdf` degrades to `documents.extract-text`; **`.docx/.pptx/.xlsx/.html/.htm` have no fallback and hard-fail** (`docling_extract.py:6-17`, their URGENT-TODO #17) |
| Tesseract OCR | `ocr` extra (`pyproject.toml:80-83`); absent from `requirements.txt` and both Dockerfiles — **not functional at runtime** |
| Not present at all | LlamaIndex, LlamaParse, unstructured, pandoc, markitdown, tika, textract — absent from `pyproject.toml`, `uv.lock`, `requirements.txt`, and every import |
| Semantica `parse/` | **17 working format modules** (pdf/docx/pptx/xlsx/html/docling/email/image-OCR/csv/json/xml/yaml/code/media/mcp/web) using pdfplumber, python-docx, python-pptx, openpyxl, BeautifulSoup, pytesseract. **Zero callers outside the vendored subtree** |
| `StructuralChunker` | `server/vendored/semantica/semantica/split/structural_chunker.py` — structure-aware, has vendored tests, **zero callers** |
| Semantica platform wiring | `semantica_wiring.py:133-149` — `"deploy": "APPROVALS-gated; fixture/in-process adapter only"`. Callers: `scripts/run_semantica_fixture.py`, a config-printing smoke script, 3 test files |
| Semantica candidate sink | Writes `working.candidate_entity` / `candidate_fact` / **`candidate_event`** (`semantica_candidates.py:32-63`) |
| Timeline sink | Timeline reads **`timeline.event_candidate`** (`sql/0035_timeline_projection.sql:62`) — a **different table**. **No bridge exists between them** |
| `timeline.event_candidate` | Purpose-built for this class: `source_system` examples include `'ai_chat'`; table comment records **D-082 — "an AI-chat-derived row is a lead, never evidence"**; append-only via `forbid_mutation()` trigger; corrections are new rows with a new `extraction_run_id`; deliberately **not FK-constrained** so "any producer that can name its own system/record/version may write here" |
| Timeline module | `40ef4b2` **IS on `main`** (verified `git merge-base --is-ancestor`). `server/timeline/` = generation.py (382 lines), projector, receipts, hashing, models, cli + `sql/0035` (504 lines) + 392 lines of tests. **CLI-only, no HTTP route, zero production callers** (only importer is `tests/test_timeline_projection.py`). Its docs say upstream extraction (WP-B01) is "blocked upstream" |
| `working.investigation_event*` | Schema only (`sql/0024:224-291`) — **zero Python writers anywhere** |
| Searchability | Content ingested via `/v1/ingest` **never reaches the collections `/knowledge/search` queries**. Only reachable paths: `GET /v1/knowledge/items` (exact match) and `GET /v1/records?q=` (plain `ILIKE`, not the existing FTS/trigram indexes) |
| Evidence search | `/v1/evidence/search` and `/v1/operator/evidence/search` hardcode `"knowledge_lane": "evidence"` — cannot see non-evidence lanes |
| Dual-lane comparison | `GraphRagLane` = `semantica` \| `sat_temporal` (`graphrag_contracts.py:14-18`, "callers cannot supply graph database names"). `GraphRagExtractionComparisonWorkflow` **IS registered on the worker** (`server/temporal/worker.py:71`). Output documented as "Two independent lane receipts plus their **no-fusion** reconciliation state" |
| Temporal worker registry | Workflows: `ChatTranscriptIngest`, `ClassificationBatchPipeline`, `GraphRagExtractionComparisonWorkflow`. Activities: `custody_activity`, `parse_activity`, `store_activity`, `knowledge_activity`, `n8n_webhook_activity` (`worker.py:33-78`) |
| Feature flags | **Decided: Unleash.** Queued in `docs/MASTER-TODO-2026-08-18.md` (added 2026-08-29 from owner directive), behind the Workbench/UIW release slice. Standing rule: side-by-side deploys / swappable implementations use named flags |
| NvidiaReranker | `server/core/reranker.py:36` — complete client, **zero callers**; no `Knowledge(...)` passes `reranker=` |
| PII / git safety | Ingested content lands in Postgres + `/r2/evidence` blob root + `/tmp` staging — **outside git**. Owner ruling 2026-08-29: no redaction or PII modification until export time; everything stays in |
| Production database | **`platform` is the new production database** (owner, 2026-08-29). The `ai` database referenced in the `PHASE-0-FREEZE` STOP items (`STOP-R13-2`, `STOP-R14-2`) is **no longer production** — that freeze line is stale. See `sql/0043_platform_single_case_foundation.sql`, `sql/0046_agno_app_role.sql` |
| n8n integration pattern | **Owner, 2026-08-29: n8n exists to utilize the tools. To date every custom tool is wrapped in an n8n code node.** New capability should be exposed as a callable tool and wrapped that way, not as a bespoke route. `n8n_webhook_activity` (`server/temporal/n8n_activities.py:45`) is the Temporal↔n8n bridge and is registered on the worker |
| Chonkie semantic tier | `SemanticChunker`/`NeuralChunker`/`LateChunker`/`SlumberChunker` require model or LLM inference. Owner hard rule: **no local models on this box** — any model-backed chunking must call out to remote (Colab Pro / NIM), and Chonkie's own remote executor is a stub (`chonkie_chunkers.py:186-228`, line 192 "the remote executor is not wired yet", D-046) |

## HARD CONSTRAINT — Semantica atomic tool vs Semantica lane

> _Owner ruling, 2026-08-29._

Two different things share the name "Semantica" and they have **opposite authorizations**:

| | Authorization |
|---|---|
| **Semantica as an ATOMIC TOOL** — calling `StructuralChunker` or a single `parse/` module directly to parse/chunk one document | **ALLOWED NOW.** Use it this way. Owner: *"if one of the bundled semantica tools will work, we can call on those… we're going to utilize that tool atomically."* |
| **Semantica as an EXTRACTION LANE** — content flowing through the Semantica pipeline for entity/fact/event extraction | **BLOCKED until change detection is ordered.** Semantica is downstream of context creation and is triggered by change detection; it must not run ahead of that ordering |

Why this matters: Semantica is one half of the `no-fusion` dual-lane comparison
(`GraphRagLane.semantica` vs `GraphRagLane.sat_temporal`). Running its extraction lane before
change detection is ordered breaks D-069 context-first ingest and invalidates the comparison —
the two lanes must observe the same ordered context state to be comparable at all.

**Do not read WP-5 as authorization to wire the Semantica lane.** WP-5 is an atomic call for
document structure only. Lane activation is WP-6+, gated on WP-1.

## Parser strategy — multiple approaches, deliberately selected

> _Owner directive, 2026-08-29: "I would like to have multiple approaches for parsing these
> things out, in case one of them doesn't work the way that we expect."_

This is **not** a return to the exception-chained fallback mesh (owner rejected that: routing
must be by analysis, not by retry-until-something-doesn't-raise). The contract is:

- **Detection selects a primary** — signature-based, via `format_router`.
- **Alternates are registered under the same capability with EXPLICIT priorities** (the
  `sbv_sms.py:393 priority=100` pattern), never left to `pkgutil` alphabetical order.
- **Alternates are chosen by named Unleash flag or explicit operator hint**, not reached by
  catching an exception.
- **A failure of the routed primary is a hard, logged error naming the file** — never a silent
  slide into a lesser parser.

### Candidate set (verified availability as of this HEAD)

| # | Approach | Installed? | Needs | Risk / unknown |
|---|---|---|---|---|
| A | **Semantica `StructuralChunker`** (`vendored/semantica/semantica/split/structural_chunker.py`) | **Yes — vendored** | Nothing. No network, no model | Zero callers today; behavior on these files unproven |
| B | **Semantica `parse/` document modules** (17 modules incl. `document_parser`, `docling_parser`) | **Yes — vendored** | Nothing for the pure-python ones | `docling_parser` inherits the missing-Docling problem; others use pdfplumber/python-docx/BeautifulSoup which ARE base deps |
| C | **Chonkie `RecursiveChunker` + hand-specified heading delimiters** (`RecursiveLevel(delimiters=['\n# ','\n## ','\n### '])`) | **Yes — `requirements.txt:23`** | Explicit rules config | `from_recipe("markdown")` is NOT usable — verified live, attempts a network download of `markdown_en` and fails |
| D | **Chonkie `TableChunker`** for the tabular passages | **Yes** | Nothing | Narrow; complements rather than replaces |
| E | **Chonkie `SemanticChunker`** | **Yes (lib)** | **Remote inference** — embedding model. Owner hard rule: no local models. Must call out (Colab Pro / NIM) | Chonkie's own remote executor is a stub (`chonkie_chunkers.py:192`, D-046) — the call-out path does not exist yet |
| F | **Docling** | **NO — not in any deploy image** | `document-ai` extra + image rebuild | Converter; for *already-markdown* input the conversion is a no-op, so low value for THIS class. Real value is the office formats that hard-fail today |
| G | **LlamaParse** | **NO — not present at all** | API key; transmits case content externally | Escalation tier for hard scanned PDFs only. Not needed for markdown |

### Recommended order to try (and prove)

**A → C → B**, with D as a complement for tables. A and C are both zero-install and
zero-network, so they can be bake-offed immediately. E only becomes viable once a remote
inference path exists. F is worth doing for *office formats*, on its own merits, not for these
files. G stays deferred.

### WP-5c — Bake-off, not a guess

Run A, C, and B over the **four real sample files** (the two NotebookLM outputs, the strategy
memo, and the 56KB Michigan guide) and record, per approach: chunk count, whether `##` section
boundaries survive, whether the chronology's dated entries stay intact as units, and whether a
known phrase ("MRE 901 authentication") retrieves as one coherent section. Pick the primary on
evidence; register the runners-up behind flags. This is the only way "in case one doesn't work
as expected" is actually answered rather than assumed.

## Findings (ranked)

1. **The router is correct; its signature table is unfinished.** `detect_format` runs on every
   ingest and works as designed — it just has three JSON signatures and none for markdown, so
   100% of `.md` input skips routing and lands in the try-until-one-doesn't-raise mesh. This is
   the single root cause of the "guessing instead of routing" behavior. Fixing it is additive
   (new `FormatSig` rows), not architectural.

2. **The destination table was purpose-built for this content class and has no producer.**
   `timeline.event_candidate` already names `'ai_chat'` as a source system and already encodes
   D-082 (AI-derived = lead, never evidence) in its table comment, with an append-only trigger
   and no FK requirement. Everything downstream of it is built and tested. Nothing writes to it.

3. **Two parallel, both-half-installed document stacks.** `docling_extract.py` +
   `extract_text.py` are wired in code but their libraries aren't installed in any image;
   Semantica's `parse/` has 17 working format modules with zero callers. The platform is
   maintaining two document layers and running neither.

4. **`StructuralChunker` is the closest thing to the right tool for this class** and is vendored,
   tested, and uncalled. For already-markdown input it needs no converter at all — Docling and
   LlamaParse are converters, and conversion is a no-op here.

5. **Ingest defaults to the `platform` lane.** Forgetting `lane=` silently routes custody-case
   material into `platform`. The "nothing reaches evidence without promotion" invariant holds,
   but the default lands in the wrong non-evidence lane.

6. **Guard asymmetry across two parse paths.** ADR-0044's evidence-lane prohibition is enforced
   on the HTTP ingest facade only. The production Temporal `parse_activity` has no lane guard.
   Not currently exploitable (nothing routes straight to evidence), but the protection is not
   structural.

7. **Parser precedence is decided by alphabetical filesystem order.** Only `sbv_sms` declares a
   priority. `ai_chat/` sorting before `generic/` is what currently keeps the whole-file fallback
   last. Renaming a package would silently promote the fallback above every real parser, and no
   test would catch it because whole-file always succeeds.

8. **Ingested content is effectively unsearchable.** Substring `ILIKE` only; semantically
   invisible; and the FTS/trigram indexes that already exist are not used by that route.

## UNRESOLVED (mandatory)

- **No bridge `working.candidate_event` → `timeline.event_candidate`.** Semantica's existing
  extractor writes the former; the timeline reads the latter. Not attempted — the correct
  direction (bridge vs. write `event_candidate` directly) is an owner/architecture call, and
  `event_candidate` takes free-text `extraction_run_id` with no FK, so direct write is viable.
- **`sql/0045_context_fingerprint_semantics.sql` not reviewed.** It is untracked and in Codex's
  live working tree; auditing a file changing underneath produces false findings. It is very
  likely the change-detection substrate this handoff depends on — reconcile before building.
- **Chonkie heading-aware chunking has no verified path.** `from_recipe("markdown")` fails
  (network download). Workaround would be hand-specified `RecursiveLevel` delimiters
  (`['\n# ','\n## ',...]`) — NOT verified working. `StructuralChunker` is the untested-in-context
  alternative. One must be proven before relying on either.
- **BUILD_STATUS UNKNOWN.** No tests run; repo is frozen and dirty. Do not claim PASS.
- **Nothing verified against a live database or deployed service.** All findings are from source
  reading plus one local read-only parser probe. Migration/deploy state is read from file headers.

## Pending owner decisions

1. **Lane assignment for derived AI work products.** WHAT: decide whether these land in `context`
   uniformly, or route per ADR-0053. WHY: owner stated "everything goes to context" (×3), but
   ADR-0053 would place the research guide + strategy memo in `legal` and the chronology in
   `personal_history`. Options: (a) uniform `context`, simplest, contradicts ADR-0053 — the ADR
   must then be amended, not silently ignored; (b) per-ADR routing, needs a classifier or an
   explicit `lane=` at submit. RECOMMENDATION: (b) with explicit `lane=`, since the promotion
   path to evidence is owner-gated either way and ADR-0053 already encodes the taxonomy.
2. **Is `platform` the intended ingest LANE default?** STILL OPEN. Owner confirmed 2026-08-29
   that `platform` is the new production **database** — that is recorded above and is a
   different question from `IngestLane.platform` being the default lane on
   `contracts/ingest.py:75`. WHY it matters: forgetting `lane=` silently files case material
   under the platform-design domain (`_DB_DOMAIN`, `service.py:33`). RECOMMENDATION: make
   `lane` required so nothing lands by accident. Do not treat the database ruling as having
   settled this.
3. **One document stack or two?** WHAT: install the `document-ai` + `ocr` extras into the deploy
   images, or standardize on Semantica's `parse/` layer and retire the parallel extractors.
   WHY: both are currently half-installed; office formats hard-fail today. Owner 2026-08-29:
   *"If one of the bundled semantica tools will work, we can call on those."* RECOMMENDATION:
   Semantica for parse/structure (already vendored, no new deps, no network, nothing to
   install), Docling installed only if binary-format fidelity proves insufficient.
4. **LlamaParse tier.** WHAT: whether to add it as an escalation tier for hard scanned PDFs.
   WHY: it is API-based and transmits case content externally — a different question from local
   storage, which the owner has ruled stays unredacted. RECOMMENDATION: defer; not needed for
   markdown, and Tesseract is the cheaper first fix.

## Next steps (work in order)

Each item is a bounded work package. Nothing here is authorized to run during the
Workbench/UIW critical path or against Codex's in-flight files.

1. **WP-1 — Reconcile with `0045`.** Read `sql/0045_context_fingerprint_semantics.sql` once
   committed; confirm whether it provides the change-detection trigger this chain assumes.
   Blocks WP-6.
2. **WP-2 — Add markdown signatures to `format_router.SIGNATURES`.** Lift the existing role
   regexes into `FormatSig` rows: `gemini_md._ROLE_RE` (`**You:**`/`**Gemini:**`),
   `chatgpt_custom_gpt_md._ROLE_RE` (`You asked:`/`ChatGPT Replied:`), plus claude/perplexity
   markdown markers. Verifiable: a real Gemini `.md` export routes first-try with
   `attempts == 1`.
3. **WP-3 — Add a `document-markdown` signature** (headings present, role markers absent) that
   routes AWAY from `parse.transcript` to a document capability. This is the class the four
   files belong to; nothing detects it today.
4. **WP-4 — Give the whole-file fallback an explicit lowest priority.** Set `priority=-100` on
   `transcripts.markdown` (and `transcripts.generic-md` above it) so precedence stops depending
   on `pkgutil` alphabetical order. Add a test asserting the fallback resolves last.
5. **WP-5 — Wire a structure-preserving document parse for markdown.** Prefer the **bundled
   Semantica tools** (owner-sanctioned): `StructuralChunker`
   (`server/vendored/semantica/semantica/split/structural_chunker.py`) and, where a format
   converter is genuinely needed, the matching module from Semantica's `parse/` set. Fallback
   option is a hand-specified Chonkie `RecursiveRules` with heading delimiters — whichever is
   proven working first. **Do not use Chonkie's `from_recipe("markdown")`** (verified failing:
   attempts a network download). If a model-backed tier (`SemanticChunker`) is chosen instead,
   it must route to remote inference per the no-local-models rule, and Chonkie's remote executor
   is still a stub. Register behind a named Unleash flag. Verifiable: the 56KB guide chunks on
   `##` boundaries, and "MRE 901 authentication" retrieves as one coherent section.
5b. **WP-5b — Expose the chosen parser as a tool and wrap it in an n8n code node,** matching the
   existing pattern (owner: every custom tool to date is wrapped that way). It should be
   callable from n8n and reachable from Temporal via `n8n_webhook_activity`
   (`server/temporal/n8n_activities.py:45`), not added as a bespoke HTTP route. Verifiable: the
   n8n workflow parses one of the four sample files end-to-end and returns chunk counts.
6. **WP-6 — Build the `timeline.event_candidate` producer.** Write rows with
   `source_system='ai_chat'`, a real `extraction_run_id`, and `source_locator` pointing back at
   the context row. Decide bridge-vs-direct per UNRESOLVED. Verifiable: an event from the FULL
   CASE EXTRACTION chronology appears as a candidate with a working source-open pointer.
7. **WP-7 — Give the timeline an HTTP/Temporal surface.** It is CLI-only today. Expose
   generation/projection as a Temporal activity so n8n can drive it.
8. **WP-8 — Close the searchability gap.** Make non-evidence lanes reachable from a real
   retrieval path (`/knowledge/search` collections, or FTS/trigram on `/v1/records`). Currently
   `ILIKE`-only. Verifiable: semantic query returns a section of the guide.
9. **WP-9 — Make the evidence invariant structural.** Remove `lane` from the ingest surface or
   assert `context`-only at all three Temporal activity entry points, so evidence is
   unreachable by ingest rather than merely guarded.
10. **WP-10 — Install `ocr` extra + system `tesseract-ocr`/`poppler`,** or formally retire the
    OCR tier. Today it is wired in code and absent at runtime.
11. **WP-11 — Resolve the office-format hard-fail** (URGENT-TODO #17) per decision 3.

## Owner working-style contract

- Structured replies: bullets, labeled blocks, white space, answer-first.
- Confirm before changes; never hard-delete (quarantine); byline every artifact; verify before
  claiming done.
- No redaction or PII modification until export time — owner ruling 2026-08-29.
- Nothing is ingested directly to evidence under any circumstances; promotion from context is
  the only path.
- Shared worktree: stage only your own files by explicit path; never `git add -A`.
