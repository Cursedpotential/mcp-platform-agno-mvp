"""Tests for scripts/bootstrap_platform_database.py.

Fully offline: no live database, no psycopg connection is ever opened. Every function that would
touch a real cluster (`gather_live_state`, `apply_bootstrap`, `pg_connect`) is either not called
here or is called only through `main()` paths proven not to reach it (dry-run, refused targets,
missing password, drift, runtime-safety violation) via monkeypatched stand-ins that raise if
invoked. This mirrors tests/test_check_deploy_drift.py's fixture/mock-only style for the sibling
read-only-by-default script.
"""
# Byline: Claude Code · Sonnet 5 · 2026-08-27

from __future__ import annotations

import re

import pytest

from scripts.bootstrap_platform_database import (
    APPLY_0036_SCRIPT,
    CONTEXT_IMPORT_SQL,
    CONTEXT_IMPORT_WRITER_ROLE,
    CONTEXT_OWNER_ROLE,
    CONTEXT_READER_ROLE,
    DEFAULT_EXTENSIONS,
    FOUNDATION_MIGRATION_ID,
    FOUNDATION_SQL,
    PLATFORM_ADMIN_ROLE,
    PLATFORM_RUNTIME_ROLE,
    PROTECTED_DATABASES,
    RUNTIME_PASSWORD_ENV,
    TARGET_DATABASE,
    BootstrapState,
    ConnectionSettings,
    LedgerRow,
    LiveState,
    build_plan,
    classify_state,
    discover_required_extensions,
    foundation_checksum,
    guard_target_database,
    load_connection_settings,
    main,
    missing_extensions,
    require_runtime_password,
    runtime_role_violates_safety,
    verify_invariants,
)

_FAKE_SETTINGS = ConnectionSettings(host="example-host", port="5432", user="ai", password="ai")
_FAKE_DIGEST = b"\x01" * 32
_OTHER_DIGEST = b"\x02" * 32


def _state(**overrides) -> LiveState:
    base = dict(
        ai_database_exists=True,
        target_database_exists=False,
        target_database_owner=None,
        admin_role_exists=False,
        runtime_role_exists=False,
        runtime_role_login=None,
        runtime_role_or_memberships_dangerous=None,
        context_owner_role_exists=False,
        admin_is_context_owner_member=False,
        context_owner_has_create_on_database=False,
        context_import_writer_role_exists=False,
        context_reader_role_exists=False,
        runtime_is_context_import_writer_member=False,
        runtime_is_context_reader_member=False,
        public_has_connect_or_temp=None,
        schema_version_table_exists=False,
        schema_version_active_unique_index_exists=False,
        ledger_row=None,
    )
    base.update(overrides)
    return LiveState(**base)


def _fully_bootstrapped_state(ddl_hash: bytes = _FAKE_DIGEST) -> LiveState:
    return _state(
        target_database_exists=True,
        target_database_owner=PLATFORM_ADMIN_ROLE,
        admin_role_exists=True,
        runtime_role_exists=True,
        runtime_role_login=True,
        runtime_role_or_memberships_dangerous=False,
        context_owner_role_exists=True,
        admin_is_context_owner_member=True,
        context_owner_has_create_on_database=True,
        context_import_writer_role_exists=True,
        context_reader_role_exists=True,
        runtime_is_context_import_writer_member=True,
        runtime_is_context_reader_member=True,
        public_has_connect_or_temp=False,
        schema_version_table_exists=True,
        schema_version_active_unique_index_exists=True,
        ledger_row=LedgerRow(FOUNDATION_MIGRATION_ID, ddl_hash, "active"),
    )


# --------------------------------------------------------------------------------------- secrets


def test_load_connection_settings_env_overrides_dotenv():
    env = {"DB_HOST": "10.0.0.9", "DB_USER": "svc", "DB_PASS": "hunter2", "DB_PORT": "5433"}
    settings = load_connection_settings(env=env)
    assert settings.host == "10.0.0.9"
    assert settings.user == "svc"
    assert settings.port == "5433"


def test_load_connection_settings_host_flag_wins_over_env():
    settings = load_connection_settings(target_host="override-host", env={"DB_HOST": "env-host"})
    assert settings.host == "override-host"


