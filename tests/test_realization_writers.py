"""Unit tests for server.evidence.realization (Wave 1.2).

DB-free: a stub SQLAlchemy Connection routes on the SQL text so the writer's
guard logic, lifecycle SQL, and idempotency are exercised without a live DB.
The live rollback-transaction validation (propose -> approve -> visible_from
moves, on the real ``working.visible_from``) lives in
``scripts/_wave1_validate_w12_realization.py``.

Byline: Claude Code . glm-5.2:cloud . 2026-08-14
Byline amendment: Codex · GPT-5 · 2026-08-18 (source-availability ordering guard)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import pytest

from server.evidence.realization import (
    approve_realizations,
    propose_realization,
    supersede_realization,
)


# ---------------------------------------------------------------------------
# Stub SQLAlchemy connection — routes on SQL text, records every call.
# ---------------------------------------------------------------------------


class _Result:
    def __init__(
        self,
        *,
        scalar: Any = None,
        rows: list[tuple] | None = None,
        fetchone_row: tuple | None = None,
        rowcount: int = 0,
    ) -> None:
        self._scalar = scalar
        self._rows = rows or []
        self._fetchone_row = fetchone_row
        self.rowcount = rowcount

    def scalar(self) -> Any:
        return self._scalar

    def fetchall(self) -> list[tuple]:
        return self._rows

    def fetchone(self) -> tuple | None:
        return self._fetchone_row


class _StubConn:
    def __init__(self, *, latest_available: datetime | None = None, found: int = 1, available: int = 1) -> None:
        self.calls: list[tuple[str, Any]] = []
        self.latest_available = latest_available
        self.found = found
        self.available = available
        self.new_id = "00000000-0000-7000-8000-000000000001"
        self.approved_ids: list[str] = []
        self.supersede_hit = True

    def execute(self, stmt: Any, params: Any = None) -> _Result:
        sql = str(stmt)
        self.calls.append((sql, params))
        if "MAX(working.source_available_from(id))" in sql:
            return _Result(fetchone_row=(self.found, self.available, self.latest_available))
        if "INSERT INTO working.realization_event " in sql and "RETURNING id" in sql:
            return _Result(scalar=self.new_id)
        if "INSERT INTO working.realization_event_record" in sql:
            cnt = len(params) if isinstance(params, list) else 1
            return _Result(rowcount=cnt)
        # supersede first: its SQL carries both 'superseded' (SET) and 'approved'
        # (WHERE), so it would otherwise match the approve branch below.
        if "approval_state='superseded'" in sql and "RETURNING id" in sql:
            row = (self.new_id,) if self.supersede_hit else None
            return _Result(fetchone_row=row)
        if "approval_state='approved'" in sql and "approval_state='proposed'" in sql:
            return _Result(rows=[(i,) for i in self.approved_ids])
        return _Result()


# ---------------------------------------------------------------------------
# propose_realization
# ---------------------------------------------------------------------------


def test_propose_rejects_realized_at_before_linked_source_available_from():
    """A realization cannot predate possession of any source it reveals."""
    available = datetime(2024, 6, 1, tzinfo=timezone.utc)
    conn = _StubConn(latest_available=available)
    rid = uuid.uuid4()
    with pytest.raises(ValueError, match="precedes the latest linked source availability"):
        propose_realization(
            kind="manual",
            realized_at=datetime(2024, 5, 1, tzinfo=timezone.utc),  # before occurred
            record_ids=[rid],
            connection=conn,
        )
    # The guard SELECT ran, but NO insert followed (rejected before insert).
    assert any("source_available_from" in s for s, _ in conn.calls)
    assert not any("INSERT INTO working.realization_event" in s for s, _ in conn.calls)


def test_propose_accepts_realized_at_at_or_after_source_availability():
    available = datetime(2024, 6, 1, tzinfo=timezone.utc)
    for realized in (available, available.replace(year=available.year + 1)):
        conn = _StubConn(latest_available=available)
        eid = propose_realization(
            kind="contradiction",
            realized_at=realized,
            record_ids=[uuid.uuid4()],
            connection=conn,
        )
        assert eid == uuid.UUID(conn.new_id)
        # Insert of the event + the link row both ran.
        inserts = [s for s, _ in conn.calls if "INSERT INTO working.realization_event " in s]
        assert len(inserts) == 1
        assert "'proposed'" in inserts[0]  # inert state is a literal in the SQL
        link_inserts = [s for s, _ in conn.calls if "realization_event_record" in s]
        assert len(link_inserts) == 1


def test_propose_with_no_records_skips_guard():
    """A told_by_person / manual realization with no records yet has nothing to
    compare; the F5 guard is skipped (no SELECT MIN(occurred_at) call)."""
    conn = _StubConn()
    eid = propose_realization(
        kind="told_by_person",
        realized_at=datetime(2024, 6, 1, tzinfo=timezone.utc),
        record_ids=[],
        connection=conn,
    )
    assert eid == uuid.UUID(conn.new_id)
    assert not any("source_available_from" in s for s, _ in conn.calls)
    assert not any("realization_event_record" in s for s, _ in conn.calls)


def test_propose_rejects_bad_kind_and_proposer_without_db_access():
    """Validation runs before _do, so a bad kind/proposer never touches the conn."""
    conn = _StubConn()
    with pytest.raises(ValueError, match="not allowed"):
        propose_realization(kind="bogus", realized_at=datetime(2024, 6, 1, tzinfo=timezone.utc), connection=conn)
    with pytest.raises(ValueError, match="not allowed"):
        propose_realization(
            kind="manual", realized_at=datetime(2024, 6, 1, tzinfo=timezone.utc), proposer="robot", connection=conn
        )
    assert conn.calls == []


def test_propose_rejects_empty_case_id():
    conn = _StubConn()
    with pytest.raises(ValueError, match="case_id"):
        propose_realization(
            kind="manual", realized_at=datetime(2024, 6, 1, tzinfo=timezone.utc), case_id="  ", connection=conn
        )
    assert conn.calls == []


def test_propose_honors_caller_connection():
    """connection= must be used in place — no private engine created."""
    occurred = datetime(2024, 6, 1, tzinfo=timezone.utc)
    conn = _StubConn(latest_available=occurred)
    propose_realization(
        kind="manual",
        realized_at=occurred.replace(year=occurred.year + 1),
        record_ids=[uuid.uuid4()],
        connection=conn,
    )
    # Every statement the writer issued landed on the stub, proving no separate
    # engine/transaction was opened.
    assert conn.calls, "writer issued no statements on the passed connection"


def test_propose_fails_closed_when_linked_source_has_no_availability():
    conn = _StubConn(latest_available=None, found=1, available=0)
    with pytest.raises(ValueError, match="source-availability boundary"):
        propose_realization(
            kind="manual",
            realized_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            record_ids=[uuid.uuid4()],
            connection=conn,
        )


# ---------------------------------------------------------------------------
# approve_realizations
# ---------------------------------------------------------------------------


def test_approve_flips_only_proposed_rows():
    conn = _StubConn()
    approved = ["aaaaaaaa-0000-7000-8000-000000000001", "bbbbbbbb-0000-7000-8000-000000000002"]
    conn.approved_ids = approved
    res = approve_realizations(
        event_ids=[uuid.UUID(a) for a in approved] + [uuid.UUID("cccccccc-0000-7000-8000-000000000003")],
        approved_by="owner",
        connection=conn,
    )
    assert res["approved"] == sorted(approved)
    assert res["not_proposed"] == ["cccccccc-0000-7000-8000-000000000003"]
    update = [s for s, _ in conn.calls if "approval_state='approved'" in s][0]
    assert "approval_state='proposed'" in update  # only proposed rows touched


def test_approve_empty_is_noop_without_db():
    conn = _StubConn()
    res = approve_realizations(event_ids=[], connection=conn)
    assert res == {"approved": [], "not_proposed": []}
    assert conn.calls == []


def test_approve_rejects_empty_approved_by():
    conn = _StubConn()
    with pytest.raises(ValueError, match="approved_by"):
        approve_realizations(event_ids=[uuid.uuid4()], approved_by="", connection=conn)
    assert conn.calls == []


# ---------------------------------------------------------------------------
# supersede_realization
# ---------------------------------------------------------------------------


def test_supersede_marks_approved_row():
    conn = _StubConn()
    conn.supersede_hit = True
    ok = supersede_realization(event_id=uuid.uuid4(), connection=conn)
    assert ok is True
    upd = [s for s, _ in conn.calls if "approval_state='superseded'" in s][0]
    assert "approval_state='approved'" in upd  # only an approved row is superseded


def test_supersede_idempotent_on_missing_or_nonapproved():
    conn = _StubConn()
    conn.supersede_hit = False
    ok = supersede_realization(event_id=uuid.uuid4(), connection=conn)
    assert ok is False
