"""Read-only ai -> platform consolidation inventory and deterministic copy manifest.

This tool never copies data and has no mutation mode. Both database connections are placed in
READ ONLY transactions before inventory begins. It emits no connection strings, passwords, SQL
row contents, or environment values; libpq service names are the only connection inputs.

Usage:
    uv run python scripts/audit_ai_platform_consolidation.py \
        --source-service ai_consolidation_source \
        --target-service platform_consolidation_target --pretty

Byline: Codex · GPT-5.6 · 2026-08-29
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import re
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import psycopg
from psycopg import sql

SOURCE_DATABASE = "ai"
TARGET_DATABASE = "platform"
SYSTEM_SCHEMAS = ("pg_catalog", "information_schema")
STATEMENT_TIMEOUT_MS = 300_000
RELEVANT_ROLES = (
    "agno_app",
    "platform_admin",
    "platform_runtime",
    "context_owner",
    "context_import_writer",
    "context_reader",
    "timeline_writer",
    "timeline_projector",
    "timeline_reader",
)
# 2026-09-01 owner restructure: engine/workbench moved under modules/, docker/
# under deploy/ (deploy already covers it). modules/vendored stays excluded via
# IGNORED_CALLER_PARTS ("vendored").
CALLER_ROOTS = ("server", "modules", "deploy", "scripts", ".github")
CALLER_SUFFIXES = {
    ".cfg",
    ".conf",
    ".env",
    ".go",
    ".ini",
    ".js",
    ".json",
    ".jsonc",
    ".properties",
    ".ps1",
    ".py",
    ".sh",
    ".tf",
    ".toml",
    ".ts",
    ".tsx",
    ".xml",
    ".yaml",
    ".yml",
}
CALLER_PATTERNS = {
    "db_database_ai_default": re.compile(r"(?<![A-Z0-9_])DB_DATABASE\b[^\n]{0,120}(?::-|=|:|,)\s*[\"']?ai\b", re.I),
    "postgres_db_ai_default": re.compile(r"(?<![A-Z0-9_])POSTGRES_DB\b[^\n]{0,120}(?::-|=|:|,)\s*[\"']?ai\b", re.I),
    "pgdatabase_ai_default": re.compile(r"(?<![A-Z0-9_])PGDATABASE\b[^\n]{0,120}(?::-|=|:|,)\s*[\"']?ai\b", re.I),
    "database_name_ai_default": re.compile(
        r"(?<![A-Z0-9_])(?:DB_NAME|DATABASE_NAME|DB_POSTGRESDB_DATABASE)\b"
        r"[^\n]{0,120}(?::-|=|:|,)\s*[\"']?ai\b",
        re.I,
    ),
    "dbname_ai_literal": re.compile(r"(?<![\w])dbname\s*=\s*[\"']?ai(?:[\"']|\b)", re.I),
    "database_ai_literal": re.compile(r"(?<![\w])database\s*(?:=|:)\s*[\"']ai[\"']", re.I),
    "postgres_url_ai_database": re.compile(r"postgres(?:ql)?://[^\s\"']+/ai(?:[?\s\"']|$)", re.I),
}
IGNORED_CALLER_PARTS = {
    ".git",
    ".next",
    ".venv",
    "__pycache__",
    "build",
    "dist",
    "node_modules",
    "tests",
    "to_be_deleted",
    "vendored",
}
LIVE_CONFIG_CONTRACT = "ai-platform-caller-fence-v2"
SELF_CALLER_PATHS = {"scripts/audit_ai_platform_consolidation.py"}


@dataclass(frozen=True, order=True)
class Relation:
    qualified_name: str
    schema_name: str
    relation_name: str
    relation_kind: str
    is_partition: bool
    row_count: int


@dataclass(frozen=True, order=True)
class ForeignKey:
    child: str
    parent: str
    constraint_name: str
    definition: str


@dataclass(frozen=True, order=True)
class CallerReference:
    path: str
    line_number: int
    pattern: str


@dataclass(frozen=True, order=True)
class SnapshotObservation:
    database: str
    database_oid: int
    transaction_snapshot: str
    wal_lsn: str
    observed_at: str
    postmaster_started_at: str
    server_version_num: int
    server_address: str | None
    server_port: int | None
    system_identifier: str | None


@dataclass(frozen=True, order=True)
class LiveConfigAttestation:
    path: str
    sha256: str
    attestation_id: str
    issued_at: str
    fence_established_at: str
    valid_until: str
    repo_revision: str
    source_database: str
    target_database: str
    source_snapshot_sha256: str
    target_snapshot_sha256: str
    signer_key_id: str
    attested_by: str
    signature_verified: bool
    gate_passed: bool


def canonical_json(value: Any) -> str:
    """Return stable JSON suitable for hashing and diffing between rehearsals."""
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def digest_payload(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def guard_database(cursor: psycopg.Cursor[Any], expected: str) -> None:
    cursor.execute("SELECT current_database()")
    actual = cursor.fetchone()[0]
    if actual != expected:
        raise RuntimeError(f"refusing database {actual!r}; expected {expected!r}")


def begin_read_only(connection: psycopg.Connection[Any], expected: str) -> None:
    """Establish the fail-closed transaction boundary before any inventory query."""
    with connection.cursor() as cursor:
        cursor.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY")
        cursor.execute("SELECT set_config('statement_timeout', %s, true)", (str(STATEMENT_TIMEOUT_MS),))
        guard_database(cursor, expected)


def fetch_snapshot_observation(connection: psycopg.Connection[Any]) -> SnapshotObservation:
    """Capture the identity and MVCC/WAL boundary for one database transaction."""
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT current_database(),
                   (SELECT oid FROM pg_database WHERE datname = current_database()),
                   txid_current_snapshot()::text,
                   pg_current_wal_lsn()::text,
                   clock_timestamp(),
                   pg_postmaster_start_time(),
                   current_setting('server_version_num')::integer,
                   inet_server_addr()::text,
                   inet_server_port(),
                   has_function_privilege(current_user, 'pg_control_system()', 'EXECUTE')
            """
        )
        row = cursor.fetchone()
        system_identifier: str | None = None
        if row[9]:
            cursor.execute("SELECT system_identifier::text FROM pg_control_system()")
            system_identifier = cursor.fetchone()[0]
        return SnapshotObservation(
            database=row[0],
            database_oid=int(row[1]),
            transaction_snapshot=row[2],
            wal_lsn=row[3],
            observed_at=row[4].isoformat(),
            postmaster_started_at=row[5].isoformat(),
            server_version_num=int(row[6]),
            server_address=row[7],
            server_port=row[8],
            system_identifier=system_identifier,
        )


