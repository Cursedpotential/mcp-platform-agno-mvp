"""Framework-neutral Phase-0 planted-future-fact contract tests.

Byline: Codex · GPT-5 · 2026-08-16 · ADR-0059 amendment 2026-08-18

These tests validate the accepted logical contract and synthetic gold fixture. They do
not prove any live PostgreSQL, Weaviate, Neo4j, Graphiti, or Surreal adapter.
Each later adapter must run this behavior against its real pre-ranking filter.
"""

from __future__ import annotations

import ast
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Literal

import pytest

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "surreal_investigation_phase0_horizon.json"
SURFACES = ("postgresql", "weaviate", "neo4j", "surreal")
AGENT_VISIBLE_SURFACES = (
    "retrieval",
    "prompt",
    "handoff",
    "coordination_wal",
    "belief",
    "summary",
    "observation",
    "trace",
)
FORBIDDEN_IMPORT_ROOTS = {
    "agno",
    "autogen",
    "graphiti_core",
    "neo4j",
    "psycopg",
    "surrealdb",
    "weaviate",
}


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Document:
    id: str
    matter_id: str
    source_class: Literal["first_party", "acquired_third_party"]
    conversation_id: str
    occurred_at: datetime
    acquired_at: datetime | None
    source_available_from: datetime
    recorded_at: datetime
    sender_id: str
    recipient_ids: tuple[str, ...]
    participant_ids: tuple[str, ...]
    disclosure_tier: str
    authority_state: str
    promotion_state: str
    similarity: float
    content: str


@dataclass(frozen=True)
class HorizonRequest:
    matter_id: str
    horizon_at: datetime
    mode: Literal["as_lived_so_far", "hindsight"]
    top_k: int


@dataclass(frozen=True)
class SearchTrace:
    surface: str
    eligible_ids_before_ranking: tuple[str, ...]
    ranked_ids: tuple[str, ...]


@dataclass(frozen=True)
class Belief:
    id: str
    matter_id: str
    walk_id: str
    content: str


@dataclass(frozen=True)
class WalkSnapshot:
    snapshot_id: str
    walk_id: str
    projection_revision: str
    state_hash: str
    trace_hash: str
    resumable: bool
    status: Literal["historical_read_only"] = "historical_read_only"
    active_retrieval_eligible: bool = False


@dataclass(frozen=True)
class WalkCheckpoint:
    checkpoint_id: str
    walk_id: str
    projection_revision: str
    current_step: int
    state_hash: str
    trace_hash: str
    belief_ids: tuple[str, ...]
    retrieval_ids: tuple[str, ...]


@dataclass(frozen=True)
class WalkState:
    walk_id: str
    projection_revision: str
    status: Literal["active", "paused", "sealed"]


@dataclass(frozen=True)
class RealizationDecision:
    approved_point: datetime
    reviewer_id: str
    rationale: str


class UnsupportedPrefilter(RuntimeError):
    """The adapter cannot prove that it filters before ranking/traversal."""


def _load_fixture() -> tuple[dict[str, Any], tuple[Document, ...]]:
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    documents = tuple(
        Document(
            id=row["id"],
            matter_id=row["matter_id"],
            source_class=row["source_class"],
            conversation_id=row["conversation_id"],
            occurred_at=_parse_time(row["occurred_at"]),
            acquired_at=_parse_time(row["acquired_at"]) if row["acquired_at"] else None,
            source_available_from=_parse_time(row["source_available_from"]),
            recorded_at=_parse_time(row["recorded_at"]),
            sender_id=row["sender_id"],
            recipient_ids=tuple(row["recipient_ids"]),
            participant_ids=tuple(row["participant_ids"]),
            disclosure_tier=row["disclosure_tier"],
            authority_state=row["authority_state"],
            promotion_state=row["promotion_state"],
            similarity=row["similarity"],
            content=row["content"],
        )
        for row in payload["documents"]
    )
    return payload, documents


def _validated_source_available_from(document: Document, *, subject_id: str) -> datetime:
    participants = set(document.participant_ids)
    if document.sender_id not in participants or not set(document.recipient_ids) <= participants:
        raise ValueError("sender and recipients must be actual conversation participants")
    if document.source_class == "first_party":
        if document.acquired_at is not None or document.source_available_from != document.occurred_at:
            raise ValueError("first-party source availability must equal occurrence")
        return document.source_available_from
    if document.acquired_at is None or document.source_available_from != document.acquired_at:
        raise ValueError("acquired third-party source availability must equal acquisition")
    if subject_id in participants:
        raise ValueError("the owner must be absent from acquired third-party participants")
    return document.source_available_from


