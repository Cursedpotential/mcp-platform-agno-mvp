# Byline: Claude Code · Sonnet 5 · 2026-08-26
"""Dataclasses for the ADR-0060 canonical timeline contract, on the PG side.

Field names mirror `timesketch-fork/personal_case_authority/authority.py`'s
`TimelineProjectionMember` fixture as closely as the two independent codebases can (that module
is fixture/interface-only; this one is the real PostgreSQL implementation TS-03/WP-E02 was
scoped to build) — but this module does NOT import from `timesketch-fork/` and vice versa.
`server/` and the Timesketch fork are two separate deployable applications with independent
dependency graphs (see `../AGENTS.md` dependency-direction table); the shared shape is a
contract, not a code import.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal, Optional

TemporalPrecision = Literal["point", "interval", "uncertain"]
AuthorityState = Literal["candidate_context", "evidence_approved", "amendment_candidate"]
VerificationState = Literal["unverified", "disputed", "verified", "revoked", "superseded"]
ChangeClass = Literal["core", "annotation", "unchanged"]


@dataclass(frozen=True)
class SourceMemberRow:
    """One row read from `timeline.timeline_member` joined to its source (candidate or governed).

    This is the INPUT to generation-building — not yet hashed, not yet a projection row.
    """

    source_member_id: str  # timeline.timeline_member.id
    collection_id: str
    authority_state: AuthorityState
    source_system: str
    source_record_id: str
    source_record_version: Optional[str]
    temporal_precision: TemporalPrecision
    occurred_at: Optional[datetime]
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    temporal_confidence: Optional[float]
    display_summary: str
    event_type: str
    entity_refs: tuple[str, ...] = field(default_factory=tuple)
    verification_state: VerificationState = "unverified"
    privacy_level: Optional[str] = None
    privileged: bool = False
    source_available_from: Optional[datetime] = None  # required by the time projection runs; see generation.py
    amends_stable_member_id: Optional[str] = None


@dataclass(frozen=True)
class ProjectedMember:
    """One fully-computed `timeline.timeline_projection_member` row, ready to insert."""

    source_member_id: str
    stable_member_id: str
    opensearch_doc_id: str
    authority_state: AuthorityState
    amends_stable_member_id: Optional[str]
    display_at_utc: datetime
    display_summary: str
    event_type: str
    temporal_precision: TemporalPrecision
    occurred_at: Optional[datetime]
    valid_from: Optional[datetime]
    valid_to: Optional[datetime]
    temporal_confidence: Optional[float]
    source_available_from: datetime
    entity_refs: tuple[str, ...]
    verification_state: VerificationState
    privacy_level: Optional[str]
    privileged: bool
    source_system: str
    source_record_id: str
    source_record_version: Optional[str]
    core_content_hash: str
    annotation_content_hash: str
    member_content_hash: str
    change_class: ChangeClass


@dataclass(frozen=True)
class GenerationResult:
    """Return shape of `generation.build_generation()`."""

    generation_id: str
    sequence: int
    created: bool  # False when an idempotent replay returned an existing generation
    member_count: int
    skipped_unresolved_governed_members: tuple[str, ...] = field(default_factory=tuple)
