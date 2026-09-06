"""H-04 contract: every chunk read goes through working.content_chunk_message.

These are deliberately *text* assertions against the real SQL that ships, not
assertions against mocks.  The previous coverage on this path was mock-only and
therefore passed for the entire period during which every one of these queries
named ``working.normalized_record_chunk`` -- a table
``sql/0058_the_reckoning.sql:97`` had already dropped (D-116).  A mock cannot
tell you a table does not exist; the emitted SQL can.

The live test at the bottom applies migration 0072 inside a transaction and
rolls back, so it proves the DDL and the rewritten function against the real
database without writing anything.

Byline: Claude Code · Opus 5 · 2026-09-05
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4

import pytest

ROOT = Path(__file__).resolve().parents[1]
MIGRATION = ROOT / "sql" / "0072_content_chunk_message_bridge.sql"

_REWIRED_MODULES = (
    "server/evidence/vector_projection.py",
    "server/evidence/native_activation.py",
    "server/evidence/store.py",
    "server/proffer/query.py",
)

# A comment, docstring, or error message may still *name* the dropped table --
# that is how the history stays legible.  What must not survive is an
# executable reference: the table sitting behind a SQL clause keyword.
_SQL_FRAGMENT = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE|TABLE)\s+working\.normalized_record_chunk\b",
    re.IGNORECASE,
)


def _source(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


@pytest.mark.parametrize("relative", _REWIRED_MODULES)
def test_no_module_emits_sql_naming_the_dropped_chunk_table(relative: str) -> None:
    offenders = _SQL_FRAGMENT.findall(_source(relative))
    assert offenders == [], f"{relative} still emits SQL against the dropped table: {offenders}"


@pytest.mark.parametrize(
    "relative",
    ("server/evidence/vector_projection.py", "server/evidence/native_activation.py", "server/proffer/query.py"),
)
def test_every_chunk_reader_joins_the_bridge(relative: str) -> None:
    source = _source(relative)
    assert "working.content_chunk_message" in source
    assert "working.content_chunk" in source


def test_projection_drain_resolves_one_message_per_job_through_the_center() -> None:
    """One job -> one message coordinate (2026-08-29 dual-graph rule)."""
    source = _source("server/evidence/vector_projection.py")
    assert "JOIN working.content_chunk chunk ON chunk.id=job.chunk_id " in source
    assert "ON bridge.chunk_id=chunk.id AND bridge.is_center " in source
    assert "JOIN working.normalized_record nr ON nr.id=bridge.message_id " in source
    # chunker_id and source_content_hash have no column on content_chunk; they
    # come from the generation and the message row respectively.
    assert "gen.chunker_id" in source
    assert "encode(nr.source_content_sha256,'hex') AS source_content_hash" in source


def test_projection_kind_default_is_the_surviving_chunk_model() -> None:
    for relative in ("server/evidence/vector_projection.py", "server/evidence/native_activation.py"):
        source = _source(relative)
        assert "'normalized_record_chunk'" not in source
        assert "projection_kind,'content_chunk'" in source


def test_python_chunk_writer_is_retired_and_quarantined() -> None:
    source = _source("server/evidence/store.py")
    assert "INSERT INTO working.normalized_record_chunk" not in source
    assert "raise NotImplementedError(" in source
    assert "Go message-window chunker" in source
    quarantine = ROOT / ".review_hold" / "store_normalized_record_chunk_writer_retired_20260905.txt"
    assert quarantine.exists(), "retired code must be quarantined, never deleted"
    assert "source_content_sha256" in quarantine.read_text(encoding="utf-8")


def test_store_record_batch_refuses_chunks() -> None:
    from server.evidence.store import store_record_batch

    # Fails closed before any record validation or database access.
    with pytest.raises(NotImplementedError, match="Python chunk writer is retired"):
        store_record_batch([], [object()], object())  # type: ignore[list-item, arg-type]


def test_evidence_embedder_contract_is_the_live_nim_model() -> None:
    from server.core.evidence_vector_store import EVIDENCE_EMBED_DIM, EVIDENCE_EMBED_MODEL

    # nvidia/nv-embed-v1 was end-of-lifed on NIM 2026-08-25 (HTTP 410).
    assert EVIDENCE_EMBED_MODEL == "nvidia/nemotron-3-embed-1b"
    assert EVIDENCE_EMBED_DIM == 2048


def test_migration_0072_declares_the_ruled_bridge_shape() -> None:
    sql = MIGRATION.read_text(encoding="utf-8")
    assert "CREATE TABLE IF NOT EXISTS working.content_chunk_message" in sql
    assert "PRIMARY KEY (chunk_id, message_id)" in sql
    assert "REFERENCES working.content_chunk(id) ON DELETE CASCADE" in sql
    assert "REFERENCES working.normalized_record(id) ON DELETE CASCADE" in sql
    assert "content_chunk_message_message_idx" in sql
    assert "created_at TIMESTAMPTZ NOT NULL DEFAULT now()" in sql
    # Append-only (Q9) and the queue re-anchor.
    assert "is append-only" in sql
    assert "evidence_vector_projection_job_chunk_fk" in sql
    # The function keeps its signature and now selects through the bridge.
    assert "working.enqueue_evidence_vector_projection(p_record_ids uuid[], p_reason text)" in sql
    assert "FROM working.content_chunk_message bridge" in sql


@pytest.mark.integration
def test_0072_applies_and_the_function_answers_on_a_live_database() -> None:
    """Apply 0072 in a transaction, exercise it with zero rows, then ROLL BACK.

    A minimal end-to-end chain is deliberately NOT inserted: reaching
    ``working.normalized_record`` requires an ``evidence.evidence_hash`` row,
    and fabricating a custody digest to satisfy a test is exactly the thing
    custody exists to prevent.  So the assertions are structural plus a real
    zero-row invocation of the rewritten function.
    """
    pytest.importorskip("sqlalchemy")
    from sqlalchemy import create_engine, text

    from server.core.url import build_db_url

    if not (os.getenv("PLATFORM_DB_URL") or os.getenv("DB_PASS")):
        pytest.skip("no database credentials configured")

    engine = create_engine(build_db_url())
    statements = MIGRATION.read_text(encoding="utf-8")
    # The file wraps itself in BEGIN/COMMIT; strip both so the test owns the
    # transaction and can roll back.
    body = statements.replace("\nBEGIN;\n", "\n", 1)
    body = body[: body.rindex("COMMIT;")]

    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text(body))
            # Idempotent: applying twice inside one transaction must be a no-op.
            connection.execute(text(body))

            assert connection.execute(text("SELECT to_regclass('working.content_chunk_message')")).scalar() is not None
            assert (
                connection.execute(
                    text(
                        "SELECT count(*) FROM pg_constraint WHERE conrelid="
                        "'working.evidence_vector_projection_job'::regclass "
                        "AND conname='evidence_vector_projection_job_chunk_fk'"
                    )
                ).scalar_one()
                == 1
            )

            empty = connection.execute(
                text("SELECT working.enqueue_evidence_vector_projection(CAST(:ids AS uuid[]), :reason)"),
                {"ids": [], "reason": "h04-contract-test"},
            ).scalar_one()
            unknown = connection.execute(
                text("SELECT working.enqueue_evidence_vector_projection(CAST(:ids AS uuid[]), :reason)"),
                {"ids": [str(uuid4())], "reason": "h04-contract-test"},
            ).scalar_one()
            assert empty == 0 and unknown == 0

            with pytest.raises(Exception, match="VECTOR_PROJECTION_REASON_REQUIRED"):
                connection.execute(
                    text("SELECT working.enqueue_evidence_vector_projection(CAST(:ids AS uuid[]), :reason)"),
                    {"ids": [], "reason": "  "},
                )
        finally:
            transaction.rollback()

    with engine.connect() as connection:
        assert connection.execute(text("SELECT to_regclass('working.content_chunk_message')")).scalar() is None
