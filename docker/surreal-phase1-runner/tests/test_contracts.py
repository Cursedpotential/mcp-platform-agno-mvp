"""Pure contract tests for horizon filtering and failure transitions.

Byline: Codex · GPT-5 · 2026-08-17 (sanitized structured failure diagnostics)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""

import json
from pathlib import Path

import pytest
from surrealdb import NotAllowedError

from horizon_surreal_phase1.contracts import (
    HorizonContext,
    ProjectionGuard,
    WalkCheckpoint,
    WalkSnapshot,
    WalkState,
    eligible_ranked_ids,
    link_rewalk,
    pause_walk,
    resume_walk,
    seal_walk,
    source_available_from,
    transition_projection_guard,
)
from horizon_surreal_phase1.runner import (
    EXPORT_TABLES,
    _canonical_export,
    _record_absent,
    _safe_error_details,
)

FIXTURE = Path(__file__).parents[1] / "fixtures" / "t0_manifest.json"


def _manifest() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_early_filter_happens_before_top_k_and_fills_k() -> None:
    manifest = _manifest()
    context = HorizonContext(
        matter_id="matter-synthetic-a",
        horizon_at="2024-06-01T00:00:00Z",
        mode="as_lived_so_far",
        projection_revision="projection-t0-r1",
        policy_version="horizon-policy-v2",
    )
    assert eligible_ranked_ids(manifest["documents"], context, top_k=2) == [
        "first-party-occurrence-a",
        "first-party-occurrence-b",
    ]


def test_late_and_hindsight_positive_controls_are_not_overfiltered() -> None:
    manifest = _manifest()
    late = HorizonContext(
        matter_id="matter-synthetic-a",
        horizon_at="2026-06-01T00:00:00Z",
        mode="as_lived_so_far",
        projection_revision="projection-t0-r1",
        policy_version="horizon-policy-v2",
    )
    hindsight = HorizonContext(
        matter_id="matter-synthetic-a",
        horizon_at="2024-06-01T00:00:00Z",
        mode="hindsight",
        projection_revision="projection-t0-r1",
        policy_version="horizon-policy-v2",
    )
    assert eligible_ranked_ids(manifest["documents"], late, top_k=2) == [
        "future-occurring-canary",
        "acquired-third-party-canary",
    ]
    assert eligible_ranked_ids(manifest["documents"], hindsight, top_k=2) == [
        "hindsight-only-canary",
        "future-occurring-canary",
    ]


def test_quarantine_is_terminal_and_rewalk_gets_new_identity() -> None:
    active = ProjectionGuard("projection-t0-r1", "active")
    quarantined = transition_projection_guard(active, "quarantined", "HASH_DRIFT")
    assert quarantined.status == "quarantined"
    with pytest.raises(ValueError, match="TERMINAL_PROJECTION_GUARD"):
        transition_projection_guard(quarantined, "active")

    sealed = WalkState("walk-t0-r1", "sealed", projection_revision="projection-t0-r1")
    rewalk = link_rewalk(sealed, "walk-t0-r2", "projection-t0-r2")
    assert rewalk.walk_id != sealed.walk_id
    assert rewalk.rewalk_of == sealed.walk_id
    assert rewalk.projection_revision == "projection-t0-r2"


def test_safe_error_details_reports_only_allowlisted_denial_fields() -> None:
    denial = NotAllowedError(
        kind="NotAllowed",
        message="Method not allowed",
        details={"kind": "Method", "details": {"name": "create"}},
    )
    wrapped = RuntimeError("stage=projection")
    wrapped.__cause__ = denial

    assert _safe_error_details(wrapped) == {
        "kind": "NotAllowed",
        "method": "create",
    }


def test_safe_error_details_omits_unstructured_exception_text() -> None:
    assert _safe_error_details(RuntimeError("credential-like text")) == {}


def test_permission_filtered_empty_shapes_are_absent() -> None:
    assert _record_absent(None)
    assert _record_absent([])
    assert not _record_absent("forbidden")


def test_sanitized_export_is_deterministic_and_omits_native_ids() -> None:
    rows = {
        "retrieval_chunk": [
            {"id": "retrieval_chunk:native-b", "platform_id": "b", "content_hash": "sha256:b"},
            {"id": "retrieval_chunk:native-a", "platform_id": "a", "content_hash": "sha256:a"},
        ],
        "rewalk_of": [
            {
                "id": "rewalk_of:native-edge",
                "in": "walk:walk-t0-r2",
                "out": "walk:walk-t0-r1",
                "matter_id": "matter-synthetic-a",
            }
        ],
    }

    exported = _canonical_export(rows)

    assert [row["platform_id"] for row in exported["retrieval_chunk"]] == ["a", "b"]
    assert "id" not in exported["retrieval_chunk"][0]
    assert exported["rewalk_of"][0]["in"] == "walk-t0-r2"
    assert exported["rewalk_of"][0]["out"] == "walk-t0-r1"
    assert "walk_checkpoint" in EXPORT_TABLES
    assert "walk_snapshot" in EXPORT_TABLES


def test_sealed_walk_cannot_be_reused_for_active_recall() -> None:
    sealed = WalkState("walk-t0-r1", "sealed", projection_revision="projection-t0-r1")
    with pytest.raises(ValueError, match="REWALK_REQUIRES_NEW_IDENTITY"):
        link_rewalk(sealed, sealed.walk_id, "projection-t0-r2")


def test_healthy_walk_pauses_and_resumes_with_same_identity() -> None:
    active = WalkState("walk-t0-r1", "active", projection_revision="projection-t0-r1")
    checkpoint = WalkCheckpoint(
        "checkpoint-walk-t0-r1-1",
        walk_id=active.walk_id,
        projection_revision=active.projection_revision,
        horizon_id="horizon-as_lived_so_far-2024-06-01",
        current_step=1,
        state_hash="sha256:state",
        trace_hash="sha256:trace",
        belief_ids=("belief-1",),
        retrieval_ids=("first-party-occurrence-a",),
    )

    paused = pause_walk(active, checkpoint)
    resumed = resume_walk(paused, checkpoint)

    assert paused.status == "paused"
    assert resumed == active


def test_terminal_snapshot_requires_linked_rewalk() -> None:
    active = WalkState("walk-t0-r1", "active", projection_revision="projection-t0-r1")
    terminal = WalkSnapshot(
        "snapshot-walk-t0-r1-terminal",
        walk_id=active.walk_id,
        projection_revision=active.projection_revision,
        horizon_id="horizon-as_lived_so_far-2024-06-01",
        current_step=1,
        state_hash="sha256:state",
        trace_hash="sha256:trace",
        belief_ids=("belief-1",),
        retrieval_ids=("first-party-occurrence-a",),
        failure_reason="SYNTHETIC_HASH_DRIFT",
    )
    sealed = seal_walk(active, terminal)

    with pytest.raises(ValueError, match="RESUME_REQUIRES_PAUSED_WALK"):
        resume_walk(
            sealed,
            WalkCheckpoint(
                "checkpoint-walk-t0-r1-1",
                walk_id=active.walk_id,
                projection_revision=active.projection_revision,
                horizon_id=terminal.horizon_id,
                current_step=1,
                state_hash=terminal.state_hash,
                trace_hash=terminal.trace_hash,
                belief_ids=terminal.belief_ids,
                retrieval_ids=terminal.retrieval_ids,
            ),
        )

    rewalk = link_rewalk(sealed, "walk-t0-r2", "projection-t0-r2")
    assert rewalk.rewalk_of == sealed.walk_id


def test_source_availability_separates_occurrence_acquisition_and_realization() -> None:
    manifest = _manifest()
    by_id = {row["id"]: row for row in manifest["documents"]}
    first_party = by_id["first-party-occurrence-a"]
    third_party = by_id["acquired-third-party-canary"]

    assert source_available_from(first_party) == first_party["occurred_at"]
    assert source_available_from(third_party) == third_party["acquired_at"]
    assert third_party["occurred_at"] < third_party["acquired_at"]
    assert manifest["subject_id"] not in third_party["participant_ids"]
    assert third_party["sender_id"] in third_party["participant_ids"]
    assert set(third_party["recipient_ids"]).issubset(third_party["participant_ids"])
    assert [item["id"] for item in third_party["realization_links"]] == manifest["expected"][
        "third_party_realization_ids"
    ]
    assert len({item["realized_at"] for item in third_party["realization_links"]}) == 3
    assert source_available_from(third_party) == third_party["acquired_at"]


def test_third_party_subject_participation_fails_closed() -> None:
    manifest = _manifest()
    row = next(item for item in manifest["documents"] if item["source_class"] == "acquired_third_party")
    contaminated = {**row, "participant_ids": [*row["participant_ids"], manifest["subject_id"]]}

    with pytest.raises(ValueError, match="THIRD_PARTY_SUBJECT_IS_PARTICIPANT"):
        source_available_from(contaminated)
