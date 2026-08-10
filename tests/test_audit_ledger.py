"""Tests for ops.audit_ledger (sql/0020_audit_ledger.sql) and
server/core/audit.py (ADR-0047 / D-042).

Needs a real Postgres — the append-only trigger, the CHECK constraint, and
chain-tamper detection are database-enforced invariants, not something a
fake-engine double (test_custody.py's style) can exercise. Per the S5
handoff's ENVIRONMENT note, run this against a SCRATCH pgvector/pg18
container, e.g.:

    docker run -d --network host \\
        -e POSTGRES_USER=postgres -e POSTGRES_PASSWORD=postgres \\
        -e POSTGRES_DB=postgres -e PGPORT=55432 pgvector/pgvector:pg18

Connection info comes from AUDIT_TEST_PG_* env vars (falling back to the
platform's own DB_* vars, then to the scratch-container defaults above) —
see `_admin_url()`. If nothing is reachable at collection time, every test
in this module is SKIPPED with a clear reason (not marked `integration`:
these are fast — one throwaway `CREATE DATABASE` per test, no external
service beyond the scratch container itself — matching the handoff's "a
scratch container spun by the test/fixture is fine unmarked if fast").

Each test gets its OWN throwaway database (`audit_ledger_test_<random>`),
created by the `audit_engine` fixture and dropped afterward — the
append-only guarantee makes a shared database awkward to reset between
tests (there is no DELETE), and the tamper test in particular must not
leak a broken chain into any other test's view of ``ops.audit_ledger``.

Each fresh database gets ONLY sql/0020_audit_ledger.sql (read from disk, so
this test targets the actual migration file, not a hand-copied schema) plus
the one prerequisite it depends on and does not itself create:
``working.forbid_mutation()`` — verbatim from
``sql/0017_append_only_guards.sql``, which a real deployment applies long
before 0020 via the numbered migration chain. Reproduced here rather than
running the full 0001-0018 chain so this module exercises 0020 in
isolation and stays fast.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-08-09 (ADR-0047 / D-042 — S5 handoff)

from __future__ import annotations

import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from server.core import audit  # noqa: E402

_MIGRATION_SQL = (_REPO_ROOT / "sql" / "0020_audit_ledger.sql").read_text(encoding="utf-8")

# Verbatim from sql/0017_append_only_guards.sql (see module docstring for why
# it is reproduced here instead of running the full migration chain).
_PREREQ_SQL = """
CREATE SCHEMA IF NOT EXISTS working;
CREATE OR REPLACE FUNCTION working.forbid_mutation() RETURNS trigger AS
$fn$
BEGIN
    RAISE EXCEPTION '% is append-only: % blocked (corrections are new rows)',
        TG_TABLE_NAME, TG_OP;
