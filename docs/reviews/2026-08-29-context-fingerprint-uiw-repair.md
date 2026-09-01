# Context fingerprint / UIW repair receipt — 2026-08-29

> _Byline: Codex · GPT-5 · 2026-08-29_

STATUS: IMPLEMENTED AND LOCALLY VERIFIED

BUILD_STATUS: SCOPED PASS (all owned Go packages pass tagged test/vet; contract and migration suites pass, including rollback-only apply and fail-closed catalog-shape proofs against the disposable PostgreSQL 18 service. The repository-wide tagged Go run is currently blocked by a concurrent SBV attachment-lane interface mismatch outside this lane.)

LIVE_STATUS: NOT APPLIED OR DEPLOYED — production migration, Temporal replay against captured history, Coolify deployment, and live PostgreSQL/UIW verification remain required gates.

## Result

R02 intake now uses one non-custody vocabulary across UIW scheduling, Activity
bodies, repository reads/writes, JSON contracts, and the 0036 PostgreSQL schema:

| Layer | Source | Raw record | Raw generation |
|---|---|---|---|
| Activity | `fingerprint_source_activity` | `fingerprint_raw_records_activity` | `fingerprint_raw_generation_activity` |
| Receipt kind | `context_source_fingerprint` | `context_raw_record_fingerprint` | `context_raw_generation_fingerprint` |
| Construction | `context-source-fingerprint-v1` | `context-rawrecord-fingerprint-v1` or `context-rawspan-fingerprint-v1` | `context-rawgen-fingerprint-chain-v1` |

These values are integrity fingerprints. They are not custody H1/H2/H3; custody
begins at the owner-promotion boundary.

## Defects closed

- UIW now passes the canonical `context_source_fingerprint` and
  `raw_fingerprint_manifest` reference keys end to end.
- Raw verification accepts the old `h1` key only as a conflict-checked replay
  alias and otherwise requires the canonical key.
- PostgreSQL recomputation and receipt verification query the three context
  fingerprint kinds, including the canonical raw fingerprint receipt-set key.
- Raw rows use context-specific record/span constructions; the active R02 path
  no longer writes custody H2 canons.
- The v1 hash-receipt schema, example, and negative fixtures now describe the
  same five R02 computations as the Go implementation.
- The abandoned first draft of migration 0045 was confirmed never applied and
  structurally incompatible with 0036. Its exact source is preserved at
  `to_be_deleted/sql/0045_context_fingerprint_semantics.broken-historical-20260829.sql`;
  the live 0045 slot is now a transactional, non-mutating, fail-closed
  supersession guard. Migration `0048_context_fingerprint_uiw_repair.sql` is
  the governed fix-forward against the actual 0036 tables, inline checks,
  raw-row construction column, indexes, reconciliation JSON check, and trigger
  functions. The numbered 0045 -> 0048 platform sequence is no longer blocked
  by references to nonexistent registry/custody objects.
- Temporal compatibility is explicit: `workflow.GetVersion` preserves the old
  three Activity command names for existing histories, the worker registers
  exactly three replay adapters, and new executions schedule only canonical
  fingerprint names. The legacy raw-manifest and source-ref keys are translated
  at the compatibility boundary.
- Legacy retries preserve the original Activity name through
  `context.activity_execution`, its idempotency coordinate, `computed_by`, and
  the legacy raw receipt-set result reference. Corrected context semantics do
  not rewrite immutable Temporal execution provenance.
- Raw/source verification reopens and hashes every retained raw member and the
  retained original source. It no longer refolds stored receipt digests or
  echoes the source fingerprint into both sides of the comparison. Missing or
  truncated external bytes and a missing governed object opener fail closed.
  Direct executable Go tests now cover deterministic success, corrupt source,
  corrupt raw member, truncated external range, and missing opener behavior.
- Preview rejection is a durable `rejected` hold state. A later approval Signal
  resumes the same workflow identity only after carrying an explicit repaired
  parser-selection or parser-options reference. The repaired references are
  surfaced in the preview query and passed to `execute_parser_activity`.
  Temporal `GetVersion` preserves replay behavior for histories recorded before
  repair-reference enforcement; timeout remains terminal and fail-closed.
