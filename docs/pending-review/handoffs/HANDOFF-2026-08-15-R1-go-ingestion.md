# HANDOFF — R1 Go Ingestion and Parallelization (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_
STATUS: PARTIAL
BUILD_STATUS: UNKNOWN

## Verified-live state (do not re-derive)

| Thing | State |
|---|---|
| Go subtree | `vendored/sbv` contains format importers, universal engine, custody package, tests, and viewer/API code |
| Stream contract | Importers consume `bufio.Reader`; H1/H2/H3 streaming support and bounded record logic exist |
| Production concurrency | `RunImportSequential` uses a global mutex because progress and legacy SQLite behavior are shared |
| Routing decision | Owner/canon require coverage-based routing, never size-based routing |
| Test command | `go test -tags fts5 ./...`; plain tests are invalid for DB-backed coverage |

## Findings / work done

- The Go lane is mature work, not a replaceable prototype: SMS XML, NDJSON, ChatGPT, Facebook, Google Chat/Voice, email, CSV, HTML, and text importers are present.
- The universal engine owns ordered custody, rejection/dedup accounting, reconciliation, and immutable import identity.
- Safe parallelism must preserve decoder encounter order and ordered H3 folding.
- Recommended pipeline: ordered decode/hash → bounded workers → bounded reorder buffer → ordered commit.
- Per-import progress must replace the global singleton before concurrent production imports are enabled.

## UNRESOLVED (mandatory)

- Full golden-corpus status per format and provenance of the latest uncommitted Go work.
- Safe concurrency ceiling for SQLite WAL and attachment conversion.
- Which transformations are independently parallelizable without materializing large raw records.

## Pending owner decisions

- Adopt bounded ordered parallelism — WHAT: parallelize normalization/repair while serializing source decode and commit · WHY: retain custody determinism and gain throughput · APPROACHES: whole-import goroutines, per-record workers, or process-level sharding · SHORTCOMINGS: reorder buffering and cancellation are more complex. Recommendation: bounded per-record pipeline plus limited concurrent imports.

## Next steps (work in order)

1. Inventory decoder coverage and golden fixtures.
2. Benchmark current sequential memory/throughput.
3. Specify versioned Go→platform record/rejection/summary envelopes.
4. Replace global progress with per-import state.
5. Implement bounded workers and ordered committer behind a feature flag.
6. Prove sequential/parallel equivalence for records, hashes, and reconciliation.

## Owner working-style contract

- Preserve Go coverage; no size thresholds; never hard-delete; verify hashes and counts before success claims.