def repository_revision(repo_root: Path) -> str:
    """Return the exact repository revision, or a fail-closed unavailable marker."""
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        check=False,
        capture_output=True,
        text=True,
        timeout=10,
    )
    revision = completed.stdout.strip()
    return revision if completed.returncode == 0 and re.fullmatch(r"[0-9a-fA-F]{40,64}", revision) else "unavailable"


def _aware_datetime(value: str, field: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"{field} must include a timezone")
    return parsed


def load_live_config_attestations(
    paths: Sequence[Path],
    repo_root: Path,
    repo_revision: str,
    source_snapshot: SnapshotObservation,
    target_snapshot: SnapshotObservation,
    trusted_fence_keys: Mapping[str, bytes],
) -> list[LiveConfigAttestation]:
    """Authenticate live-config evidence and bind it to both database observations."""
    source_observed = _aware_datetime(source_snapshot.observed_at, "source_observed_at")
    target_observed = _aware_datetime(target_snapshot.observed_at, "target_observed_at")
    source_snapshot_sha256 = digest_payload(asdict(source_snapshot))
    target_snapshot_sha256 = digest_payload(asdict(target_snapshot))
    attestations: list[LiveConfigAttestation] = []
    for path in paths:
        resolved = path.resolve()
        payload_bytes = resolved.read_bytes()
        payload = json.loads(payload_bytes)
        required = {
            "contract_version",
            "attestation_id",
            "issued_at",
            "fence_established_at",
            "valid_until",
            "repo_revision",
            "source_database",
            "target_database",
            "source_database_oid",
            "target_database_oid",
            "source_system_identifier",
            "target_system_identifier",
            "source_server_address",
            "target_server_address",
            "source_server_port",
            "target_server_port",
            "source_postmaster_started_at",
            "target_postmaster_started_at",
            "source_snapshot_sha256",
            "target_snapshot_sha256",
            "source_writer_admission_blocked",
            "target_writer_admission_blocked",
            "caller_inventory_complete",
            "source_active_writer_count",
            "target_active_writer_count",
            "coolify_checked",
            "n8n_checked",
            "temporal_checked",
            "attested_by",
            "signer_key_id",
            "signature_hmac_sha256",
        }
        if not isinstance(payload, dict) or not required <= payload.keys():
            raise ValueError(f"live-config evidence {resolved.name!r} is missing required fields")
        issued_at = _aware_datetime(str(payload["issued_at"]), "issued_at")
        established = _aware_datetime(str(payload["fence_established_at"]), "fence_established_at")
        valid_until = _aware_datetime(str(payload["valid_until"]), "valid_until")
        signer_key_id = str(payload["signer_key_id"])
        supplied_signature = str(payload["signature_hmac_sha256"]).lower()
        signed_payload = {key: value for key, value in payload.items() if key != "signature_hmac_sha256"}
        trusted_key = trusted_fence_keys.get(signer_key_id)
        expected_signature = (
            hmac.new(trusted_key, canonical_json(signed_payload).encode("utf-8"), hashlib.sha256).hexdigest()
            if trusted_key
            else ""
        )
        signature_verified = bool(
            trusted_key
            and re.fullmatch(r"[0-9a-f]{64}", supplied_signature)
            and hmac.compare_digest(supplied_signature, expected_signature)
        )
        source_identity_complete = bool(
            source_snapshot.system_identifier and source_snapshot.server_address and source_snapshot.server_port
        )
        target_identity_complete = bool(
            target_snapshot.system_identifier and target_snapshot.server_address and target_snapshot.server_port
        )
        gate_passed = bool(
            payload["contract_version"] == LIVE_CONFIG_CONTRACT
            and payload["source_database"] == SOURCE_DATABASE
            and payload["target_database"] == TARGET_DATABASE
            and payload["repo_revision"] == repo_revision
            and repo_revision != "unavailable"
            and issued_at <= established <= source_observed <= valid_until
            and issued_at <= established <= target_observed <= valid_until
            and source_identity_complete
            and target_identity_complete
            and source_snapshot.system_identifier == target_snapshot.system_identifier
            and payload["source_database_oid"] == source_snapshot.database_oid
            and payload["target_database_oid"] == target_snapshot.database_oid
            and str(payload["source_system_identifier"]) == source_snapshot.system_identifier
            and str(payload["target_system_identifier"]) == target_snapshot.system_identifier
            and payload["source_server_address"] == source_snapshot.server_address
            and payload["target_server_address"] == target_snapshot.server_address
            and payload["source_server_port"] == source_snapshot.server_port
            and payload["target_server_port"] == target_snapshot.server_port
            and _aware_datetime(str(payload["source_postmaster_started_at"]), "source_postmaster_started_at")
            == _aware_datetime(source_snapshot.postmaster_started_at, "source_snapshot.postmaster_started_at")
            and _aware_datetime(str(payload["target_postmaster_started_at"]), "target_postmaster_started_at")
            == _aware_datetime(target_snapshot.postmaster_started_at, "target_snapshot.postmaster_started_at")
            and str(payload["source_snapshot_sha256"]).lower() == source_snapshot_sha256
            and str(payload["target_snapshot_sha256"]).lower() == target_snapshot_sha256
            and payload["source_writer_admission_blocked"] is True
            and payload["target_writer_admission_blocked"] is True
            and payload["caller_inventory_complete"] is True
            and type(payload["source_active_writer_count"]) is int
            and payload["source_active_writer_count"] == 0
            and type(payload["target_active_writer_count"]) is int
            and payload["target_active_writer_count"] == 0
            and payload["coolify_checked"] is True
            and payload["n8n_checked"] is True
            and payload["temporal_checked"] is True
            and str(payload["attestation_id"]).strip()
            and str(payload["attested_by"]).strip()
            and signer_key_id.strip()
            and signature_verified
        )
        try:
            relative = resolved.relative_to(repo_root.resolve()).as_posix()
        except ValueError:
            relative = resolved.name
        attestations.append(
            LiveConfigAttestation(
                path=relative,
                sha256=hashlib.sha256(payload_bytes).hexdigest(),
                attestation_id=str(payload["attestation_id"]),
                issued_at=issued_at.isoformat(),
                fence_established_at=established.isoformat(),
                valid_until=valid_until.isoformat(),
                repo_revision=str(payload["repo_revision"]),
                source_database=str(payload["source_database"]),
                target_database=str(payload["target_database"]),
                source_snapshot_sha256=str(payload["source_snapshot_sha256"]).lower(),
                target_snapshot_sha256=str(payload["target_snapshot_sha256"]).lower(),
                signer_key_id=signer_key_id,
                attested_by=str(payload["attested_by"]),
                signature_verified=signature_verified,
                gate_passed=gate_passed,
            )
        )
    return sorted(attestations)


