"""scripts/bootstrap_platform_database.py — safe, repeatable bootstrap for a fresh `platform`
PostgreSQL 18 database, alongside the untouched, existing `ai` database.

WHY: the platform is adding a second database (`platform`) without disturbing `ai` (owner
directive — see this script's originating task). This script creates/verifies exactly the
pieces sql/0036_context_import_foundation.sql builds on: the `platform_admin`, `platform_runtime`,
and `context_owner` roles (with `context_owner` granted to `platform_admin`), the minimal
extension set, and a `public.schema_version` ledger table — nothing more. It never drops,
renames, or otherwise mutates `ai` or any other database, and it never mutates anything at all
unless `--apply` is passed (default: dry-run/plan only).

sql/0036_context_import_foundation.sql now exists (Codex · GPT-5 · 2026-08-26); this script's
`discover_required_extensions()` still reads it live rather than trusting a point-in-time note, so
a future revision that adds a `CREATE EXTENSION` is caught automatically. The platform-DB
apply/validator scripts remain a different work lane's ownership and are untouched here.

Safety model:
  - `ai`, `postgres`, `template0`, `template1` can never be the target database
    (`guard_target_database`) — this script only ever creates/verifies a NEW database.
  - No mutation happens without `--apply`; the default run only reads (pg_database/pg_roles/
    public.schema_version) and prints a plan.
  - `platform_runtime` never receives SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS — the foundation
    SQL states this explicitly (not merely relies on CREATE ROLE defaults), and if a live cluster
    already has any of those set on `platform_runtime` (e.g. an out-of-band manual grant), this
    script REFUSES rather than silently tightening or loosening it (`runtime_role_violates_safety`).
  - Before ANY mutation, `classify_state()` must find the target either unbootstrapped or
    already up to date. A DRIFTED state (the recorded `schema_version` checksum for
    `platform_foundation.sql` does not match the file on disk) refuses outright — never
    silently re-applied or overwritten.
  - `ai` presence is itself checked as a sanity guard: if the connected host has no `ai`
    database at all, that means the wrong host was targeted, not that `ai` should be created.
  - Secrets (DB_PASS) are read from existing sources (`.env`, process environment — the same
    contract as server/core/url.py) and are never printed; `ConnectionSettings.describe()`
    redacts the password, and PGPASSWORD only ever travels via the child process environment.

Usage:
    uv run python scripts/bootstrap_platform_database.py                  # plan only (default)
    uv run python scripts/bootstrap_platform_database.py --host <ip>      # plan against a host
    uv run python scripts/bootstrap_platform_database.py --host <ip> --apply   # perform it

Exit codes: 0 = success or clean no-op dry run; 1 = refused (protected target, drift, `ai`
missing); 2 = hard error (no psql found, connection/query failure).
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-27

from __future__ import annotations

import argparse
import hashlib
import os
import pathlib
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

REPO = pathlib.Path(__file__).resolve().parents[1]
FOUNDATION_SQL = REPO / "sql" / "bootstrap" / "platform_foundation.sql"
CONTEXT_IMPORT_SQL = REPO / "sql" / "0036_context_import_foundation.sql"
DOTENV = REPO / ".env"

PLATFORM_ADMIN_ROLE = "platform_admin"
PLATFORM_RUNTIME_ROLE = "platform_runtime"
CONTEXT_OWNER_ROLE = "context_owner"
FOUNDATION_VERSION = "0000_platform_foundation"
DEFAULT_TARGET_DATABASE = "platform"
DEFAULT_EXTENSIONS: tuple[str, ...] = ("pgcrypto",)
PROTECTED_DATABASES = frozenset({"ai", "postgres", "template0", "template1"})
PGBIN_DEFAULT = pathlib.Path(r"C:\Program Files\PostgreSQL\18\bin")

_EXTENSION_RE = re.compile(r"CREATE EXTENSION IF NOT EXISTS\s+(\w+)", re.IGNORECASE)
_DOTENV_RE = re.compile(r"^\s*([A-Z0-9_]+)\s*=\s*(.+?)\s*$")
_IDENTIFIER_RE = re.compile(r"^[a-z_][a-z0-9_]*$")


class BootstrapState(Enum):
    """Where the target database's foundation ledger stands relative to disk."""

    NOT_BOOTSTRAPPED = "not_bootstrapped"
    UP_TO_DATE = "up_to_date"
    DRIFTED = "drifted"


