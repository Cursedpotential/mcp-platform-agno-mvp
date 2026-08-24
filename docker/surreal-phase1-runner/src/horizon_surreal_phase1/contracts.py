# Byline amendment: Codex · GPT-5 · 2026-08-18 (combined-change hygiene)
"""Framework-neutral contracts shared by tests and the live runner.

No database or framework client is imported here.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Any, Literal


HorizonMode = Literal["as_lived_so_far", "hindsight"]
GuardStatus = Literal["building", "active", "quarantined"]
WalkStatus = Literal["active", "paused", "sealed"]
SourceClass = Literal["first_party", "acquired_third_party"]


@dataclass(frozen=True, slots=True)
class HorizonContext:
    matter_id: str
    horizon_at: str
    mode: HorizonMode
    projection_revision: str
    policy_version: str


@dataclass(frozen=True, slots=True)
class ProjectionGuard:
    revision_id: str
    status: GuardStatus
    quarantine_reason: str | None = None


@dataclass(frozen=True, slots=True)
class WalkState:
    walk_id: str
    status: WalkStatus
    projection_revision: str
    rewalk_of: str | None = None


@dataclass(frozen=True, slots=True)
class WalkCheckpoint:
    checkpoint_id: str
    walk_id: str
    projection_revision: str
    horizon_id: str
    current_step: int
    state_hash: str
    trace_hash: str
    belief_ids: tuple[str, ...]
    retrieval_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class WalkSnapshot:
    snapshot_id: str
    walk_id: str
    projection_revision: str
    horizon_id: str
    current_step: int
    state_hash: str
    trace_hash: str
    belief_ids: tuple[str, ...]
    retrieval_ids: tuple[str, ...]
    failure_reason: str
    resumable: Literal[False] = False


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def source_available_from(row: dict[str, Any], *, subject_id: str = "owner-synthetic") -> str:
    """Return the source-possession clock without collapsing realization dates.

    First-party messages are available when they occur. Acquired third-party
    messages are available only when the conversation is acquired, and the
    subject must not be inferred as one of its participants.
    """

    source_class = row.get("source_class")
    occurred_at = row.get("occurred_at")
    acquired_at = row.get("acquired_at")
    projected = row.get("source_available_from")
    participants = {str(item) for item in row.get("participant_ids", [])}
    sender_id = str(row.get("sender_id") or "")
    recipient_ids = {str(item) for item in row.get("recipient_ids", [])}
    if source_class == "first_party":
        if not occurred_at or projected != occurred_at:
            raise ValueError("FIRST_PARTY_AVAILABILITY_MISMATCH")
    elif source_class == "acquired_third_party":
        if not acquired_at or projected != acquired_at:
            raise ValueError("THIRD_PARTY_AVAILABILITY_MISMATCH")
        if subject_id in participants:
            raise ValueError("THIRD_PARTY_SUBJECT_IS_PARTICIPANT")
        if not sender_id or sender_id not in participants or not recipient_ids.issubset(participants):
            raise ValueError("THIRD_PARTY_PARTICIPANT_MISMATCH")
    else:
        raise ValueError("SOURCE_CLASS_REQUIRED")
    return str(projected)


def _eligible(row: dict[str, Any], context: HorizonContext) -> bool:
    if row["matter_id"] != context.matter_id:
        return False
    if row["projection_revision"] != context.projection_revision:
        return False
    if row["policy_version"] != context.policy_version:
        return False
    if row["authority_state"] != "approved" or row["promotion_state"] != "active":
        return False
    try:
        availability = source_available_from(row)
    except ValueError:
        return False
    if context.mode == "hindsight":
        return True
    if row["disclosure_tier"] == "hindsight":
        return False
    return _parse_utc(availability) <= _parse_utc(context.horizon_at)


def eligible_ranked_ids(rows: list[dict[str, Any]], context: HorizonContext, *, top_k: int) -> list[str]:
    """Prefilter the eligible set, then rank it; never rank a global set first."""

    eligible = [row for row in rows if _eligible(row, context)]
    eligible.sort(key=lambda row: (-float(row["similarity"]), str(row["id"])))
    return [str(row["id"]) for row in eligible[:top_k]]


def transition_projection_guard(
    guard: ProjectionGuard,
    next_status: GuardStatus,
    reason: str | None = None,
) -> ProjectionGuard:
    """Apply the only valid guard transitions; quarantine is terminal."""

    if guard.status == "quarantined":
        raise ValueError("TERMINAL_PROJECTION_GUARD")
    allowed = {("building", "active"), ("building", "quarantined"), ("active", "quarantined")}
    if (guard.status, next_status) not in allowed:
        raise ValueError("INVALID_PROJECTION_GUARD_TRANSITION")
    if next_status == "quarantined" and not reason:
        raise ValueError("QUARANTINE_REASON_REQUIRED")
    return replace(guard, status=next_status, quarantine_reason=reason)


def link_rewalk(sealed: WalkState, new_walk_id: str, new_revision: str) -> WalkState:
    """Create a new walk linked to an immutable sealed predecessor."""

    if sealed.status != "sealed":
        raise ValueError("REWALK_REQUIRES_SEALED_WALK")
    if new_walk_id == sealed.walk_id or new_revision == sealed.projection_revision:
        raise ValueError("REWALK_REQUIRES_NEW_IDENTITY")
    return WalkState(
        walk_id=new_walk_id,
        status="active",
        projection_revision=new_revision,
        rewalk_of=sealed.walk_id,
    )


def pause_walk(active: WalkState, checkpoint: WalkCheckpoint) -> WalkState:
    """Pause a healthy walk at a resumable, identity-pinned checkpoint."""

    if active.status != "active":
        raise ValueError("PAUSE_REQUIRES_ACTIVE_WALK")
    if checkpoint.walk_id != active.walk_id or checkpoint.projection_revision != active.projection_revision:
        raise ValueError("CHECKPOINT_IDENTITY_MISMATCH")
    return replace(active, status="paused")


def resume_walk(paused: WalkState, checkpoint: WalkCheckpoint) -> WalkState:
    """Resume the same healthy walk; sealed or mismatched state must rewalk."""

    if paused.status != "paused":
        raise ValueError("RESUME_REQUIRES_PAUSED_WALK")
    if checkpoint.walk_id != paused.walk_id or checkpoint.projection_revision != paused.projection_revision:
        raise ValueError("CHECKPOINT_IDENTITY_MISMATCH")
    return replace(paused, status="active")


def seal_walk(walk: WalkState, snapshot: WalkSnapshot) -> WalkState:
    """Seal a compromised walk without changing its historical identity."""

    if walk.status == "sealed":
        raise ValueError("WALK_ALREADY_SEALED")
    if (
        snapshot.walk_id != walk.walk_id
        or snapshot.projection_revision != walk.projection_revision
        or snapshot.resumable
        or not snapshot.failure_reason
    ):
        raise ValueError("SNAPSHOT_IDENTITY_MISMATCH")
    return replace(walk, status="sealed")