def fetch_relations(connection: psycopg.Connection[Any]) -> list[Relation]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT n.nspname, c.relname, c.relkind,
                   c.relispartition AS is_partition
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relkind IN ('r', 'p')
              AND n.nspname <> ALL(%s)
              AND n.nspname NOT LIKE 'pg_toast%%'
              AND n.nspname NOT LIKE 'pg_temp_%%'
            ORDER BY n.nspname, c.relname
            """,
            (list(SYSTEM_SCHEMAS),),
        )
        identities = list(cursor.fetchall())

        relations: list[Relation] = []
        for schema_name, relation_name, relation_kind, is_partition in identities:
            cursor.execute(
                sql.SQL("SELECT count(*) FROM {}.{}").format(sql.Identifier(schema_name), sql.Identifier(relation_name))
            )
            relations.append(
                Relation(
                    qualified_name=f"{schema_name}.{relation_name}",
                    schema_name=schema_name,
                    relation_name=relation_name,
                    relation_kind=relation_kind,
                    is_partition=bool(is_partition),
                    row_count=int(cursor.fetchone()[0]),
                )
            )
    return sorted(relations)


def fetch_foreign_keys(connection: psycopg.Connection[Any]) -> list[ForeignKey]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT child_ns.nspname || '.' || child.relname,
                   parent_ns.nspname || '.' || parent.relname,
                   con.conname,
                   pg_get_constraintdef(con.oid, true)
            FROM pg_constraint con
            JOIN pg_class child ON child.oid = con.conrelid
            JOIN pg_namespace child_ns ON child_ns.oid = child.relnamespace
            JOIN pg_class parent ON parent.oid = con.confrelid
            JOIN pg_namespace parent_ns ON parent_ns.oid = parent.relnamespace
            WHERE con.contype = 'f'
              AND child_ns.nspname <> ALL(%s)
              AND parent_ns.nspname <> ALL(%s)
            ORDER BY 1, 2, 3
            """,
            (list(SYSTEM_SCHEMAS), list(SYSTEM_SCHEMAS)),
        )
        return sorted(ForeignKey(*row) for row in cursor.fetchall())


