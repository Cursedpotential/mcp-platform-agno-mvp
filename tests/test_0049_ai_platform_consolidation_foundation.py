"""Contracts for the non-destructive ai -> platform consolidation foundation.

Byline: Codex · GPT-5.6 · 2026-08-29
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
from dataclasses import asdict
from pathlib import Path

import pytest
import sqlparse

from scripts.audit_ai_platform_consolidation import (
    CallerReference,
    ForeignKey,
    LiveConfigAttestation,
    Relation,
    SnapshotObservation,
    begin_read_only,
    build_manifest,
    canonical_json,
    deterministic_copy_order,
    fetch_roles,
    load_live_config_attestations,
    scan_runtime_callers,
)

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0049_ai_platform_consolidation_foundation.sql"
AUDITOR = ROOT / "scripts" / "audit_ai_platform_consolidation.py"
SQL = MIGRATION.read_text(encoding="utf-8")
NORMALIZED = " ".join(SQL.lower().split())


def _relation(name: str, rows: int) -> Relation:
    schema_name, relation_name = name.split(".", 1)
    return Relation(name, schema_name, relation_name, "r", False, rows)


def _snapshot(database: str, snapshot: str, lsn: str) -> SnapshotObservation:
    return SnapshotObservation(
        database=database,
        database_oid=16_384 if database == "ai" else 16_385,
        transaction_snapshot=snapshot,
        wal_lsn=lsn,
        observed_at="2026-08-29T20:00:00+00:00",
        postmaster_started_at="2026-08-29T00:00:00+00:00",
        server_version_num=180001,
        server_address="100.91.190.107",
        server_port=5432,
        system_identifier="123456789",
    )


def _attestation() -> LiveConfigAttestation:
    return LiveConfigAttestation(
        path="proof/caller-fence.json",
        sha256="aa" * 32,
        attestation_id="fence-1",
        issued_at="2026-08-29T19:58:00+00:00",
        fence_established_at="2026-08-29T19:59:00+00:00",
        valid_until="2026-08-29T20:05:00+00:00",
        repo_revision="1" * 40,
        source_database="ai",
        target_database="platform",
        source_snapshot_sha256="bb" * 32,
        target_snapshot_sha256="cc" * 32,
        signer_key_id="pytest-key",
        attested_by="pytest",
        signature_verified=True,
        gate_passed=True,
    )


def _signed_fence_payload(
    source: SnapshotObservation,
    target: SnapshotObservation,
    key: bytes,
    **overrides: object,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": "ai-platform-caller-fence-v2",
        "attestation_id": "fence-20260829",
        "issued_at": "2026-08-29T19:58:00Z",
        "fence_established_at": "2026-08-29T19:59:00Z",
        "valid_until": "2026-08-29T20:05:00Z",
        "repo_revision": "1" * 40,
        "source_database": "ai",
        "target_database": "platform",
        "source_database_oid": source.database_oid,
        "target_database_oid": target.database_oid,
        "source_system_identifier": source.system_identifier,
        "target_system_identifier": target.system_identifier,
        "source_server_address": source.server_address,
        "target_server_address": target.server_address,
        "source_server_port": source.server_port,
        "target_server_port": target.server_port,
        "source_postmaster_started_at": source.postmaster_started_at,
        "target_postmaster_started_at": target.postmaster_started_at,
        "source_snapshot_sha256": hashlib.sha256(canonical_json(asdict(source)).encode()).hexdigest(),
        "target_snapshot_sha256": hashlib.sha256(canonical_json(asdict(target)).encode()).hexdigest(),
        "source_writer_admission_blocked": True,
        "target_writer_admission_blocked": True,
        "caller_inventory_complete": True,
        "source_active_writer_count": 0,
        "target_active_writer_count": 0,
        "coolify_checked": True,
        "n8n_checked": True,
        "temporal_checked": True,
        "attested_by": "pytest",
        "signer_key_id": "pytest-key",
    }
    payload.update(overrides)
    payload["signature_hmac_sha256"] = hmac.new(
        key, canonical_json(payload).encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return payload


def test_0049_is_forward_only_platform_guarded_and_transactional() -> None:
    statements = [statement for statement in sqlparse.split(SQL) if statement.strip()]
    assert statements[0].strip().lower().endswith("begin;")
    assert statements[-1].strip().lower() == "commit;"
    assert "current_database() <> 'platform'" in NORMALIZED
    assert "migration 0046 remains immutable historical state" in NORMALIZED
    assert "grant usage, create on schema public to platform_admin" in NORMALIZED
    assert "set local role platform_admin" in NORMALIZED
    assert "migration 0049 refuses login inheritance of platform_admin" in NORMALIZED
    assert "create table public.platform_consolidation_checkpoint" in NORMALIZED
    assert "create table public.platform_consolidation_proof_receipt" in NORMALIZED
    assert "create table public.platform_consolidation_receipt_claim" in NORMALIZED
    assert "source_database = 'ai'" in NORMALIZED
    assert "target_database = 'platform'" in NORMALIZED
    assert "verified_receipt_id" in NORMALIZED
    assert "required_proof_kind" in NORMALIZED
    assert "source_snapshot_id" in NORMALIZED
    assert "target_snapshot_id" in NORMALIZED
    assert "manifest_sha256" in NORMALIZED
    assert "repository_revision" in NORMALIZED
    assert "fence_attestation_sha256" in NORMALIZED
    assert "create or replace function" not in NORMALIZED
    assert "migration 0049 refuses to replace an existing consolidation namespace object" in NORMALIZED


def test_0049_is_additive_append_only_and_has_no_cutover_or_trigger_bypass() -> None:
    for forbidden in (
        "drop table",
        "delete from",
        "truncate public.",
        "disable trigger",
        "alter database ai",
        "revoke connect on database ai",
        "grant connect on database platform to agno_app",
        "grant insert on table public.platform_consolidation_checkpoint to platform_runtime",
    ):
        assert forbidden not in NORMALIZED
    assert NORMALIZED.count("before update or delete") == 3
    assert NORMALIZED.count("before truncate") == 3
    assert "public.forbid_consolidation_proof_mutation_v0049()" in NORMALIZED
    assert "platform_consolidation_verified_requires_pass" in NORMALIZED
    assert "source_row_count = target_row_count" in NORMALIZED
    assert "unique (plan_id, phase_key, relation_key, attempt_key)" in NORMALIZED
    assert "unique (checkpoint_id, proof_kind, proof_sha256)" in NORMALIZED
    assert NORMALIZED.count("on delete restrict") >= 3
    assert "platform_consolidation_bound_receipt_no_supersede" in NORMALIZED
    assert "successor.supersedes_receipt_id" in NORMALIZED
    assert "details <> '{}'::jsonb" in NORMALIZED
    assert "receipt_id uuid primary key" in NORMALIZED
    assert "claim_kind in ('verified', 'superseded')" in NORMALIZED
    assert "already has an incompatible immutable claim" in NORMALIZED


def test_auditor_exposes_no_apply_or_mutating_sql_mode() -> None:
    source = AUDITOR.read_text(encoding="utf-8")
    lowered = source.lower()
    assert "--apply" not in lowered
    assert "set transaction isolation level repeatable read, read only" in lowered
    assert "statement_timeout" in lowered
    assert 'source_database = "ai"' in lowered
    assert 'target_database = "platform"' in lowered
    assert "mutation_authorized" in lowered
    assert "password" not in "\n".join(line for line in lowered.splitlines() if "emits no connection" not in line)
    for mutation in ("insert into", "update ", "delete from", "truncate ", "alter table"):
        assert mutation not in lowered


def test_copy_order_is_deterministic_parents_first_and_exposes_cycles() -> None:
    relations = [_relation("working.child", 2), _relation("working.parent", 1), _relation("working.peer", 3)]
    foreign_keys = [ForeignKey("working.child", "working.parent", "child_parent_fk", "FOREIGN KEY")]
    first = deterministic_copy_order(relations, foreign_keys)
    second = deterministic_copy_order(reversed(relations), reversed(foreign_keys))
    assert first == second
    positions = {item["relation"]: item["order"] for item in first}
    assert positions["working.parent"] < positions["working.child"]
    assert all(not item["unresolved_cycle_dependencies"] for item in first)

    cycle = deterministic_copy_order(
        [_relation("working.a", 0), _relation("working.b", 0)],
        [
            ForeignKey("working.a", "working.b", "a_b_fk", "FOREIGN KEY"),
            ForeignKey("working.b", "working.a", "b_a_fk", "FOREIGN KEY"),
        ],
    )
    assert cycle[0]["relation"] == "working.a"
    assert cycle[0]["unresolved_cycle_dependencies"] == ["working.b"]

    self_cycle = deterministic_copy_order(
        [_relation("working.node", 1)],
        [ForeignKey("working.node", "working.node", "node_parent_fk", "FOREIGN KEY")],
    )
    assert self_cycle[0]["unresolved_cycle_dependencies"] == ["working.node"]


def test_copy_order_inventories_but_does_not_double_copy_partition_children() -> None:
    parent = Relation("ops.events", "ops", "events", "p", False, 10)
    child = Relation("ops.events_2026", "ops", "events_2026", "r", True, 10)
    order = deterministic_copy_order([child, parent], [])
    assert [item["relation"] for item in order] == ["ops.events"]


def test_fixture_manifest_is_deterministic_and_reports_parity_without_copying() -> None:
    source = [_relation("working.message", 7), _relation("working.person", 2)]
    target = [_relation("working.message", 6)]
    foreign_keys = [ForeignKey("working.message", "working.person", "message_person_fk", "FOREIGN KEY")]
    kwargs = {
        "source_relations": source,
        "target_relations": target,
        "source_foreign_keys": foreign_keys,
        "source_extensions": [{"name": "pgcrypto", "version": "1.3", "schema": "public"}],
        "target_extensions": [{"name": "pgcrypto", "version": "1.3", "schema": "public"}],
        "source_roles": [{"name": "platform_runtime", "can_login": True}],
        "target_roles": [{"name": "platform_runtime", "can_login": True}],
        "caller_references": [],
        "zero_caller_proof": {"other_sessions": 0, "prepared_transactions": 0},
        "source_snapshot": _snapshot("ai", "10:10:", "0/100"),
        "target_snapshot": _snapshot("platform", "20:20:", "0/200"),
        "repo_revision": "1" * 40,
        "live_config_attestations": [_attestation()],
    }
    first = build_manifest(**kwargs)
    second = build_manifest(**kwargs)
    assert first == second
    assert first["manifest_sha256"] == second["manifest_sha256"]
    assert first["source_snapshot_sha256"] == second["source_snapshot_sha256"]
    assert first["mode"] == "read_only_dry_run"
    assert first["mutation_authorized"] is False
    assert first["zero_caller_gate_passed"] is True
    assert len(first["source_snapshot_sha256"]) == 64
    assert len(first["target_snapshot_sha256"]) == 64
    parity = {item["relation"]: item for item in first["row_parity"]}
    assert parity["working.message"]["status"] == "different"
    assert parity["working.person"]["status"] == "missing_target"

    with_static_caller = build_manifest(
        **{**kwargs, "caller_references": [CallerReference("compose.yaml", 1, "db_database_ai_default")]}
    )
    assert with_static_caller["zero_caller_gate_passed"] is False

    without_fence = build_manifest(**{**kwargs, "live_config_attestations": []})
    assert without_fence["zero_caller_gate_passed"] is False
    assert without_fence["caller_gate_components"]["attested_live_config_fence"] is False

    without_database_observations = build_manifest(**{**kwargs, "zero_caller_proof": {}})
    assert without_database_observations["zero_caller_gate_passed"] is False


def test_caller_inventory_reports_location_but_not_line_contents(tmp_path: Path) -> None:
    server = tmp_path / "server"
    server.mkdir()
    (server / "runtime.py").write_text('database = "ai"  # secret-like text must not be emitted\n', encoding="utf-8")
    references = scan_runtime_callers(tmp_path)
    assert references == [CallerReference("server/runtime.py", 1, "database_ai_literal")]
    assert "secret-like" not in repr(references)

    (tmp_path / "compose.yaml").write_text(
        "services:\n  app:\n    environment:\n      DB_DATABASE: ${DB_DATABASE:-ai}\n",
        encoding="utf-8",
    )
    engine = tmp_path / "engine"
    engine.mkdir()
    (engine / "runtime.go").write_text('const database = "ai"\n', encoding="utf-8")
    references = scan_runtime_callers(tmp_path)
    assert CallerReference("compose.yaml", 4, "db_database_ai_default") in references


def test_caller_inventory_covers_runtime_config_types_without_self_matching(tmp_path: Path) -> None:
    fixtures = {
        ".env": "DB_DATABASE=ai\n",
        "compose.production.yaml": "services:\n  api:\n    environment:\n      DB_DATABASE: ai\n",
        "workbench/api/.env.production": "DB_DATABASE=ai\n",
        "workbench/api/.env.local": "DATABASE_NAME=ai\n",
        "deploy/runtime.env": "PGDATABASE=ai\n",
        "deploy/runtime.json": '{"DB_DATABASE":"ai"}\n',
        "deploy/runtime.jsonc": '{"DB_DATABASE":"ai"}\n',
        "deploy/runtime.ini": "DB_NAME=ai\n",
        "deploy/runtime.toml": 'database = "ai"\n',
        "docker/worker/Dockerfile": "ENV POSTGRES_DB=ai\n",
        "scripts/start.ps1": '$env:DB_DATABASE = "ai"\n',
        "scripts/start.js": 'const options = {database: "ai"};\n',
        "server/config.ts": 'const url = "postgresql://user:redacted@db:5432/ai";\n',
    }
    for relative, content in fixtures.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    auditor = tmp_path / "scripts" / "audit.py"
    auditor.write_text('SOURCE_DATABASE = "ai"\nTARGET_DATABASE = "platform"\n', encoding="utf-8")
    actual_auditor = tmp_path / "scripts" / "audit_ai_platform_consolidation.py"
    actual_auditor.write_text('database = "ai"\n', encoding="utf-8")

    references = scan_runtime_callers(tmp_path)
    found_paths = {item.path for item in references}
    assert found_paths == set(fixtures)
    assert "scripts/audit.py" not in found_paths
    assert "scripts/audit_ai_platform_consolidation.py" not in found_paths


def test_live_config_attestation_is_time_revision_and_fence_bound(tmp_path: Path) -> None:
    evidence = tmp_path / "fence.json"
    key = b"pytest-fence-key-material-32-bytes-minimum"
    source = _snapshot("ai", "10:10:", "0/100")
    target = _snapshot("platform", "20:20:", "0/200")
    payload = _signed_fence_payload(source, target, key)
    evidence.write_text(json.dumps(payload), encoding="utf-8")
    accepted = load_live_config_attestations([evidence], tmp_path, "1" * 40, source, target, {"pytest-key": key})
    assert accepted[0].gate_passed is True
    assert accepted[0].signature_verified is True
    assert accepted[0].sha256

    wrong_revision = load_live_config_attestations([evidence], tmp_path, "2" * 40, source, target, {"pytest-key": key})
    assert wrong_revision[0].gate_passed is False

    for name, overrides in (
        ("wrong-target", {"target_database": "other"}),
        ("wrong-cluster", {"target_system_identifier": "987654321"}),
        ("wrong-target-oid", {"target_database_oid": 99_999}),
        ("active-target-writer", {"target_active_writer_count": 1}),
    ):
        evidence.write_text(json.dumps(_signed_fence_payload(source, target, key, **overrides)), encoding="utf-8")
        rejected = load_live_config_attestations([evidence], tmp_path, "1" * 40, source, target, {"pytest-key": key})
        assert rejected[0].gate_passed is False, name

    tampered = _signed_fence_payload(source, target, key)
    tampered["target_database"] = "other"
    evidence.write_text(json.dumps(tampered), encoding="utf-8")
    rejected_signature = load_live_config_attestations(
        [evidence], tmp_path, "1" * 40, source, target, {"pytest-key": key}
    )
    assert rejected_signature[0].signature_verified is False
    assert rejected_signature[0].gate_passed is False

    stale_source = SnapshotObservation(**{**asdict(source), "observed_at": "2026-08-29T20:06:00+00:00"})
    stale_target = SnapshotObservation(**{**asdict(target), "observed_at": "2026-08-29T20:06:01+00:00"})
    evidence.write_text(
        json.dumps(_signed_fence_payload(stale_source, stale_target, key, valid_until="2026-08-29T20:05:00Z")),
        encoding="utf-8",
    )
    stale = load_live_config_attestations(
        [evidence], tmp_path, "1" * 40, stale_source, stale_target, {"pytest-key": key}
    )
    assert stale[0].gate_passed is False


def test_0049_pg18_apply_and_append_only_rollback_when_service_is_available() -> None:
    service = os.getenv("PLATFORM_0049_TEST_SERVICE")
    if not service:
        pytest.skip("set PLATFORM_0049_TEST_SERVICE for rollback-only PostgreSQL 18 proof")
    psycopg = pytest.importorskip("psycopg")
    body = SQL.split("BEGIN;", 1)[1].rsplit("COMMIT;", 1)[0]

    audit_connection = psycopg.connect(f"service={service}", autocommit=False)
    try:
        begin_read_only(audit_connection, "platform")
        with audit_connection.cursor() as cursor:
            cursor.execute("SHOW transaction_read_only")
            assert cursor.fetchone()[0] == "on"
            cursor.execute("SHOW transaction_isolation")
            assert cursor.fetchone()[0] == "repeatable read"
        assert isinstance(fetch_roles(audit_connection), list)
    finally:
        audit_connection.rollback()
        audit_connection.close()

    connection = psycopg.connect(f"service={service}", autocommit=False)
    before: tuple[str | None, str | None, str | None]
    try:
        with connection.cursor() as cursor:
            cursor.execute("SHOW server_version_num")
            assert int(cursor.fetchone()[0]) >= 180000
            cursor.execute(
                "SELECT to_regclass('public.platform_consolidation_checkpoint')::text, "
                "to_regclass('public.platform_consolidation_proof_receipt')::text, "
                "to_regclass('public.platform_consolidation_receipt_claim')::text"
            )
            before = cursor.fetchone()
            cursor.execute(body)
            cursor.execute("SAVEPOINT namespace_collision_probe")
            with pytest.raises(psycopg.errors.RaiseException, match="refuses to replace"):
                cursor.execute(body)
            cursor.execute("ROLLBACK TO SAVEPOINT namespace_collision_probe")
            cursor.execute("RELEASE SAVEPOINT namespace_collision_probe")
            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_checkpoint (
                    plan_id, phase_key, relation_key, attempt_key, required_proof_kind,
                    checkpoint_status, source_snapshot_id, target_snapshot_id,
                    source_snapshot_sha256, target_snapshot_sha256, manifest_sha256, repository_revision,
                    source_snapshot_observed_at, target_snapshot_observed_at,
                    source_row_count, target_row_count,
                    proof_ref, recorded_by
                ) VALUES (
                    '11111111-1111-1111-1111-111111111111', 'inventory', '__phase__',
                    'rollback-test', 'inventory', 'planned', '10:10:', '20:20:',
                    decode(repeat('00', 32), 'hex'), decode(repeat('01', 32), 'hex'),
                    decode(repeat('02', 32), 'hex'), repeat('1', 40), now(), now(), NULL, NULL,
                    'test/rollback', 'pytest'
                ) RETURNING id
                """
            )
            checkpoint_id = cursor.fetchone()[0]
            cursor.execute("SAVEPOINT append_only_probe")
            with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                cursor.execute(
                    "UPDATE public.platform_consolidation_checkpoint SET proof_ref = 'changed' WHERE id = %s",
                    (checkpoint_id,),
                )
            cursor.execute("ROLLBACK TO SAVEPOINT append_only_probe")
            cursor.execute("RELEASE SAVEPOINT append_only_probe")

            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_proof_receipt (
                    checkpoint_id, proof_kind, result, proof_sha256, details, observed_by
                ) VALUES (%s, 'inventory', 'pass', decode(repeat('11', 32), 'hex'),
                    '{"note":"append-only-probe"}'::jsonb, 'pytest')
                RETURNING id
                """,
                (checkpoint_id,),
            )
            receipt_id = cursor.fetchone()[0]
            cursor.execute("SET CONSTRAINTS platform_consolidation_verified_requires_pass IMMEDIATE")
            mutation_probes = (
                (
                    "DELETE FROM public.platform_consolidation_checkpoint WHERE id = %s",
                    (checkpoint_id,),
                ),
                (
                    "UPDATE public.platform_consolidation_proof_receipt SET result = 'fail' WHERE id = %s",
                    (receipt_id,),
                ),
                (
                    "DELETE FROM public.platform_consolidation_proof_receipt WHERE id = %s",
                    (receipt_id,),
                ),
                ("TRUNCATE public.platform_consolidation_proof_receipt", None),
                ("TRUNCATE public.platform_consolidation_checkpoint CASCADE", None),
            )
            for index, (statement, parameters) in enumerate(mutation_probes):
                savepoint = f"mutation_probe_{index}"
                cursor.execute(f"SAVEPOINT {savepoint}")
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    cursor.execute(statement, parameters)
                cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                cursor.execute(f"RELEASE SAVEPOINT {savepoint}")

            cursor.execute("SET CONSTRAINTS platform_consolidation_verified_requires_pass DEFERRED")

            cursor.execute("SAVEPOINT unequal_verified_probe")
            with pytest.raises(psycopg.errors.CheckViolation):
                cursor.execute(
                    """
                    INSERT INTO public.platform_consolidation_checkpoint (
                        plan_id, phase_key, attempt_key, required_proof_kind, checkpoint_status,
                        source_snapshot_id, target_snapshot_id, source_snapshot_sha256,
                        target_snapshot_sha256, manifest_sha256, repository_revision, source_snapshot_observed_at,
                        target_snapshot_observed_at, source_row_count, target_row_count,
                        proof_ref, verified_receipt_id, recorded_by
                    ) VALUES (
                        '22222222-2222-2222-2222-222222222222', 'parity', 'unequal',
                        'row_parity', 'verified', '10:10:', '20:20:',
                        decode(repeat('22', 32), 'hex'), decode(repeat('23', 32), 'hex'),
                        decode(repeat('24', 32), 'hex'), repeat('1', 40), now(), now(), 2, 1,
                        'test/unequal', '22222222-2222-2222-2222-222222222223', 'pytest'
                    )
                    """
                )
            cursor.execute("ROLLBACK TO SAVEPOINT unequal_verified_probe")
            cursor.execute("RELEASE SAVEPOINT unequal_verified_probe")

            cursor.execute("SAVEPOINT missing_proof_probe")
            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_checkpoint (
                    plan_id, phase_key, attempt_key, required_proof_kind, checkpoint_status,
                    source_snapshot_id, target_snapshot_id, source_snapshot_sha256,
                    target_snapshot_sha256, manifest_sha256, repository_revision, source_snapshot_observed_at,
                    target_snapshot_observed_at, source_row_count, target_row_count,
                    proof_ref, verified_receipt_id, recorded_by
                ) VALUES (
                    '33333333-3333-3333-3333-333333333333', 'parity', 'missing-proof',
                    'row_parity', 'verified', '10:10:', '20:20:',
                    decode(repeat('33', 32), 'hex'), decode(repeat('34', 32), 'hex'),
                    decode(repeat('35', 32), 'hex'), repeat('1', 40), now(), now(), 1, 1,
                    'test/missing-proof', '33333333-3333-3333-3333-333333333334', 'pytest'
                )
                """
            )
            with pytest.raises(
                psycopg.errors.RaiseException, match="requires its exact unsuperseded passing row_parity receipt"
            ):
                cursor.execute("SET CONSTRAINTS platform_consolidation_verified_requires_pass IMMEDIATE")
            cursor.execute("ROLLBACK TO SAVEPOINT missing_proof_probe")
            cursor.execute("RELEASE SAVEPOINT missing_proof_probe")

            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            cursor.execute("SAVEPOINT wrong_proof_kind_probe")
            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_checkpoint (
                    id, plan_id, phase_key, attempt_key, required_proof_kind, checkpoint_status,
                    source_snapshot_id, target_snapshot_id, source_snapshot_sha256,
                    target_snapshot_sha256, manifest_sha256, repository_revision, source_snapshot_observed_at,
                    target_snapshot_observed_at, source_row_count, target_row_count,
                    proof_ref, verified_receipt_id, recorded_by
                ) VALUES (
                    '66666666-6666-6666-6666-666666666660',
                    '66666666-6666-6666-6666-666666666666', 'parity', 'wrong-kind',
                    'row_parity', 'verified', '60:60:', '61:61:',
                    decode(repeat('66', 32), 'hex'), decode(repeat('67', 32), 'hex'),
                    decode(repeat('68', 32), 'hex'), repeat('1', 40), now(), now(), 1, 1,
                    'test/wrong-kind', '66666666-6666-6666-6666-666666666661', 'pytest'
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_proof_receipt (
                    id, checkpoint_id, proof_kind, result, proof_sha256, details, observed_by
                ) VALUES (
                    '66666666-6666-6666-6666-666666666661',
                    '66666666-6666-6666-6666-666666666660', 'inventory', 'pass',
                    decode(repeat('69', 32), 'hex'),
                    jsonb_build_object(
                        'phase_key', 'parity', 'relation_key', '__phase__',
                        'proof_kind', 'inventory', 'source_snapshot_id', '60:60:',
                        'target_snapshot_id', '61:61:',
                        'source_snapshot_sha256', repeat('66', 32),
                        'target_snapshot_sha256', repeat('67', 32),
                        'manifest_sha256', repeat('68', 32), 'repository_revision', repeat('1', 40)
                    ), 'pytest'
                )
                """
            )
            with pytest.raises(psycopg.errors.RaiseException, match="exact unsuperseded passing row_parity"):
                cursor.execute("SET CONSTRAINTS platform_consolidation_verified_requires_pass IMMEDIATE")
            cursor.execute("ROLLBACK TO SAVEPOINT wrong_proof_kind_probe")
            cursor.execute("RELEASE SAVEPOINT wrong_proof_kind_probe")

            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
            cursor.execute("SAVEPOINT unbound_proof_probe")
            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_checkpoint (
                    id, plan_id, phase_key, attempt_key, required_proof_kind, checkpoint_status,
                    source_snapshot_id, target_snapshot_id, source_snapshot_sha256,
                    target_snapshot_sha256, manifest_sha256, repository_revision, source_snapshot_observed_at,
                    target_snapshot_observed_at, source_row_count, target_row_count,
                    proof_ref, verified_receipt_id, recorded_by
                ) VALUES (
                    '77777777-7777-7777-7777-777777777770',
                    '77777777-7777-7777-7777-777777777777', 'parity', 'unbound',
                    'row_parity', 'verified', '70:70:', '71:71:',
                    decode(repeat('77', 32), 'hex'), decode(repeat('78', 32), 'hex'),
                    decode(repeat('79', 32), 'hex'), repeat('1', 40), now(), now(), 1, 1,
                    'test/unbound', '77777777-7777-7777-7777-777777777771', 'pytest'
                )
                """
            )
            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_proof_receipt (
                    id, checkpoint_id, proof_kind, result, proof_sha256, details, observed_by
                ) VALUES (
                    '77777777-7777-7777-7777-777777777771',
                    '77777777-7777-7777-7777-777777777770', 'row_parity', 'pass',
                    decode(repeat('7a', 32), 'hex'),
                    jsonb_build_object(
                        'phase_key', 'parity', 'relation_key', '__phase__',
                        'proof_kind', 'row_parity', 'source_snapshot_id', '70:70:',
                        'target_snapshot_id', '71:71:',
                        'source_snapshot_sha256', repeat('00', 32),
                        'target_snapshot_sha256', repeat('78', 32),
                        'manifest_sha256', repeat('79', 32), 'repository_revision', repeat('1', 40)
                    ), 'pytest'
                )
                """
            )
            with pytest.raises(psycopg.errors.RaiseException, match="unbound proof receipt"):
                cursor.execute("SET CONSTRAINTS platform_consolidation_verified_requires_pass IMMEDIATE")
            cursor.execute("ROLLBACK TO SAVEPOINT unbound_proof_probe")
            cursor.execute("RELEASE SAVEPOINT unbound_proof_probe")

            cursor.execute("SET CONSTRAINTS ALL DEFERRED")

            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_checkpoint (
                    id, plan_id, phase_key, attempt_key, required_proof_kind, checkpoint_status,
                    source_snapshot_id, target_snapshot_id, source_snapshot_sha256,
                    target_snapshot_sha256, manifest_sha256, repository_revision, source_snapshot_observed_at,
                    target_snapshot_observed_at, source_row_count, target_row_count,
                    proof_ref, verified_receipt_id, recorded_by
                ) VALUES (
                    '44444444-4444-4444-4444-444444444440',
                    '44444444-4444-4444-4444-444444444444', 'parity', 'with-proof',
                    'row_parity', 'verified', '10:10:', '20:20:',
                    decode(repeat('44', 32), 'hex'), decode(repeat('45', 32), 'hex'),
                    decode(repeat('46', 32), 'hex'), repeat('1', 40), now(), now(), 3, 3,
                    'test/with-proof', '55555555-5555-5555-5555-555555555550', 'pytest'
                ) RETURNING id
                """
            )
            verified_checkpoint_id = cursor.fetchone()[0]
            cursor.execute(
                """
                INSERT INTO public.platform_consolidation_proof_receipt (
                    id, checkpoint_id, proof_kind, result, proof_sha256, details, observed_by
                ) VALUES ('55555555-5555-5555-5555-555555555550', %s, 'row_parity', 'pass',
                    decode(repeat('55', 32), 'hex'),
                    jsonb_build_object(
                        'phase_key', 'parity', 'relation_key', '__phase__',
                        'proof_kind', 'row_parity', 'source_snapshot_id', '10:10:',
                        'target_snapshot_id', '20:20:',
                        'source_snapshot_sha256', repeat('44', 32),
                        'target_snapshot_sha256', repeat('45', 32),
                        'manifest_sha256', repeat('46', 32), 'repository_revision', repeat('1', 40)
                    ), 'pytest')
                """,
                (verified_checkpoint_id,),
            )
            cursor.execute("SET CONSTRAINTS platform_consolidation_verified_requires_pass IMMEDIATE")
            cursor.execute("SET CONSTRAINTS platform_consolidation_bound_receipt_no_supersede IMMEDIATE")
            cursor.execute(
                "SELECT claim_kind, checkpoint_id, successor_receipt_id "
                "FROM public.platform_consolidation_receipt_claim WHERE receipt_id = %s",
                ("55555555-5555-5555-5555-555555555550",),
            )
            assert cursor.fetchone() == ("verified", verified_checkpoint_id, None)

            cursor.execute("SAVEPOINT receipt_claim_key_probe")
            with pytest.raises(psycopg.errors.UniqueViolation):
                cursor.execute(
                    """
                    INSERT INTO public.platform_consolidation_receipt_claim (
                        receipt_id, claim_kind, successor_receipt_id
                    ) VALUES (
                        '55555555-5555-5555-5555-555555555550', 'superseded',
                        '55555555-5555-5555-5555-555555555550'
                    )
                    """
                )
            cursor.execute("ROLLBACK TO SAVEPOINT receipt_claim_key_probe")
            cursor.execute("RELEASE SAVEPOINT receipt_claim_key_probe")

            cursor.execute("SAVEPOINT superseded_bound_proof_probe")
            with pytest.raises(psycopg.errors.RaiseException, match="cannot be superseded"):
                cursor.execute(
                    """
                    INSERT INTO public.platform_consolidation_proof_receipt (
                        checkpoint_id, supersedes_receipt_id, proof_kind, result,
                        proof_sha256, details, observed_by
                    ) VALUES (%s, '55555555-5555-5555-5555-555555555550', 'row_parity', 'fail',
                        decode(repeat('56', 32), 'hex'), '{"reason":"stale"}'::jsonb, 'pytest')
                    """,
                    (verified_checkpoint_id,),
                )
            cursor.execute("ROLLBACK TO SAVEPOINT superseded_bound_proof_probe")
            cursor.execute("RELEASE SAVEPOINT superseded_bound_proof_probe")

            immutable_claim_probes = (
                "UPDATE public.platform_consolidation_receipt_claim SET claim_kind = 'superseded' "
                "WHERE receipt_id = '55555555-5555-5555-5555-555555555550'",
                "DELETE FROM public.platform_consolidation_receipt_claim "
                "WHERE receipt_id = '55555555-5555-5555-5555-555555555550'",
                "TRUNCATE public.platform_consolidation_receipt_claim",
            )
            for index, statement in enumerate(immutable_claim_probes):
                savepoint = f"claim_mutation_probe_{index}"
                cursor.execute(f"SAVEPOINT {savepoint}")
                with pytest.raises(psycopg.errors.RaiseException, match="append-only"):
                    cursor.execute(statement)
                cursor.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
                cursor.execute(f"RELEASE SAVEPOINT {savepoint}")
    finally:
        connection.rollback()
        connection.close()

    proof = psycopg.connect(f"service={service}", autocommit=False)
    try:
        with proof.cursor() as cursor:
            cursor.execute(
                "SELECT to_regclass('public.platform_consolidation_checkpoint')::text, "
                "to_regclass('public.platform_consolidation_proof_receipt')::text, "
                "to_regclass('public.platform_consolidation_receipt_claim')::text"
            )
            assert cursor.fetchone() == before
    finally:
        proof.rollback()
        proof.close()
