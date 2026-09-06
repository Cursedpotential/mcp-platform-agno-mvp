# ADR-0048/0049 boundary correction against accepted ADR-0061 — 2026-08-29

> _Byline: Codex · GPT-5 · 2026-08-29_
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

STATUS: DOCUMENTATION RECONCILED — implementation and live verification remain separate.

## Result

ADR-0048 and ADR-0049 remain useful dated records of the SBV streaming-decoder work and the move
toward a common Go-selected parser contract. They no longer define the target application boundary.
Accepted ADR-0061 establishes the current shape:

- Workbench is the unified shell, verified operator-context boundary, and authentication boundary.
- SBV is a storage-free message and pipeline-preview client composed inside Workbench. It owns no
  SQLite/cache authority, local authentication, bespoke ingestion, parser selection, hashing authority,
  or canonical state.
- The Go coordinator selects registered parsers through one coverage/quality contract. Implementations
  may be Go-native or reached through the governed `platform-tools` adapter. Python is not the permanent
  platform orchestrator.
- Temporal is the durable scheduler of load-bearing activities. n8n owns visual integration/agent
  workflow bodies, notifications, and human-facing signals at bounded seams; it starts/signals Temporal
  or is called by a Temporal activity.

## Hash and custody boundary

UIW pre-parse source/raw-record/raw-generation values are context integrity fingerprints. They provide
integrity and reproducibility but create no evidence authority and must not be called custody H1/H2/H3.

Evidence custody begins only at governed promotion. Promotion re-opens the retained original, recomputes
H1, verifies every H2 over the pinned canonical normalized bytes in frozen generation order, and verifies
the platform H3. Dispatch binds the complete canon tuple: algorithm, hash level, canonical byte recipe or
serializer version, ordered membership definition, construction tag, and writer/version. A bare `H3` or
legacy tag is insufficient. `h3-chain-h1genesis-hexconcat-v1` is the platform promotion construction;
`h3-chain-sbv-genesisempty-v1` is a separate import construction and cannot satisfy promotion.

## MMS attachment correction

The claim that the current SBV decoder retains only the first MMS part is stale. Current
`vendored/sbv/internal/sms_xml_importer.go::streamMMSRecord` iterates the parts in the MMS source.
Historical SBV SQLite can still be lossy and is not a migration authority.

The current blocker is the platform adapter boundary:

- `vendored/sbv/pkg/parseonly` has no immutable platform attachment sink/locator and rejects emitted
  attachment artifacts/references.
- `engine/adapters/sbv` truthfully advertises `SupportsAttachments: false`.

Retained source XML remains the re-ingest authority, but re-ingest cannot be declared complete until the
immutable attachment sink/locator is implemented and the live platform read path proves every part.

## Preview identity and API requirement

The composed preview requires UIW-native endpoints for preview state, records, decisions, and events.
They must carry or resolve the UIW workflow ID, source-version reference, and correlated platform run ID
under one verified mapping. A UIW identifier must never be passed to legacy `/v1/records` or legacy
run-event SSE as though equal text established identity. Missing or conflicting correlation fails closed.

## Documentation changes

- ADR-0048 and ADR-0049 now carry prominent partial-supersession boundaries while preserving their
  original dated text.
- The ADR index describes the surviving common-parser decision and the superseded SBV application/
  authority claims.
- The active handoff corrects the custody, orchestration, MMS attachment, and preview-correlation rules.

## Verification boundary

This was a documentation-only reconciliation. It does not prove the attachment sink, UIW-native preview
APIs, correlation enforcement, promotion-time canon dispatcher, deployment, or live behavior. Those
remain implementation and production-verification gates.