def fetch_extensions(connection: psycopg.Connection[Any]) -> list[dict[str, str]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT e.extname, e.extversion, n.nspname
            FROM pg_extension e
            JOIN pg_namespace n ON n.oid = e.extnamespace
            ORDER BY e.extname
            """
        )
        return [
            {"name": name, "version": version, "schema": schema_name}
            for name, version, schema_name in cursor.fetchall()
        ]


def fetch_roles(connection: psycopg.Connection[Any]) -> list[dict[str, Any]]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT role.rolname, role.rolcanlogin, role.rolsuper, role.rolcreatedb,
                   role.rolcreaterole, role.rolreplication, role.rolbypassrls,
                   has_database_privilege(role.rolname, current_database(), 'CONNECT'),
                   has_database_privilege(role.rolname, current_database(), 'CREATE'),
                   ARRAY(
                       SELECT parent.rolname
                       FROM pg_auth_members membership
                       JOIN pg_roles parent ON parent.oid = membership.roleid
                       WHERE membership.member = role.oid
                       ORDER BY parent.rolname
                   )
            FROM pg_roles AS role
            WHERE role.rolname = ANY(%s)
            ORDER BY rolname
            """,
            (list(RELEVANT_ROLES),),
        )
        return [
            {
                "name": row[0],
                "can_login": row[1],
                "superuser": row[2],
                "create_database": row[3],
                "create_role": row[4],
                "replication": row[5],
                "bypass_rls": row[6],
                "database_connect": row[7],
                "database_create": row[8],
                "member_of": list(row[9]),
            }
            for row in cursor.fetchall()
        ]


