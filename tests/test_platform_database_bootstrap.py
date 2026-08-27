"""Tests for scripts/bootstrap_platform_database.py.

Fully offline: no live database, no psql subprocess. Every function that would touch a real
cluster (`gather_live_state`, `apply_bootstrap`, `psql_*`) is either not called here or is called
only through `main()` paths that are proven not to reach it (dry-run, protected-target refusal).
This mirrors tests/test_check_deploy_drift.py's fixture/mock-only style for the sibling
read-only-by-default script.
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-27

from __future__ import annotations

import re

import pytest

from scripts.bootstrap_platform_database import (
    CONTEXT_IMPORT_SQL,
    DEFAULT_EXTENSIONS,
    FOUNDATION_SQL,
    PLATFORM_ADMIN_ROLE,
    PLATFORM_RUNTIME_ROLE,
    PROTECTED_DATABASES,
    BootstrapState,
    ConnectionSettings,
    LiveState,
    SchemaVersionRow,
    build_plan,
    classify_state,
    discover_required_extensions,
    foundation_checksum,
    guard_target_database,
    load_connection_settings,
    main,
    missing_extensions,
    validate_identifier,
)

_FAKE_SETTINGS = ConnectionSettings("postgresql+psycopg", "ai", "ai", "example-host", "5432")


def _state(**overrides) -> LiveState:
    base = dict(
        ai_database_exists=True,
        target_database_exists=False,
        admin_role_exists=False,
        runtime_role_exists=False,
        schema_version_row=None,
    )
    base.update(overrides)
    return LiveState(**base)


# --------------------------------------------------------------------------------------- secrets


def test_load_connection_settings_env_overrides_dotenv():
    env = {"DB_HOST": "10.0.0.9", "DB_USER": "svc", "DB_PASS": "hunter2", "DB_PORT": "5433"}
    settings = load_connection_settings(env=env)
    assert settings.host == "10.0.0.9"
    assert settings.user == "svc"
    assert settings.port == "5433"
    assert settings.driver == "postgresql+psycopg"


def test_load_connection_settings_host_flag_wins_over_env():
    settings = load_connection_settings(target_host="override-host", env={"DB_HOST": "env-host"})
    assert settings.host == "override-host"


def test_connection_settings_describe_never_contains_password():
    settings = load_connection_settings(env={"DB_PASS": "super-secret-value"})
    described = settings.describe("platform")
    assert "super-secret-value" not in described
    assert "***" in described


def test_load_connection_settings_defaults_when_nothing_set():
    settings = load_connection_settings(env={})
    assert settings.host == "localhost"
    assert settings.port == "5432"
    assert settings.driver == "postgresql+psycopg"


# ------------------------------------------------------------------------------------ safe names


@pytest.mark.parametrize("protected", sorted(PROTECTED_DATABASES))
def test_guard_target_database_refuses_protected_names(protected):
    with pytest.raises(ValueError, match="refusing to target protected database"):
        guard_target_database(protected)


def test_guard_target_database_allows_platform():
    guard_target_database("platform")  # must not raise


@pytest.mark.parametrize("bad", ["Platform", "plat-form", "1platform", "platform;drop", "plat form", ""])
def test_validate_identifier_rejects_unsafe_names(bad):
    with pytest.raises(ValueError):
        validate_identifier(bad, what="--target-db")


def test_validate_identifier_accepts_safe_name():
    validate_identifier("platform", what="--target-db")  # must not raise


# -------------------------------------------------------------------------------------- checksum


def test_foundation_checksum_is_stable_sha256_hexdigest():
    first = foundation_checksum()
    second = foundation_checksum()
    assert first == second
    assert re.fullmatch(r"[0-9a-f]{64}", first)


def test_foundation_checksum_changes_when_file_content_changes(tmp_path):
    a = tmp_path / "a.sql"
    b = tmp_path / "b.sql"
    a.write_text("CREATE TABLE public.schema_version (version TEXT);", encoding="utf-8")
    b.write_text("CREATE TABLE public.schema_version (version TEXT, extra TEXT);", encoding="utf-8")
    assert foundation_checksum(a) != foundation_checksum(b)


# ---------------------------------------------------------------------------- extension discovery


def test_discover_required_extensions_defaults_when_0036_absent():
    assert not CONTEXT_IMPORT_SQL.exists(), (
        "sql/0036_context_import_foundation.sql exists now — re-run this test against the real "
        "file's CREATE EXTENSION list instead of assuming it is still missing"
    )
    assert discover_required_extensions() == DEFAULT_EXTENSIONS


def test_discover_required_extensions_parses_a_real_file(tmp_path):
    fixture = tmp_path / "0036_context_import_foundation.sql"
    fixture.write_text(
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;\n"
        "CREATE EXTENSION IF NOT EXISTS VECTOR;\n"
        "CREATE EXTENSION IF NOT EXISTS pgcrypto;  -- duplicate, should not repeat\n",
        encoding="utf-8",
    )
    assert discover_required_extensions(fixture) == ("pgcrypto", "vector")


def test_discover_required_extensions_falls_back_when_file_has_none(tmp_path):
    fixture = tmp_path / "empty.sql"
    fixture.write_text("-- nothing here\n", encoding="utf-8")
    assert discover_required_extensions(fixture) == DEFAULT_EXTENSIONS


def test_missing_extensions_reports_only_the_gap():
    assert missing_extensions(["pgcrypto", "vector", "citext"], covered=("pgcrypto",)) == ("vector", "citext")


def test_missing_extensions_empty_when_fully_covered():
    assert missing_extensions(["pgcrypto"], covered=("pgcrypto", "vector")) == ()


# -------------------------------------------------------------------------------- drift detection


def test_classify_state_not_bootstrapped_when_no_row():
    assert classify_state(None, expected_checksum="abc123") is BootstrapState.NOT_BOOTSTRAPPED


def test_classify_state_up_to_date_when_checksum_matches():
    row = SchemaVersionRow(version="0000_platform_foundation", checksum="abc123")
    assert classify_state(row, expected_checksum="abc123") is BootstrapState.UP_TO_DATE


def test_classify_state_drifted_when_checksum_differs():
    row = SchemaVersionRow(version="0000_platform_foundation", checksum="abc123")
    assert classify_state(row, expected_checksum="def456") is BootstrapState.DRIFTED


# ------------------------------------------------------------------------------------- plan build


def test_build_plan_marks_everything_pending_on_a_fresh_cluster():
    plan = build_plan("platform", _state(), extension_gap=())
    assert all(not step.already_satisfied for step in plan if "ai" not in step.name)
    names = " ".join(step.name for step in plan)
    assert PLATFORM_ADMIN_ROLE in names
    assert PLATFORM_RUNTIME_ROLE in names
    assert "platform_foundation.sql" in names


def test_build_plan_marks_satisfied_steps_when_already_bootstrapped():
    state = _state(
        target_database_exists=True,
        admin_role_exists=True,
        runtime_role_exists=True,
        schema_version_row=SchemaVersionRow(version="0000_platform_foundation", checksum="x"),
    )
    plan = build_plan("platform", state, extension_gap=())
    assert all(step.already_satisfied for step in plan)


def test_build_plan_flags_ai_missing_as_not_satisfied():
    plan = build_plan("platform", _state(ai_database_exists=False), extension_gap=())
    ai_step = next(step for step in plan if step.name.startswith("verify `ai`"))
    assert not ai_step.already_satisfied
    assert "MISSING" in ai_step.detail


def test_build_plan_reports_extension_gap_without_hiding_it():
    plan = build_plan("platform", _state(), extension_gap=("vector", "citext"))
    gap_step = next(step for step in plan if "needs extensions beyond" in step.name)
    assert "vector" in gap_step.detail
    assert "citext" in gap_step.detail
    assert not gap_step.already_satisfied


def test_no_plan_step_ever_mentions_drop():
    for state in (_state(), _state(target_database_exists=True)):
        plan = build_plan("platform", state, extension_gap=())
        assert not any("drop" in step.name.lower() or "drop" in step.detail.lower() for step in plan)


# ----------------------------------------------------------------------- CLI: refuses before I/O


def test_main_refuses_protected_target_before_any_connection(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("must not attempt a connection for a protected target")

    monkeypatch.setattr("scripts.bootstrap_platform_database.load_connection_settings", _boom)
    monkeypatch.setattr("scripts.bootstrap_platform_database.gather_live_state", _boom)
    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--target-db", "ai"]) == 1
    assert main(["--target-db", "ai", "--apply"]) == 1
    assert main(["--target-db", "postgres"]) == 1


def test_main_refuses_unsafe_identifier_before_any_connection(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("must not attempt a connection for an unsafe identifier")

    monkeypatch.setattr("scripts.bootstrap_platform_database.load_connection_settings", _boom)
    assert main(["--target-db", "plat-form; drop table x"]) == 1


def test_main_dry_run_never_applies_even_when_state_is_fresh(monkeypatch):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings",
        lambda target_host=None: _FAKE_SETTINGS,
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.resolve_pgbin", lambda explicit: None)
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.gather_live_state",
        lambda settings, target_database, pgbin: _state(),
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("dry run (no --apply) must never call apply_bootstrap")

    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--target-db", "platform"]) == 0


def test_main_refuses_when_drifted_even_with_apply(monkeypatch):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings",
        lambda target_host=None: _FAKE_SETTINGS,
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.resolve_pgbin", lambda explicit: None)
    drifted_row = SchemaVersionRow(version="0000_platform_foundation", checksum="not-the-real-checksum")
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.gather_live_state",
        lambda settings, target_database, pgbin: _state(target_database_exists=True, schema_version_row=drifted_row),
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("a DRIFTED state must never reach apply_bootstrap")

    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--target-db", "platform", "--apply"]) == 1


def test_main_refuses_when_ai_missing_on_target_host(monkeypatch):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings",
        lambda target_host=None: _FAKE_SETTINGS,
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.resolve_pgbin", lambda explicit: None)
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.gather_live_state",
        lambda settings, target_database, pgbin: _state(ai_database_exists=False),
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("must not apply when the sanity check for `ai` fails")

    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--target-db", "platform", "--apply"]) == 1


# ---------------------------------------------------------------- static safety of the SQL file


def test_platform_foundation_sql_never_drops_anything():
    text = FOUNDATION_SQL.read_text(encoding="utf-8").upper()
    for forbidden in ("DROP DATABASE", "DROP SCHEMA", "DROP TABLE", "DROP ROLE", "TRUNCATE"):
        assert forbidden not in text, f"{forbidden} must never appear in the foundation bootstrap SQL"


def test_platform_foundation_sql_creates_expected_roles_and_ledger():
    text = FOUNDATION_SQL.read_text(encoding="utf-8")
    assert PLATFORM_ADMIN_ROLE in text
    assert PLATFORM_RUNTIME_ROLE in text
    assert "public.schema_version" in text
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in text
