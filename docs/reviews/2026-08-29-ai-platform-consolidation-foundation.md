# Receipt — AI → Platform Consolidation Foundation

> _Byline: Codex · GPT-5.6 · 2026-08-29 · v3 acceptance hardening_

## Result

Implemented a non-destructive, platform-only consolidation proof foundation. No live data was
copied, no caller was changed, and the legacy `ai` database was not mutated or parked.

## Files

- `sql/0049_ai_platform_consolidation_foundation.sql`
- `scripts/audit_ai_platform_consolidation.py`
- `tests/test_0049_ai_platform_consolidation_foundation.py`
- `docs/awaiting-verification/AI-TO-PLATFORM-CONSOLIDATION-2026-08-29.md`
- this receipt

## Corrections made

- Preserved applied migration `0046`; all correction is forward-only in `0049`.
- Removed the proposal to disable append-only/custody triggers during copy.
- Removed mutation/cutover claims from this slice.
- Made retained `ai` state and a later read-only park explicit; no delete path exists.

## Structural guarantees

- Exact `platform` current-database guard.
- Safe `platform_admin` role guard.
- Immutable checkpoint and proof-receipt tables.
- Statement-level `TRUNCATE` rejection in addition to row UPDATE/DELETE rejection.
- A verified checkpoint names one exact deferred proof receipt of its required proof kind. The
  receipt must be passing, unsuperseded, non-empty, and bound to the same phase, relation,
  source/target transaction snapshots, snapshot hashes, manifest hash, and repository revision.
- Row-parity verification requires equal non-null row counts. Caller verification additionally
  binds the exact external fence-attestation ID, digest, establishment time, and expiry.
- A receipt bound to a verified checkpoint cannot later be superseded; corrections require a new
  immutable checkpoint attempt. An immutable receipt-claim row keyed by receipt ID makes verified
  binding and supersession mutually exclusive at the database unique-key layer, including when
  competing transactions begin before either can see the other's row.
- Migration-owned functions use versioned names and plain `CREATE FUNCTION`. A namespace preflight
  rejects any pre-existing consolidation table or function rather than replacing it.
- Idempotent phase/relation/attempt and receipt proof keys.
- No runtime write grants.
- Repeatable-read, read-only source/target transactions with a bounded statement timeout.
- Caller-drain success requires database quiescence, zero static runtime references, and at least
  one authenticated `ai-platform-caller-fence-v2` HMAC attestation from an explicitly trusted key.
  The signed payload binds the repository revision; both database names, OIDs, snapshot hashes,
  system identifier, server address/port and postmaster start; separate source/target writer counts
  and admission fences; issuance/establishment/expiry times; and Coolify, n8n, and Temporal checks.
- Static scanning covers nested dotenv variants, root and nested `compose.*.yaml`, Dockerfiles,
  PowerShell, JSON/JSONC, INI/config/properties, Terraform, TOML, JS/TS, Python, Go, shell, XML,
  YAML, and workflow configuration. The auditor path is explicitly excluded from its own scan.
- Role inventory includes database privileges and direct memberships; the migration rejects any
  LOGIN role inheriting `platform_admin`.
- Deterministic FK-derived copy manifest with cycle disclosure and explicit per-database transaction
  snapshot, WAL LSN, observation time, database OID, server identity fields, and independent hashes.
- Partition-aware logical copy order (physical children remain inventoried, not double-copied).
- No auditor mutation mode and no secret or source-row output.

## Verification

```text
uv run ruff check scripts/audit_ai_platform_consolidation.py tests/test_0049_ai_platform_consolidation_foundation.py
All checks passed!

uv run pytest -q tests/test_0049_ai_platform_consolidation_foundation.py -k "not pg18"
9 passed, 1 deselected
```

The current PostgreSQL 18 behavior test additionally covers wrong-kind and unbound receipts,
immutable claim creation and mutation rejection, attempted supersession of a bound receipt, and
pre/post state for all three migration relations. Its current-code rerun remains pending restoration
of the disposable `platform_migration_test` service credential in this shell. Earlier PG18 receipts
predate these assertions and are not current-revision proof. The test remains rollback-only and
reconnects to compare pre/post relation state, so a successful run leaves no net database write.

## Not claimed

- no live PostgreSQL apply;
- no data-copy rehearsal;
- no full-suite or live integration result;
- no caller drain, Coolify deployment, cutover, or `ai` park;
- no production completion.