def fetch_zero_caller_proof(connection: psycopg.Connection[Any]) -> dict[str, int]:
    """Count cluster-level activity that must be zero before the legacy DB can be parked."""
    checks = {
        "other_sessions": (
            "SELECT count(*) FROM pg_stat_activity WHERE datname = current_database() AND pid <> pg_backend_pid()"
        ),
        "non_idle_sessions": (
            "SELECT count(*) FROM pg_stat_activity "
            "WHERE datname = current_database() AND pid <> pg_backend_pid() AND state <> 'idle'"
        ),
        "prepared_transactions": ("SELECT count(*) FROM pg_prepared_xacts WHERE database = current_database()"),
        "database_replication_slots": ("SELECT count(*) FROM pg_replication_slots WHERE database = current_database()"),
        "other_database_locks": (
            "SELECT count(*) FROM pg_locks l JOIN pg_database d ON d.oid = l.database "
            "WHERE d.datname = current_database() AND l.pid <> pg_backend_pid()"
        ),
    }
    results: dict[str, int] = {}
    with connection.cursor() as cursor:
        for name, statement in checks.items():
            cursor.execute(statement)
            results[name] = int(cursor.fetchone()[0])
    return results


def _is_runtime_config(path: Path) -> bool:
    lowered_name = path.name.lower()
    return bool(
        lowered_name == ".env"
        or lowered_name.startswith(".env.")
        or ".env." in lowered_name
        or lowered_name.endswith(".env")
        or lowered_name.startswith("dockerfile")
        or re.fullmatch(r"compose(?:\.[^.]+)*\.ya?ml", lowered_name)
        or path.suffix.lower() in CALLER_SUFFIXES
    )


def scan_runtime_callers(repo_root: Path) -> list[CallerReference]:
    """Report only path/line/pattern; never echo possibly secret-bearing source lines."""
    matches: set[CallerReference] = set()
    candidates = {path for path in repo_root.iterdir() if path.is_file() and _is_runtime_config(path)}
    for root_name in CALLER_ROOTS:
        root = repo_root / root_name
        if not root.is_dir():
            continue
        for directory, dirnames, filenames in os.walk(root):
            dirnames[:] = sorted(name for name in dirnames if name not in IGNORED_CALLER_PARTS)
            base = Path(directory)
            for filename in filenames:
                path = base / filename
                if filename.lower().endswith(
                    ("_test.go", "_test.py", ".test.js", ".test.ts", ".test.tsx")
                ) or filename.lower().startswith("test_"):
                    continue
                if _is_runtime_config(path):
                    candidates.add(path)
    for path in sorted(candidates):
        relative = path.relative_to(repo_root).as_posix()
        if relative in SELF_CALLER_PATHS or path.resolve() == Path(__file__).resolve():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for pattern_name, pattern in CALLER_PATTERNS.items():
                if pattern.search(line):
                    matches.add(CallerReference(relative, line_number, pattern_name))
    return sorted(matches)