def test_load_connection_settings_defaults_when_nothing_set():
    settings = load_connection_settings(env={})
    assert settings.host == "localhost"
    assert settings.port == "5432"


def test_connection_settings_describe_never_contains_password():
    settings = load_connection_settings(env={"DB_PASS": "super-secret-value"})
    described = settings.describe(TARGET_DATABASE)
    assert "super-secret-value" not in described
    assert "***" in described


def test_connection_settings_dsn_has_no_password():
    settings = ConnectionSettings(host="h", port="5432", user="u", password="super-secret-value")
    assert "super-secret-value" not in settings.dsn(TARGET_DATABASE)


def test_require_runtime_password_missing_raises():
    with pytest.raises(ValueError, match=RUNTIME_PASSWORD_ENV):
        require_runtime_password(env={})


def test_require_runtime_password_returns_the_value():
    assert require_runtime_password(env={RUNTIME_PASSWORD_ENV: "correct-horse"}) == "correct-horse"


def test_require_runtime_password_error_message_never_echoes_a_value():
    # There is no value to echo when it's missing — assert the message doesn't leak anything
    # from a differently-named secret that happens to also be set in the same env mapping.
    try:
        require_runtime_password(env={"DB_PASS": "unrelated-secret"})
    except ValueError as exc:
        assert "unrelated-secret" not in str(exc)
    else:
        pytest.fail("expected ValueError")


# ------------------------------------------------------------------------------------ safe names


@pytest.mark.parametrize("bad", sorted(PROTECTED_DATABASES) + ["scratch", "Platform", "PLATFORM"])
def test_guard_target_database_refuses_anything_but_platform(bad):
    with pytest.raises(ValueError, match="refusing --database"):
        guard_target_database(bad)


def test_guard_target_database_allows_exactly_platform():
    guard_target_database(TARGET_DATABASE)  # must not raise


# -------------------------------------------------------------------------------------- checksum


def test_foundation_checksum_is_stable_32_byte_sha256_digest():
    first = foundation_checksum()
    second = foundation_checksum()
    assert first == second
    assert isinstance(first, bytes)
    assert len(first) == 32
    assert re.fullmatch(r"[0-9a-f]{64}", first.hex())


def test_foundation_checksum_changes_when_file_content_changes(tmp_path):
    a = tmp_path / "a.sql"
    b = tmp_path / "b.sql"
    a.write_text("CREATE TABLE public.schema_version (version TEXT);", encoding="utf-8")
    b.write_text("CREATE TABLE public.schema_version (version TEXT, extra TEXT);", encoding="utf-8")
    assert foundation_checksum(a) != foundation_checksum(b)


# ---------------------------------------------------------------------------- extension discovery


def test_discover_required_extensions_falls_back_when_0036_path_is_missing(tmp_path):
    assert discover_required_extensions(tmp_path / "does_not_exist.sql") == DEFAULT_EXTENSIONS


@pytest.mark.skipif(
    not CONTEXT_IMPORT_SQL.exists(),
    reason="sql/0036_context_import_foundation.sql is owned by a different lane and not committed "
    "to every checkout yet — skip rather than hard-fail where it hasn't landed",
)
def test_discover_required_extensions_against_the_real_0036_file():
    # Confirmed by reading the file: it declares zero CREATE EXTENSION statements (uuidv7() is
    # native, digest() comes from pgcrypto, already shipped by sql/bootstrap/platform_foundation.sql)
    # — so the live cross-check falls back to this bootstrap's own default, not an empty tuple.
    assert discover_required_extensions(CONTEXT_IMPORT_SQL) == DEFAULT_EXTENSIONS
    assert missing_extensions(discover_required_extensions()) == ()


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
    assert classify_state(None, expected_digest=_FAKE_DIGEST) is BootstrapState.NOT_BOOTSTRAPPED


def test_classify_state_up_to_date_when_hash_matches():
    row = LedgerRow(FOUNDATION_MIGRATION_ID, _FAKE_DIGEST, "active")
    assert classify_state(row, expected_digest=_FAKE_DIGEST) is BootstrapState.UP_TO_DATE


