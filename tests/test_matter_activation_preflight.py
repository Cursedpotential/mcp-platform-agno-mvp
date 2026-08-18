"""Tests for the read-only Matter activation preflight.

Byline: Codex · GPT-5 · 2026-08-15; native Weaviate amendment 2026-08-18
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import SimpleNamespace

from weaviate.classes.config import DataType, Property


SCRIPT = Path(__file__).parents[1] / "scripts" / "_matter_activation_preflight.py"
SPEC = importlib.util.spec_from_file_location("matter_activation_preflight", SCRIPT)
assert SPEC and SPEC.loader
preflight = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = preflight
SPEC.loader.exec_module(preflight)


def _snapshot(*, present: bool = False):
    return {
        "server_version_num": 180004,
        "extensions": ["pg_duckdb", "pgcrypto", "postgis", "vector"],
        "markers": {f"{number:04d}": present for number in range(26, 31)},
        "horizon_uses_visible_from": present,
    }


def test_static_release_contract_is_current() -> None:
    checks = preflight.static_checks()
    assert checks
    assert {check.status for check in checks} == {"PASS"}


def test_native_evidence_contract_requires_versioned_typed_source_clock() -> None:
    good = SimpleNamespace(
        EVIDENCE_VECTOR_COLLECTION_VERSION=1,
        EVIDENCE_VECTOR_COLLECTION="EvidenceChunkV1",
        EVIDENCE_VECTOR_ALIAS="EvidenceChunks",
        EVIDENCE_EMBED_MODEL="nvidia/nv-embed-v1",
        EVIDENCE_EMBED_DIM=4096,
        evidence_vector_properties=lambda: [
            Property(
                name=name,
                data_type={
                    "text": DataType.TEXT,
                    "uuid": DataType.UUID,
                    "boolean": DataType.BOOL,
                    "date": DataType.DATE,
                    "int": DataType.INT,
                }[data_type],
                index_range_filters=requires_range or None,
            )
            for name, (data_type, requires_range) in preflight.REQUIRED_NATIVE_PROPERTIES.items()
        ],
    )
    checks = preflight.evaluate_native_evidence_contract(good)
    assert all(check.status == "PASS" for check in checks)

    wrong = SimpleNamespace(**vars(good))
    wrong.EVIDENCE_VECTOR_COLLECTION_VERSION = 2
    wrong.evidence_vector_properties = lambda: [
        property_ for property_ in good.evidence_vector_properties() if property_.name != "source_available_from"
    ]
    failed = preflight.evaluate_native_evidence_contract(wrong)
    assert {check.check_id for check in failed if check.status == "FAIL"} == {
        "weaviate.native_contract_identity",
        "weaviate.native_contract_properties",
    }


def test_pinned_weaviate_version_floor_is_static_and_fail_closed(tmp_path) -> None:
    deploy = tmp_path / "deploy"
    deploy.mkdir()
    manifest = deploy / "data-weaviate.yaml"

    manifest.write_text("services:\n  weaviate:\n    image: semitechnologies/weaviate:1.26.0\n", encoding="utf-8")
    assert preflight.pinned_weaviate_version_checks(tmp_path)[0].status == "PASS"

    manifest.write_text("services:\n  weaviate:\n    image: semitechnologies/weaviate:1.25.9\n", encoding="utf-8")
    assert preflight.pinned_weaviate_version_checks(tmp_path)[0].status == "FAIL"

    manifest.write_text("services:\n  weaviate:\n    image: semitechnologies/weaviate:latest\n", encoding="utf-8")
    assert preflight.pinned_weaviate_version_checks(tmp_path)[0].status == "FAIL"


def test_static_scope_does_not_invoke_database_credentials_or_services(monkeypatch) -> None:
    monkeypatch.setattr(preflight, "static_checks", lambda: [])
    monkeypatch.setattr(preflight, "git_checks", lambda: [])
    monkeypatch.setattr(preflight, "database_snapshot", lambda dsn: (_ for _ in ()).throw(AssertionError("database")))
    monkeypatch.setattr(preflight, "credential_checks", lambda: (_ for _ in ()).throw(AssertionError("credentials")))
    monkeypatch.setattr(preflight, "service_checks", lambda args: (_ for _ in ()).throw(AssertionError("services")))

    checks, exit_code = preflight.run(
        SimpleNamespace(
            scope="static",
            database_dsn_env="MATTER_PREFLIGHT_DATABASE_URL",
            expected_migrations=None,
            workbench_url="https://workbench.invalid",
            spine_url="https://spine.invalid",
            weaviate_url="https://weaviate.invalid",
        )
    )

    assert checks == []
    assert exit_code == 0


def test_credentials_require_long_distinct_inbound_and_spine_keys() -> None:
    good = preflight.credential_checks({"WORKBENCH_API_KEY": "w" * 32, "AGENTOS_API_TOKEN": "spine-secret"})
    assert all(check.status == "PASS" for check in good)

    missing = preflight.credential_checks({})
    assert all(check.status == "FAIL" for check in missing)

    reused = preflight.credential_checks({"WORKBENCH_API_KEY": "x" * 32, "AGENTOS_API_TOKEN": "x" * 32})
    assert next(check for check in reused if check.check_id == "credential.separation").status == "FAIL"


def test_database_snapshot_requires_uniform_migration_state() -> None:
    absent = preflight.evaluate_database_snapshot(_snapshot(), "absent")
    assert all(check.status == "PASS" for check in absent)

    present = preflight.evaluate_database_snapshot(_snapshot(present=True), "present")
    assert all(check.status == "PASS" for check in present)

    partial = _snapshot()
    partial["markers"]["0026"] = True
    checks = preflight.evaluate_database_snapshot(partial, "absent")
    assert next(check for check in checks if check.check_id == "database.migration_state").status == "FAIL"


def test_database_snapshot_fails_wrong_engine_or_extensions() -> None:
    snapshot = _snapshot()
    snapshot["server_version_num"] = 170009
    snapshot["extensions"] = ["pgcrypto"]
    checks = preflight.evaluate_database_snapshot(snapshot, "absent")
    assert next(check for check in checks if check.check_id == "database.postgres18").status == "FAIL"
    assert next(check for check in checks if check.check_id == "database.extensions").status == "FAIL"


def test_service_checks_cover_matter_knowledge_graphiti_and_weaviate(monkeypatch) -> None:
    calls = []

    def fake_probe(check_id, base_url, path, token=None):
        calls.append((check_id, base_url, path, token))
        return preflight.Check(check_id, "PASS", "fixture")

    monkeypatch.setattr(preflight, "_probe", fake_probe)
    args = SimpleNamespace(
        workbench_url="https://workbench.invalid",
        spine_url="https://spine.invalid",
        weaviate_url="https://weaviate.invalid",
    )
    checks = preflight.service_checks(
        args,
        {"WORKBENCH_API_KEY": "workbench-key", "AGENTOS_API_TOKEN": "spine-key"},
    )

    assert all(check.status == "PASS" for check in checks)
    assert [call[0] for call in calls] == [
        "service.workbench_health",
        "service.workbench_matter",
        "service.workbench_knowledge_prefilter",
        "service.workbench_graphiti_namespace",
        "service.spine_matter",
        "service.weaviate",
    ]
    assert "case_id=primary&lane=evidence" in calls[2][2]
    assert "group_id=platform" in calls[3][2]
    assert calls[1][3] == "workbench-key"
    assert calls[4][3] == "spine-key"


def test_database_and_activation_scopes_default_to_honest_migration_states(monkeypatch) -> None:
    monkeypatch.setenv("MATTER_PREFLIGHT_DATABASE_URL", "fixture-dsn")
    monkeypatch.setattr(preflight, "static_checks", lambda: [])
    monkeypatch.setattr(preflight, "git_checks", lambda: [])
    monkeypatch.setattr(preflight, "credential_checks", lambda: [])
    monkeypatch.setattr(preflight, "service_checks", lambda args: [])

    database_args = SimpleNamespace(
        scope="database",
        database_dsn_env="MATTER_PREFLIGHT_DATABASE_URL",
        expected_migrations=None,
        workbench_url="",
        spine_url="",
        weaviate_url="",
    )
    monkeypatch.setattr(preflight, "database_snapshot", lambda dsn: _snapshot(present=False))
    database_checks, database_code = preflight.run(database_args)
    assert database_code == 0
    assert next(check for check in database_checks if check.check_id == "database.migration_state").status == "PASS"

    activation_args = SimpleNamespace(
        scope="activation",
        database_dsn_env="MATTER_PREFLIGHT_DATABASE_URL",
        expected_migrations=None,
        workbench_url="https://workbench.invalid",
        spine_url="https://spine.invalid",
        weaviate_url="https://weaviate.invalid",
    )
    monkeypatch.setattr(preflight, "database_snapshot", lambda dsn: _snapshot(present=True))
    activation_checks, activation_code = preflight.run(activation_args)
    assert activation_code == 0
    assert next(check for check in activation_checks if check.check_id == "database.migration_state").status == "PASS"


def test_static_cli_report_contains_no_secret_values(capsys) -> None:
    exit_code = preflight.main(["--scope", "static", "--json"])
    report = capsys.readouterr().out
    assert exit_code in {0, 2}  # the test itself makes git dirty before commit
    assert "WORKBENCH_API_KEY" not in report
    assert "AGENTOS_API_TOKEN" not in report