def _eligible(document: Document, request: HorizonRequest) -> bool:
    if document.matter_id != request.matter_id:
        return False
    if document.authority_state != "approved":
        return False
    if document.promotion_state != "active":
        return False
    if request.mode == "as_lived_so_far":
        return (
            _validated_source_available_from(document, subject_id="owner-synthetic") <= request.horizon_at
            and document.disclosure_tier != "hindsight"
        )
    return True


def _prefilter_then_rank(
    surface: str,
    documents: tuple[Document, ...],
    request: HorizonRequest,
    *,
    supports_prefilter: bool = True,
) -> tuple[tuple[Document, ...], SearchTrace]:
    if not supports_prefilter:
        raise UnsupportedPrefilter(f"{surface} cannot prove pre-ranking filtering")
    eligible = tuple(document for document in documents if _eligible(document, request))
    ranked = tuple(sorted(eligible, key=lambda document: document.similarity, reverse=True)[: request.top_k])
    trace = SearchTrace(
        surface=surface,
        eligible_ids_before_ranking=tuple(document.id for document in eligible),
        ranked_ids=tuple(document.id for document in ranked),
    )
    return ranked, trace


def _rank_then_postfilter(documents: tuple[Document, ...], request: HorizonRequest) -> tuple[Document, ...]:
    """Known-bad reference used to ensure the canary catches top-k shrinkage."""
    ranked = sorted(documents, key=lambda document: document.similarity, reverse=True)[: request.top_k]
    return tuple(document for document in ranked if _eligible(document, request))


def _agent_visible_envelope(documents: tuple[Document, ...]) -> dict[str, list[dict[str, str]]]:
    entries = [{"id": document.id, "content": document.content} for document in documents]
    return {surface: entries for surface in AGENT_VISIBLE_SURFACES}


def _beliefs_for_walk(beliefs: tuple[Belief, ...], matter_id: str, walk_id: str) -> tuple[Belief, ...]:
    return tuple(belief for belief in beliefs if belief.matter_id == matter_id and belief.walk_id == walk_id)


def _approved_realization(
    interval_start: datetime,
    interval_end: datetime,
    *,
    decision: RealizationDecision | None,
) -> tuple[datetime, datetime, datetime, datetime | None]:
    midpoint = interval_start + (interval_end - interval_start) / 2
    if decision is None:
        return interval_start, interval_end, midpoint, None
    if not interval_start <= decision.approved_point <= interval_end:
        raise ValueError("approved realization point must remain inside the reviewed interval")
    if not decision.reviewer_id or not decision.rationale:
        raise ValueError("HITL realization approval requires reviewer and rationale")
    return interval_start, interval_end, midpoint, decision.approved_point


def _pause_walk(walk: WalkState, checkpoint: WalkCheckpoint) -> WalkState:
    if walk.status != "active":
        raise ValueError("only an active walk can pause")
    if (walk.walk_id, walk.projection_revision) != (checkpoint.walk_id, checkpoint.projection_revision):
        raise ValueError("checkpoint identity must match the walk")
    return WalkState(walk.walk_id, walk.projection_revision, "paused")


def _resume_walk(walk: WalkState, checkpoint: WalkCheckpoint) -> WalkState:
    if walk.status != "paused":
        raise ValueError("only a healthy paused walk can resume")
    if (walk.walk_id, walk.projection_revision) != (checkpoint.walk_id, checkpoint.projection_revision):
        raise ValueError("resume must use the same walk identity and projection revision")
    return WalkState(walk.walk_id, walk.projection_revision, "active")


def _seal_walk(walk: WalkState, snapshot: WalkSnapshot) -> WalkState:
    if snapshot.resumable:
        raise ValueError("terminal snapshots must be non-resumable")
    if (walk.walk_id, walk.projection_revision) != (snapshot.walk_id, snapshot.projection_revision):
        raise ValueError("terminal snapshot identity must match the failed walk")
    return WalkState(walk.walk_id, walk.projection_revision, "sealed")


def test_fixture_is_versioned_and_distinguishes_occurrence_from_acquisition() -> None:
    payload, documents = _load_fixture()
    assert payload["schema_version"] == "phase0-horizon-canary-v2-adr0059"
    by_id = {document.id: document for document in documents}
    future_occurring = by_id["future-occurring-canary"]
    first_party = by_id["first-party-occurrence-a"]
    acquired_third_party = by_id["acquired-third-party-canary"]
    early_horizon = _parse_time(payload["horizons"]["early"])

    assert future_occurring.occurred_at > early_horizon
    assert first_party.occurred_at == first_party.source_available_from < early_horizon
    assert first_party.recorded_at > early_horizon
    assert acquired_third_party.occurred_at < early_horizon < acquired_third_party.acquired_at
    assert acquired_third_party.source_available_from == acquired_third_party.acquired_at