def deterministic_copy_order(relations: Iterable[Relation], foreign_keys: Iterable[ForeignKey]) -> list[dict[str, Any]]:
    """Produce a stable parents-before-children manifest without executing a copy.

    Cycles are reported explicitly. The lexicographically first remaining relation is emitted as
    a cycle break so the output is deterministic; this does not authorize bypassing constraints.
    """
    # Partition children remain in the physical inventory, but copying both a partitioned
    # parent and its child partitions would duplicate rows. The logical manifest copies through
    # the parent; the later schema foundation remains responsible for recreating partition DDL.
    names = {relation.qualified_name for relation in relations if not relation.is_partition}
    dependencies: dict[str, set[str]] = {name: set() for name in names}
    for foreign_key in foreign_keys:
        if foreign_key.child in names and foreign_key.parent in names:
            dependencies[foreign_key.child].add(foreign_key.parent)

    remaining = set(names)
    emitted: set[str] = set()
    output: list[dict[str, Any]] = []
    while remaining:
        ready = sorted(name for name in remaining if dependencies[name] <= emitted)
        cycle_break = False
        if not ready:
            ready = [min(remaining)]
            cycle_break = True
        for name in ready:
            unresolved = sorted(dependencies[name] - emitted)
            output.append(
                {
                    "order": len(output) + 1,
                    "relation": name,
                    "dependencies": sorted(dependencies[name]),
                    "unresolved_cycle_dependencies": unresolved if cycle_break else [],
                }
            )
            emitted.add(name)
            remaining.remove(name)
    return output


def build_manifest(
    source_relations: Sequence[Relation],
    target_relations: Sequence[Relation],
    source_foreign_keys: Sequence[ForeignKey],
    source_extensions: Sequence[dict[str, str]],
    target_extensions: Sequence[dict[str, str]],
    source_roles: Sequence[dict[str, Any]],
    target_roles: Sequence[dict[str, Any]],
    caller_references: Sequence[CallerReference],
    zero_caller_proof: dict[str, int],
    source_snapshot: SnapshotObservation,
    target_snapshot: SnapshotObservation,
    repo_revision: str,
    live_config_attestations: Sequence[LiveConfigAttestation],
) -> dict[str, Any]:
    target_by_name = {relation.qualified_name: relation for relation in target_relations}
    parity = []
    for source in sorted(source_relations):
        target = target_by_name.get(source.qualified_name)
        parity.append(
            {
                "relation": source.qualified_name,
                "source_rows": source.row_count,
                "target_rows": None if target is None else target.row_count,
                "status": (
                    "missing_target"
                    if target is None
                    else "equal"
                    if source.row_count == target.row_count
                    else "different"
                ),
            }
        )

    source_snapshot_payload = asdict(source_snapshot)
    target_snapshot_payload = asdict(target_snapshot)
    source_snapshot_sha256 = digest_payload(source_snapshot_payload)
    target_snapshot_sha256 = digest_payload(target_snapshot_payload)
    static_gate_passed = not caller_references
    database_gate_passed = bool(zero_caller_proof) and all(value == 0 for value in zero_caller_proof.values())
    live_config_gate_passed = bool(live_config_attestations) and all(
        item.gate_passed for item in live_config_attestations
    )
    manifest: dict[str, Any] = {
        "contract_version": "ai-platform-consolidation-readonly-v2",
        "mode": "read_only_dry_run",
        "source_database": SOURCE_DATABASE,
        "target_database": TARGET_DATABASE,
        "repository_revision": repo_revision,
        "source_snapshot": source_snapshot_payload,
        "source_snapshot_sha256": source_snapshot_sha256,
        "target_snapshot": target_snapshot_payload,
        "target_snapshot_sha256": target_snapshot_sha256,
        "source_relations": [asdict(item) for item in sorted(source_relations)],
        "target_relations": [asdict(item) for item in sorted(target_relations)],
        "source_foreign_keys": [asdict(item) for item in sorted(source_foreign_keys)],
        "copy_order": deterministic_copy_order(source_relations, source_foreign_keys),
        "row_parity": parity,
        "extensions": {"source": list(source_extensions), "target": list(target_extensions)},
        "roles": {"source": list(source_roles), "target": list(target_roles)},
        "runtime_caller_references": [asdict(item) for item in sorted(caller_references)],
        "zero_caller_proof": dict(sorted(zero_caller_proof.items())),
        "live_config_attestations": [asdict(item) for item in sorted(live_config_attestations)],
        "caller_gate_components": {
            "database_quiescence": database_gate_passed,
            "static_inventory": static_gate_passed,
            "attested_live_config_fence": live_config_gate_passed,
        },
        "zero_caller_gate_passed": database_gate_passed and static_gate_passed and live_config_gate_passed,
        "mutation_authorized": False,
    }
    manifest["manifest_sha256"] = digest_payload(manifest)
    return manifest


