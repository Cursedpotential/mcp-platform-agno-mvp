# engine/ — platform-owned Go Temporal runtime

> Byline: Claude Code · Sonnet 5 · 2026-08-26 (`engine/proffer` orchestration added same day)
> drift-fix 2026-09-06 Claude Code · Sonnet 5.1: D-137..D-141 rename — `engine/uiw`
> is now `engine/proffer`, `UniversalImportWorkflow` is now `ProfferWorkflow`
> (formerly UIW / Universal Import Workflow).

This module is the platform's own Go orchestration runtime. It is the
authoritative implementation of `ProfferWorkflow`, the single Temporal
workflow that every source — every format, every client, every entrypoint —
runs through. See
`docs/reviews/2026-08-25-schema-audit/SBV-GO-TEMPORAL-RUNTIME-BOUNDARY.html`
for the full boundary decision this module implements (Lane C in that
document's collision-safe lane table).

## What lives here today

`engine/stagegraph` locks the exact atomic stage graph for
`ProfferWorkflow` before any Temporal SDK code is written: the 23
required stages, their single responsibility each, their dependency edges,
and the safe parallel fan-out after `retain_original_activity`. It has no
external dependencies — not even the Temporal SDK — by design, so the stage
contract can be reviewed and tested in isolation from workflow-engine
concerns.

Five, not four, stages compute hashes — `hash_source` (H1), `hash_raw_records`
(H2, per raw record/span), `hash_raw_generation` (H3, the order-sensitive fold
of the ordered H2 digests), `hash_normalized_records`, and
`hash_normalized_generation`. The universal-import H3 reuses the tested SBV
empty-genesis fold implementation but uses the distinct
`h3-chain-platform-rawall-genesisempty-v1` tag because its membership includes
every ordered raw row, including envelope/unparsed spans; legacy SBV H3 covers
logical records and keeps its own tag. H1/H2/H3 name only the raw-custody
hashes; the normalized-side pair computes separately
named digests (a normalized record digest and a normalized generation
manifest digest) that are never called H2 or H3, and are never compared for
equality against H1 — reconciliation/verification of a hash against its
manifest is a distinct responsibility from computing it.

`engine/proffer` (Universal Import Workflow) is the real Temporal SDK
orchestration that consumes that graph: `ProfferWorkflow(ctx,
WorkflowInput) (WorkflowResult, error)`, built on
`go.temporal.io/sdk v1.48.0`. It implements the graph in `engine/stagegraph`
exactly — the same 23 stages, the same dependency edges, the same safe
parallel fan-outs (the four-way fan-out after `retain_original_activity`,
the `reconcile_record_accounting`/`reconcile_byte_coverage` pair — which now
runs after `hash_raw_generation` completes the raw generation's full H2+H3
custody chain, not directly after `hash_raw_records` — and the
`persist_lineage`→`validate_raw_lineage` branch running concurrently with
the `hash_normalized_records`→`hash_normalized_generation` branch) — with
explicit, per-stage `ActivityOptions` (a bounded `RetryPolicy` and a
`StartToCloseTimeout`, sized to what each stage actually does) and
fail-closed control flow: an Activity execution error or an explicit
`StatusFailed` result halts every descendant, including
`seal_generation_activity` and `publish_generation_activity`, without ever
calling `workflow.ExecuteActivity` for them. `StatusSuccess` and
`StatusNotApplicable` both let the workflow continue.

`engine/activities` now implements twelve of the twenty-three Activity bodies:
source register/retain; filesystem metadata, container inventory, and embedded
metadata; parser select/execute; and the five hashing Activities. The hash
bodies provide streamed source H1, streamed per-raw-record H2, the
authoritative SBV `pkg/custodyhash` fold under the platform raw-all H3 tag, streamed normalized-record
digests, and a separately framed ordered normalized-generation digest. Each
batch is written incrementally, fails closed on empty or out-of-order
membership, reports compact heartbeat progress, aborts partial output on
cancellation/error, and returns only result/receipt references. Parser
selection is persisted as an exact parser ID/version pin, so execution rejects
registry drift instead of silently selecting again. All implemented methods
are registered under exact `stagegraph.StageID` names. The concrete PostgreSQL
hash repository is implemented and locally verified; lifecycle, parser, and
observation stores are being integrated. Eleven post-parse Activity bodies
remain.

Every Activity is invoked by its canon name (`stagegraph.StageID`, e.g.
`"register_source_activity"`) via `workflow.ExecuteActivity(ctx, name, req)`;
the worker registers implementations under those same names against Lane A's
contracts and Lane B's PostgreSQL interfaces. Only compact wire types cross
the workflow boundary — `Ref` (an opaque pointer into external storage),
`Status` (`success` / `not_applicable` / `failed`), `StageRequest`, and
`StageResult` — never a file, a raw record, a normalized record, or a
metadata payload; `engine/proffer/workflow_test.go`'s
`TestWireTypesCarryOnlyCompactReferences` proves this by reflecting over
every wire type's fields.

## `vendored/sbv` is a downstream adapter, not the runtime

`vendored/sbv` (the Go SBV project) is a UI and, optionally, a visual client
that talks to this platform's API. It does not own import execution, parser
routing, hashing, or canonical persistence. Per the boundary document's
section 6 (SBV boundary): SBV may keep upload/submit UI, source browsing,
raw/normalized comparison views, search, and progress/failure display; it
gives up in-memory jobs, its own goroutine-based scheduler, its
process-global import mutex, direct hash invocation, and SQLite as an
authority for imports, custody, audit, or canonical records. SBV can be
stopped entirely while an agent starts, observes, and completes an import
through the platform API — the browser is never required for processing.

## One parser contract, every language

Parsers are adapters, not workflows. An existing Go, Python, or JS/TS parser
is wrapped behind one versioned contract (`ParserInput` in, `RawExtractionBundle`
out) and does nothing else: it decodes its declared format, preserves order
and exact locators, reports attachments/failures/unknown spans, and exposes
native metadata it encounters. It never hashes, establishes custody, writes
PostgreSQL, normalizes, deduplicates, enriches, classifies, schedules
fallback/retries, or promotes evidence. There is no parser-specific
workflow: `select_parser_activity` picks one registered adapter by declared
format coverage; `execute_parser_activity` only parses. Reusing an adequate
existing Python (or other-language) parser behind this contract is the
expected path — Go is required for the orchestration runtime, not as a
rewrite mandate for every parser.

## References-only Temporal history

Full parser record arrays, raw rows, and normalized rows never cross
Temporal history. Every Activity result is a compact reference (an ID, a
receipt, a manifest pointer) into immutable storage or PostgreSQL. Large
containers use bounded child workflows or batches; long-running work reports
heartbeats; and history growth is bounded with Continue-As-New rather than
letting a single workflow execution accumulate unbounded event history.
Never one Temporal Activity per record.

`engine/proffer` today: `StageRequest`/`StageResult` already enforce the
references-only contract at the type level, and every stage that can walk or
hash a large source (`retain_original`, `hash_source`,
`inventory_container`, `extract_embedded_metadata`, `hash_raw_records`,
`normalize_generation`, `hash_normalized_records`) carries an explicit
`HeartbeatTimeout`. `hash_raw_generation` does not — it folds already-computed
H2 hex digests, not source bytes, so it is cheap like `hash_normalized_generation`.
`ProfferWorkflow` is a single, fixed 23-stage
run — it does not yet batch per-record work into child workflows or apply
Continue-As-New. The hashing bodies already stream members internally rather
than creating one Activity per record, so record count does not expand
Temporal history; Continue-As-New remains required for future orchestration
loops whose Workflow history itself can grow without bound.

## No parser-specific workflows, no shortcuts

Every source family — messaging, documents, PDFs, email, media, OCR,
archives, whatever comes next — runs through the same 23-stage
`ProfferWorkflow`. No source family gets a shortcut, an alternate
database, a reduced stage set, or a silently skipped stage; a stage that
does not apply to a given source still emits an explicit `not_applicable`
receipt so the gap is visible rather than absent.