def test_classify_state_drifted_when_hash_differs():
    row = LedgerRow(FOUNDATION_MIGRATION_ID, _FAKE_DIGEST, "active")
    assert classify_state(row, expected_digest=_OTHER_DIGEST) is BootstrapState.DRIFTED


# --------------------------------------------------------------------------- runtime role safety


def test_runtime_role_violates_safety_false_when_role_absent():
    assert runtime_role_violates_safety(_state(runtime_role_or_memberships_dangerous=None)) is False


def test_runtime_role_violates_safety_false_when_closure_clean():
    assert runtime_role_violates_safety(_state(runtime_role_or_memberships_dangerous=False)) is False


def test_runtime_role_violates_safety_true_when_dangerous():
    assert runtime_role_violates_safety(_state(runtime_role_or_memberships_dangerous=True)) is True


# ------------------------------------------------------------------------------------- plan build


def test_build_plan_marks_everything_pending_on_a_fresh_cluster():
    plan = build_plan(_state(), extension_gap=())
    # "ai present" and "runtime holds no dangerous attribute" are trivially satisfied on a fresh
    # cluster (nothing to violate yet) — every role/database/grant/revoke/ledger step is not.
    trivially_satisfied_markers = ("verify `ai`", "holds no SUPERUSER")
    assert all(
        not step.already_satisfied
        for step in plan
        if not any(marker in step.name for marker in trivially_satisfied_markers)
    )
    names = " ".join(step.name for step in plan)
    assert PLATFORM_ADMIN_ROLE in names
    assert PLATFORM_RUNTIME_ROLE in names
    assert CONTEXT_OWNER_ROLE in names
    assert CONTEXT_IMPORT_WRITER_ROLE in names
    assert CONTEXT_READER_ROLE in names
    assert "revoke" in names
    assert "platform_foundation.sql" in names
    assert "unique-active-migration_id" in names


def test_build_plan_marks_satisfied_steps_when_already_bootstrapped():
    plan = build_plan(_fully_bootstrapped_state(), extension_gap=())
    assert all(step.already_satisfied for step in plan)


def test_build_plan_flags_runtime_safety_violation():
    plan = build_plan(_state(runtime_role_or_memberships_dangerous=True), extension_gap=())
    violation_step = next(step for step in plan if "holds no SUPERUSER" in step.name)
    assert not violation_step.already_satisfied
    assert "VIOLATION" in violation_step.detail


def test_build_plan_grant_step_not_satisfied_until_membership_confirmed():
    plan = build_plan(_state(admin_role_exists=True, context_owner_role_exists=True), extension_gap=())
    grant_step = next(step for step in plan if step.name.startswith(f"grant {CONTEXT_OWNER_ROLE!r}"))
    assert not grant_step.already_satisfied


def test_build_plan_revoke_step_pending_when_public_still_has_access():
    plan = build_plan(_state(public_has_connect_or_temp=True), extension_gap=())
    revoke_step = next(step for step in plan if "revoke CONNECT/TEMPORARY" in step.name)
    assert not revoke_step.already_satisfied
    assert "PUBLIC still has" in revoke_step.detail


def test_build_plan_reports_extension_gap_without_hiding_it():
    plan = build_plan(_state(), extension_gap=("vector", "citext"))
    gap_step = next(step for step in plan if "needs extensions beyond" in step.name)
    assert "vector" in gap_step.detail
    assert "citext" in gap_step.detail
    assert not gap_step.already_satisfied


def test_no_plan_step_ever_mentions_drop():
    for state in (_state(), _fully_bootstrapped_state()):
        plan = build_plan(state, extension_gap=())
        assert not any("drop" in step.name.lower() or "drop" in step.detail.lower() for step in plan)


# ---------------------------------------------------------------------------- post-apply verify


def test_verify_invariants_ok_on_a_fully_bootstrapped_state():
    result = verify_invariants(_fully_bootstrapped_state(), expected_digest=_FAKE_DIGEST)
    assert result.ok is True
    assert result.failures == ()


