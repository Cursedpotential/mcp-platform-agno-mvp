"""Immutable target identity and legacy denylist.

Byline: Codex · GPT-5 · 2026-08-16
# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TargetIdentity:
    """Every connection coordinate that must match before opening a socket."""

    endpoint: str
    namespace: str
    database: str
    context_id: str


APPROVED_TARGET = TargetIdentity(
    endpoint="ws://data-surreal-phase1-t0-r1:8000/rpc",
    namespace="phase1_surreal",
    database="t0_slice_r1",
    context_id="phase1_surreal_t0_slice_r1",
)

APPROVED_RESTORE_TARGET = TargetIdentity(
    endpoint="ws://data-surreal-phase1-t0-r1:8000/rpc",
    namespace="phase1_surreal",
    database="t0_slice_r1_restore",
    context_id="phase1_surreal_t0_slice_r1_restore",
)

APPROVED_TARGETS = (APPROVED_TARGET, APPROVED_RESTORE_TARGET)


def validate_target_identity(candidate: TargetIdentity) -> TargetIdentity:
    """Fail closed unless every coordinate equals the owner-approved T0 target."""

    if candidate not in APPROVED_TARGETS:
        raise ValueError("TARGET_IDENTITY_MISMATCH")
    return candidate


def sdk_endpoint(identity: TargetIdentity) -> str:
    """Return the SDK base URL; SDK 2.0 appends ``/rpc`` itself."""

    validate_target_identity(identity)
    return identity.endpoint.removesuffix("/rpc")
