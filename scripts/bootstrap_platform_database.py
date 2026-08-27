"""scripts/bootstrap_platform_database.py — safe, repeatable bootstrap for a fresh `platform`
PostgreSQL 18 database, alongside the untouched, existing `ai` database.

WHY: the platform is adding a second database (`platform`) without disturbing `ai` (owner
directive). This script creates/verifies exactly what sql/0036_context_import_foundation.sql
builds on: platform_admin (LOGIN-less DB owner), platform_runtime (the LOGIN application
identity), context_owner (the intended owner of the `context` schema 0036 creates),
context_import_writer/context_reader (NOLOGIN group roles granted to platform_runtime), the
minimal extension set, PUBLIC's CONNECT/TEMPORARY revoked, and a public.schema_version ledger
table shaped to match scripts/apply_0036_live.py's own read/write contract exactly (confirmed by
reading that file — see sql/bootstrap/platform_foundation.sql's header). It never drops, renames,
or otherwise mutates `ai` or any other database, and never mutates anything at all unless
`--apply` is passed (default: dry-run/plan only).

psycopg only — no local `psql`/PostgreSQL-client-tools dependency. Every statement, including
sql/bootstrap/platform_foundation.sql itself, runs through a psycopg connection's cursor, the
same pattern scripts/apply_0036_live.py and scripts/validate_0036_live.py already use for
migration 0036 (a whole multi-statement SQL file passed to one parameterless `cursor.execute()`
call — Postgres's own parser handles the dollar-quoted `DO $$ ... $$` bodies inside it correctly,
same as `psql -f` would).

Safety model:
  - Only `--database platform` is ever accepted — not merely "anything not on a deny-list".
    `ai`, `postgres`, `template0`, `template1`, and any other name are refused outright
    (`guard_target_database`), matching scripts/apply_0036_live.py's own "only 'platform' is
    accepted" contract so the two scripts can never target different databases.
  - No mutation happens without `--apply`; the default run only reads (pg_database/pg_roles/
    pg_auth_members/public.schema_version) and prints a plan.
  - `platform_runtime` never receives SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS —
    sql/bootstrap/platform_foundation.sql states this explicitly (not merely CREATE ROLE
    defaults), and `gather_live_state()` walks platform_runtime's FULL transitive role-membership
    closure (`pg_auth_members`, recursively) so a dangerous attribute reachable only via an
    inherited membership is caught too, not just a direct attribute on the role itself. If a live
    cluster already has any of this, this script REFUSES rather than silently tightening or
    loosening it (`runtime_role_violates_safety`).
  - `platform_runtime`'s LOGIN password is set ONLY under `--apply`, ONLY from the
    `PLATFORM_DATABASE_PASSWORD` environment variable (or `.env`, same trust boundary as the
    admin DB_* credentials below), via a safely quoted psycopg SQL literal — never
    interpolated into a printed string, never written to any file, never logged. A missing value
    refuses before any connection is attempted.
  - Before ANY mutation, `classify_state()` must find the foundation ledger row either absent or
    matching the file on disk. A DRIFTED state (recorded `ddl_hash` for
    `migration_id = '0000_platform_foundation'` does not match sql/bootstrap/platform_foundation.sql
    on disk) refuses outright — never silently re-applied or overwritten.
  - `ai` presence is itself checked as a sanity guard: if the connected host has no `ai`
    database at all, that means the wrong host was targeted, not that `ai` should be created.
  - After `--apply` runs, this script re-reads live state with fresh connections
    (`gather_live_state`) and checks every invariant (`verify_invariants`) before printing
    anything claiming success — an apply that "ran without error" is not the same claim as
    "verified correct", and only the latter is ever printed.
  - Admin connection credentials (DB_HOST/DB_USER/DB_PASS/DB_PORT) are read from existing secret
    sources (`.env`, process environment — the same contract as server/core/url.py) and are never
    printed; `ConnectionSettings.describe()` redacts the password.

Usage:
    uv run python scripts/bootstrap_platform_database.py                  # plan only (default)
    uv run python scripts/bootstrap_platform_database.py --host <ip>      # plan against a host
    PLATFORM_DATABASE_PASSWORD=... uv run python scripts/bootstrap_platform_database.py \
        --host <ip> --apply                                              # perform it

Exit codes: 0 = success or clean no-op dry run; 1 = refused (wrong target database, drift, `ai`
missing, runtime-safety violation, missing password); 2 = hard error (connection/query failure,
or post-apply verification failed).
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-27

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional, Sequence

import psycopg
from psycopg import sql as psycopg_sql

REPO = pathlib.Path(__file__).resolve().parents[1]
FOUNDATION_SQL = REPO / "sql" / "bootstrap" / "platform_foundation.sql"
CONTEXT_IMPORT_SQL = REPO / "sql" / "0036_context_import_foundation.sql"
APPLY_0036_SCRIPT = REPO / "scripts" / "apply_0036_live.py"
DOTENV = REPO / ".env"

PLATFORM_ADMIN_ROLE = "platform_admin"
PLATFORM_RUNTIME_ROLE = "platform_runtime"
CONTEXT_OWNER_ROLE = "context_owner"
CONTEXT_IMPORT_WRITER_ROLE = "context_import_writer"
CONTEXT_READER_ROLE = "context_reader"
TARGET_DATABASE = "platform"
FOUNDATION_MIGRATION_ID = "0000_platform_foundation"
RUNTIME_PASSWORD_ENV = "PLATFORM_DATABASE_PASSWORD"
DEFAULT_EXTENSIONS: tuple[str, ...] = ("pgcrypto",)
PROTECTED_DATABASES = frozenset({"ai", "postgres", "template0", "template1"})
assert TARGET_DATABASE not in PROTECTED_DATABASES  # self-check: the one accepted name must be safe

_EXTENSION_RE = re.compile(r"CREATE EXTENSION IF NOT EXISTS\s+(\w+)", re.IGNORECASE)
_DOTENV_RE = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$")
_RECOGNIZED_ENV_KEYS = ("DB_USER", "DB_PASS", "DB_HOST", "DB_PORT", RUNTIME_PASSWORD_ENV)

# Walks the FULL transitive role-membership closure starting at the named role (included via the
# base case) and reports whether any role reached — the role itself or anything it is, directly
# or indirectly, a member of — holds a dangerous attribute. Membership does not automatically
# exercise another role's SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS, but a member can always
# `SET ROLE`/`SET SESSION AUTHORIZATION` into a role it belongs to and exercise it explicitly —
# so a dangerous attribute anywhere in the closure is a real, not merely theoretical, risk.
_TRANSITIVE_DANGEROUS_ATTRIBUTES_SQL = """
WITH RECURSIVE closure AS (
    SELECT oid FROM pg_roles WHERE rolname = %s
    UNION
    SELECT m.roleid
    FROM pg_auth_members m
    JOIN closure c ON c.oid = m.member
)
SELECT bool_or(r.rolsuper OR r.rolcreatedb OR r.rolcreaterole OR r.rolreplication OR r.rolbypassrls)
FROM closure c
JOIN pg_roles r ON r.oid = c.oid
"""

# grantee = 0 is Postgres's representation of the PUBLIC pseudo-role in an aclitem. A freshly
# created database has a NULL datacl, which means "the built-in default ACL applies" (PUBLIC
# CONNECT + TEMPORARY included) — acldefault('d', owner) reproduces that default explicitly so
# this query gives the right answer both before and after the REVOKE below.
_PUBLIC_DATABASE_PRIVILEGE_COUNT_SQL = """
SELECT count(*)
FROM pg_database d, aclexplode(coalesce(d.datacl, acldefault('d', d.datdba))) a
WHERE d.datname = %s AND a.grantee = 0 AND a.privilege_type IN ('CONNECT', 'TEMPORARY')
"""


class BootstrapState(Enum):
    """Where the target database's foundation ledger stands relative to disk."""

    NOT_BOOTSTRAPPED = "not_bootstrapped"
    UP_TO_DATE = "up_to_date"
    DRIFTED = "drifted"


