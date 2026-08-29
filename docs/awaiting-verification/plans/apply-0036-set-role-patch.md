# Required root-lane patch: `scripts/apply_0036_live.py` must run under `SET LOCAL ROLE context_owner`

> _Byline: Claude Code · Sonnet 5 · 2026-08-27_

## Why this doc exists instead of a code change

`scripts/apply_0036_live.py` (and `scripts/validate_0036_live.py`) belong to a different/root
work lane. This worktree's task scope is limited to
`scripts/bootstrap_platform_database.py`, `sql/bootstrap/platform_foundation.sql`, and
`tests/test_platform_database_bootstrap.py` — it explicitly does not own the apply/validator
scripts. Per the owner's result-persistence rule, the finding and the exact fix are recorded here
instead of being silently left for someone to rediscover.

## The gap

`scripts/apply_0036_live.py` connects as whatever `DB_USER`/`POSTGRES_USER` resolves from its
secrets file (`~/.secrets/Agno-MCP-Platform.env` or `.env`) and then runs migration 0036's DDL
verbatim:

```python
with psycopg.connect(dsn, password=password, connect_timeout=10) as conn:
    conn.autocommit = False
    with conn.cursor() as cursor:
        cursor.execute("SET LOCAL lock_timeout = '5s'")
        cursor.execute("SET LOCAL statement_timeout = '120s'")
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext('apply-0036-context-import'))")
        ...
        cursor.execute(migration_sql)   # <-- creates `context` schema + all its objects
```

Everything migration 0036 creates (`CREATE SCHEMA context`, every `context.*` table, every
`context.*` function/trigger) ends up **owned by whatever role `DB_USER` resolves to** — not by
`context_owner`, the role `sql/bootstrap/platform_foundation.sql` creates specifically to own
this schema (owner directive, 2026-08-27). `platform_admin` was granted membership in
`context_owner` for exactly this administration purpose, but membership grants nothing about
*new* objects' ownership — only `SET ROLE`/`SET LOCAL ROLE` at creation time does that.

## The fix

Add one line to `scripts/apply_0036_live.py`, inside the same transaction, **after** the advisory
lock is acquired and **before** `cursor.execute(migration_sql)` runs:

```python
cursor.execute("SET LOCAL ROLE context_owner")
```

`SET LOCAL` is transaction-scoped — it resets automatically at `COMMIT`/`ROLLBACK`, so no
`RESET ROLE` is needed and it cannot leak into the second (post-commit, read-only) connection
later in the same script. Every object `migration_sql` creates from that point on is owned by
`context_owner`. The final ledger `INSERT ... created_by, current_user` also then records
`context_owner` as `created_by` for that row, which is the more accurate attribution once the
role switch is in effect — no other change to that statement is needed.

### Precondition this bootstrap already provides

`SET LOCAL ROLE` requires the connecting role to be a **member** of `context_owner` (or be a
superuser). `sql/bootstrap/platform_foundation.sql` does **not** grant `context_owner` to
whatever `DB_USER` resolves to for `apply_0036_live.py` — it only grants it to `platform_admin`.
Root must additionally run, once, before applying 0036:

```sql
GRANT context_owner TO <the role apply_0036_live.py connects as>;
```

(Skip this if that role is already a cluster superuser — superusers can `SET ROLE` to anything
without an explicit grant.) `sql/bootstrap/platform_foundation.sql` also grants `context_owner`
`CREATE ON DATABASE platform`, which is what actually lets a `SET LOCAL ROLE context_owner`
session run `CREATE SCHEMA context` and the table/function DDL inside it — without that grant the
migration would fail with a permission error immediately after the `SET LOCAL ROLE` line, not
silently apply under the wrong owner.

## What this patch does not solve (recorded, not fixed here)

`context.register_raw_format_subtype(...)` (defined in migration 0036) is `SECURITY INVOKER` by
default and runs dynamic `CREATE TABLE`/`CREATE TRIGGER` DDL. When a *runtime* caller (a
`context_import_writer` member, e.g. `platform_runtime`) invokes it later, that DDL executes
**as the caller**, not as `context_owner` — so `context_import_writer` will also need `CREATE` on
the `context` schema (or the function needs `SECURITY DEFINER`) before that runtime path works.
This is a schema-level runtime-ACL question that depends on 0036's actual call pattern and is out
of this bootstrap's scope (which only creates the `context_import_writer`/`context_reader` role
*names* and grants them to `platform_runtime` — see `sql/bootstrap/platform_foundation.sql`'s
header). Flagging it here so it isn't rediscovered cold when the first live import runs.

## Verification once patched

After root applies both the `GRANT context_owner TO <apply_0036_live.py's DB_USER>` and the
`SET LOCAL ROLE` code change, a live (non-`--apply`, i.e. `validate_0036_live.py`) or `--apply`
run's `context` schema objects should show `context_owner` as their owner:

```sql
SELECT nspowner::regrole FROM pg_namespace WHERE nspname = 'context';
SELECT tableowner FROM pg_tables WHERE schemaname = 'context' LIMIT 5;
```

Both should report `context_owner`, not the `DB_USER`/`POSTGRES_USER` identity
`apply_0036_live.py` connects as.
