# Matter/CourtCase Foundation — Pre-Mortem (2026-08-15)

> _Byline: Codex · GPT-5 · 2026-08-15_

STATUS: BUILT, HELD, UNAPPLIED

## Decision implemented

The existing text Knowledge/horizon partition remains `primary`. The new
case-management layer models an enduring `Matter` separately from one or more
`CourtCase` proceedings. `analysis.matter_knowledge_partition` is the explicit
anti-corruption bridge between those concepts.

Migration `sql/0030_matter_case_foundation.sql` is additive. It leaves the
legacy UUID `analysis.evidence_item.case_id` untouched and adds nullable,
paired `matter_id` and `court_case_id` columns for the new contract.

## Pre-mortem failures and controls

| Failure | Consequence | Control in 0030 | Residual risk |
|---|---|---|---|
| Treat `primary` as a CourtCase UUID | Knowledge isolation and horizon filters drift | Dedicated TEXT `partition_key` bridge; no spine type change | Documentation must keep the distinction explicit |
| Evidence points across matters | Confidentiality and case-integrity breach | Composite CourtCase/Matter and EvidenceItem-scope foreign keys | API authorization remains mandatory |
| Retry creates duplicate evidence | Review queue and exhibits silently duplicate | Unique request key and canonical source-pointer hash | Pointer serialization must remain versioned/canonical |
| Ranked Knowledge text lacks custody provenance | Context or memory is misrepresented as evidence | Insert guard verifies the normalized record partition plus custody hash/source/file/run chain | API must still fail closed before attempting promotion |
| Promoted evidence starts court-ready | Unreviewed material leaks into exports | Insert guard requires unreviewed, HITL-required, unauthenticated, unsafe EvidenceItem state | Later review changes remain governed by the existing review model |
| Promotion history is edited | Evidentiary audit trail becomes indefensible | Append-only `working.forbid_mutation()` trigger | Superuser operation remains an architectural risk |
| Seed invents personal docket facts | False court metadata becomes canonical | Neutral `Primary matter` / `Primary proceeding`; docket fields remain NULL | Owner must fill actual proceeding metadata later |
| Migration is applied ahead of held Wave 1 | Schema history and deployment order diverge | HELD/UNAPPLIED banner; no deploy/apply action in this task | Release coordinator must promote 0026-0029 first |
| Generated baseline is hand-edited | Bootstrap no longer represents verified live schema | Baseline is untouched | Regeneration remains required after eventual live apply |

## Rollback plan

- Validation defaults to static checks and never opens a database connection.
- Optional database validation requires an explicitly labeled scratch,
  development, or staging target, strips the migration's own transaction
  controls, and always rolls back. It refuses a target where 0030 objects
  already exist, so it cannot be mistaken for an upgrade or production apply.
- The rollback-only path now builds a synthetic Source → FileNode → H1 hash →
  ProcessingRun → NormalizedRecord → EvidenceItem chain. It proves the default
  unsafe state, request and source-pointer dedupe, append-only protection,
  cross-matter bridge denial, and provenance mismatch rejection before rollback.
- After rollback it rechecks that all 0030 relations are absent and that the
  synthetic source marker was not retained.
- Production is rejected by the validator.
- Before activation, a failed application rolls back the outer transaction.
- After promotion rows exist, do not drop the ledger. Disable the write route,
  preserve the records, and supersede the schema additively after owner review.

## Validation evidence

Fresh local verification on 2026-08-15:

- `uv run ruff check scripts/_matter_validate_0030.py tests/test_matter_migration.py`
  — PASS.
- `uv run ruff format --check scripts/_matter_validate_0030.py tests/test_matter_migration.py`
  — PASS.
- `uv run python scripts/_matter_validate_0030.py` — PASS (static contract;
  no database connection).
- `uv run pytest -q tests/test_matter_migration.py` — **11 passed**.

The strengthened path was executed against a new isolated PostgreSQL **18.4**
cluster using `tests/fixtures/matter_0030_prerequisites.sql`. The first run
correctly rolled back after exposing an ambiguous JSON parameter type in the
validator; the harness was fixed with an explicit `::text` cast. The second run
passed the complete migration/promotion contract and reported **zero net
write**. A post-run probe confirmed the server was stopped.

The stopped cluster is retained, never deleted, at
`to_be_deleted/matter-validation-pg/` for owner-controlled disposal. This proves
PostgreSQL execution against the purpose-built minimal prerequisite schema; it
does not replace later replay against a full restored baseline or deployed
services.

A subsequent empty-database numbered-chain probe failed at the canonical
boundary, `0008_temporal_clocks_and_provenance.sql`, because
`evidence.source` is an out-of-band historical object. This matches
`sql/README.md`: 0001→0030 is not a bootstrap path. The experimental harness
was moved—not deleted—to
`to_be_deleted/_matter_validate_full_chain_failed-probe-20260815.py`.
Full release proof must restore `sql/bootstrap/schema_baseline.sql` in an image
with pg_duckdb, PostGIS, and pgvector, then replay 0026–0030 in order.

A second clean scratch database then ran
`scripts/_matter_validate_repository.py`. It applied the fixture and migration
inside one outer transaction and exercised the **real** repository source
resolution, evidence promotion, retry idempotency, evidence listing, and atomic
`ops.audit_ledger` write. The complete repository/audit proof passed with zero
net writes; the outer transaction removed both fixture and migration objects.

No database migration was persisted or applied to a shared/deployed database;
no deployment, baseline edit, push, or production mutation was performed.