@dataclass(frozen=True)
class ConnectionSettings:
    """Admin-capable Postgres connection parameters, resolved from existing secret sources.

    Never render `password` directly — use `describe()` for any printed/logged form. No SQLAlchemy
    URL/driver string: psycopg connects via a keyword DSN, matching scripts/apply_0036_live.py.
    """

    host: str
    port: str
    user: str
    password: str

    def describe(self, database: str) -> str:
        """Human-readable connection target with the password redacted."""
        return f"postgresql://{self.user}:***@{self.host}:{self.port}/{database}"

    def dsn(self, database: str) -> str:
        return f"host={self.host} port={self.port} dbname={database} user={self.user}"


@dataclass(frozen=True)
class LedgerRow:
    migration_id: str
    ddl_hash: bytes
    status: str


@dataclass(frozen=True)
class LiveState:
    """Snapshot of what already exists, gathered by read-only introspection.

    Built by `gather_live_state()` against a real cluster, or directly in tests — every field
    here comes from a SELECT, never a mutation. `Optional[bool]` fields are `None` when the
    thing they describe (usually a role) does not exist yet, so there is nothing to check.
    """

    ai_database_exists: bool
    target_database_exists: bool
    target_database_owner: Optional[str]
    admin_role_exists: bool
    runtime_role_exists: bool
    runtime_role_login: Optional[bool]
    runtime_role_or_memberships_dangerous: Optional[bool]
    context_owner_role_exists: bool
    admin_is_context_owner_member: bool
    context_owner_has_create_on_database: bool
    context_import_writer_role_exists: bool
    context_reader_role_exists: bool
    runtime_is_context_import_writer_member: bool
    runtime_is_context_reader_member: bool
    public_has_connect_or_temp: Optional[bool]
    schema_version_table_exists: bool
    schema_version_active_unique_index_exists: bool
    ledger_row: Optional[LedgerRow]


