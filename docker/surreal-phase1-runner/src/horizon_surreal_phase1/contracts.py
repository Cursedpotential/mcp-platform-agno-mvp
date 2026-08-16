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


def _parse_utc(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _eligible(row: dict[str, Any], context: HorizonContext) -> bool:
    if row["matter_id"] != context.matter_id:
        return False
    if row["projection_revision"] != context.projection_revision:
        return False
    if row["policy_version"] != context.policy_version:
        return False
    if row["authority_state"] != "approved" or row["promotion_state"] != "active":
        return False
    if context.mode == "hindsight":
        return True
    if row["disclosure_tier"] == "hindsight" or row.get("visible_from") is None:
        return False
    return _parse_utc(row["visible_from"]) <= _parse_utc(context.horizon_at)


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
