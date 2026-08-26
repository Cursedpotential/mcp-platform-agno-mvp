"""Typed, fixture/interface-only model of the D-084/D-085 authority-state contract.

See ``personal_case_authority/__init__.py`` for scope. Every field name below is
chosen to match ADR-0060's canonical timeline mapping contract table and D-085's
authority description as closely as possible, but NONE of it is a live schema --
R00 owns final column names/types (SEMANTIC-AGENT-WORK-PACKAGES.md WP-A01).
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from typing import Optional, Protocol


class AuthorityState(enum.Enum):
    """Where a timeline item sits in the D-082..D-085 authority flow.

    Non-negotiable ordering per ADR-0060/D-082: a CANDIDATE never becomes
    EVIDENCE_APPROVED by itself -- only independent custody-backed evidence review
    does that (out of band, in the evidence/fact workflow). An edit proposed against
    an EVIDENCE_APPROVED item becomes an AMENDMENT_CANDIDATE, never an in-place
    change to the approved item.
    """

    CANDIDATE_CONTEXT = "candidate_context"
    EVIDENCE_APPROVED = "evidence_approved"
    AMENDMENT_CANDIDATE = "amendment_candidate"


class VerificationState(enum.Enum):
    UNVERIFIED = "unverified"
    DISPUTED = "disputed"
    VERIFIED = "verified"
    REVOKED = "revoked"
    SUPERSEDED = "superseded"


class TemporalPrecision(enum.Enum):
    """An imprecise/interval event is never coerced into a false-precision point."""

    POINT = "point"
    INTERVAL = "interval"
    UNCERTAIN = "uncertain"


@dataclass(frozen=True)
class TemporalValue:
    """Preserves point/range/uncertainty separately from the display anchor.

    ``display_at_utc`` is the ADR-0060 required projection/display point mapped to
    Timesketch's ``datetime`` field. It never overwrites ``occurred_at``/
    ``valid_from``/``valid_to`` -- those travel alongside it as bounded attributes.
    """

    precision: TemporalPrecision
    display_at_utc: str  # ISO-8601; a display anchor, not the sole truth
    occurred_at: Optional[str] = None
    valid_from: Optional[str] = None
    valid_to: Optional[str] = None
    confidence: Optional[float] = None


@dataclass(frozen=True)
class SourceLineage:
    """Stable source/version IDs for replay, reconciliation, and source opening."""

    source_system: str  # e.g. "ai_chat", "sms", "custody_evidence"
    source_record_id: str
    source_version: Optional[str] = None
    ingestion_run_id: Optional[str] = None


@dataclass(frozen=True)
class TimelineProjectionMember:
    """One row of the ADR-0060 canonical timeline contract, fixture-shaped.

    Maps 1:1 onto the ADR-0060 mapping table:
    ``display_at_utc`` -> Timesketch ``datetime``;
    ``display_summary`` -> Timesketch ``message``;
    ``event_type`` -> Timesketch ``timestamp_desc``;
    everything else -> bounded Timesketch attributes.
    """

    stable_member_id: str
    authority_state: AuthorityState
    temporal: TemporalValue
    display_summary: str
    event_type: str
    lineage: SourceLineage
    entity_refs: tuple[str, ...] = field(default_factory=tuple)
    verification_state: VerificationState = VerificationState.UNVERIFIED
    privacy_level: Optional[str] = None
    privileged: bool = False
    projection_generation: Optional[str] = None
    projection_hash: Optional[str] = None
    # Only set when authority_state == AMENDMENT_CANDIDATE.
    amends_stable_member_id: Optional[str] = None


class TimelineProjectionSource(Protocol):
    """Interface a real TS-03 (WP-E02) PostgreSQL projector implements.

    Fixture/interface-only: calling any method here is a programming error in
    WP-E01 -- there is no implementation, deliberately, until TS-03.
    """

    def fetch_generation(
        self, since_generation: Optional[str] = None
    ) -> tuple[str, list[TimelineProjectionMember]]:
        """Return (new_generation_id, members) for outbox-driven reprojection."""
        raise NotImplementedError("TS-03 (WP-E02) implements this against PostgreSQL")


class CurationCommandSink(Protocol):
    """Interface a real TS-04 (WP-F01) curation API implements.

    Fixture/interface-only, matching the TIMESKETCH-FORK-CURATION-HANDOFF.md
    bulk-edit contract shape (batch/item, expected generation, atomic-or-itemized).
    """

    def submit_batch(
        self,
        *,
        actor: str,
        idempotency_key: str,
        expected_projection_generation: str,
        items: tuple[dict, ...],
        atomic: bool = False,
    ) -> dict:
        """Return a receipt with per-item accepted/rejected/conflict/no_op results."""
        raise NotImplementedError("TS-04 (WP-F01) implements this against PostgreSQL")
