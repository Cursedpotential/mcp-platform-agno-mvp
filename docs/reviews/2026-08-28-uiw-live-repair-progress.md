# Universal Import live repair progress — retention and custody slice

> _Byline: Codex · GPT-5.6 · 2026-08-28; migration implementation assisted by OpenCode · GLM 5.3 Cloud._
> _Naming: written before the 2026-09-05 rename (D-137..D-141); see docs/NAMING.md for the old->new glossary._

STATUS: PARTIAL — MIGRATIONS_APPLIED; WORKER_DEPLOYMENT_PENDING; N8N_INACTIVE
LIVE_PROOF: RETENTION_PASS_AND_NEW_CUSTODY_BLOCKER_REPRODUCED

## Outcome first

The confirmed production repair cleared both previously known blockers, then exposed and repaired a
third defect in the H1 custody receipt trigger. The owner-facing reject path is not yet certified:
the matching Go query fix still requires commit, push, Coolify deployment, and resumed-run proof.

No case material was used. The run used the repository-owned synthetic SMS Backup & Restore fixture
whose live copy matched SHA-256
`72640c6c2995d7dd89ce01e5757f7ee5ccc5af2945f1faadefc60339b77c9a55`.

## Applied production changes

1. Migration `0039_context_source_retention_lock` applied and independently verified:
   `52d986a1d3cd87d929c5fc868c482539d9d720ef2f5c753d6111f4a4df14c924`.
2. The five deployed Universal Import workflows were changed only at their outbound URL fields.
   Automated before/after comparison proved the node graphs, connections, and two credential bindings
   per workflow were preserved.
3. All five workflows were activated on their new versions. Unauthenticated probes to start, preview,
   decision, select-parser, and execute-parser each returned HTTP 403.
4. Authenticated start through n8n succeeded for workflow
   `uiw-live-reject-20260828-001`, Temporal run
   `01a04abe-b26b-7514-bfc4-5c8287c0f3c5`.
5. Worker evidence proved `register_source_activity`, `retain_original_activity`,
   `capture_filesystem_metadata_activity`, `inventory_container_activity`, and
   `extract_embedded_metadata_activity` advanced. This is the first live proof that migration 0039
   cleared the retain-original blocker.

## Newly observed H1 blocker

`hash_source_activity` then retried with:

```text
commit H1: write H1 receipt: ERROR: function pg_catalog.substring(bytea, bigint, bigint) does not exist
```

The applied 0036 trigger function contained an inline raw-range validation expression using BIGINT
offset/length arguments even though PostgreSQL's BYTEA substring function accepts INTEGER arguments.
The same defect existed in `engine/postgres/hash_repository.go` and would block a later approved run.

The failure occurred while inserting the H1 receipt because PostgreSQL compiled the trigger function's
raw-range statement for the first live invocation; no select-parser or execute-parser n8n execution
occurred. The run never reached `awaiting_decision`, and no approval/rejection signal was sent.

## Migration 0042 repair

Migration `0042_context_hash_bytea_slice` redefines only
`context.guard_hash_receipt_insert()` while preserving the rest of the applied 0036 behavior. The
inline range now fails closed on negative or out-of-INT4 bounds, checks the retained byte length, and
casts both BYTEA substring arguments to `int4`. The Go query carries the same guards and casts.

Verification before production apply:

- `go test ./postgres`: passed;
- `uv run pytest -q tests/test_0042_context_hash_bytea_slice.py`: 9 passed;
- Ruff check and format check: passed;
- rollback-only live validation: passed and restored the prior function definition exactly.

Production apply then completed and independently reconnected successfully:

- migration: `0042_context_hash_bytea_slice`
- committed SQL SHA-256: `87ee74705d9995ddb25ac72fd04853ec971444ec9f9894e5a0dedd2034bac49e`

## Fail-closed residual state

- All five Universal Import n8n workflows were returned to inactive immediately after the custody
  failure was identified.
- The existing Temporal run and activity evidence were preserved; the run was not deleted or
  terminated.
- A Coolify stop was requested for only the Universal Import worker with Docker cleanup disabled, so
  the durable run can resume after the matching worker code is deployed.
- Starter and parser-runtime health checks remained HTTP 200; parser readiness reported 11 parsers.

## Next production gate

1. Commit and push the exact 0039, n8n contract, 0042, Go query, tests, and receipt allowlist.
2. Verify Coolify builds the intended commit for the worker, starter, and parser runtime.
3. Resume the worker and prove the preserved run advances through H1 to `awaiting_decision`.
4. Reactivate the five workflows, submit the rejection signal, and prove
   `execute_parser_activity` never ran.
5. Keep approve-to-publication and same-request idempotency as separate subsequent proofs.