@pytest.mark.parametrize(
    "override,expected_snippet",
    [
        ({"ai_database_exists": False}, "ai"),
        ({"target_database_exists": False}, "platform"),
        ({"target_database_owner": "someone_else"}, "owner"),
        ({"runtime_role_login": False}, "not LOGIN"),
        ({"runtime_role_or_memberships_dangerous": True}, "dangerous attribute"),
        ({"admin_is_context_owner_member": False}, CONTEXT_OWNER_ROLE),
        ({"context_owner_has_create_on_database": False}, "CREATE"),
        ({"runtime_is_context_import_writer_member": False}, CONTEXT_IMPORT_WRITER_ROLE),
        ({"runtime_is_context_reader_member": False}, CONTEXT_READER_ROLE),
        ({"public_has_connect_or_temp": True}, "PUBLIC"),
        ({"schema_version_active_unique_index_exists": False}, "unique-active-migration_id"),
        ({"ledger_row": None}, "no active"),
    ],
)
def test_verify_invariants_catches_each_violation(override, expected_snippet):
    state = _fully_bootstrapped_state()
    for key, value in override.items():
        state = _state(**{**state.__dict__, key: value})
    result = verify_invariants(state, expected_digest=_FAKE_DIGEST)
    assert result.ok is False
    assert any(expected_snippet in failure for failure in result.failures)


def test_verify_invariants_catches_ledger_hash_mismatch():
    state = _fully_bootstrapped_state(ddl_hash=_OTHER_DIGEST)
    result = verify_invariants(state, expected_digest=_FAKE_DIGEST)
    assert result.ok is False
    assert any("ddl_hash does not match" in failure for failure in result.failures)


# ----------------------------------------------------------------------- CLI: refuses before I/O


def test_main_refuses_non_platform_target_before_any_connection(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("must not attempt a connection for a refused target")

    monkeypatch.setattr("scripts.bootstrap_platform_database.load_connection_settings", _boom)
    monkeypatch.setattr("scripts.bootstrap_platform_database.gather_live_state", _boom)
    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--database", "ai"]) == 1
    assert main(["--database", "ai", "--apply"]) == 1
    assert main(["--database", "scratch"]) == 1


def test_main_dry_run_never_requires_or_reads_the_runtime_password(monkeypatch):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings", lambda target_host=None: _FAKE_SETTINGS
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.gather_live_state", lambda settings: _state())

    def _boom(*_args, **_kwargs):
        raise AssertionError("dry run (no --apply) must never require PLATFORM_DATABASE_PASSWORD")

    monkeypatch.setattr("scripts.bootstrap_platform_database.require_runtime_password", _boom)
    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main([]) == 0


def _fail_password(*_args, **_kwargs):
    raise ValueError(f"{RUNTIME_PASSWORD_ENV} must be set")


def test_main_refuses_apply_without_runtime_password(monkeypatch):
    def _boom(*_args, **_kwargs):
        raise AssertionError("must not connect when the runtime password is missing")

    monkeypatch.setattr("scripts.bootstrap_platform_database.load_connection_settings", _boom)
    monkeypatch.setattr("scripts.bootstrap_platform_database.require_runtime_password", _fail_password)
    monkeypatch.setattr("scripts.bootstrap_platform_database.gather_live_state", _boom)
    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--apply"]) == 1


def test_main_refuses_when_drifted_even_with_apply(monkeypatch):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings", lambda target_host=None: _FAKE_SETTINGS
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.require_runtime_password", lambda: "correct-horse")
    drifted = _fully_bootstrapped_state(ddl_hash=_OTHER_DIGEST)
    monkeypatch.setattr("scripts.bootstrap_platform_database.gather_live_state", lambda settings: drifted)

    def _boom(*_args, **_kwargs):
        raise AssertionError("a DRIFTED state must never reach apply_bootstrap")

    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--apply"]) == 1


def test_main_refuses_when_ai_missing_on_target_host(monkeypatch):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings", lambda target_host=None: _FAKE_SETTINGS
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.require_runtime_password", lambda: "correct-horse")
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.gather_live_state",
        lambda settings: _state(ai_database_exists=False),
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("must not apply when the sanity check for `ai` fails")

    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--apply"]) == 1


def test_main_refuses_when_runtime_role_already_has_dangerous_attributes(monkeypatch):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings", lambda target_host=None: _FAKE_SETTINGS
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.require_runtime_password", lambda: "correct-horse")
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.gather_live_state",
        lambda settings: _state(runtime_role_exists=True, runtime_role_or_memberships_dangerous=True),
    )

    def _boom(*_args, **_kwargs):
        raise AssertionError("must not apply when platform_runtime already violates the safety contract")

    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", _boom)

    assert main(["--apply"]) == 1