- The published v1 schema remains backward compatible: legacy H1/H2/H3-shaped
  v1 receipts still decode, while new writes use context-fingerprint names.
- Migration 0048 now has transaction boundaries, target/role/relation/function
  prerequisites, pinned function search paths, trigger-safe relabeling, and
  explicit least-privilege ACL repair. Its one catalog-derived 0036 function
  rewrite now fails closed before dynamic execution if `search_path` is already
  configured or the expected `LANGUAGE plpgsql` clause is not present exactly
  once; this prevents silently rewriting an independently changed function.

## Verification

Executed from `engine/` after remediation:

- `go test -tags fts5 ./activities ./postgres ./stagegraph ./temporal ./uiw ./uiwworker`
  — PASS
- `go vet -tags fts5 ./activities ./postgres ./stagegraph ./temporal ./uiw ./uiwworker`
  — PASS
- `go test -tags fts5 ./...` — BLOCKED outside this lane: the concurrent
  SBV attachment lane is mid-signature migration. Its tests still call the old
  one-argument `NewFilesystemArtifactSink` and two-argument `ArtifactDir`, while
  the concurrent implementation now requires a registrar and source reference.
  This lane did not edit or revert any SBV-owned file.

Executed from repository root:

- `uv run python contracts/import/v1/self_validate.py` — PASS: 13/13 meta-schemas,
  12/12 examples, 1/1 legacy-v1 compatibility fixture, 10/10 negative cases
- `uv run pytest -q tests/test_0048_context_fingerprint_uiw_repair.py` — PASS: 7,
  SKIP: 2 when run without the optional PostgreSQL service setting
- `PLATFORM_0048_TEST_SERVICE=platform_migration_test uv run pytest -q
  tests/test_0048_context_fingerprint_uiw_repair.py` — PASS: 9 against
  PostgreSQL 18.1. Both migration application and the deliberately
  preconfigured-function refusal path ran inside forced rollbacks; the latter
  proves that catalog text with `SET search_path TO ...` is rejected before
  `EXECUTE`.
- `uv run pytest -q tests/test_0045_context_fingerprint_semantics.py` — PASS: 4;
  proves the live slot is transactional/non-mutating/guarded and the broken
  historical source remains preserved outside the migration chain
- `uv run pytest -q tests/test_0045_context_fingerprint_semantics.py tests/test_0048_context_fingerprint_uiw_repair.py tests/test_temporal_skeleton.py`
  — PASS: 51, SKIP: 1 (the same unavailable PG18 rollback service)
- `git diff --check` — PASS (line-ending notices only; no whitespace errors)

The tests include new-workflow scheduling, forced `workflow.DefaultVersion`
legacy scheduling, immutable legacy execution identity, exact worker
registration (23 canonical + 3 replay aliases), canonical/legacy reference
handling, conflicting alias rejection, rejected-state query, refusal of a
post-rejection approval without repair references, repaired-reference execution
on same-workflow resume, direct retained-byte recomputation failure modes, and
canonical/legacy repository receipt-set parsing.

## Required live gates

1. Apply the guarded 0045 supersession and migration 0048, in order, to the
   intended `platform` PostgreSQL database through the governed deployment path;
   confirm constraints, trigger definitions, relabeled rows, indexes, and
   raw-generation sealing with catalog queries.
2. Replay at least one captured pre-change open `UniversalImportWorkflow`
   history with the production worker build; the unit test forces the same
   default-version branch but is not a captured-history proof.
3. Deploy through Coolify and run the mandatory live integration suite plus one
   real UIW import through raw verification/seal.

No Docker/Compose service was started, no canonical database was modified, and
no deployment was attempted in this repair lane. The existing disposable
PostgreSQL 18 rehearsal database was exercised only inside forced rollbacks;
its credential was held transiently in the test process and was not printed or
persisted by this lane.