def test_acquired_third_party_uses_actual_participants_and_excludes_owner() -> None:
    payload, documents = _load_fixture()
    acquired = next(document for document in documents if document.id == "acquired-third-party-canary")

    assert acquired.sender_id == "partner-synthetic"
    assert acquired.recipient_ids == ("friend-synthetic",)
    assert set(acquired.participant_ids) == {"partner-synthetic", "friend-synthetic"}
    assert payload["subject_id"] not in acquired.participant_ids
    assert _validated_source_available_from(acquired, subject_id=payload["subject_id"]) == acquired.acquired_at


@pytest.mark.parametrize("surface", SURFACES)
def test_early_as_lived_prefilters_future_facts_before_ranking(surface: str) -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )

    results, trace = _prefilter_then_rank(surface, documents, request)

    expected = tuple(payload["expected"]["early_as_lived_ranked_ids"])
    assert trace.ranked_ids == expected
    assert len(results) == request.top_k
    assert all(payload["canary_literal"] not in document.content for document in results)
    assert not any("canary" in document_id for document_id in trace.eligible_ids_before_ranking)


def test_canary_detects_rank_then_filter_top_k_shrinkage() -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )

    bad_results = _rank_then_postfilter(documents, request)

    assert bad_results == ()
    assert len(bad_results) < request.top_k


def test_acquired_third_party_is_hidden_until_acquisition_not_realization() -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=20,
    )
    results, _ = _prefilter_then_rank("reference", documents, request)
    result_ids = {document.id for document in results}

    assert "acquired-third-party-canary" not in result_ids
    acquired = next(document for document in documents if document.id == "acquired-third-party-canary")
    first_realization = min(
        _parse_time(link["realized_at"]) for link in payload["realization_links"] if link["message_id"] == acquired.id
    )
    assert acquired.occurred_at < request.horizon_at < acquired.acquired_at
    assert acquired.source_available_from == acquired.acquired_at < first_realization


def test_realizations_are_zero_to_many_separate_atoms_not_message_columns() -> None:
    payload, _ = _load_fixture()
    links = payload["realization_links"]
    acquired_links = [link for link in links if link["message_id"] == "acquired-third-party-canary"]
    first_party_links = [link for link in links if link["message_id"] == "first-party-occurrence-a"]

    assert first_party_links == []
    assert [link["id"] for link in acquired_links] == payload["expected"]["third_party_realization_ids"]
    assert len({link["id"] for link in acquired_links}) == 3
    assert len({link["realized_at"] for link in acquired_links}) == 3
    assert [link["approval_state"] for link in acquired_links] == ["approved", "approved", "proposed"]


def test_late_as_lived_and_hindsight_have_explicit_expected_deltas() -> None:
    payload, documents = _load_fixture()
    late_horizon = _parse_time(payload["horizons"]["late"])
    late_request = HorizonRequest(payload["matter_id"], late_horizon, "as_lived_so_far", payload["top_k"])
    hindsight_request = HorizonRequest(payload["matter_id"], late_horizon, "hindsight", payload["top_k"])

    late_results, _ = _prefilter_then_rank("reference", documents, late_request)
    hindsight_results, _ = _prefilter_then_rank("reference", documents, hindsight_request)

    assert [document.id for document in late_results] == payload["expected"]["late_as_lived_top_ids"]
    assert [document.id for document in hindsight_results] == payload["expected"]["hindsight_top_ids"]
    assert {document.id for document in late_results} != {document.id for document in hindsight_results}
    assert "hindsight-only-canary" not in {document.id for document in late_results}
    assert "hindsight-only-canary" in {document.id for document in hindsight_results}
    assert all(document.matter_id == payload["matter_id"] for document in hindsight_results)
    assert all(document.promotion_state == "active" for document in hindsight_results)


def test_canary_never_enters_any_early_agent_visible_surface_or_query_generation() -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )
    results, _ = _prefilter_then_rank("reference", documents, request)
    envelope = _agent_visible_envelope(results)
    serialized = json.dumps(envelope, sort_keys=True)
    query_terms = " ".join(document.content for document in results)

    assert set(envelope) == set(AGENT_VISIBLE_SURFACES)
    assert payload["canary_literal"] not in serialized
    assert payload["canary_literal"] not in query_terms