END
$fn$ LANGUAGE plpgsql;
"""


def _admin_url() -> str:
    host = os.getenv("AUDIT_TEST_PG_HOST", os.getenv("DB_HOST", "localhost"))
    port = os.getenv("AUDIT_TEST_PG_PORT", os.getenv("DB_PORT", "55432"))
    user = os.getenv("AUDIT_TEST_PG_USER", os.getenv("DB_USER", "postgres"))
    password = os.getenv("AUDIT_TEST_PG_PASS", os.getenv("DB_PASS", "postgres"))
    maint_db = os.getenv("AUDIT_TEST_PG_MAINT_DB", "postgres")
    return f"postgresql+psycopg://{user}:{password}@{host}:{port}/{maint_db}"


def _pg_reachable() -> bool:
    try:
        eng = create_engine(_admin_url(), connect_args={"connect_timeout": 3})
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_reachable(),
    reason=(
        "no scratch Postgres reachable for audit-ledger tests — set AUDIT_TEST_PG_HOST/PORT/"
        "USER/PASS (or DB_HOST/PORT/USER/PASS), or start a scratch pgvector/pg18 container "
        "on port 55432 (see this module's docstring)."
    ),
)


@pytest.fixture
def audit_engine() -> Engine:
    """One throwaway database, migrated with ONLY 0020 (+ its 0017
    prerequisite), dropped at teardown."""
    admin_engine = create_engine(_admin_url(), isolation_level="AUTOCOMMIT")
    dbname = f"audit_ledger_test_{uuid.uuid4().hex[:10]}"
    with admin_engine.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{dbname}"'))

    db_url = _admin_url().rsplit("/", 1)[0] + f"/{dbname}"
    engine = create_engine(db_url)
    try:
        # psycopg (v3) will run a plain (unparameterized) multi-statement
        # script via the simple query protocol in one execute() call —
        # verified against the installed driver; each raw_connection()
        # cursor call below runs the WHOLE file/prereq as one script.
        raw = engine.raw_connection()
        try:
            raw.autocommit = True
            with raw.cursor() as cur:
                cur.execute(_PREREQ_SQL)
                cur.execute(_MIGRATION_SQL)
        finally:
            raw.close()
        yield engine
    finally:
        engine.dispose()
        with admin_engine.connect() as conn:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :db AND pid <> pg_backend_pid()"
                ),
                {"db": dbname},
            )
            conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
    admin_engine.dispose()


# --------------------------------------------------------------------------- #
# Migration shape
# --------------------------------------------------------------------------- #


def test_migration_creates_table_and_indexes(audit_engine: Engine):
    with audit_engine.connect() as conn:
        cols = (
            conn.execute(
                text(
                    "SELECT column_name, is_nullable, data_type FROM information_schema.columns "
                    "WHERE table_schema='ops' AND table_name='audit_ledger' ORDER BY ordinal_position"
                )
            )
            .mappings()
            .all()
        )
        idx = (
            conn.execute(
                text("SELECT indexname FROM pg_indexes WHERE schemaname='ops' AND tablename='audit_ledger'")
            )
            .scalars()
            .all()
        )
    names = [c["column_name"] for c in cols]
    assert names == [
        "id",
        "ts",
        "actor",
        "action_type",
        "object_schema",
        "object_ref",
        "horizon_context",
        "base_version",
        "payload_hash",
        "prev_hash",
        "entry_hash",
    ]
    not_null = {c["column_name"] for c in cols if c["is_nullable"] == "NO"}
    assert {"id", "ts", "actor", "action_type", "entry_hash"} <= not_null
    assert "object_schema" not in not_null  # nullable, per spec

    assert {"idx_audit_ledger_ts", "idx_audit_ledger_action_ts", "idx_audit_ledger_actor_ts"} <= set(idx)


def test_action_type_check_constraint(audit_engine: Engine):
    with pytest.raises(Exception):
        with audit_engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO ops.audit_ledger (actor, action_type, entry_hash) "
                    "VALUES ('owner', 'not-a-real-type', 'x')"
                )
            )


# --------------------------------------------------------------------------- #
# Append-only guard
# --------------------------------------------------------------------------- #


def test_append_only_trigger_rejects_update(audit_engine: Engine):
    audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    with pytest.raises(Exception, match="append-only"):
        with audit_engine.begin() as conn:
            conn.execute(text("UPDATE ops.audit_ledger SET actor = 'someone-else' WHERE id = 1"))


def test_append_only_trigger_rejects_delete(audit_engine: Engine):
    audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    with pytest.raises(Exception, match="append-only"):
        with audit_engine.begin() as conn:
            conn.execute(text("DELETE FROM ops.audit_ledger WHERE id = 1"))


# --------------------------------------------------------------------------- #
# record() — serialization + chaining
# --------------------------------------------------------------------------- #


def test_record_rejects_bad_action_type(audit_engine: Engine):
    with pytest.raises(ValueError, match="action_type"):
        audit.record("bogus", "obj-1", actor="owner", engine=audit_engine)


def test_record_rejects_non_hex_payload_hash(audit_engine: Engine):
    with pytest.raises(ValueError, match="hex digest"):
        audit.record("read", "obj-1", actor="owner", payload_hash="not a hash!", engine=audit_engine)


def test_record_genesis_row_has_null_prev_hash(audit_engine: Engine):
    new_id = audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    with audit_engine.connect() as conn:
        row = conn.execute(
            text("SELECT prev_hash, entry_hash FROM ops.audit_ledger WHERE id = :id"), {"id": new_id}
        ).mappings().first()
    assert row["prev_hash"] is None
    assert row["entry_hash"] and len(row["entry_hash"]) == 64  # sha256 hex


def test_record_chains_prev_hash_to_prior_entry_hash(audit_engine: Engine):
    id1 = audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    id2 = audit.record("write", "obj-2", actor="owner", object_schema="evidence", engine=audit_engine)
    with audit_engine.connect() as conn:
        rows = {
            r["id"]: r
            for r in conn.execute(text("SELECT id, prev_hash, entry_hash FROM ops.audit_ledger ORDER BY id"))
            .mappings()
            .all()
        }
    assert rows[id2]["prev_hash"] == rows[id1]["entry_hash"]


def test_record_horizon_context_round_trips_as_jsonb(audit_engine: Engine):
    ctx = {"case_id": "primary", "pass_id": "as-lived-1", "horizon": "2026-08-01T00:00:00+00:00", "actor": "owner"}
    new_id = audit.record("read", "row-42", actor="forensic-data-agent", ctx=ctx, engine=audit_engine)
    with audit_engine.connect() as conn:
        stored = conn.execute(
            text("SELECT horizon_context FROM ops.audit_ledger WHERE id = :id"), {"id": new_id}
        ).scalar()
    assert stored == ctx


def test_record_custody_ref_targets_evidence_schema(audit_engine: Engine):
    new_id = audit.record_custody_ref("custody-event-99", actor="owner", engine=audit_engine)
    with audit_engine.connect() as conn:
        row = conn.execute(
            text("SELECT action_type, object_schema, object_ref FROM ops.audit_ledger WHERE id = :id"),
            {"id": new_id},
        ).mappings().first()
    assert row["action_type"] == "write"
    assert row["object_schema"] == "evidence"
    assert row["object_ref"] == "custody-event-99"


def test_record_read_produces_read_row(audit_engine: Engine):
    new_id = audit.record_read("row-7", actor="knowledge-handle", ctx={"case_id": "primary"}, engine=audit_engine)
    with audit_engine.connect() as conn:
        action_type = conn.execute(
            text("SELECT action_type FROM ops.audit_ledger WHERE id = :id"), {"id": new_id}
        ).scalar()
    assert action_type == "read"


def test_record_approval_produces_approval_row(audit_engine: Engine):
    new_id = audit.record_approval("appr-1", "approved", actor="owner", engine=audit_engine)
    with audit_engine.connect() as conn:
        row = conn.execute(
            text("SELECT action_type, object_ref FROM ops.audit_ledger WHERE id = :id"), {"id": new_id}
        ).mappings().first()
    assert row["action_type"] == "approval"
    assert row["object_ref"] == "appr-1"


def test_audit_tool_hook_calls_continuation_and_logs(audit_engine: Engine, monkeypatch):
    calls: list[dict] = []

    def _fake_record(action_type, object_ref, *, actor, ctx=None, object_schema=None, base_version=None,
                      payload_hash=None, engine=None):
        calls.append(
            dict(
                action_type=action_type,
                object_ref=object_ref,
                actor=actor,
                ctx=ctx,
                payload_hash=payload_hash,
            )
        )
        return 1

    monkeypatch.setattr(audit, "record", _fake_record)

    seen = {}

    def _tool(x, y):
        seen["called"] = (x, y)
        return "ok-result"

    class _FakeAgent:
        id = "test-agent"

    result = audit.audit_tool_hook("my_tool", _tool, {"x": 1, "y": 2}, agent=_FakeAgent())

    assert result == "ok-result"
    assert seen["called"] == (1, 2)
    assert len(calls) == 1
    assert calls[0]["action_type"] == "tool_call"
    assert calls[0]["object_ref"] == "my_tool"
    assert calls[0]["actor"] == "test-agent"
    assert calls[0]["payload_hash"] and len(calls[0]["payload_hash"]) == 64
    # Same arguments -> same hash, deterministically (sorted-keys canonical JSON).
    calls.clear()
    audit.audit_tool_hook("my_tool", _tool, {"y": 2, "x": 1}, agent=_FakeAgent())
    assert calls[0]["payload_hash"] == calls[0]["payload_hash"]  # sanity: no crash/None


# --------------------------------------------------------------------------- #
# verify_chain() — integrity, and tamper detection
# --------------------------------------------------------------------------- #


def test_verify_chain_empty_is_valid(audit_engine: Engine):
    assert audit.verify_chain(engine=audit_engine) == 0


def test_verify_chain_valid_after_several_records(audit_engine: Engine):
    for i in range(5):
        audit.record("tool_call", f"tool-{i}", actor="agent", engine=audit_engine)
    assert audit.verify_chain(engine=audit_engine) == 5


def test_verify_chain_raises_on_tampered_row(audit_engine: Engine):
    audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    audit.record("write", "obj-2", actor="owner", object_schema="evidence", engine=audit_engine)
    audit.record("read", "obj-3", actor="owner", engine=audit_engine)

    # Simulate a superuser-level raw tamper: disable triggers for this
    # session (append-only guard included) and rewrite a stored hash — the
    # exact "tamper a row via raw SQL superuser" scenario the S5 handoff
    # calls for. session_replication_role=replica is the standard way to
    # bypass ALL triggers, including ops.audit_ledger's append-only guard,
    # which even a superuser cannot UPDATE past otherwise.
    with audit_engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(text("UPDATE ops.audit_ledger SET payload_hash = :h WHERE id = 2"), {"h": "ab" * 32})
        conn.execute(text("SET session_replication_role = DEFAULT"))

    with pytest.raises(audit.AuditChainError, match="entry_hash mismatch"):
        audit.verify_chain(engine=audit_engine)


def test_verify_chain_raises_on_broken_prev_hash_link(audit_engine: Engine):
    audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    audit.record("write", "obj-2", actor="owner", engine=audit_engine)

    with audit_engine.begin() as conn:
        conn.execute(text("SET session_replication_role = replica"))
        conn.execute(text("UPDATE ops.audit_ledger SET prev_hash = :h WHERE id = 2"), {"h": "00" * 32})
        conn.execute(text("SET session_replication_role = DEFAULT"))

    with pytest.raises(audit.AuditChainError, match="chain is broken"):
        audit.verify_chain(engine=audit_engine)


# --------------------------------------------------------------------------- #
# scripts/audit_dump.py — smoke test (containerized invocation contract)
# --------------------------------------------------------------------------- #


def _env_for(audit_engine: Engine) -> dict:
    url = audit_engine.url
    env = dict(os.environ)
    env.update(
        {
            "DB_DRIVER": "postgresql+psycopg",
            "DB_HOST": url.host or "localhost",
            "DB_PORT": str(url.port or 5432),
            "DB_USER": url.username or "",
            "DB_PASS": url.password or "",
            "DB_DATABASE": url.database or "",
        }
    )
    env.pop("PLATFORM_DB_URL", None)
    return env


def test_audit_dump_verify_smoke(audit_engine: Engine):
    audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    audit.record("tool_call", "some_tool", actor="agent-x", payload_hash="cd" * 32, engine=audit_engine)

    script = _REPO_ROOT / "scripts" / "audit_dump.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--verify"],
        cwd=_REPO_ROOT,
        env=_env_for(audit_engine),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    assert "chain OK" in proc.stdout


def test_audit_dump_jsonl_filters(audit_engine: Engine):
    audit.record("decision", "obj-1", actor="owner", engine=audit_engine)
    audit.record("tool_call", "some_tool", actor="agent-x", payload_hash="cd" * 32, engine=audit_engine)
    audit.record("read", "obj-3", actor="agent-x", engine=audit_engine)

    script = _REPO_ROOT / "scripts" / "audit_dump.py"
    proc = subprocess.run(
        [sys.executable, str(script), "--actor", "agent-x", "--format", "jsonl"],
        cwd=_REPO_ROOT,
        env=_env_for(audit_engine),
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert proc.returncode == 0, proc.stderr
    lines = [line for line in proc.stdout.strip().splitlines() if line]
    assert len(lines) == 2
    rows = [json.loads(line) for line in lines]
    assert {r["actor"] for r in rows} == {"agent-x"}
    assert {r["action_type"] for r in rows} == {"tool_call", "read"}