@dataclass(frozen=True)
class PlanStep:
    name: str
    already_satisfied: bool
    detail: str = ""


@dataclass(frozen=True)
class VerificationResult:
    ok: bool
    failures: tuple[str, ...]


def _load_env_values(env: Optional[dict[str, str]] = None) -> dict[str, str]:
    """`.env` provides defaults; real environment variables win — same precedence
    scripts/capture_bootstrap_ddl.py already uses. Only a fixed, recognized key set is read from
    the process environment (never the whole environment), so unrelated env vars are never
    mistaken for trusted DB/secret config.
    """
    resolved: dict[str, str] = {}
    if DOTENV.exists():
        for line in DOTENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = _DOTENV_RE.match(line)
            if m:
                resolved[m.group(1)] = m.group(2).strip("\"'")
    process_env = os.environ if env is None else env
    for key in _RECOGNIZED_ENV_KEYS:
        if key in process_env:
            resolved[key] = process_env[key]
    return resolved


def load_connection_settings(
    target_host: Optional[str] = None, env: Optional[dict[str, str]] = None
) -> ConnectionSettings:
    """Resolve admin-capable Postgres connection settings from existing secret sources.

    Mirrors server/core/url.py's env-var contract (DB_USER/DB_PASS/DB_HOST/DB_PORT) so this
    script authenticates the same way the application does, instead of inventing a parallel
    credential path.

    Parameters
    ----------
    target_host:
        Explicit host override (CLI `--host`); takes precedence over `DB_HOST`.
    env:
        Environment mapping to read instead of the real process environment (tests only).

    Returns
    -------
    ConnectionSettings
    """
    values = _load_env_values(env)
    return ConnectionSettings(
        host=target_host or values.get("DB_HOST", "localhost"),
        port=values.get("DB_PORT", "5432"),
        user=values.get("DB_USER", "ai"),
        password=values.get("DB_PASS", "ai"),
    )


def require_runtime_password(env: Optional[dict[str, str]] = None) -> str:
    """Resolve `platform_runtime`'s LOGIN password — required only when `--apply` runs.

    Raises
    ------
    ValueError
        If `PLATFORM_DATABASE_PASSWORD` is not set in `.env` or the process environment. The
        message never echoes a value (there is none to echo when it's missing, and the function
        never logs it when present either).
    """
    values = _load_env_values(env)
    password = values.get(RUNTIME_PASSWORD_ENV)
    if not password:
        raise ValueError(
            f"{RUNTIME_PASSWORD_ENV} must be set (in .env or the process environment) to --apply "
            f"— it becomes {PLATFORM_RUNTIME_ROLE!r}'s LOGIN password and is required only for "
            "the apply path, never for the default dry run"
        )
    return password


def guard_target_database(name: str) -> None:
    """Refuse any `--database` value other than the exact accepted target.

    Raises
    ------
    ValueError
        If `name` is not exactly `TARGET_DATABASE` (`'platform'`). Mirrors
        scripts/apply_0036_live.py's own "only 'platform' is accepted" contract — this bootstrap
        and that migration-apply script must always agree on exactly one target database name,
        not merely both avoid a deny-list.
    """
    if name != TARGET_DATABASE:
        raise ValueError(
            f"refusing --database {name!r} — this script bootstraps exactly {TARGET_DATABASE!r} "
            f"and nothing else ({sorted(PROTECTED_DATABASES)} included)"
        )


def foundation_checksum(path: pathlib.Path = FOUNDATION_SQL) -> bytes:
    """SHA-256 digest (raw bytes) of the foundation SQL file.

    Raw bytes, not a hex string: this is stored/compared directly against
    `public.schema_version.ddl_hash`, a BYTEA column — the exact shape
    scripts/apply_0036_live.py already reads and writes. Use `.hex()` on the result for display.
    """
    return hashlib.sha256(path.read_bytes()).digest()


