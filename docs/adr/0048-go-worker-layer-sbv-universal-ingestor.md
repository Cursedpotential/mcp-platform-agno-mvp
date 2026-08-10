# ADR-0048: Go worker layer = the SBV universal import engine; messaging lane first (Timeline parked)

- Status: ~~**PROPOSED** — direction chosen by owner 2026-08-09 ("Option B"); awaiting sign-off on
  this written scope before implementation.~~
  **ACCEPTED / REALIZED — corrected 2026-08-10.** The PROPOSED status was misleading: it implied
  the whole ADR was unbuilt and blocked on sign-off. It is not. This ADR has two halves and they
  are in different states:
  - **The architecture (Option B) is DONE and in production.** The SBV universal import engine
    landed in PR #18 (`aacf21c`, 2026-08-06) — `vendored/sbv/internal/{importer,engine,custody}.go`
    plus **nine** working decoder modules already built against it (`sms_xml`, `facebook_json`,
    `google_chat`, `google_voice_html`, `messaging_csv`, `messaging_html`, `messaging_txt`,
    `ndjson`, `email`), with `universal_engine_test.go` covering the core. Nothing is waiting on
    sign-off; the messaging lane already ships on this architecture.
  - **The unbuilt part is Google Takeout — and it is PARKED, not pending approval.** Confirmed
    with the owner 2026-08-10: **Timeline JSON and Takeout are pushed out the same way; the rest
    of this ADR is complete.** `internal/google_timeline_importer.go` was confirmed absent from
    the tree 2026-08-10. The "Scope" section below is a parked reference only — do not read it as
    queued work, and do not propose new Takeout work until the owner raises it.
    **Precision added 2026-08-10 (my earlier wording here was too broad):** parking applies to
    *remaining* Takeout work, chiefly Timeline — it does **not** un-ship Takeout decoders that
    already exist. `google_chat` emits `format = "takeout-messages-json"`
    (`google_chat_importer.go:212`); `google_voice_html` and `mbox` are registered and live.
  — _Claude Code · Opus 5 · 2026-08-10_
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
  is a decoder module against a core we already trust — no new projects. **Note (2026-08-10): the
  Takeout examples here are PARKED work, not a queue.** Timeline JSON and remaining Takeout work
  are pushed out by owner directive. Already-shipped Takeout decoders (`google_chat`,
  `google_voice_html`, `mbox`) are unaffected and stay live.
- **Widened by ADR-0049 (2026-08-10, PROPOSED):** the owner's target is SBV as the universal
  parser for **all** parsing — including AI chats — with the repair layer in Go and the SBV app's
  functional GUI retained. ADR-0049 inventories the gap. Until it is signed, this ADR remains the
  operative statement and SBV stays a messaging/email engine.
- ~~SBV remains **shadow/comparison-grade** for SMS provenance (de1ca9f gate,
  `SBV_PRIMARY_ENABLED`); this ADR does not change that. Whether Timeline imports run SBV-primary
  or shadow is decided at deploy time by the same flag discipline.~~
  **CORRECTED 2026-08-10 — this bullet was already stale when written.** SBV is the
  **PRIMARY** SMS-XML parser, not shadow. The 2026-08-02 demotion (`de1ca9f`) set an explicit
  restore condition — import-scoped reads — and PR #18 (`aacf21c`, merged 2026-08-06) delivered
  exactly that, which promoted SBV back. Authority: `docs/DECISION_LOG.md` D-040 (decided
  2026-08-05, backfilled 2026-08-09). Confirmed in live code: `_sbv_enabled()`
  (`server/tools/parsers/messaging/sbv_sms.py:361`) gates only on `SBV_SERVICE_PASS`, and
  **`SBV_PRIMARY_ENABLED` no longer exists anywhere in `server/`** — `sms_xml.py` is now the
  pure-Python *fallback*, not the effective primary. Timeline-import parser selection therefore
  follows normal capability resolution, not a demotion flag.
  — _Claude Code · Opus 5 · 2026-08-10_
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
