"""tests/test_evidence_retrieval.py — the horizon-gated evidence seam (ADR-0050 §4, Phase 3).

Byline: Claude Code · Fable 5 · 2026-08-11

Observed-behavior tests per the approved plan's Phase 3 verification: seed
documents with different visibility clocks, query at an intermediate horizon,
and observe that ONLY the earlier document returns — plus deny-undated,
case-id defense, and the audit-or-fail contract.
"""

from __future__ import annotations

import asyncio

import pytest

from server.evidence.retrieval import evidence_search


class _Doc:
    def __init__(self, name: str, meta: dict) -> None:
        self.name = name
        self.meta_data = meta


class _FakeKnowledge:
    """TEST-DOUBLE: stands in for the evidence Knowledge instance."""

    def __init__(self, docs: list[_Doc]) -> None:
        self._docs = docs

    async def async_search(self, query: str, max_results: int = 10, **_: object) -> list[_Doc]:
        return self._docs[:max_results]


def _audit_recorder(calls: list[dict]):
    def _audit(object_ref: str, **kwargs: object) -> int:
        calls.append({"object_ref": object_ref, **kwargs})
        return len(calls)

    return _audit


EARLY = _Doc("early", {"case_id": "primary", "occurred_at_min": "2024-01-01T00:00:00+00:00"})
LATE = _Doc("late", {"case_id": "primary", "occurred_at_min": "2025-06-01T00:00:00+00:00"})
UNDATED = _Doc("undated", {"case_id": "primary"})
OTHER_CASE = _Doc("other", {"case_id": "someone-else", "occurred_at_min": "2024-01-01T00:00:00+00:00"})
REALIZED = _Doc(
    "realized",
    # visible_from (S6 surface) WINS over occurred_at_min per ADR-0045 COALESCE:
    # occurred early, but only became visible late.
    {"case_id": "primary", "occurred_at_min": "2024-01-01T00:00:00+00:00", "visible_from": "2025-09-01T00:00:00+00:00"},
)


def test_intermediate_horizon_returns_only_earlier_doc():
    calls: list[dict] = []
    res = asyncio.run(
        evidence_search(
            _FakeKnowledge([EARLY, LATE]),
            "what happened",
            horizon="2024-12-31T23:59:59+00:00",
            actor="test",
            audit=_audit_recorder(calls),
        )
    )
    assert [d.name for d in res.documents] == ["early"]
    assert res.kept == 1 and res.denied == 1


def test_undated_documents_are_denied():
    calls: list[dict] = []
    res = asyncio.run(
        evidence_search(
            _FakeKnowledge([UNDATED, EARLY]),
            "q",
            horizon="2026-01-01T00:00:00+00:00",
            actor="test",
            audit=_audit_recorder(calls),
        )
    )
    assert [d.name for d in res.documents] == ["early"]
    assert res.denied == 1


def test_visible_from_wins_over_occurred_at():
    calls: list[dict] = []
    res = asyncio.run(
        evidence_search(
            _FakeKnowledge([REALIZED]),
            "q",
            horizon="2025-01-01T00:00:00+00:00",  # after occurred_at, BEFORE visible_from
            actor="test",
            audit=_audit_recorder(calls),
        )
    )
    assert res.documents == [] and res.denied == 1


def test_foreign_case_id_is_denied():
    calls: list[dict] = []
    res = asyncio.run(
        evidence_search(
            _FakeKnowledge([OTHER_CASE]),
            "q",
            horizon="2026-01-01T00:00:00+00:00",
            actor="test",
            audit=_audit_recorder(calls),
        )
    )
    assert res.documents == [] and res.denied == 1


def test_every_search_is_audited_with_horizon_context():
    calls: list[dict] = []
    asyncio.run(
        evidence_search(
            _FakeKnowledge([EARLY]),
            "sensitive query text",
            horizon="2026-01-01T00:00:00+00:00",
            actor="legal-team",
            audit=_audit_recorder(calls),
        )
    )
    assert len(calls) == 1
    row = calls[0]
    # query is hashed, never stored as text
    assert "sensitive" not in row["object_ref"] and len(row["object_ref"]) == 64
    assert row["actor"] == "legal-team"
    ctx = row["ctx"]
    assert ctx["lane"] == "evidence" and ctx["horizon"] == "2026-01-01T00:00:00+00:00"
    assert ctx["kept"] == 1 and ctx["denied"] == 0


def test_audit_failure_fails_the_search():
    def _broken_audit(*a: object, **k: object) -> int:
        raise RuntimeError("ledger down")

    with pytest.raises(RuntimeError, match="ledger down"):
        asyncio.run(
            evidence_search(
                _FakeKnowledge([EARLY]),
                "q",
                horizon="2026-01-01T00:00:00+00:00",
                actor="test",
                audit=_broken_audit,
            )
        )


def test_missing_horizon_rejected():
    with pytest.raises(ValueError):
        asyncio.run(evidence_search(_FakeKnowledge([]), "q", horizon="", actor="test"))