def discover_required_extensions(path: pathlib.Path = CONTEXT_IMPORT_SQL) -> tuple[str, ...]:
    """Extensions the platform foundation should cover, per sql/0036 if it exists yet.

    Reads the real file live rather than hardcoding its contents, so a future revision that adds
    a `CREATE EXTENSION` is caught automatically. Falls back to `DEFAULT_EXTENSIONS` (this
    bootstrap's own minimal requirement, also what sql/bootstrap/platform_foundation.sql ships)
    when the file is absent.

    Parameters
    ----------
    path:
        Path to sql/0036_context_import_foundation.sql (overridable for tests).

    Returns
    -------
    tuple[str, ...]
        Extension names in first-seen order, lowercased, deduplicated.
    """
    if not path.exists():
        return DEFAULT_EXTENSIONS
    text = path.read_text(encoding="utf-8", errors="ignore")
    found = tuple(dict.fromkeys(m.group(1).lower() for m in _EXTENSION_RE.finditer(text)))
    return found or DEFAULT_EXTENSIONS


def missing_extensions(required: Sequence[str], covered: Sequence[str] = DEFAULT_EXTENSIONS) -> tuple[str, ...]:
    """Extensions in `required` (e.g. discovered from sql/0036) that `covered` does not ship.

    Informational only — this script never auto-applies an extension it did not already ship
    in sql/bootstrap/platform_foundation.sql; see that file's header for why.
    """
    covered_set = {e.lower() for e in covered}
    return tuple(e for e in required if e.lower() not in covered_set)


def classify_state(existing: Optional[LedgerRow], expected_digest: bytes) -> BootstrapState:
    """Decide whether the foundation is unapplied, up to date, or drifted.

    Parameters
    ----------
    existing:
        The active `public.schema_version` row for `FOUNDATION_MIGRATION_ID`, if the target
        database, the table, and an active row all already exist; `None` if any of those is
        missing.
    expected_digest:
        `foundation_checksum()` of the SQL file on disk right now.

    Returns
    -------
    BootstrapState
        `NOT_BOOTSTRAPPED` if there is no recorded row yet, `UP_TO_DATE` if the recorded
        `ddl_hash` matches the file on disk, `DRIFTED` if it does not — a drifted database must
        never be silently re-applied or overwritten by this script.
    """
    if existing is None:
        return BootstrapState.NOT_BOOTSTRAPPED
    if existing.ddl_hash == expected_digest:
        return BootstrapState.UP_TO_DATE
    return BootstrapState.DRIFTED


def runtime_role_violates_safety(state: LiveState) -> bool:
    """True only if `platform_runtime` (or anything it is, directly or transitively, a member
    of) currently holds SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS.

    `state.runtime_role_or_memberships_dangerous` is `None` when the role does not exist yet
    (nothing to violate) and `False` when the whole transitive closure is clean — both count as
    safe. This script never grants any of those attributes itself (see
    sql/bootstrap/platform_foundation.sql); a live `True` here means something else did, and
    `main()` refuses rather than silently tightening or loosening it.
    """
    return state.runtime_role_or_memberships_dangerous is True


