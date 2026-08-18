"""Horizon axes on retrievable documents — the contamination guard (C-01).

Byline: Claude Code . Fable 5 . 2026-08-02
Byline amendment: Codex · GPT-5 · 2026-08-18 (source availability clock split)

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

from server.contracts.records import DisclosureTier, MessageCorpus, NormalizedRecord, RecordType
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
        message_corpus=MessageCorpus.first_party,
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
    # First-party source availability is occurrence. Realization is a separate
    # atom and does not move this raw-source clock.
    assert axes["source_available_from"] == (T0 + timedelta(days=30)).isoformat()
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
    """The compatibility ``visible_from`` axis aliases source availability. A document
    that OCCURRED after the horizon is excluded — even though nothing about its
    text or embedding would distinguish it from a contemporaneous one
    (embeddings have no sense of time, AGENTS.md WHY THIS EXISTS).

    Realization events are independent horizon atoms. ``knowledge_time`` is
    audit-only and is never the source-availability clock."""
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


def test_acquired_third_party_requires_authoritative_pg_approval():
    record = rec("friends", 1000, o_days=5)
    acquired = T0 + timedelta(days=700)
    record = record.model_copy(
        update={
            "role": "alex",
            "participants": ["alex", "jordan"],
            "message_corpus": MessageCorpus.acquired_third_party,
            "attrs": {"acquired_at": acquired.isoformat()},
        }
    )
    axes = horizon_axes([record])
    assert axes["occurred_at_min"] == (T0 + timedelta(days=5)).isoformat()
    assert axes["source_availability_complete"] is False
    assert "source_available_from" not in axes
    assert "visible_from" not in axes
    assert "owner" not in record.participants


def test_acquired_third_party_accepts_only_explicit_authoritative_pg_handoff():
    acquired = T0 + timedelta(days=700)
    record = rec("friends", 1000, o_days=5).model_copy(
        update={
            "message_corpus": MessageCorpus.acquired_third_party,
            "attrs": {"_normalized_record_id": "record-id", "acquired_at": (T0 + timedelta(days=1)).isoformat()},
        }
    )
    axes = horizon_axes(
        [record],
        authoritative_source_available_from={"record-id": acquired},
    )
    assert axes["source_available_from"] == acquired.isoformat()
    assert axes["visible_from"] == acquired.isoformat()


def test_unrouted_message_fails_closed():
    record = rec("unknown", 10, o_days=5).model_copy(update={"message_corpus": None})
    axes = horizon_axes([record])
    assert axes["source_availability_complete"] is False
    assert "visible_from" not in axes
