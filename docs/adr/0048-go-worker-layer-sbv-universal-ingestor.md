# ADR-0048: Go worker layer = the SBV universal import engine; messaging lane first (Timeline parked)

- Status: **PROPOSED** — direction chosen by owner 2026-08-09 ("Option B"); awaiting sign-off on
  this written scope before implementation.
- Date: 2026-08-09
- _Byline: Claude Code · Fable 5 · 2026-08-09_
- Records (retroactively) the July decision that never got an ADR, plus the 2026-08-09 direction.

## Context

A 5-day claude.ai conversation (~2026-07-22→26; export:
`C:\Users\matts\Downloads\Claude_export_Explaining complex topics simply_6b19dce6-….md`) settled
how Go phases into the platform. Because it never landed in an ADR, the decision went missing
until recovered from session logs on 2026-08-09. Locked shape from that conversation:

- **Go is NOT the orchestrator.** Agno/Python remains the reasoning + orchestration layer
  permanently. Go is the parallel **worker/muscle** layer for deterministic, CPU-bound,
  embarrassingly-parallel grind, invoked via manifest table / subprocess / HTTP.
- Target architecture: **one Go streaming ingestor core** (streaming decode, bounded memory,
  fan-out, manifest wiring) with **pluggable per-format decoders** — not one binary per format.
- Ranked ports at the time: (1) TraceIQ Timeline JSON ETL, (2) Zone 1→2 ingest hasher,
  (3) bulk pattern scan.

Since then, the SBV app (Go, `vendored/sbv`) was extended into the **universal import engine +
governed repair slice** (PR #18, `aacf21c`): a registry of pluggable `Importer` implementations
(`internal/importer.go:142` — `Format/Priority/Detect/Run`), an engine owning identity, H1/H2/H3
custody hashing, storage, dedup, and reconciliation (`internal/engine.go`), with ~10 message
formats already plugged in (SMS/MMS XML, NDJSON, CSV, iMessage TXT/HTML, Facebook JSON, Google
Chat, Google Voice, EML/MBOX). Exploration 2026-08-09 confirms the engine is genuinely
format-agnostic (`kind` is open-ended; `metadata` is lossless catch-all), and its streaming
patterns are proven at multi-GB scale (128 KiB bounded MMS base64 streaming).

**Owner corrections recorded 2026-08-09:**
- The R2 custody-hashing worker (`perf(r2)` commits) is for **deduplication + original-file
  integrity only** — it is NOT the platform processing-integrity mechanism and did not replace
  the ingest-hasher port.
- Platform processing integrity is intended as **three-level caching once data hits the
  platform**, handled through **Semantica or Postgres — explicitly undecided** ("or PG, I don't
  know"). That is an OPEN question, out of scope here; do not treat either as locked.

## Decision

**Option B — generalize SBV.** The merged SBV universal import engine IS the "one Go streaming
ingestor core" from the July plan. New evidence formats are added as decoder modules to it; we do
NOT stand up a separate Go binary. Agno/Python remains orchestrator (unchanged).

~~**First new decoder: Google Timeline/Takeout location JSON**~~ **CORRECTED 2026-08-09 (owner,
emphatic): Timeline is PARKED.** The Timeline task has been iterated ~87 times across ~14 agents
over the past year; the owner is explicitly not ready to cross that bridge, and no agent should
propose Timeline work until the owner raises it. **The near-term decoder/engine work serves the
MESSAGING lane** (the standing queue order: messaging lane first, Timeline after — see the
`takeout-timeline-next-integration` memory, which already said this). The Timeline scope below is
retained as a parked reference only.

## Scope (from the 2026-08-09 structural exploration)

One new file `internal/google_timeline_importer.go` (~400–430 LOC total incl. tests), zero
changes to engine, storage, or API:

1. `Run()`: incremental JSON stream-parse of the `locations: [...]` array (json.Decoder token
   walk; per-object bound like `maxLineRecordBytes`), emitting one `SourceRecord` per location —
   `kind="location"`, raw object bytes as the H2 input, `OccurredAt` from timestampMs,
   format-specific fields lossless in `Metadata` (~150–200 LOC).
2. `Detect()`: conservative — filename pattern (`Location History.json` / Records.json) AND
   structural keys (`locations`, `timestampMs`) (~30 LOC).
3. Registration: `init()` + format constant (~5 LOC). Auto-picked-up by `/api/imports`.
4. Tests: fixture + streaming/bounded-memory test following `sms_xml_importer_test.go`'s
   io.Pipe pattern (~150 LOC).

**Flagged, accepted as-is:** H3 chain is order-sensitive by design; Google exports are not
guaranteed monotonic, so re-exports may produce different chains for "the same" history —
forensic fidelity, not a bug; document it in `UNIVERSAL_IMPORTS.md`.

## Consequences

- Every future evidence format (Takeout mbox variants, more messaging exports, media manifests)
  is a decoder module against a core we already trust — no new projects.
- SBV remains **shadow/comparison-grade** for SMS provenance (de1ca9f gate,
  `SBV_PRIMARY_ENABLED`); this ADR does not change that. Whether Timeline imports run SBV-primary
  or shadow is decided at deploy time by the same flag discipline.
- The three-level platform caching / processing-integrity design (Semantica vs PG) is a
  **separate future ADR** — blocked on owner decision.
- TraceIQ (Python) is not retired by this ADR; it becomes a candidate for mining/retirement only
  after the decoder is proven ([[mine-before-retiring]]).

## Alternatives considered

- Separate Go binary for Timeline (July plan's original #1) — rejected 2026-08-09: the merged
  SBV engine already provides streaming core, custody hashing, storage, dedup, reconciliation,
  and a repair lane; a second binary duplicates all of it.
- Porting TraceIQ wholesale — rejected: same reasons; the decoder replaces only the parse/ETL
  seam.