def build_plan(state: LiveState, extension_gap: Sequence[str]) -> list[PlanStep]:
    """Compute the ordered, human-readable bootstrap plan for `TARGET_DATABASE`.

    Pure function — no I/O. Every step reports whether it is already satisfied so the default
    dry run shows exactly what `--apply` would (and would not) do.

    Parameters
    ----------
    state:
        Current live state, from `gather_live_state()` or a test fixture.
    extension_gap:
        Extensions sql/0036 will need beyond this bootstrap's own coverage — informational only,
        never auto-applied (see `discover_required_extensions` / `missing_extensions`).

    Returns
    -------
    list[PlanStep]
    """
    violates = runtime_role_violates_safety(state)
    steps = [
        PlanStep(
            "verify `ai` database is present and untouched",
            already_satisfied=state.ai_database_exists,
            detail="present" if state.ai_database_exists else "MISSING — wrong host? investigate before proceeding",
        ),
        PlanStep(f"create role {PLATFORM_ADMIN_ROLE!r} (NOLOGIN)", already_satisfied=state.admin_role_exists),
        PlanStep(
            f"create role {PLATFORM_RUNTIME_ROLE!r} "
            "(LOGIN, NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS)",
            already_satisfied=state.runtime_role_exists,
            detail=f"password set separately from {RUNTIME_PASSWORD_ENV} on every --apply run",
        ),
        PlanStep(
            f"verify {PLATFORM_RUNTIME_ROLE!r} and its role memberships "
            "holds no SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS",
            already_satisfied=not violates,
            detail="" if not violates else "VIOLATION — refuse until reconciled manually",
        ),
        PlanStep(f"create role {CONTEXT_OWNER_ROLE!r} (NOLOGIN)", already_satisfied=state.context_owner_role_exists),
        PlanStep(
            f"grant {CONTEXT_OWNER_ROLE!r} to {PLATFORM_ADMIN_ROLE!r}",
            already_satisfied=state.admin_is_context_owner_member,
        ),
        PlanStep(
            f"create role {CONTEXT_IMPORT_WRITER_ROLE!r} (NOLOGIN)",
            already_satisfied=state.context_import_writer_role_exists,
        ),
        PlanStep(f"create role {CONTEXT_READER_ROLE!r} (NOLOGIN)", already_satisfied=state.context_reader_role_exists),
        PlanStep(
            f"grant {CONTEXT_IMPORT_WRITER_ROLE!r} to {PLATFORM_RUNTIME_ROLE!r}",
            already_satisfied=state.runtime_is_context_import_writer_member,
        ),
        PlanStep(
            f"grant {CONTEXT_READER_ROLE!r} to {PLATFORM_RUNTIME_ROLE!r}",
            already_satisfied=state.runtime_is_context_reader_member,
        ),
        PlanStep(
            f"create database {TARGET_DATABASE!r} (OWNER {PLATFORM_ADMIN_ROLE})",
            already_satisfied=state.target_database_exists,
        ),
        PlanStep(
            f"grant CREATE ON DATABASE {TARGET_DATABASE!r} to {CONTEXT_OWNER_ROLE!r}",
            already_satisfied=state.context_owner_has_create_on_database,
        ),
        PlanStep(
            f"revoke CONNECT/TEMPORARY on database {TARGET_DATABASE!r} from PUBLIC",
            already_satisfied=state.public_has_connect_or_temp is False,
            detail="" if state.public_has_connect_or_temp is False else "PUBLIC still has CONNECT/TEMPORARY",
        ),
        PlanStep(
            "apply sql/bootstrap/platform_foundation.sql (extensions + public.schema_version active ledger row)",
            already_satisfied=state.ledger_row is not None,
        ),
        PlanStep(
            "public.schema_version has its unique-active-migration_id index",
            already_satisfied=state.schema_version_active_unique_index_exists,
        ),
    ]
    if extension_gap:
        steps.append(
            PlanStep(
                "sql/0036_context_import_foundation.sql needs extensions beyond this bootstrap",
                already_satisfied=False,
                detail=f"gap: {', '.join(extension_gap)} — not applied here; reconcile once 0036 lands",
            )
        )
    return steps


def verify_invariants(state: LiveState, expected_digest: bytes) -> VerificationResult:
    """Re-check every safety/shape invariant against freshly re-read live state.

    Pure function over a `LiveState` snapshot — `main()` calls `gather_live_state()` again after
    `apply_bootstrap()` returns and passes the fresh result here before printing anything that
    claims success. "The apply ran without raising" is not "verified correct"; only this
    function's `ok=True` is.
    """
    failures: list[str] = []
    if not state.ai_database_exists:
        failures.append("`ai` database is missing")
    if not state.target_database_exists:
        failures.append(f"{TARGET_DATABASE!r} database is missing")
    elif state.target_database_owner != PLATFORM_ADMIN_ROLE:
        failures.append(
            f"{TARGET_DATABASE!r} owner is {state.target_database_owner!r}, expected {PLATFORM_ADMIN_ROLE!r}"
        )
    if not state.admin_role_exists:
        failures.append(f"{PLATFORM_ADMIN_ROLE!r} role is missing")
    if not state.runtime_role_exists:
        failures.append(f"{PLATFORM_RUNTIME_ROLE!r} role is missing")
    elif state.runtime_role_login is not True:
        failures.append(f"{PLATFORM_RUNTIME_ROLE!r} is not LOGIN")
    if runtime_role_violates_safety(state):
        failures.append(f"{PLATFORM_RUNTIME_ROLE!r} (or an inherited membership) holds a dangerous attribute")
    if not state.context_owner_role_exists:
        failures.append(f"{CONTEXT_OWNER_ROLE!r} role is missing")
    if not state.admin_is_context_owner_member:
        failures.append(f"{PLATFORM_ADMIN_ROLE!r} is not a member of {CONTEXT_OWNER_ROLE!r}")
    if not state.context_owner_has_create_on_database:
        failures.append(f"{CONTEXT_OWNER_ROLE!r} lacks CREATE on {TARGET_DATABASE!r}")
    if not state.context_import_writer_role_exists:
        failures.append(f"{CONTEXT_IMPORT_WRITER_ROLE!r} role is missing")
    if not state.context_reader_role_exists:
        failures.append(f"{CONTEXT_READER_ROLE!r} role is missing")
    if not state.runtime_is_context_import_writer_member:
        failures.append(f"{PLATFORM_RUNTIME_ROLE!r} is not a member of {CONTEXT_IMPORT_WRITER_ROLE!r}")
    if not state.runtime_is_context_reader_member:
        failures.append(f"{PLATFORM_RUNTIME_ROLE!r} is not a member of {CONTEXT_READER_ROLE!r}")
    if state.public_has_connect_or_temp is not False:
        failures.append("PUBLIC still has CONNECT/TEMPORARY on the target database")
    if not state.schema_version_table_exists:
        failures.append("public.schema_version is missing")
    if not state.schema_version_active_unique_index_exists:
        failures.append("public.schema_version lacks its unique-active-migration_id index")
    if state.ledger_row is None:
        failures.append(f"no active public.schema_version row for migration_id={FOUNDATION_MIGRATION_ID!r}")
    elif state.ledger_row.ddl_hash != expected_digest:
        failures.append("public.schema_version active ddl_hash does not match the file on disk")
    return VerificationResult(ok=not failures, failures=tuple(failures))