@dataclass(frozen=True)
class ConnectionSettings:
    """Admin-capable Postgres connection parameters, resolved from existing secret sources.

    Never render `password` directly — use `describe()` for any printed/logged form.
    """

    driver: str
    user: str
    password: str
    host: str
    port: str

    def describe(self, database: str) -> str:
        """Human-readable connection target with the password redacted."""
        return f"{self.driver}://{self.user}:***@{self.host}:{self.port}/{database}"


@dataclass(frozen=True)
class SchemaVersionRow:
    version: str
    checksum: str


@dataclass(frozen=True)
class LiveState:
    """Snapshot of what already exists, gathered by read-only introspection.

    Built by `gather_live_state()` against a real cluster, or directly in tests — every field
    here comes from a SELECT, never a mutation.
    """

    ai_database_exists: bool
    target_database_exists: bool
    admin_role_exists: bool
    runtime_role_exists: bool
    context_owner_role_exists: bool
    admin_is_context_owner_member: bool
    runtime_role_has_dangerous_attributes: Optional[bool]
    schema_version_row: Optional[SchemaVersionRow]


@dataclass(frozen=True)
class PlanStep:
    name: str
    already_satisfied: bool
    detail: str = ""


def load_connection_settings(
    target_host: Optional[str] = None, env: Optional[dict[str, str]] = None
) -> ConnectionSettings:
    """Resolve admin-capable Postgres connection settings from existing secret sources.

    Mirrors server/core/url.py's env-var contract (DB_DRIVER/DB_USER/DB_PASS/DB_HOST/DB_PORT) so
    this script authenticates the same way the application does, instead of inventing a parallel
    credential path. `.env` supplies defaults; real environment variables (an already-exported
    shell/session var, or a Coolify-injected one) win over `.env`, matching the precedence
    scripts/capture_bootstrap_ddl.py already uses for the same file.

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
    resolved: dict[str, str] = {}
    if DOTENV.exists():
        for line in DOTENV.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = _DOTENV_RE.match(line)
            if m:
                resolved[m.group(1)] = m.group(2).strip("\"'")
    process_env = os.environ if env is None else env
    for key in ("DB_DRIVER", "DB_USER", "DB_PASS", "DB_HOST", "DB_PORT"):
        if key in process_env:
            resolved[key] = process_env[key]

    return ConnectionSettings(
        driver=resolved.get("DB_DRIVER", "postgresql+psycopg"),
        user=resolved.get("DB_USER", "ai"),
        password=resolved.get("DB_PASS", "ai"),
        host=target_host or resolved.get("DB_HOST", "localhost"),
        port=resolved.get("DB_PORT", "5432"),
    )


def validate_identifier(name: str, *, what: str) -> None:
    """Refuse a database/role name that is not a safe lowercase SQL identifier.

    Postgres DDL cannot bind identifiers as query parameters (`CREATE DATABASE $1` is not
    valid), so this script builds a handful of DDL strings with the target database name
    interpolated directly. Restricting it to `^[a-z_][a-z0-9_]*$` up front removes any need to
    reason about quoting/escaping later.

    Raises
    ------
    ValueError
        If `name` contains anything outside `[a-z0-9_]`, or does not start with a letter/underscore.
    """
    if not _IDENTIFIER_RE.match(name):
        raise ValueError(f"{what} {name!r} is not a safe identifier (must match ^[a-z_][a-z0-9_]*$)")


def guard_target_database(name: str) -> None:
    """Refuse any target database name this script must never create or touch destructively.

    Raises
    ------
    ValueError
        If `name` is `ai`, `postgres`, `template0`, or `template1` — the existing production
        database and the cluster's own maintenance/template databases.
    """
    if name in PROTECTED_DATABASES:
        raise ValueError(
            f"refusing to target protected database {name!r} — this script only ever "
            f"creates/verifies a NEW database (default {DEFAULT_TARGET_DATABASE!r}); "
            f"{sorted(PROTECTED_DATABASES)} are never dropped, renamed, or mutated here"
        )


def foundation_checksum(path: pathlib.Path = FOUNDATION_SQL) -> str:
    """SHA-256 hex digest of the foundation SQL file, for schema_version drift detection."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def discover_required_extensions(path: pathlib.Path = CONTEXT_IMPORT_SQL) -> tuple[str, ...]:
    """Extensions the platform foundation should cover, per sql/0036 if it exists yet.

    sql/0036_context_import_foundation.sql is owned by a different work lane and had not landed
    in this checkout as of authoring — this reads the real file live rather than hardcoding its
    contents, so a future run (once 0036 exists) automatically cross-checks against it instead
    of a guess. Falls back to `DEFAULT_EXTENSIONS` (this bootstrap's own minimal requirement,
    also what sql/bootstrap/platform_foundation.sql ships) when the file is absent.

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


def classify_state(existing: Optional[SchemaVersionRow], expected_checksum: str) -> BootstrapState:
    """Decide whether the foundation is unapplied, up to date, or drifted.

    Parameters
    ----------
    existing:
        The `public.schema_version` row for `FOUNDATION_VERSION`, if the target database, the
        table, and the row all already exist; `None` if any of those is missing.
    expected_checksum:
        `foundation_checksum()` of the SQL file on disk right now.

    Returns
    -------
    BootstrapState
        `NOT_BOOTSTRAPPED` if there is no recorded row yet, `UP_TO_DATE` if the recorded
        checksum matches the file on disk, `DRIFTED` if it does not — a drifted database must
        never be silently re-applied or overwritten by this script.
    """
    if existing is None:
        return BootstrapState.NOT_BOOTSTRAPPED
    if existing.checksum == expected_checksum:
        return BootstrapState.UP_TO_DATE
    return BootstrapState.DRIFTED


def runtime_role_violates_safety(state: LiveState) -> bool:
    """True only if `platform_runtime` currently holds SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS.

    `state.runtime_role_has_dangerous_attributes` is `None` when the role does not exist yet
    (nothing to violate) and `False` when it exists with none of those attributes — both count
    as safe. This script never grants any of those attributes itself (see
    sql/bootstrap/platform_foundation.sql); a live `True` here means something else did, and
    `main()` refuses rather than silently tightening or loosening it.
    """
    return state.runtime_role_has_dangerous_attributes is True


def build_plan(target_database: str, state: LiveState, extension_gap: Sequence[str]) -> list[PlanStep]:
    """Compute the ordered, human-readable bootstrap plan for `target_database`.

    Pure function — no I/O. Every step reports whether it is already satisfied so the default
    dry run shows exactly what `--apply` would (and would not) do.

    Parameters
    ----------
    target_database:
        The database this run is bootstrapping (default `platform`).
    state:
        Current live state, from `gather_live_state()` or a test fixture.
    extension_gap:
        Extensions sql/0036 will need beyond this bootstrap's own coverage — informational only,
        never auto-applied (see `discover_required_extensions` / `missing_extensions`).

    Returns
    -------
    list[PlanStep]
    """
    steps = [
        PlanStep(
            "verify `ai` database is present and untouched",
            already_satisfied=state.ai_database_exists,
            detail="present" if state.ai_database_exists else "MISSING — wrong host? investigate before proceeding",
        ),
        PlanStep(f"create role {PLATFORM_ADMIN_ROLE!r} (NOLOGIN)", already_satisfied=state.admin_role_exists),
        PlanStep(
            f"create role {PLATFORM_RUNTIME_ROLE!r} (NOLOGIN, NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS)",
            already_satisfied=state.runtime_role_exists,
        ),
        PlanStep(
            f"verify {PLATFORM_RUNTIME_ROLE!r} has no SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS",
            already_satisfied=not runtime_role_violates_safety(state),
            detail="" if not runtime_role_violates_safety(state) else "VIOLATION — refuse until reconciled manually",
        ),
        PlanStep(f"create role {CONTEXT_OWNER_ROLE!r} (NOLOGIN)", already_satisfied=state.context_owner_role_exists),
        PlanStep(
            f"grant {CONTEXT_OWNER_ROLE!r} to {PLATFORM_ADMIN_ROLE!r}",
            already_satisfied=state.admin_is_context_owner_member,
        ),
        PlanStep(
            f"create database {target_database!r} (OWNER {PLATFORM_ADMIN_ROLE})",
            already_satisfied=state.target_database_exists,
        ),
        PlanStep(
            "apply sql/bootstrap/platform_foundation.sql (extensions + public.schema_version)",
            already_satisfied=state.schema_version_row is not None,
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


# --------------------------------------------------------------------------------------------
# process execution — everything below here touches a real psql process. Kept separate from the
# pure functions above so tests can exercise plan/state/drift logic without a live database.


def resolve_pgbin(explicit: Optional[str]) -> pathlib.Path:
    """Locate the directory containing the `psql` client binary.

    Parameters
    ----------
    explicit:
        `--pgbin` CLI override. Takes precedence over everything else.

    Returns
    -------
    pathlib.Path
        Directory containing `psql`/`psql.exe`.

    Raises
    ------
    FileNotFoundError
        If no explicit override was given, the repo's known PostgreSQL 18 install path
        (matching scripts/capture_bootstrap_ddl.py) does not exist, and `psql` is not on PATH.
    """
    if explicit:
        return pathlib.Path(explicit)
    if PGBIN_DEFAULT.exists():
        return PGBIN_DEFAULT
    found = shutil.which("psql") or shutil.which("psql.exe")
    if found:
        return pathlib.Path(found).parent
    raise FileNotFoundError(
        f"no psql found — checked {PGBIN_DEFAULT} and PATH; pass --pgbin to point at the "
        "PostgreSQL 18 client tools directory"
    )


def _psql_base(settings: ConnectionSettings, pgbin: pathlib.Path, database: str) -> list[str]:
    psql = str(pgbin / ("psql.exe" if os.name == "nt" else "psql"))
    return [psql, "-h", settings.host, "-p", settings.port, "-U", settings.user, "-d", database]


def _run(cmd: list[str], password: str) -> subprocess.CompletedProcess[str]:
    """Run a subprocess with PGPASSWORD in its environment only — never in `cmd` or a log line."""
    child_env = dict(os.environ)
    child_env["PGPASSWORD"] = password
    return subprocess.run(cmd, env=child_env, capture_output=True, text=True)


def psql_scalar(settings: ConnectionSettings, pgbin: pathlib.Path, database: str, sql: str) -> str:
    """Run a read-only `-c` query and return its single scalar result as text (empty if none)."""
    proc = _run(_psql_base(settings, pgbin, database) + ["-tAX", "-c", sql], settings.password)
    if proc.returncode != 0:
        raise SystemExit(f"psql query failed against {database!r}:\n{proc.stderr[-2000:]}")
    return proc.stdout.strip()


def psql_exec(settings: ConnectionSettings, pgbin: pathlib.Path, database: str, sql: str) -> None:
    """Run a mutating `-c` statement, stopping on the first error."""
    proc = _run(_psql_base(settings, pgbin, database) + ["-v", "ON_ERROR_STOP=1", "-c", sql], settings.password)
    if proc.returncode != 0:
        raise SystemExit(f"psql statement failed against {database!r}:\n{proc.stderr[-2000:]}")


def psql_apply_file(settings: ConnectionSettings, pgbin: pathlib.Path, database: str, path: pathlib.Path) -> None:
    """Apply a SQL file with `psql -f`, stopping on the first error."""
    proc = _run(_psql_base(settings, pgbin, database) + ["-v", "ON_ERROR_STOP=1", "-f", str(path)], settings.password)
    if proc.returncode != 0:
        raise SystemExit(f"psql -f {path} failed against {database!r}:\n{proc.stderr[-2000:]}")


def gather_live_state(settings: ConnectionSettings, target_database: str, pgbin: pathlib.Path) -> LiveState:
    """Read-only introspection of the current cluster/database state.

    Every query here is a SELECT — nothing is created, altered, or dropped. Safe to call before
    deciding whether `--apply` is even warranted.
    """
    ai_exists = psql_scalar(settings, pgbin, "postgres", "SELECT 1 FROM pg_database WHERE datname = 'ai'") == "1"
    target_exists = (
        psql_scalar(settings, pgbin, "postgres", f"SELECT 1 FROM pg_database WHERE datname = '{target_database}'")
        == "1"
    )
    admin_role = (
        psql_scalar(settings, pgbin, "postgres", f"SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_ADMIN_ROLE}'")
        == "1"
    )
    runtime_role = (
        psql_scalar(settings, pgbin, "postgres", f"SELECT 1 FROM pg_roles WHERE rolname = '{PLATFORM_RUNTIME_ROLE}'")
        == "1"
    )
    context_owner_role = (
        psql_scalar(settings, pgbin, "postgres", f"SELECT 1 FROM pg_roles WHERE rolname = '{CONTEXT_OWNER_ROLE}'")
        == "1"
    )

    admin_is_context_owner_member = False
    if admin_role and context_owner_role:
        admin_is_context_owner_member = (
            psql_scalar(
                settings,
                pgbin,
                "postgres",
                f"SELECT pg_has_role('{PLATFORM_ADMIN_ROLE}', '{CONTEXT_OWNER_ROLE}', 'MEMBER')",
            )
            == "t"
        )

    runtime_dangerous_attributes: Optional[bool] = None
    if runtime_role:
        runtime_dangerous_attributes = (
            psql_scalar(
                settings,
                pgbin,
                "postgres",
                "SELECT (rolsuper OR rolcreatedb OR rolcreaterole OR rolbypassrls) "
                f"FROM pg_roles WHERE rolname = '{PLATFORM_RUNTIME_ROLE}'",
            )
            == "t"
        )

    row: Optional[SchemaVersionRow] = None
    if target_exists:
        table_exists = (
            psql_scalar(
                settings,
                pgbin,
                target_database,
                "SELECT 1 FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_name = 'schema_version'",
            )
            == "1"
        )
        if table_exists:
            checksum = psql_scalar(
                settings,
                pgbin,
                target_database,
                f"SELECT checksum FROM public.schema_version WHERE version = '{FOUNDATION_VERSION}'",
            )
            if checksum:
                row = SchemaVersionRow(version=FOUNDATION_VERSION, checksum=checksum)

    return LiveState(
        ai_database_exists=ai_exists,
        target_database_exists=target_exists,
        admin_role_exists=admin_role,
        runtime_role_exists=runtime_role,
        context_owner_role_exists=context_owner_role,
        admin_is_context_owner_member=admin_is_context_owner_member,
        runtime_role_has_dangerous_attributes=runtime_dangerous_attributes,
        schema_version_row=row,
    )


def apply_bootstrap(settings: ConnectionSettings, target_database: str, pgbin: pathlib.Path, checksum: str) -> None:
    """Perform the actual mutations.

    Only ever called under `--apply`, and only after `main()` has confirmed via
    `classify_state()` that the target is `NOT_BOOTSTRAPPED` or `UP_TO_DATE` — never `DRIFTED`.
    Every statement is idempotent, matching sql/bootstrap/platform_foundation.sql itself.
    """
    admin_role_sql = (
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
        f"'{PLATFORM_ADMIN_ROLE}') THEN CREATE ROLE {PLATFORM_ADMIN_ROLE} NOLOGIN; END IF; END $$;"
    )
    # Explicit, not merely default: SUPERUSER/CREATEDB/CREATEROLE/BYPASSRLS stated OFF so intent
    # is grep-able in the DDL itself (owner directive) — see runtime_role_violates_safety() for
    # the corresponding live check this script runs before ever reaching here.
    runtime_role_sql = (
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
        f"'{PLATFORM_RUNTIME_ROLE}') THEN CREATE ROLE {PLATFORM_RUNTIME_ROLE} "
        "NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOBYPASSRLS; END IF; END $$;"
    )
    context_owner_role_sql = (
        "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = "
        f"'{CONTEXT_OWNER_ROLE}') THEN CREATE ROLE {CONTEXT_OWNER_ROLE} NOLOGIN; END IF; END $$;"
    )
    psql_exec(settings, pgbin, "postgres", admin_role_sql)
    psql_exec(settings, pgbin, "postgres", runtime_role_sql)
    psql_exec(settings, pgbin, "postgres", context_owner_role_sql)
    # Idempotent: re-granting an already-held role membership is a silent no-op in Postgres.
    psql_exec(settings, pgbin, "postgres", f"GRANT {CONTEXT_OWNER_ROLE} TO {PLATFORM_ADMIN_ROLE}")

    already_exists = (
        psql_scalar(settings, pgbin, "postgres", f"SELECT 1 FROM pg_database WHERE datname = '{target_database}'")
        == "1"
    )
    if not already_exists:
        psql_exec(settings, pgbin, "postgres", f'CREATE DATABASE "{target_database}" OWNER {PLATFORM_ADMIN_ROLE}')

    psql_apply_file(settings, pgbin, target_database, FOUNDATION_SQL)

    psql_exec(
        settings,
        pgbin,
        target_database,
        "INSERT INTO public.schema_version (version, description, checksum) VALUES "
        f"('{FOUNDATION_VERSION}', 'sql/bootstrap/platform_foundation.sql — extensions + "
        f"schema_version ledger', '{checksum}') ON CONFLICT (version) DO NOTHING",
    )


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--host", help="Override DB_HOST (default: .env/environment, matching server/core/url.py)")
    ap.add_argument("--target-db", default=DEFAULT_TARGET_DATABASE, help="Database to bootstrap (default: platform)")
    ap.add_argument("--pgbin", help="Directory containing psql (default: PostgreSQL 18 client tools, or PATH)")
    ap.add_argument(
        "--apply",
        action="store_true",
        help="Perform the bootstrap. Without this flag, only reads live state and prints the plan (default).",
    )
    return ap.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)

    try:
        validate_identifier(args.target_db, what="--target-db")
        guard_target_database(args.target_db)
    except ValueError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 1

    settings = load_connection_settings(target_host=args.host)
    print(f"target cluster: {settings.describe(args.target_db)}")

    extension_gap = missing_extensions(discover_required_extensions())
    if CONTEXT_IMPORT_SQL.exists():
        print("sql/0036_context_import_foundation.sql found — cross-checked its CREATE EXTENSION list")
    else:
        print(
            "sql/0036_context_import_foundation.sql not present in this checkout yet (owned by a "
            "different lane) — using this bootstrap's own minimal extension set"
        )

    try:
        pgbin = resolve_pgbin(args.pgbin)
    except FileNotFoundError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    try:
        state = gather_live_state(settings, args.target_db, pgbin)
    except SystemExit as exc:
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
            f"REFUSED: {PLATFORM_RUNTIME_ROLE!r} already holds SUPERUSER/CREATEDB/CREATEROLE/"
            "BYPASSRLS on this cluster. This script never grants any of those and will not "
            "silently revoke them either — reconcile manually (a deliberate ALTER ROLE) before "
            "re-running.",
            file=sys.stderr,
        )
        return 1

    expected_checksum = foundation_checksum()
    status = classify_state(state.schema_version_row, expected_checksum)

    plan = build_plan(args.target_db, state, extension_gap)
    print("\nPlan:")
    for step in plan:
        marker = "already satisfied" if step.already_satisfied else "PENDING"
        suffix = f" ({step.detail})" if step.detail else ""
        print(f"  [{marker}] {step.name}{suffix}")
    print(f"\nfoundation checksum on disk: {expected_checksum[:12]}...")
    print(f"state: {status.value}")

    if status is BootstrapState.DRIFTED:
        print(
            "\nREFUSED: public.schema_version records a different checksum for "
            f"{FOUNDATION_VERSION!r} than sql/bootstrap/platform_foundation.sql on disk right "
            "now — the file changed after being applied, or a different bootstrap was recorded "
            "under this version key. Reconcile manually; this script will not overwrite a "
            "drifted database.",
            file=sys.stderr,
        )
        return 1

    if not args.apply:
        print("\nDry run only (pass --apply to perform the PENDING steps above). No mutation was attempted.")
        return 0

    apply_bootstrap(settings, args.target_db, pgbin, expected_checksum)
    print(
        f"\napplied. {PLATFORM_ADMIN_ROLE}/{PLATFORM_RUNTIME_ROLE}/{CONTEXT_OWNER_ROLE} verified "
        f"({CONTEXT_OWNER_ROLE!r} granted to {PLATFORM_ADMIN_ROLE!r}), {args.target_db!r} "
        f"bootstrapped, checksum recorded for {FOUNDATION_VERSION!r}."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
