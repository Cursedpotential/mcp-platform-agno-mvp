"""Fail-closed endpoint identity tests for the disposable T0 target.

Byline: Codex · GPT-5 · 2026-08-16
"""

from dataclasses import replace

import pytest

from horizon_surreal_phase1.identity import TargetIdentity, validate_target_identity


APPROVED = TargetIdentity(
    endpoint="ws://data-surreal-phase1-t0-r1:8000/rpc",
    namespace="phase1_surreal",
    database="t0_slice_r1",
    context_id="phase1_surreal_t0_slice_r1",
)


def test_exact_approved_identity_is_accepted() -> None:
    assert validate_target_identity(APPROVED) == APPROVED


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("endpoint", "ws://data-surreal:8000/rpc"),
        ("endpoint", "ws://surrealdb:8000/rpc"),
        ("endpoint", "ws://100.119.96.29:8000/rpc"),
        ("endpoint", "ws://100.91.190.107:8000/rpc"),
        ("endpoint", "http://data-surreal-phase1-t0-r1:8000"),
        ("namespace", "agno"),
        ("database", "platform"),
        ("context_id", "production"),
    ],
)
def test_aliases_legacy_and_widened_identity_fail_closed(field: str, value: str) -> None:
    candidate = replace(APPROVED, **{field: value})
    with pytest.raises(ValueError, match="TARGET_IDENTITY_MISMATCH"):
        validate_target_identity(candidate)
