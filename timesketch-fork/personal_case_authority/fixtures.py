"""One example instance per authority state -- for later packets to render/test
against before TS-03's real projector exists. Not used by any running code path.
"""

from __future__ import annotations

from .authority import (
    AuthorityState,
    SourceLineage,
    TemporalPrecision,
    TemporalValue,
    TimelineProjectionMember,
    VerificationState,
)

CANDIDATE_FROM_AI_CHAT = TimelineProjectionMember(
    stable_member_id="fixture-candidate-0001",
    authority_state=AuthorityState.CANDIDATE_CONTEXT,
    temporal=TemporalValue(
        precision=TemporalPrecision.UNCERTAIN,
        display_at_utc="2026-03-14T00:00:00Z",
        occurred_at=None,
        confidence=0.4,
    ),
    display_summary=(
        "AI-chat lead: possible missed exchange window mentioned in conversation"
    ),
    event_type="context_lead",
    lineage=SourceLineage(
        source_system="ai_chat",
        source_record_id="fixture-chat-msg-0042",
    ),
    verification_state=VerificationState.UNVERIFIED,
)

EVIDENCE_APPROVED_EVENT = TimelineProjectionMember(
    stable_member_id="fixture-approved-0001",
    authority_state=AuthorityState.EVIDENCE_APPROVED,
    temporal=TemporalValue(
        precision=TemporalPrecision.POINT,
        display_at_utc="2026-03-14T18:22:00Z",
        occurred_at="2026-03-14T18:22:00Z",
        confidence=1.0,
    ),
    display_summary="SMS sent, custody-hash verified",
    event_type="message_sent",
    lineage=SourceLineage(
        source_system="sms",
        source_record_id="fixture-sms-0917",
        source_version="v1",
    ),
    verification_state=VerificationState.VERIFIED,
    projection_generation="fixture-gen-0007",
    projection_hash="fixture-hash-abc123",
)

AMENDMENT_CANDIDATE_AGAINST_APPROVED = TimelineProjectionMember(
    stable_member_id="fixture-amendment-0001",
    authority_state=AuthorityState.AMENDMENT_CANDIDATE,
    temporal=EVIDENCE_APPROVED_EVENT.temporal,
    display_summary="Proposed correction: display summary too terse, add context",
    event_type="message_sent",
    lineage=EVIDENCE_APPROVED_EVENT.lineage,
    verification_state=VerificationState.UNVERIFIED,
    amends_stable_member_id=EVIDENCE_APPROVED_EVENT.stable_member_id,
)

ALL_FIXTURES = (
    CANDIDATE_FROM_AI_CHAT,
    EVIDENCE_APPROVED_EVENT,
    AMENDMENT_CANDIDATE_AGAINST_APPROVED,
)