def audit(
    source_service: str,
    target_service: str,
    repo_root: Path,
    live_config_evidence: Sequence[Path],
    trusted_fence_keys: Mapping[str, bytes],
) -> dict[str, Any]:
    source = psycopg.connect(f"service={source_service}", autocommit=False)
    try:
        target = psycopg.connect(f"service={target_service}", autocommit=False)
        try:
            begin_read_only(source, SOURCE_DATABASE)
            begin_read_only(target, TARGET_DATABASE)
            source_snapshot = fetch_snapshot_observation(source)
            target_snapshot = fetch_snapshot_observation(target)
            revision = repository_revision(repo_root)
            attestations = load_live_config_attestations(
                live_config_evidence,
                repo_root,
                revision,
                source_snapshot,
                target_snapshot,
                trusted_fence_keys,
            )
            return build_manifest(
                fetch_relations(source),
                fetch_relations(target),
                fetch_foreign_keys(source),
                fetch_extensions(source),
                fetch_extensions(target),
                fetch_roles(source),
                fetch_roles(target),
                scan_runtime_callers(repo_root),
                fetch_zero_caller_proof(source),
                source_snapshot,
                target_snapshot,
                revision,
                attestations,
            )
        finally:
            target.rollback()
            target.close()
    finally:
        source.rollback()
        source.close()


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-service", required=True, help="libpq service whose current_database() is ai")
    parser.add_argument("--target-service", required=True, help="libpq service whose current_database() is platform")
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument(
        "--live-config-evidence",
        action="append",
        default=[],
        type=Path,
        help="time-bounded JSON attestation that Coolify/n8n/Temporal callers are inventoried and fenced",
    )
    parser.add_argument(
        "--trusted-fence-key",
        action="append",
        default=[],
        metavar="KEY_ID=PATH",
        help="trusted HMAC key file for authenticating a caller-fence attestation; repeatable",
    )
    parser.add_argument("--pretty", action="store_true")
    return parser.parse_args(argv)


def load_trusted_fence_keys(specifications: Sequence[str]) -> dict[str, bytes]:
    """Load explicitly trusted HMAC keys without placing key bytes in output or errors."""
    keys: dict[str, bytes] = {}
    for specification in specifications:
        key_id, separator, path_text = specification.partition("=")
        if not separator or not key_id.strip() or not path_text.strip():
            raise ValueError("each --trusted-fence-key must be KEY_ID=PATH")
        normalized_key_id = key_id.strip()
        if normalized_key_id in keys:
            raise ValueError(f"duplicate trusted fence key id {normalized_key_id!r}")
        key = Path(path_text).resolve().read_bytes()
        if len(key) < 32:
            raise ValueError(f"trusted fence key {normalized_key_id!r} must contain at least 32 bytes")
        keys[normalized_key_id] = key
    return keys


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    manifest = audit(
        args.source_service,
        args.target_service,
        args.repo_root.resolve(),
        args.live_config_evidence,
        load_trusted_fence_keys(args.trusted_fence_key),
    )
    print(json.dumps(manifest, sort_keys=True, indent=2 if args.pretty else None))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