def test_main_apply_success_re_reads_state_and_prints_verified(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings", lambda target_host=None: _FAKE_SETTINGS
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.require_runtime_password", lambda: "correct-horse")
    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", lambda *a, **k: None)

    from scripts.bootstrap_platform_database import foundation_checksum

    digest = foundation_checksum()
    calls = {"n": 0}

    def _gather(settings):
        calls["n"] += 1
        return _fully_bootstrapped_state(ddl_hash=digest)

    monkeypatch.setattr("scripts.bootstrap_platform_database.gather_live_state", _gather)

    assert main(["--apply"]) == 0
    assert calls["n"] == 2, "expected gather_live_state to be called once pre-apply and once post-apply"
    assert "APPLIED AND VERIFIED" in capsys.readouterr().out


def test_main_apply_does_not_claim_verified_when_post_apply_state_fails_invariants(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.bootstrap_platform_database.load_connection_settings", lambda target_host=None: _FAKE_SETTINGS
    )
    monkeypatch.setattr("scripts.bootstrap_platform_database.require_runtime_password", lambda: "correct-horse")
    monkeypatch.setattr("scripts.bootstrap_platform_database.apply_bootstrap", lambda *a, **k: None)

    from scripts.bootstrap_platform_database import foundation_checksum

    digest = foundation_checksum()
    calls = {"n": 0}

    def _gather(settings):
        calls["n"] += 1
        if calls["n"] == 1:
            return _fully_bootstrapped_state(ddl_hash=digest)  # pre-apply: clean enough to proceed
        # post-apply: something regressed (e.g. PUBLIC access crept back) — must not be reported
        # as verified even though apply_bootstrap() itself raised nothing.
        return _state(**{**_fully_bootstrapped_state(ddl_hash=digest).__dict__, "public_has_connect_or_temp": True})

    monkeypatch.setattr("scripts.bootstrap_platform_database.gather_live_state", _gather)

    assert main(["--apply"]) == 2
    out = capsys.readouterr().out
    assert "APPLIED AND VERIFIED" not in out


# ---------------------------------------------------------------- static safety of the SQL file


def test_platform_foundation_sql_never_drops_or_shells_out():
    text = FOUNDATION_SQL.read_text(encoding="utf-8").upper()
    for forbidden in ("DROP DATABASE", "DROP SCHEMA", "DROP TABLE", "DROP ROLE", "TRUNCATE"):
        assert forbidden not in text, f"{forbidden} must never appear in the foundation bootstrap SQL"


def test_platform_foundation_sql_creates_expected_roles_grants_and_ledger():
    text = FOUNDATION_SQL.read_text(encoding="utf-8")
    for role in (
        PLATFORM_ADMIN_ROLE,
        PLATFORM_RUNTIME_ROLE,
        CONTEXT_OWNER_ROLE,
        CONTEXT_IMPORT_WRITER_ROLE,
        CONTEXT_READER_ROLE,
    ):
        assert role in text
    assert f"GRANT {CONTEXT_OWNER_ROLE} TO {PLATFORM_ADMIN_ROLE}" in text
    assert f"GRANT {CONTEXT_IMPORT_WRITER_ROLE} TO {PLATFORM_RUNTIME_ROLE}" in text
    assert f"GRANT {CONTEXT_READER_ROLE} TO {PLATFORM_RUNTIME_ROLE}" in text
    assert f"GRANT CREATE ON DATABASE {TARGET_DATABASE} TO {CONTEXT_OWNER_ROLE}" in text
    assert f"REVOKE CONNECT, TEMPORARY ON DATABASE {TARGET_DATABASE} FROM PUBLIC" in text
    assert "public.schema_version" in text
    assert "CREATE EXTENSION IF NOT EXISTS pgcrypto" in text
    assert "ddl_hash" in text and "BYTEA" in text.upper()
    assert "schema_version_active_migration_uq" in text
    assert "WHERE status = 'active'" in text


def test_platform_foundation_sql_makes_runtime_login_with_no_embedded_password():
    text = FOUNDATION_SQL.read_text(encoding="utf-8")
    runtime_create_line = next(
        line for line in text.splitlines() if PLATFORM_RUNTIME_ROLE in line and "CREATE ROLE" in line
    )
    assert "LOGIN" in runtime_create_line
    # No password literal anywhere in this git-tracked file's DDL — only set at runtime via
    # scripts/bootstrap_platform_database.py's parameterized ALTER ROLE ... PASSWORD %s. Comment
    # lines are prose explaining that fact and legitimately contain the word "PASSWORD".
    ddl_only = "\n".join(line for line in text.splitlines() if not line.strip().startswith("--"))
    assert "PASSWORD" not in ddl_only.upper()


def test_platform_foundation_sql_never_grants_dangerous_attributes_to_runtime():
    # DDL only — comment lines are prose and would false-positive a naive substring scan for the
    # unnegated word (e.g. "...with SUPERUSER/.../BYPASSRLS explicitly OFF").
    ddl_lines = [
        line
        for line in FOUNDATION_SQL.read_text(encoding="utf-8").upper().splitlines()
        if not line.strip().startswith("--")
    ]
    runtime_lines = [line for line in ddl_lines if PLATFORM_RUNTIME_ROLE.upper() in line]
    assert runtime_lines, "expected at least one DDL line referencing platform_runtime"
    for dangerous in ("SUPERUSER", "CREATEDB", "CREATEROLE", "REPLICATION", "BYPASSRLS"):
        for line in runtime_lines:
            if dangerous in line:
                assert f"NO{dangerous}" in line, f"{dangerous} must appear negated (NO{dangerous}) on this DDL line"


def test_bootstrap_script_has_no_psql_or_subprocess_dependency():
    import inspect

    from scripts import bootstrap_platform_database as module

    source = inspect.getsource(module)
    # These are the actual markers of a local-client-tool dependency (a subprocess call, a path
    # to the psql binary). The bare word "psql" legitimately appears in prose (module docstring,
    # comments) explaining the equivalence to how `psql -f` would run a multi-statement file —
    # that is not a dependency, so it is not scanned for here.
    for forbidden in ("subprocess", "PGBIN", "pgbin", "shutil.which"):
        assert forbidden not in source, f"{forbidden!r} must not appear — psycopg only, no local client tool"
    assert "import psycopg" in source


# --------------------------------------------------------------- cross-file ledger compatibility


@pytest.mark.skipif(
    not APPLY_0036_SCRIPT.exists(),
    reason="scripts/apply_0036_live.py is owned by a different/root lane and not committed to "
    "every checkout yet — skip rather than hard-fail where it hasn't landed",
)
def test_schema_version_shape_matches_apply_0036_live_contract():
    apply_source = APPLY_0036_SCRIPT.read_text(encoding="utf-8")
    foundation_text = FOUNDATION_SQL.read_text(encoding="utf-8")

    insert_columns = re.search(r"INSERT INTO public\.schema_version\s*\(([^)]+)\)", apply_source, re.IGNORECASE)
    assert insert_columns, "expected an INSERT INTO public.schema_version(...) in apply_0036_live.py"
    columns = [c.strip() for c in insert_columns.group(1).split(",")]
    assert columns == [
        "version_label",
        "applies_to",
        "ddl_uri",
        "ddl_hash",
        "migration_id",
        "status",
        "notes",
        "created_by",
    ]
    for column in columns:
        if column == "created_by":
            continue  # DEFAULT current_user in the DDL, not a literal column name search target
        assert column in foundation_text, (
            f"apply_0036_live.py inserts {column!r}; not declared in platform_foundation.sql"
        )

    assert "migration_id = '0036' AND status = 'active'" in apply_source
    assert "ddl_hash" in foundation_text and "BYTEA" in foundation_text.upper()
    assert "schema_version_active_migration_uq" in foundation_text


@pytest.mark.skipif(not APPLY_0036_SCRIPT.exists(), reason="apply_0036_live.py not present in this checkout")
def test_foundation_migration_id_never_collides_with_0036():
    apply_source = APPLY_0036_SCRIPT.read_text(encoding="utf-8")
    assert "'0036'" in apply_source
    assert FOUNDATION_MIGRATION_ID != "0036"
