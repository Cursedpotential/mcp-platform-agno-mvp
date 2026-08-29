# UIW retain-original PostgreSQL privilege fix

> **Status:** APPLIED AND INDEPENDENTLY VERIFIED LIVE
> **Byline:** Codex · GPT-5 · 2026-08-27

## Result

The live `retain_original_activity` failure is caused by the locking semantics of its existing
PostgreSQL query, not by a missing general read grant. The query joins `context.source_version` to
`context.source` and ends with an unqualified `FOR UPDATE`. PostgreSQL therefore requires `UPDATE`
on at least one column of **both** selected tables. Migration 0036 grants lifecycle `UPDATE` on
`source_version`, but deliberately grants no `UPDATE` on immutable `source`.

Migration `0039_context_source_retention_lock` supplies only:

```sql
GRANT UPDATE (id) ON TABLE context.source TO context_import_writer;
```

`platform_runtime` receives that capability only through its existing membership in
`context_import_writer`. It does not receive table-wide `UPDATE`, no sequence privilege is needed,
and `context_reader` receives nothing. The enabled `source_append_only` trigger still rejects every
actual source mutation; the grant exists solely so PostgreSQL can take the row lock used by the
current retain-original transaction.

## Files

- `sql/0039_context_source_retention_lock.sql`
- `scripts/validate_0039_live.py` — executes the migration and exact locking join, proves mutation
  remains blocked, then rolls the entire transaction back and compares the ACL snapshot.
- `scripts/apply_0039_live.py` — explicit `--apply`, advisory lock, migration fingerprint, hashed
  `public.schema_version` receipt, independent post-commit verification.
- `tests/test_0039_context_source_retention_lock.py` — offline least-privilege and safety invariants.

## Required live sequence

Run from the repository root with the established out-of-band PostgreSQL credentials available;
neither script prints them:

```powershell
uv run python scripts/validate_0039_live.py --database platform
uv run python scripts/apply_0039_live.py --apply --database platform
```

Then retry the same failed UIW run or submit the same idempotency coordinate and verify:

1. `retain_original_activity` completes and writes one successful activity receipt;
2. the source version advances only from `registered` to `retained`;
3. the original object membership and `original_object_id` agree;
4. the workflow advances beyond retention without a PostgreSQL permission error;
5. migration `0039` has exactly one active ledger row with the committed SQL SHA-256.

## Recovery boundary

The pre-commit validator always rolls back. After a committed production apply, recovery follows
the repository's forward-fix convention. A direct revoke would reproduce the known production
failure and must not be performed as an automatic rollback.

## Validation receipt

On 2026-08-27, the focused offline suite passed `4/4`. The rollback-only live validator then
executed against database `platform` and reported:

```text
PASS: migration 0039 rolled back; retain-original locking join succeeded and source stayed immutable
```

The post-rollback ACL snapshot matched the preflight snapshot.

## Production apply — 2026-08-28

After owner confirmation, `scripts/apply_0039_live.py --apply --database platform` committed the
forward migration and independently reconnected to verify the narrow grant, immutable-source trigger,
retain-original locking probe, and rich ledger row.

- migration: `0039_context_source_retention_lock`
- committed SQL SHA-256: `52d986a1d3cd87d929c5fc868c482539d9d720ef2f5c753d6111f4a4df14c924`
- observed result: `retain_original_activity` completed on the next synthetic production run
- boundary: this proves the retention-lock repair, not the full Universal Import Workflow
