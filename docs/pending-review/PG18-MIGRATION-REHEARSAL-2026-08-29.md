# PostgreSQL 18 migration rehearsal — 0045, 0047, and 0048

> _Byline: Codex · GPT-5 · 2026-08-29_

STATUS: PASS — 0045, 0047, and 0048 apply and roll back cleanly on PostgreSQL 18. The 0047
integration harness now authenticates its behavior section as `platform_runtime`, so its
`session_user` authorization guard is exercised rather than bypassed by the scratch superuser.

## Target and safety boundary

- Disposable Coolify PostgreSQL container:
  `horizon-swift-scratch-pg-v2-yrhzg9ksyr8sjko1yg44qvgc`.
- Database: disposable `platform`; no production database was mutated.
- Server: `PostgreSQL 18.1 (Debian 18.1-1.pgdg12+2)`.
- Connection: libpq service `platform_migration_test` over an SSH local forward. The password was
  loaded only into the test process and was neither written here nor printed.
- Every migration execution was stripped of its outer `BEGIN`/`COMMIT`, executed in a caller-owned
  transaction, and forcibly rolled back.

## Results

### Static plus rollback suite

Command:

```text
uv run pytest -q tests/test_0047_content_chunk_and_context_thread_foundation.py tests/test_0048_context_fingerprint_uiw_repair.py tests/test_0045_context_fingerprint_semantics.py
```

Result: **32 passed, 1 deselected in 3.51s**. The deselected test was the 0047 test marked
`integration`; repository default marker selection excludes it unless `-m integration` is explicit.
This run did execute `test_0048_pg18_rollback_apply_when_service_is_available`, proving the guarded
0045 -> 0048 sequence reaches PostgreSQL 18 and rolls back.

Explicit 0048 rollback test:

```text
1 passed in 1.16s
```

The test executes the non-mutating 0045 supersession body followed by 0048, checks the installed
context-fingerprint vocabulary and guarded function search path, then rolls the transaction back.

### Explicit 0047 integration test

The first execution failed before behavior checks because the schema-only scratch composition had
lost production ownership: `timeline.event_candidate`, `working`, and `timeline` were owned by the
dumping scratch role. The disposable database was corrected to the intended topology:

- `timeline.event_candidate` owner: `platform_admin`
- `working` schema owner: `platform_admin`
- `timeline` schema owner: `platform_admin`
- `context` schema owner remained `context_owner`

That was a scratch-fixture correction only; no migration/source file changed.

After the correction, 0047 applied completely, runtime could create and read the queued review
case, but the checked-in test failed at its expected denial:

```text
FAILED test_pg18_rollback_role_and_review_lifecycle_behavior
Failed: DID NOT RAISE psycopg.errors.RaiseException
```

The cause is precise: `working.guard_context_review_case_insert()` correctly checks
`pg_has_role(session_user, 'context_review_adjudicator', 'MEMBER')`; the test connects as the scratch
superuser and calls `SET LOCAL ROLE platform_runtime`, which changes `current_user` but not
`session_user`. A PostgreSQL superuser is treated as having every role, so this harness can never
exercise the denial it asserts.

A rollback-only control probe used `SET SESSION AUTHORIZATION platform_runtime`, matching the real
login identity. It proved:

```text
session_user=platform_runtime
current_user=platform_runtime
initial_open_queue=1
terminal_close_denied=True
```

The transaction was rolled back. Post-failure probes confirmed representative 0047 relations
`working.context_review_case` and `timeline.event_candidate_source_range` remained absent, proving
the failed rehearsals did not leave partial schema state.

The bounded harness repair now performs that identity transition directly in the checked-in test,
asserts both `session_user` and `current_user` before/after the transition, resets session
authorization before the remaining ACL checks, and leaves the migration's `session_user` guard
unchanged.

Post-repair results:

```text
uv run pytest -q -m integration tests/test_0047_content_chunk_and_context_thread_foundation.py::test_pg18_rollback_role_and_review_lifecycle_behavior
1 passed in 2.69s

uv run pytest -q -m "integration or not integration" tests/test_0047_content_chunk_and_context_thread_foundation.py tests/test_0048_context_fingerprint_uiw_repair.py tests/test_0045_context_fingerprint_semantics.py
33 passed in 5.40s
```

## Required follow-up

1. **Completed in this rehearsal:** the 0047 integration harness now uses
   `SET SESSION AUTHORIZATION platform_runtime` for the runtime section and restores the migration
   session afterward. The migration remains unchanged.
2. Make the disposable baseline builder preserve/recreate schema and prerequisite relation
   ownership. A `--no-owner` schema clone can pass prerequisite existence checks but silently make
   later `GRANT` statements no-ops when `platform_admin` lacks ownership/grant option.
3. **Completed in this rehearsal:** explicit 0047 integration and the complete three-file suite
   both pass with integration tests included.

## Release blocker: split `ai` and `platform` prerequisites

The rehearsal could not be built from the current live `platform` database alone. Current
`platform` supplies the new `context` foundation, while the older `ai` database still owns the
`working`, `timeline`, `evidence`, `analysis`, `ops`, and `reference` prerequisites required by
0047. The disposable rehearsal therefore had to compose a schema-only copy of legacy `ai` with the
current `platform.context` schema.

That split is a release defect, not a target architecture. Before applying 0047 in production,
those prerequisite schemas must be consolidated into canonical `platform` with preserved IDs,
foreign keys, custody/provenance clocks, role ownership, and caller cutover proof. The old `ai`
database can be parked read-only only after parity and zero-caller verification.
