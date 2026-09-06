# Resolved-Designs Recovery — the three rulings that kept getting lost

> _Byline: Claude Code · Fable 5 · 2026-09-01 (owner-ordered records recovery)._
> Owner, 2026-09-01: half the resolved designs ("the Python seam issue, the plain
> text chunking-not-parsing issue, and the DuckDB ELT implementation") had been
> forgotten because their ruling documents were never committed. This document
> makes each resolution durable, with its source, so no future session re-derives
> a wrong picture. **These are settled. Do not re-litigate any of them.**
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## Why they were lost (the records failure)

- The 2026-08-25 schema-audit ruling docs (`TEMPORAL-N8N-WORKFLOW-AND-GAPS.md`,
  `SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html`, the whole-system conceptual model)
  were referenced repeatedly in session transcripts and in agent lane prompts —
  and have **zero git history**. They were never committed anywhere.
- Decision-log entries **D-072 through D-080 never landed** in
  `docs/DECISION_LOG.md` (the log jumped over them; the 08-25 session recorded
  "decision log D-077 updated" — that update was not in the committed file).
  ~~Backfill remains OPEN~~ **RESOLVED 2026-09-02: D-072–D-081 recovered
  VERBATIM from Codex session rollouts and inserted into DECISION_LOG.md in
  numeric order; provenance per row in
  `docs/pending-review/D-072-D-080-backfill.md`. The three lost 08-25 ruling
  docs were likewise reconstructed from rollouts into
  `docs/reviews/2026-08-25-schema-audit/` (two full, one partial — see its
  RECOVERY-NOTE.md for exact gaps).**
- The external review artifacts lived only in `Downloads/`. As of this commit
  they are tracked under `docs/reviews/2026-08-31-external-reviews/`.

## Resolution 1 — the Python seam (Go ↔ Python parser bridge)

**Ruled 2026-08-29** (session transcript, worktree smart-explore-6ff9d5; encoded
in ADR-0061 authority item 2):

- Owner 16:04: the missing Go→Python parser bridge is "a gap to fix".
- Owner 16:06: "anything callable modularity-wise needs to live in the same place."
- Owner 16:09 (verbatim): "**every single parser has the same contract and the
  same destinations. And they're entirely atomic. And they do one thing, they
  parse, they do nothing more.**"
- ADR-0061: the Go coordinator selects ONE registered parser by declared
  coverage and quality; **Go-native and governed `platform-tools`
  implementations share that contract**. Python parsers participate as governed
  platform-tools implementations under the Go coordinator — there is no second
  independent Python registry choosing destinations, and Python never
  permanently orchestrates.
- Repair stays Python behind a call seam (owner 2026-08-10, ADR-0049): "if the
  repair engine can be called on and utilized inside of the go application and
  still be python then it's fine."

**Work implied (H-01 scope, corrected):** register the Python parsers as
governed platform-tools implementations under the Go coordinator's contract;
retire the Python custody journal (`PostgresReceiptJournal`,
`server/ingest/service.py`); collapse the two detection registries. The bridge
mechanism is the platform-tools governed-HTTP shape, not subprocess ad-hocs.

## Resolution 2 — plain text is CHUNKED, not parsed

**Ruled 2026-08-29** (same session):

- Owner 16:10 (verbatim): "Chunking can be separate… **If it doesn't need to be
  parsed and it really needs to be chunked and ingested, then so be it.**"
- Owner 16:16: a model may discover document structure and chunk against the
  markdown structure and a created schema.
- Owner 16:59: "extraction should happen separate from the chunking, so it all
  gets included in the chunks, but then it also creates the artifact."

**Already built** (2026-08-29 receipt `docs/reviews/2026-08-29-go-document-markdown-chunker.md`):
`modules/engine/chunk` — deterministic document-markdown chunk stage
(chronology/research_report/strategy_memo/statute_extract variants, version-pinned
caps, SHA-256 per chunk, lossless reassembly proof), with `chunk.Registry` as the
separate coordinator seam required by parser/chunker atomicity. Chunk model =
`working.content_chunk` with `content_sha256` (D-116).

**Missing leg:** the ROUTE. The ingest dispatcher has no skip-to-chunk path —
already-normalized text (AI work products, markdown, plain text) must route
straight to the chunk stage without a parse step. This is a routing wiring item,
not a design question.

## Resolution 3 — the DuckDB ELT lane

**Source artifact:** `docs/reviews/2026-08-31-external-reviews/repo-review-tweaks-and-consolidation.md`
(the owner-commissioned external review, 2026-08-31), Tweak 4 — now tracked
in-repo. Owner restated it as part of the ingest-surface flow 2026-09-01
("it could send it straight to DuckDB"). Earlier owner statement 2026-08-10:
"duckdb in pg is kind of supposed to be the ingestion point."

The ruled scope (narrow, not sweeping — do NOT route XML/PDF through DuckDB):

1. CSV and NDJSON/JSONL record extraction → `read_csv_auto` / `read_json_auto`
   **inside an `execute_parser_activity`**, producing raw record rows directly
   (targets in the `raw` schema; `raw` is insert-only for parsers).
2. Bulk normalization joins and coverage-reconciliation counts → DuckDB set
   operations instead of row-at-a-time Python.
3. R2 projection/filter pushdown for large structured sources so the
   block-scratch stage is skipped when only a subset is needed.
4. Replaces the imperative iteration in `server/tools/repair/chunkers.py` for
   the structured cases only.

**Status:** this is handoffs-v2 H-07 — but H-07 undersold it as "utilization";
it is the structured-lane ELT design of the ingest workflow and a first-class
component of the D-123 ingest surface. Custody hashing stays in Go (invariant 1);
pg_duckdb transforms, it never writes custody.

## How the three compose (D-123, 2026-09-01)

The SBV desktop-first ingest workspace (Tauri-wrapped client) is the operator
surface over exactly these three resolutions plus the atomic-Activity boundary
(2026-08-25 ruling: n8n visual flow · Temporal durable sequencing · dedicated
custody-hash Activity family separate from everything else):

hash (always first, atomic Activity) → route decision (skip-to-chunk |
parse via the one Go-selected contract | extract | structured lane straight to
DuckDB) → view preview → chunk preview → commit-with-preview → operator
context/metadata input via UIW source-context revision + repair paths.

See D-123 in `docs/DECISION_LOG.md` for the ruling text.