# --------------------------------------------------------------------------------------------
# process execution — everything below here opens a real psycopg connection. Kept separate from
# the pure functions above so tests can exercise plan/state/drift/verification logic without one.


def pg_connect(settings: ConnectionSettings, database: str, *, autocommit: bool = True) -> psycopg.Connection[Any]:
    """Open a psycopg connection, matching scripts/apply_0036_live.py's own dsn/password style."""
    conn = psycopg.connect(settings.dsn(database), password=settings.password, connect_timeout=10)
    conn.autocommit = autocommit
    return conn


def _scalar(cur: psycopg.Cursor[Any]) -> Any:
    """The single column of the single row a just-executed SELECT is expected to return.

    Every call site here follows a query (SELECT count(*), SELECT bool_or(...), SELECT
    rolcanlogin ... WHERE rolname = <a role just confirmed to exist>, etc.) that always yields
    exactly one row — the assertion documents that expectation and gives mypy a concrete,
    non-Optional value to index instead of `fetchone()`'s `Any | None`.
    """
    row = cur.fetchone()
    assert row is not None, "expected exactly one row from a scalar query"
    return row[0]


def gather_live_state(settings: ConnectionSettings) -> LiveState:
    """Read-only introspection of the current cluster/`TARGET_DATABASE` state.

    Every query here is a SELECT — nothing is created, altered, or dropped. Safe to call before
    deciding whether `--apply` is even warranted, and called again after `apply_bootstrap()` to
    verify it (see `verify_invariants`).
    """
    with pg_connect(settings, "postgres") as conn, conn.cursor() as cur:
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", ("ai",))
        ai_exists = cur.fetchone() is not None

        cur.execute("SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = %s", (TARGET_DATABASE,))
        row = cur.fetchone()
        target_exists = row is not None
        target_owner = str(row[0]) if row else None

        def role_exists(name: str) -> bool:
            cur.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (name,))
            return cur.fetchone() is not None

        def is_member(member: str, role: str) -> bool:
            if not (role_exists(member) and role_exists(role)):
                return False
            cur.execute("SELECT pg_has_role(%s, %s, 'MEMBER')", (member, role))
            return bool(_scalar(cur))

        admin_exists = role_exists(PLATFORM_ADMIN_ROLE)
        runtime_exists = role_exists(PLATFORM_RUNTIME_ROLE)
        context_owner_exists = role_exists(CONTEXT_OWNER_ROLE)
        writer_exists = role_exists(CONTEXT_IMPORT_WRITER_ROLE)
        reader_exists = role_exists(CONTEXT_READER_ROLE)

        admin_in_context_owner = is_member(PLATFORM_ADMIN_ROLE, CONTEXT_OWNER_ROLE)
        runtime_in_writer = is_member(PLATFORM_RUNTIME_ROLE, CONTEXT_IMPORT_WRITER_ROLE)
        runtime_in_reader = is_member(PLATFORM_RUNTIME_ROLE, CONTEXT_READER_ROLE)

        runtime_login: Optional[bool] = None
        runtime_dangerous: Optional[bool] = None
        if runtime_exists:
            cur.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname = %s", (PLATFORM_RUNTIME_ROLE,))
            runtime_login = bool(_scalar(cur))
            cur.execute(_TRANSITIVE_DANGEROUS_ATTRIBUTES_SQL, (PLATFORM_RUNTIME_ROLE,))
            dangerous_value = _scalar(cur)
            runtime_dangerous = bool(dangerous_value) if dangerous_value is not None else False

        context_owner_can_create = False
        if context_owner_exists and target_exists:
            cur.execute("SELECT has_database_privilege(%s, %s, 'CREATE')", (CONTEXT_OWNER_ROLE, TARGET_DATABASE))
            context_owner_can_create = bool(_scalar(cur))

        public_access: Optional[bool] = None
        if target_exists:
            cur.execute(_PUBLIC_DATABASE_PRIVILEGE_COUNT_SQL, (TARGET_DATABASE,))
            public_access = _scalar(cur) > 0

    schema_version_table_exists = False
    schema_version_index_exists = False
    ledger_row: Optional[LedgerRow] = None
    if target_exists:
        with pg_connect(settings, TARGET_DATABASE) as conn, conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.schema_version') IS NOT NULL")
            schema_version_table_exists = bool(_scalar(cur))
            if schema_version_table_exists:
                cur.execute(
                    "SELECT indexdef FROM pg_indexes WHERE schemaname = 'public' "
                    "AND tablename = 'schema_version' AND indexdef ILIKE %s",
                    ("%status = 'active'%",),
                )
                schema_version_index_exists = cur.fetchone() is not None
                cur.execute(
                    "SELECT ddl_hash, status FROM public.schema_version WHERE migration_id = %s",
                    (FOUNDATION_MIGRATION_ID,),
                )
                for ddl_hash, status in cur.fetchall():
                    if status == "active":
                        ledger_row = LedgerRow(FOUNDATION_MIGRATION_ID, bytes(ddl_hash), status)
                        break

    return LiveState(
        ai_database_exists=ai_exists,
        target_database_exists=target_exists,
        target_database_owner=target_owner,
        admin_role_exists=admin_exists,
        runtime_role_exists=runtime_exists,
        runtime_role_login=runtime_login,
        runtime_role_or_memberships_dangerous=runtime_dangerous,
        context_owner_role_exists=context_owner_exists,
        admin_is_context_owner_member=admin_in_context_owner,
        context_owner_has_create_on_database=context_owner_can_create,
        context_import_writer_role_exists=writer_exists,
        context_reader_role_exists=reader_exists,
        runtime_is_context_import_writer_member=runtime_in_writer,
        runtime_is_context_reader_member=runtime_in_reader,
        public_has_connect_or_temp=public_access,
        schema_version_table_exists=schema_version_table_exists,
        schema_version_active_unique_index_exists=schema_version_index_exists,
        ledger_row=ledger_row,
    )


