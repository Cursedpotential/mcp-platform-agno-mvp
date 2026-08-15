"""Horizon axes on retrievable documents — the contamination guard (C-01).

Byline: Claude Code . Fable 5 . 2026-08-02

Codex's deep analysis found vector documents carried NO temporal axes, so no
agent read could pre-filter by horizon. AGENTS.md is blunt about why that is
the worst failure mode available: embeddings have no sense of time, so a
future document scores exactly as similar as a contemporaneous one, and
nothing errors — the ignorant agent just gets quietly smarter and the delta
becomes worthless.

These tests pin the aggregation rules that make the axes SAFE rather than
merely present.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from server.contracts.records import DisclosureTier, NormalizedRecord, RecordType
from server.evidence.store import group_by_conversation, horizon_axes

T0 = datetime(2023, 1, 1, tzinfo=timezone.utc)


def rec(conv: str, k_days: int, o_days: int = 0, tier=DisclosureTier.contemporaneous, **attrs):
    return NormalizedRecord(
        record_type=RecordType.message,
        source="sms-xml",
        conversation_id=conv,
        role="owner",
        participants=["owner"],
        content="x",
        occurred_at=T0 + timedelta(days=o_days),
        knowledge_time=T0 + timedelta(days=k_days),
        disclosure_tier=tier,
        attrs=attrs,
    )


def test_knowledge_time_is_the_maximum_not_the_minimum():
    """A future record hidden inside an old thread must push the whole
    document's horizon forward — otherwise it leaks."""
    axes = horizon_axes([rec("c", 0), rec("c", 900), rec("c", 10)])
    assert axes["knowledge_time"] == (T0 + timedelta(days=900)).isoformat()
    assert axes["knowledge_time_epoch"] == int((T0 + timedelta(days=900)).timestamp())


def test_one_hindsight_record_taints_the_document():
    axes = horizon_axes([rec("c", 1), rec("c", 2, tier=DisclosureTier.hindsight)])
    assert axes["disclosure_tier"] == "hindsight"


def test_contemporaneous_document_stays_contemporaneous():
    axes = horizon_axes([rec("c", 1), rec("c", 2)])
    assert axes["disclosure_tier"] == "contemporaneous"


def test_occurred_span_is_reported_and_is_not_the_horizon():
    axes = horizon_axes([rec("c", 500, o_days=1), rec("c", 501, o_days=30)])
    assert axes["occurred_at_min"] == (T0 + timedelta(days=1)).isoformat()
    assert axes["occurred_at_max"] == (T0 + timedelta(days=30)).isoformat()
    # the horizon clock is visible_from (= occurred_at_max here, the conservative
    # degenerate form with no realization events), NOT knowledge_time (which is
    # AUDIT ONLY — ADR-0045 §A, SUPERSEDED 0008:247).
    assert axes["visible_from"] == (T0 + timedelta(days=30)).isoformat()
    assert axes["visible_from_epoch"] == int((T0 + timedelta(days=30)).timestamp())
    assert axes["knowledge_time"] == (T0 + timedelta(days=501)).isoformat()


def test_mixed_actors_are_flagged_not_guessed():
    axes = horizon_axes([rec("c", 1, knowledge_actor="owner"), rec("c", 2, knowledge_actor="counterparty")])
    assert axes["knowledge_actor"] == "multiple"


def test_case_id_is_carried():
    assert horizon_axes([rec("c", 1)], case_id="matter-2")["case_id"] == "matter-2"


def test_axes_are_flat_scalars_for_dict_filters():
    """agno's Weaviate adapter silently DROPS FilterExpr lists — dict filters
    only — so every axis value must be a comparable primitive."""
    axes = horizon_axes([rec("c", 1)])
    assert all(isinstance(v, (str, int, float, bool)) for v in axes.values()), axes


def test_grouping_shared_by_text_and_axes():
    recs = [rec("a", 1), rec("b", 2), rec("a", 3)]
    groups = group_by_conversation(recs)
    assert set(groups) == {"a", "b"}
    assert horizon_axes(groups["a"])["record_count"] == 2


def test_visible_from_excludes_a_late_occurring_document():
    """The horizon clock is ``visible_from`` (``occurred_at_max`` in the
    degenerate, no-realization form emitted by ``horizon_axes``). A document
    that OCCURRED after the horizon is excluded — even though nothing about its
    text or embedding would distinguish it from a contemporaneous one
    (embeddings have no sense of time, AGENTS.md WHY THIS EXISTS).

    A document that occurred EARLY but was only DISCOVERED later is NOT
    excluded by this in-memory projection: hiding it until the discovery
    requires an APPROVED ``realization_event`` (ADR-0045 §A.4), a DB-level
    property tested in ``scripts/_wave1_validate_0026.py`` (the 'approved
    event moves visible_from' + 'horizon_visible denies at early horizon'
    assertions). ``knowledge_time`` is AUDIT ONLY and is never the clock
    (ADR-0045 §A, SUPERSEDED 0008:247)."""
    horizon = int((T0 + timedelta(days=100)).timestamp())
    early = horizon_axes([rec("old", 10, o_days=5)])  # occurred T0+5
    late = horizon_axes([rec("new", 10, o_days=1200)])  # occurred T0+1200

    def visible(axes):  # mirrors working.horizon_visible() on the visible_from clock
        return (
            axes["case_id"] == "primary"
            and axes["visible_from_epoch"] <= horizon
            and axes["disclosure_tier"] != "hindsight"
        )

    assert visible(early)  # occurred within the horizon -> visible
    assert not visible(late)  # occurred after the horizon -> excluded by the clock