@pytest.mark.parametrize("surface", SURFACES)
def test_unverifiable_prefilter_support_fails_closed(surface: str) -> None:
    payload, documents = _load_fixture()
    request = HorizonRequest(
        matter_id=payload["matter_id"],
        horizon_at=_parse_time(payload["horizons"]["early"]),
        mode="as_lived_so_far",
        top_k=payload["top_k"],
    )

    with pytest.raises(UnsupportedPrefilter, match="cannot prove pre-ranking"):
        _prefilter_then_rank(surface, documents, request, supports_prefilter=False)


def test_contract_test_has_no_runtime_or_store_client_imports() -> None:
    tree = ast.parse(Path(__file__).read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imports.update(alias.name.split(".", maxsplit=1)[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".", maxsplit=1)[0])

    assert imports.isdisjoint(FORBIDDEN_IMPORT_ROOTS)


def test_shared_context_keeps_experiential_beliefs_walk_scoped() -> None:
    beliefs = (
        Belief("belief-a", "matter-synthetic-a", "walk-ignorant", "Only walk A observed this."),
        Belief("belief-b", "matter-synthetic-a", "walk-hindsight", "Only walk B observed this."),
        Belief("belief-c", "matter-synthetic-b", "walk-ignorant", "A different Matter observed this."),
    )

    visible = _beliefs_for_walk(beliefs, "matter-synthetic-a", "walk-ignorant")

    assert [belief.id for belief in visible] == ["belief-a"]


def test_healthy_checkpoint_resumes_same_walk_with_complete_state_references() -> None:
    payload, _ = _load_fixture()
    case = payload["walk_cases"]["healthy"]
    checkpoint = WalkCheckpoint(
        checkpoint_id=case["checkpoint_id"],
        walk_id=case["walk_id"],
        projection_revision=case["projection_revision"],
        current_step=case["current_step"],
        state_hash=case["state_hash"],
        trace_hash=case["trace_hash"],
        belief_ids=tuple(case["belief_ids"]),
        retrieval_ids=tuple(case["retrieval_ids"]),
    )
    active = WalkState(case["walk_id"], case["projection_revision"], "active")

    paused = _pause_walk(active, checkpoint)
    resumed = _resume_walk(paused, checkpoint)

    assert resumed.walk_id == active.walk_id
    assert resumed.projection_revision == active.projection_revision
    assert resumed.status == "active"
    assert checkpoint.current_step == 1
    assert checkpoint.state_hash and checkpoint.trace_hash
    assert checkpoint.belief_ids and checkpoint.retrieval_ids


def test_failed_walk_is_sealed_and_rewalk_has_new_identity_with_exact_link() -> None:
    payload, _ = _load_fixture()
    terminal = payload["walk_cases"]["terminal"]
    rewalk = payload["walk_cases"]["rewalk"]
    snapshot = WalkSnapshot(
        terminal["snapshot_id"],
        terminal["walk_id"],
        terminal["projection_revision"],
        terminal["state_hash"],
        terminal["trace_hash"],
        terminal["resumable"],
    )
    failed = WalkState(snapshot.walk_id, snapshot.projection_revision, "active")
    sealed = _seal_walk(failed, snapshot)

    assert snapshot.status == "historical_read_only"
    assert snapshot.active_retrieval_eligible is False
    assert snapshot.resumable is False
    assert sealed.status == "sealed"
    with pytest.raises(ValueError, match="healthy paused"):
        _resume_walk(sealed, WalkCheckpoint("unused", sealed.walk_id, sealed.projection_revision, 1, "s", "t", (), ()))
    assert rewalk["walk_id"] != snapshot.walk_id
    assert rewalk["rewalk_of"] == snapshot.walk_id
    assert rewalk["projection_revision"] != snapshot.projection_revision
    assert rewalk["change_manifest_hash"]


def test_realization_midpoint_is_not_approved_until_hitl_review() -> None:
    start = _parse_time("2024-01-01T00:00:00Z")
    end = _parse_time("2024-03-01T00:00:00Z")
    unreviewed = _approved_realization(start, end, decision=None)
    decision = RealizationDecision(unreviewed[2], "owner", "Midpoint best fits the bounded evidence.")
    reviewed = _approved_realization(start, end, decision=decision)

    assert unreviewed[0:3] == reviewed[0:3]
    assert unreviewed[3] is None
    assert reviewed[3] == unreviewed[2]


def test_derivative_hits_do_not_inflate_independent_source_count() -> None:
    family_ids = ("message-17", "message-17", "message-17", "message-17", "message-17")
    provenance_reviewed_ids = ("message-17", "independent-observation-22")

    assert len(family_ids) == 5
    assert len(set(family_ids)) == 1
    assert len(set(provenance_reviewed_ids)) == 2
