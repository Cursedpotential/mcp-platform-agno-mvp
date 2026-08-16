"""Pure contract tests for horizon filtering and failure transitions.

Byline: Codex · GPT-5 · 2026-08-16
"""

import json
from pathlib import Path

import pytest

from horizon_surreal_phase1.contracts import (
    HorizonContext,
    ProjectionGuard,
    WalkState,
    eligible_ranked_ids,
    link_rewalk,
    transition_projection_guard,
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
        policy_version="horizon-policy-v1",
    )
    assert eligible_ranked_ids(manifest["documents"], context, top_k=2) == [
        "safe-contemporaneous-a",
        "safe-contemporaneous-b",
    ]


def test_late_and_hindsight_positive_controls_are_not_overfiltered() -> None:
    manifest = _manifest()
    late = HorizonContext(
        matter_id="matter-synthetic-a",
        horizon_at="2026-06-01T00:00:00Z",
        mode="as_lived_so_far",
        projection_revision="projection-t0-r1",
        policy_version="horizon-policy-v1",
    )
    hindsight = HorizonContext(
        matter_id="matter-synthetic-a",
        horizon_at="2024-06-01T00:00:00Z",
        mode="hindsight",
        projection_revision="projection-t0-r1",
        policy_version="horizon-policy-v1",
    )
    assert eligible_ranked_ids(manifest["documents"], late, top_k=2) == [
        "future-occurring-canary",
        "late-realized-old-source-canary",
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