# Only what MUST happen before TARGET_DATABASE exists (platform_admin must exist first so
# `CREATE DATABASE ... OWNER platform_admin` has an owner to name). Every other role, grant,
# revoke, and the schema_version ledger itself live solely in platform_foundation.sql and are
# applied by executing that file verbatim once connected to TARGET_DATABASE — see the module
# docstring for why duplicating them here would violate DRY for no safety benefit.
_PLATFORM_ADMIN_BOOTSTRAP_SQL = (
    "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'platform_admin') "
    "THEN CREATE ROLE platform_admin NOLOGIN; END IF; END $$;"
)


def apply_bootstrap(settings: ConnectionSettings, expected_digest: bytes, runtime_password: str) -> None:
    """Perform the actual mutations.

    Only ever called under `--apply`, and only after `main()` has confirmed via
    `classify_state()` that the target is `NOT_BOOTSTRAPPED` or `UP_TO_DATE` — never `DRIFTED`.
    `main()` re-reads live state and calls `verify_invariants()` after this returns; this
    function's success alone is never presented as "verified".
    """
    with pg_connect(settings, "postgres") as conn, conn.cursor() as cur:
        cur.execute(_PLATFORM_ADMIN_BOOTSTRAP_SQL)
        cur.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TARGET_DATABASE,))
        if cur.fetchone() is None:
            cur.execute(
                psycopg_sql.SQL("CREATE DATABASE {} OWNER {}").format(
                    psycopg_sql.Identifier(TARGET_DATABASE), psycopg_sql.Identifier(PLATFORM_ADMIN_ROLE)
                )
            )

    with pg_connect(settings, TARGET_DATABASE) as conn, conn.cursor() as cur:
        cur.execute(FOUNDATION_SQL.read_text(encoding="utf-8"))
        # PostgreSQL utility statements such as ALTER ROLE do not accept
        # extended-protocol bind parameters. Quote the password with
        # psycopg's Literal adapter; never interpolate it ourselves or log
        # the resulting statement.
        cur.execute(
            psycopg_sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(
                psycopg_sql.Identifier(PLATFORM_RUNTIME_ROLE),
                psycopg_sql.Literal(runtime_password),
            )
        )
        cur.execute(
            "INSERT INTO public.schema_version "
            "(version_label, applies_to, ddl_uri, ddl_hash, migration_id, status, notes, created_by) "
            "VALUES (%s, %s, %s, %s, %s, 'active', %s, current_user) "
            "ON CONFLICT (migration_id) WHERE status = 'active' DO NOTHING",
            (
                FOUNDATION_MIGRATION_ID,
                TARGET_DATABASE,
                "sql/bootstrap/platform_foundation.sql",
                expected_digest,
                FOUNDATION_MIGRATION_ID,
                "Applied by scripts/bootstrap_platform_database.py --apply.",
            ),
        )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", help="Override DB_HOST (default: .env/environment, matching server/core/url.py)")
    ap.add_argument(
        "--database",
        default=TARGET_DATABASE,
        help=f"Database to bootstrap; only {TARGET_DATABASE!r} is accepted",
    )
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Perform the bootstrap. Without this flag, only reads live state and prints the plan (default).",
    )
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        guard_target_database(args.database)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    runtime_password: Optional[str] = None
    if args.apply:
        try:
            runtime_password = require_runtime_password()
        except ValueError as exc:
            print(f"REFUSED: {exc}", file=sys.stderr)
            return 1

    settings = load_connection_settings(target_host=args.host)
    print(f"target cluster: {settings.describe(TARGET_DATABASE)}")

    extension_gap = missing_extensions(discover_required_extensions())
    if CONTEXT_IMPORT_SQL.exists():
        print("sql/0036_context_import_foundation.sql found — cross-checked its CREATE EXTENSION list")
    else:
        print(
            "sql/0036_context_import_foundation.sql not present in this checkout yet (owned by a "
            "different lane) — using this bootstrap's own minimal extension set"
        )

    try:
        state = gather_live_state(settings)
    except psycopg.Error as exc:
        print(f"ERROR: could not read live state — {exc}", file=sys.stderr)
        return 2

    if not state.ai_database_exists:
        print(
            "REFUSED: the existing `ai` database was not found on this host. This script never "
            "creates, repairs, or assumes away `ai` — check --host before proceeding.",
            file=sys.stderr,
        )
        return 1

    if runtime_role_violates_safety(state):
        print(
            f"REFUSED: {PLATFORM_RUNTIME_ROLE!r} (or an inherited membership) already holds "
            "SUPERUSER/CREATEDB/CREATEROLE/REPLICATION/BYPASSRLS on this cluster. This script "
            "never grants any of those and will not silently revoke them either — reconcile "
            "manually (a deliberate ALTER ROLE / REVOKE) before re-running.",
            file=sys.stderr,
        )
        return 1

    expected_digest = foundation_checksum()
    status = classify_state(state.ledger_row, expected_digest)

    plan = build_plan(state, extension_gap)
    print("\nPlan:")
    for step in plan:
        marker = "already satisfied" if step.already_satisfied else "PENDING"
        suffix = f" ({step.detail})" if step.detail else ""
        print(f"  [{marker}] {step.name}{suffix}")
    print(f"\nfoundation checksum on disk: {expected_digest.hex()[:12]}...")
    print(f"state: {status.value}")

    if status is BootstrapState.DRIFTED:
        print(
            "\nREFUSED: public.schema_version's active row for "
            f"migration_id={FOUNDATION_MIGRATION_ID!r} records a different ddl_hash than "
            "sql/bootstrap/platform_foundation.sql on disk right now — the file changed after "
            "being applied, or a different bootstrap was recorded under this migration_id. "
            "Reconcile manually; this script will not overwrite a drifted database.",
            file=sys.stderr,
        )
        return 1

    if not args.apply:
        print("\nDry run only (pass --apply to perform the PENDING steps above). No mutation was attempted.")
        return 0

    assert runtime_password is not None  # guaranteed by the --apply branch above
    apply_bootstrap(settings, expected_digest, runtime_password)

    try:
        post_state = gather_live_state(settings)
    except psycopg.Error as exc:
        print(f"ERROR: apply completed but post-apply state could not be re-read — {exc}", file=sys.stderr)
        return 2

    verification = verify_invariants(post_state, expected_digest)
    if not verification.ok:
        print("ERROR: apply completed but post-apply verification FAILED:", file=sys.stderr)
        for failure in verification.failures:
            print(f"  - {failure}", file=sys.stderr)
        return 2

    print(
        f"\nAPPLIED AND VERIFIED: every role/grant/database/ledger invariant was re-read after "
        f"apply and confirmed. {PLATFORM_ADMIN_ROLE}/{PLATFORM_RUNTIME_ROLE}/{CONTEXT_OWNER_ROLE}/"
        f"{CONTEXT_IMPORT_WRITER_ROLE}/{CONTEXT_READER_ROLE} correct, {TARGET_DATABASE!r} "
        f"bootstrapped, active ledger row recorded for {FOUNDATION_MIGRATION_ID!r}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
