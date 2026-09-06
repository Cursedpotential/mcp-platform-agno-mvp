# Go document-markdown chunker implementation receipt

> _Byline: Codex · GPT-5 · 2026-08-29._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

## Scope

Implemented the adopted deterministic document-markdown chunk stage as the isolated Go package
`engine/chunk`. This receipt makes no deployment, persistence, Temporal, n8n, or live-service
claim. No parser, extraction, SQL, Workbench, activity, UIW, PostgreSQL adapter, or SBV adapter
file was changed.

## Implemented contract

- `chronology`: cut at dated-entry offsets (`^>\s*\*\s*\*\*`).
- `research_report` and `strategy_memo`: cut at Markdown heading offsets.
- `statute_extract`: retain the whole source when under the configured cap.
- The version-pinned caps are 4,000 Unicode code points for structured variants and 6,000 for
  statute extracts. These preserve the measured 4,969-character statute as one chunk while
  forcing the measured 4,043- and 9,925-character structural units through the lossless fallback.
- Initial ranges are tiled over the entire source; whitespace and separators before a new
  structural unit remain assigned to the preceding chunk. This choice is pinned by
  `chunk.document_markdown.offsets` version `1.0.0`.
- Oversized ranges split at the last paragraph boundary within the cap, then the last line
  boundary, then at a UTF-8-safe hard code-point boundary. The final fallback is deliberately
  lossless even when an indivisible source line exceeds the cap.
- Every non-empty chunk is an original byte slice and carries half-open byte and Unicode
  code-point ranges plus its SHA-256 digest.
- The result carries source and reassembly SHA-256 values and validates contiguous, gap-free,
  non-overlapping full coverage before it is returned.
- `engine/chunk.Registry` is the separate coordinator seam required by parser/chunker atomicity.
  It reuses the established primary/fallback/experimental quality vocabulary, selects by declared
  signature coverage then quality and stable lexical identity, returns an immutable selection
  receipt, and replays only the exact persisted chunker ID/version/quality. Chunk output is never
  stuffed into `RawRecordEnvelope`, and selection does not move into n8n or Python.

## Verification boundary

Focused tests cover every signature policy, pinned separator ownership, paragraph/line fallback,
UTF-8-safe hard fallback, zero-empty behavior, invalid UTF-8 rejection, deterministic replay,
verbatim source slicing, coordinate continuity, and completeness hashes. Go unit tests are local
proof of the isolated capability only, not production deployment proof.
