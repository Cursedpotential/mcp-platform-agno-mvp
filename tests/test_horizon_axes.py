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
    # the horizon key is knowledge_time, NOT occurred_at
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


def test_planted_future_fact_is_excluded_by_the_documented_predicate():
    """The end-to-end intent: an ignorant agent at a 2023 horizon must not see
    a document whose knowledge_time is 2026, even though nothing about the
    text or its embedding would distinguish them."""
    horizon = int((T0 + timedelta(days=100)).timestamp())
    past = horizon_axes([rec("old", 10)])
    planted = horizon_axes([rec("new", 1200)])

    def visible(axes):  # mirrors working.horizon_visible()
        return (
            axes["case_id"] == "primary"
            and axes["knowledge_time_epoch"] <= horizon
            and axes["disclosure_tier"] != "hindsight"
        )

    assert visible(past)
    assert not visible(planted)
