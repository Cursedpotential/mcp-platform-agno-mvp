"""Format-neutral contracts for cross-platform conversation continuity.

First-party and acquired-third-party threads intentionally have mirrored but
distinct types. They must never be co-mingled because their authority and
source-availability clocks differ.

Byline: Codex · GPT-5 · 2026-08-29
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, Sequence

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ReviewStatus = Literal["proposed", "approved", "rejected", "needs_review"]
ClockBasis = Literal[
    "device_local",
    "platform_utc",
    "export_generated",
    "filesystem",
    "human_asserted",
    "unknown",
]
RepresentationKind = Literal[
    "screenshot",
    "device_export",
    "platform_export",
    "native_export",
    "third_party_export",
    "other",
]


class _StrictContextContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


def _aware(value: datetime | None) -> datetime | None:
    if value is not None and value.tzinfo is None:
        raise ValueError("exact timestamps must include an explicit timezone")
    return value


class _TimestampMetadata(_StrictContextContract):
    raw_metadata_ref: str
    extractor_id: str
    extractor_version: str
    clock_basis: ClockBasis
    timezone_basis: str | None = None
    parsed_timestamp: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: ReviewStatus
    ambiguity_notes: list[str] = Field(default_factory=list)

    @field_validator("raw_metadata_ref", "extractor_id", "extractor_version")
    @classmethod
    def _metadata_identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("metadata reference and extractor pins must not be blank")
        return value

    @field_validator("parsed_timestamp")
    @classmethod
    def _metadata_timestamp_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)

    @model_validator(mode="after")
    def _unknown_clock_is_ambiguous(self) -> _TimestampMetadata:
        if self.clock_basis == "unknown" and not self.ambiguity_notes:
            raise ValueError("unknown metadata clock basis requires an ambiguity note")
        return self


class FirstPartyTimestampMetadata(_TimestampMetadata):
    """Metadata-clock interpretation for a first-party representation."""

    corpus: Literal["first_party"] = "first_party"


class ThirdPartyTimestampMetadata(_TimestampMetadata):
    """Metadata-clock interpretation for an acquired-third-party representation."""

    corpus: Literal["acquired_third_party"] = "acquired_third_party"


class _RelativeDateAnchor(_StrictContextContract):
    """Reviewed bounds used when an exact primary timestamp is unavailable."""

    anchor_id: str
    anchor_version: int = Field(ge=1)
    supersedes_anchor_id: str | None = None
    last_known_before: datetime | None = None
    first_known_after: datetime | None = None
    contextual_order_ref: str | None = None
    metadata_basis: str
    raw_metadata_ref: str
    confidence: float = Field(ge=0.0, le=1.0)
    ambiguity_notes: list[str] = Field(min_length=1)
    review_status: ReviewStatus
    review_case_refs: list[str] = Field(default_factory=list)
    active_relative_anchor_assertion_refs: list[str] = Field(default_factory=list)

    @field_validator("anchor_id", "metadata_basis", "raw_metadata_ref")
    @classmethod
    def _relative_anchor_identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("relative-date anchor identity and metadata references must not be blank")
        return value

    @field_validator("last_known_before", "first_known_after")
    @classmethod
    def _relative_bounds_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)

    @model_validator(mode="after")
    def _relative_anchor_is_bounded_and_versioned(self) -> _RelativeDateAnchor:
        if self.last_known_before is None and self.first_known_after is None and not self.contextual_order_ref:
            raise ValueError("relative-date anchor requires a bound or contextual sequence reference")
        if (
            self.last_known_before is not None
            and self.first_known_after is not None
            and self.first_known_after < self.last_known_before
        ):
            raise ValueError("first_known_after cannot precede last_known_before")
        if self.anchor_version > 1 and not self.supersedes_anchor_id:
            raise ValueError("a corrected relative-date anchor must identify the version it supersedes")
        return self


class FirstPartyRelativeDateAnchor(_RelativeDateAnchor):
    """Occurrence/sequence fallback for first-party material; never acquisition-derived."""

    corpus: Literal["first_party"] = "first_party"


class ThirdPartyRelativeDateAnchor(_RelativeDateAnchor):
    """Occurrence/sequence fallback for third-party messages, not source availability."""

    corpus: Literal["acquired_third_party"] = "acquired_third_party"


class EventCandidateRelativeTimeAnchorLink(_StrictContextContract):
    """Append-only typed link from an event candidate to external time authority."""

    contract_version: Literal["event-relative-time-link-v1"] = "event-relative-time-link-v1"
    link_id: str
    link_version: int = Field(ge=1)
    supersedes_link_id: str | None = None
    event_candidate_ref: str
    relative_date_anchor_ref: str
    temporal_role: Literal[
        "occurred_at",
        "valid_from",
        "valid_to",
        "source_available_from",
        "realizable_from",
    ]
    review_status: ReviewStatus
    receipt_ref: str
    created_at: datetime

    @field_validator("link_id", "event_candidate_ref", "relative_date_anchor_ref", "receipt_ref")
    @classmethod
    def _event_time_link_fields_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("event relative-time link references must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def _event_time_link_created_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _event_time_link_is_versioned(self) -> EventCandidateRelativeTimeAnchorLink:
        if self.link_version > 1 and not self.supersedes_link_id:
            raise ValueError("a corrected event relative-time link must identify the link it supersedes")
        return self


class ConflictReviewCase(_StrictContextContract):
    """One append-only version of a conflict requiring human adjudication."""

    contract_version: Literal["conflict-review-case-v1"] = "conflict-review-case-v1"
    review_case_id: str
    case_version: int = Field(ge=1)
    supersedes_review_case_ref: str | None = None
    conflict_kind: Literal[
        "relative_anchor",
        "first_party_thread",
        "third_party_thread",
        "first_party_source_representation_equivalence",
        "third_party_source_representation_equivalence",
        "timeline_event_candidate",
    ]
    status: Literal["open", "queued", "decided", "superseded"]
    provenance_refs: list[str] = Field(min_length=1)
    created_at: datetime

    @field_validator("review_case_id", "provenance_refs")
    @classmethod
    def _review_case_fields_required(cls, value: str | list[str]) -> str | list[str]:
        values = [value] if isinstance(value, str) else value
        if any(not item.strip() for item in values):
            raise ValueError("review case identity and provenance must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def _review_case_created_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _review_case_is_append_only_versioned(self) -> ConflictReviewCase:
        if self.case_version > 1 and not self.supersedes_review_case_ref:
            raise ValueError("a later review-case version must reference the version it supersedes")
        return self


class ConflictReviewQueueEvent(_StrictContextContract):
    """Append-only queue event; queue state is derived, never updated in place."""

    contract_version: Literal["conflict-review-queue-event-v1"] = "conflict-review-queue-event-v1"
    queue_event_id: str
    review_case_ref: str
    action: Literal["enqueue", "claim", "release", "complete", "requeue"]
    queue_name: str
    actor_ref: str
    occurred_at: datetime
    provenance_ref: str

    @field_validator("queue_event_id", "review_case_ref", "queue_name", "actor_ref", "provenance_ref")
    @classmethod
    def _queue_event_fields_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("review queue event fields must not be blank")
        return value

    @field_validator("occurred_at")
    @classmethod
    def _queue_event_occurred_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value


class ConflictReviewWorkflowReference(_StrictContextContract):
    """Reference-only Temporal workflow envelope for an extended HITL wait."""

    contract_version: Literal["conflict-review-workflow-ref-v1"] = "conflict-review-workflow-ref-v1"
    canonical_authority: Literal["postgresql"] = "postgresql"
    durable_orchestrator: Literal["temporal"] = "temporal"
    workflow_type: Literal["ConflictReviewWorkflow"] = "ConflictReviewWorkflow"
    workflow_id: str
    run_id: str
    review_case_ref: str
    expected_review_case_version: int = Field(ge=1)
    idempotency_key: str
    escalation_policy_ref: str
    reminder_policy_ref: str

    @field_validator(
        "workflow_id",
        "run_id",
        "review_case_ref",
        "idempotency_key",
        "escalation_policy_ref",
        "reminder_policy_ref",
    )
    @classmethod
    def _workflow_reference_fields_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("conflict workflow references must not be blank")
        return value


class ConflictReviewDispatchReceipt(_StrictContextContract):
    """Receipt for n8n dispatch/notification, explicitly without approval authority."""

    contract_version: Literal["conflict-review-dispatch-v1"] = "conflict-review-dispatch-v1"
    dispatch_adapter: Literal["n8n"] = "n8n"
    approval_authority: Literal["none"] = "none"
    workflow_id: str
    run_id: str
    review_case_ref: str
    expected_review_case_version: int = Field(ge=1)
    idempotency_key: str
    implementation_ref: str
    dispatch_receipt_ref: str
    dispatched_at: datetime

    @field_validator(
        "workflow_id",
        "run_id",
        "review_case_ref",
        "idempotency_key",
        "implementation_ref",
        "dispatch_receipt_ref",
    )
    @classmethod
    def _dispatch_fields_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("conflict review dispatch references must not be blank")
        return value

    @field_validator("dispatched_at")
    @classmethod
    def _dispatch_time_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value


class ConflictReviewDecisionSignal(_StrictContextContract):
    """Authenticated reference-only decision signal/update delivered to Temporal."""

    contract_version: Literal["conflict-review-decision-signal-v1"] = "conflict-review-decision-signal-v1"
    workflow_id: str
    run_id: str
    review_case_ref: str
    expected_review_case_version: int = Field(ge=1)
    decision_ref: str
    authenticated_reviewer_ref: str
    authentication_receipt_ref: str
    decision_signal_receipt_ref: str
    idempotency_key: str
    signaled_at: datetime

    @field_validator(
        "workflow_id",
        "run_id",
        "review_case_ref",
        "decision_ref",
        "authenticated_reviewer_ref",
        "authentication_receipt_ref",
        "decision_signal_receipt_ref",
        "idempotency_key",
    )
    @classmethod
    def _decision_signal_fields_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("decision signal references must not be blank")
        return value

    @field_validator("signaled_at")
    @classmethod
    def _signal_time_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value


class ConflictReviewActivityRequest(_StrictContextContract):
    """One short idempotent activity invocation, containing references only."""

    contract_version: Literal["conflict-review-activity-ref-v1"] = "conflict-review-activity-ref-v1"
    activity_kind: Literal["create", "dispatch", "validate", "persist", "reproject"]
    workflow_id: str
    run_id: str
    review_case_ref: str
    expected_review_case_version: int = Field(ge=1)
    input_ref: str
    idempotency_key: str

    @field_validator("workflow_id", "run_id", "review_case_ref", "input_ref", "idempotency_key")
    @classmethod
    def _activity_reference_fields_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("conflict review activity references must not be blank")
        return value


class ConflictReviewTerminalReconciliation(_StrictContextContract):
    """Terminal PG reconciliation and re-projection receipt set."""

    contract_version: Literal["conflict-review-reconciliation-v1"] = "conflict-review-reconciliation-v1"
    canonical_authority: Literal["postgresql"] = "postgresql"
    workflow_id: str
    run_id: str
    review_case_ref: str
    reconciled_review_case_version: int = Field(ge=1)
    decision_ref: str
    decision_signal_receipt_ref: str
    persistence_receipt_ref: str
    reprojection_receipt_refs: list[str] = Field(default_factory=list)
    status: Literal["reconciled", "failed"]
    reconciled_at: datetime

    @field_validator(
        "workflow_id",
        "run_id",
        "review_case_ref",
        "decision_ref",
        "decision_signal_receipt_ref",
        "persistence_receipt_ref",
        "reprojection_receipt_refs",
    )
    @classmethod
    def _reconciliation_fields_required(cls, value: str | list[str]) -> str | list[str]:
        values = [value] if isinstance(value, str) else value
        if any(not item.strip() for item in values):
            raise ValueError("terminal reconciliation references must not be blank")
        return value

    @field_validator("reconciled_at")
    @classmethod
    def _reconciled_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value


class ConflictAdjudicationDecision(_StrictContextContract):
    """Versioned human decision; coexist/supersede are relations, not merges."""

    contract_version: Literal["conflict-adjudication-v1"] = "conflict-adjudication-v1"
    decision_id: str
    decision_version: int = Field(ge=1)
    supersedes_decision_ref: str | None = None
    review_case_ref: str
    typed_conflict_link_ref: str
    disposition: Literal["accept", "reject", "coexist", "supersede", "needs_more_evidence"]
    accepted_side: Literal["left", "right", "both", "neither"]
    superseded_side: Literal["left", "right", "neither"] = "neither"
    reviewer_ref: str
    rationale: str
    provenance_refs: list[str] = Field(min_length=1)
    decided_at: datetime

    @field_validator(
        "decision_id",
        "review_case_ref",
        "typed_conflict_link_ref",
        "reviewer_ref",
        "rationale",
        "provenance_refs",
    )
    @classmethod
    def _decision_fields_required(cls, value: str | list[str]) -> str | list[str]:
        values = [value] if isinstance(value, str) else value
        if any(not item.strip() for item in values):
            raise ValueError("adjudication identity, reviewer, rationale, and provenance must not be blank")
        return value

    @field_validator("decided_at")
    @classmethod
    def _decision_time_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _decision_is_versioned_and_non_merging(self) -> ConflictAdjudicationDecision:
        if self.decision_version > 1 and not self.supersedes_decision_ref:
            raise ValueError("a later adjudication must reference the decision it supersedes")
        if self.disposition == "supersede" and (
            self.accepted_side not in {"left", "right"}
            or self.superseded_side not in {"left", "right"}
            or self.accepted_side == self.superseded_side
        ):
            raise ValueError("supersede requires distinct accepted and superseded conflict sides")
        if self.disposition == "coexist" and self.accepted_side != "both":
            raise ValueError("coexist requires both typed conflict sides")
        if self.disposition == "reject" and self.accepted_side != "neither":
            raise ValueError("reject cannot accept a conflict side")
        return self


class _ConflictReviewLink(_StrictContextContract):
    link_id: str
    link_version: int = Field(ge=1)
    supersedes_link_ref: str | None = None
    review_case_ref: str
    receipt_ref: str
    created_at: datetime

    @field_validator("link_id", "review_case_ref", "receipt_ref")
    @classmethod
    def _conflict_link_fields_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("typed conflict link fields must not be blank")
        return value

    @field_validator("created_at")
    @classmethod
    def _conflict_link_created_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value

    @model_validator(mode="after")
    def _conflict_link_is_versioned(self) -> _ConflictReviewLink:
        if self.link_version > 1 and not self.supersedes_link_ref:
            raise ValueError("a later conflict-link version must reference the link it supersedes")
        typed_refs = [
            getattr(self, field_name)
            for field_name in type(self).model_fields
            if field_name.startswith("left_") or field_name.startswith("right_")
        ]
        if any(not value.strip() for value in typed_refs):
            raise ValueError("typed conflict subject references must not be blank")
        if len(typed_refs) == 2 and typed_refs[0] == typed_refs[1]:
            raise ValueError("a conflict must link two distinct assertions")
        return self


class RelativeAnchorConflictReviewLink(_ConflictReviewLink):
    left_relative_anchor_ref: str
    right_relative_anchor_ref: str


class FirstPartyThreadConflictReviewLink(_ConflictReviewLink):
    left_first_party_thread_ref: str
    right_first_party_thread_ref: str


class ThirdPartyThreadConflictReviewLink(_ConflictReviewLink):
    left_third_party_thread_ref: str
    right_third_party_thread_ref: str


class FirstPartySourceRepresentationEquivalenceConflictReviewLink(_ConflictReviewLink):
    left_first_party_representation_ref: str
    right_first_party_representation_ref: str


class ThirdPartySourceRepresentationEquivalenceConflictReviewLink(_ConflictReviewLink):
    left_third_party_representation_ref: str
    right_third_party_representation_ref: str


class TimelineEventCandidateConflictReviewLink(_ConflictReviewLink):
    left_event_candidate_ref: str
    right_event_candidate_ref: str


class _Participant(_StrictContextContract):
    party_id: str
    display_name: str | None = None
    role: Literal["sender", "recipient", "cc", "bcc", "group_member", "unknown"]
    is_case_owner: bool = False

    @field_validator("party_id")
    @classmethod
    def _party_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("party_id must not be blank")
        return value


class FirstPartyParticipant(_Participant):
    """Actual participant coordinate in an owner-anchored thread."""

    corpus: Literal["first_party"] = "first_party"


class ThirdPartyParticipant(_Participant):
    """Actual participant coordinate; the case owner is forbidden."""

    corpus: Literal["acquired_third_party"] = "acquired_third_party"


class _MessageAnchor(_StrictContextContract):
    message_anchor_id: str
    platform: str
    platform_message_id: str | None = None
    thread_order: int = Field(ge=0)
    source_order: int = Field(ge=0)
    occurred_at: datetime | None = None
    source_representation_ids: list[str] = Field(min_length=1)
    timestamp_metadata_ref: str
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    required_for_horizon: Literal[True] = True

    @field_validator("message_anchor_id", "platform", "timestamp_metadata_ref", "source_representation_ids")
    @classmethod
    def _message_anchor_fields_required(cls, value: str | list[str]) -> str | list[str]:
        values = [value] if isinstance(value, str) else value
        if any(not item.strip() for item in values):
            raise ValueError("message anchor identity fields must not be blank")
        if not isinstance(value, str) and len(value) != len(set(value)):
            raise ValueError("source representation ids must be unique per message anchor")
        return value

    @field_validator("occurred_at")
    @classmethod
    def _occurred_at_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)


class FirstPartyMessageAnchor(_MessageAnchor):
    corpus: Literal["first_party"] = "first_party"
    participants: list[FirstPartyParticipant] = Field(min_length=1)
    relative_date_anchor_ref: str | None = None

    @model_validator(mode="after")
    def _first_party_primary_or_relative_clock(self) -> FirstPartyMessageAnchor:
        if (self.occurred_at is None) == (self.relative_date_anchor_ref is None):
            raise ValueError("first-party message requires exactly one exact occurrence or relative-date anchor")
        if self.relative_date_anchor_ref is not None and not self.relative_date_anchor_ref.strip():
            raise ValueError("relative_date_anchor_ref must not be blank")
        return self


class ThirdPartyMessageAnchor(_MessageAnchor):
    corpus: Literal["acquired_third_party"] = "acquired_third_party"
    participants: list[ThirdPartyParticipant] = Field(min_length=1)
    relative_date_anchor_ref: str | None = None

    @model_validator(mode="after")
    def _owner_is_not_a_third_party_participant(self) -> ThirdPartyMessageAnchor:
        if any(participant.is_case_owner for participant in self.participants):
            raise ValueError("the case owner cannot be invented as a third-party participant")
        if (self.occurred_at is None) == (self.relative_date_anchor_ref is None):
            raise ValueError("third-party message requires exactly one exact occurrence or relative-date anchor")
        if self.relative_date_anchor_ref is not None and not self.relative_date_anchor_ref.strip():
            raise ValueError("relative_date_anchor_ref must not be blank")
        return self


class _SourceRepresentation(_StrictContextContract):
    representation_id: str
    source_version_ref: str
    representation_kind: RepresentationKind
    media_type: str
    platform: str | None = None
    device_principal: str | None = None
    perspective_party_id: str | None = None
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    byte_length: int = Field(ge=0)
    immutable_receipt_ref: str
    metadata: _TimestampMetadata
    metadata_captured_or_created_at: datetime | None = None
    metadata_exported_at: datetime | None = None
    observed_metadata_acquired_at: datetime | None = None
    observed_metadata_at: datetime | None = None
    relative_date_anchor_ref: str | None = None
    review_case_refs: list[str] = Field(default_factory=list)
    active_source_representation_assertion_refs: list[str] = Field(default_factory=list)
    attrs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("representation_id", "source_version_ref", "media_type", "immutable_receipt_ref")
    @classmethod
    def _representation_identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("source representation identity fields must not be blank")
        return value

    @field_validator(
        "metadata_captured_or_created_at",
        "metadata_exported_at",
        "observed_metadata_acquired_at",
        "observed_metadata_at",
    )
    @classmethod
    def _representation_clocks_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)

    @model_validator(mode="after")
    def _representation_primary_or_relative_clock(self) -> _SourceRepresentation:
        exact_clock_present = False
        if self.representation_kind == "screenshot":
            exact_clock_present = self.metadata_captured_or_created_at is not None
        if self.representation_kind in {
            "device_export",
            "platform_export",
            "native_export",
            "third_party_export",
        }:
            exact_clock_present = (
                self.metadata_exported_at is not None and self.observed_metadata_acquired_at is not None
            )
        if self.representation_kind == "other":
            exact_clock_present = self.observed_metadata_at is not None
        if exact_clock_present == (self.relative_date_anchor_ref is not None):
            raise ValueError("source representation requires exactly one exact metadata clock or relative anchor ref")
        if self.relative_date_anchor_ref is not None and not self.relative_date_anchor_ref.strip():
            raise ValueError("relative_date_anchor_ref must not be blank")
        return self


class FirstPartySourceRepresentation(_SourceRepresentation):
    corpus: Literal["first_party"] = "first_party"
    metadata: FirstPartyTimestampMetadata


class ThirdPartySourceRepresentation(_SourceRepresentation):
    corpus: Literal["acquired_third_party"] = "acquired_third_party"
    metadata: ThirdPartyTimestampMetadata
    acquired_at: datetime | None = None
    acquisition_receipt_ref: str
    acquisition_relative_date_anchor_ref: str | None = None
    required_for_horizon: Literal[True] = True

    @field_validator("acquired_at")
    @classmethod
    def _representation_acquired_at_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)

    @field_validator("acquisition_receipt_ref")
    @classmethod
    def _representation_acquisition_receipt_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("third-party representation acquisition receipt must not be blank")
        return value

    @model_validator(mode="after")
    def _representation_acquisition_is_exact_or_relative(self) -> ThirdPartySourceRepresentation:
        if (self.acquired_at is None) == (self.acquisition_relative_date_anchor_ref is None):
            raise ValueError("third-party representation requires exact acquisition or relative anchor ref")
        if (
            self.acquisition_relative_date_anchor_ref is not None
            and not self.acquisition_relative_date_anchor_ref.strip()
        ):
            raise ValueError("acquisition_relative_date_anchor_ref must not be blank")
        return self


class FirstPartyOwnerAnchor(_StrictContextContract):
    owner_party_id: str
    authenticated_assertion_receipt_ref: str

    @field_validator("owner_party_id", "authenticated_assertion_receipt_ref")
    @classmethod
    def _owner_anchor_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("first-party owner anchor fields must not be blank")
        return value


class ThirdPartyAcquisitionAnchor(_StrictContextContract):
    representation_id: str
    acquired_at: datetime
    acquisition_receipt_ref: str
    source_principal: str

    @field_validator("acquired_at")
    @classmethod
    def _acquired_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value

    @field_validator("representation_id", "acquisition_receipt_ref", "source_principal")
    @classmethod
    def _acquisition_anchor_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("third-party acquisition anchor fields must not be blank")
        return value


class ThirdPartyApprovalAnchor(_StrictContextContract):
    approved_at: datetime
    approved_by: str
    approval_receipt_ref: str

    @field_validator("approved_at")
    @classmethod
    def _approved_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value

    @field_validator("approved_by", "approval_receipt_ref")
    @classmethod
    def _approval_anchor_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("third-party approval anchor fields must not be blank")
        return value


class ReviewedRealizationLink(_StrictContextContract):
    realization_id: str
    realized_at: datetime
    review_status: Literal["approved"] = "approved"
    reviewed_by: str
    review_receipt_ref: str
    required_message_anchor_ids: list[str] = Field(default_factory=list)
    required_source_representation_ids: list[str] = Field(default_factory=list)
    required_source_available_from: datetime | None = None
    relative_date_anchor_ref: str | None = None

    @field_validator(
        "realization_id",
        "reviewed_by",
        "review_receipt_ref",
        "required_message_anchor_ids",
        "required_source_representation_ids",
    )
    @classmethod
    def _realization_fields_required(cls, value: str | list[str]) -> str | list[str]:
        values = [value] if isinstance(value, str) else value
        if any(not item.strip() for item in values):
            raise ValueError("reviewed realization fields must not be blank")
        return value

    @field_validator("realized_at")
    @classmethod
    def _realized_at_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("exact timestamps must include an explicit timezone")
        return value

    @field_validator("required_source_available_from")
    @classmethod
    def _required_source_available_from_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)

    @model_validator(mode="after")
    def _realization_membership_is_explicit(self) -> ReviewedRealizationLink:
        if not self.required_message_anchor_ids and not self.required_source_representation_ids:
            raise ValueError("realization link requires explicit message or source representation membership")
        if (self.required_source_available_from is None) == (self.relative_date_anchor_ref is None):
            raise ValueError("realization availability requires exactly one exact clock or relative anchor ref")
        if self.relative_date_anchor_ref is not None and not self.relative_date_anchor_ref.strip():
            raise ValueError("relative_date_anchor_ref must not be blank")
        if self.required_source_available_from is not None and self.realized_at < self.required_source_available_from:
            raise ValueError("reviewed realization cannot predate required source availability")
        return self


class _ContextThread(_StrictContextContract):
    contract_version: Literal["context-thread-v1"] = "context-thread-v1"
    context_thread_id: str
    thread_version: int = Field(ge=1)
    provenance_receipt_refs: list[str] = Field(min_length=1)
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: ReviewStatus
    supersedes_context_thread_id: str | None = None
    first_occurred_at: datetime | None = None
    last_occurred_at: datetime | None = None
    source_available_from: datetime | None = None
    realizable_from: datetime | None = None
    realization_links: list[ReviewedRealizationLink] = Field(default_factory=list)
    review_case_refs: list[str] = Field(default_factory=list)
    active_thread_assertion_refs: list[str] = Field(default_factory=list)

    @field_validator("context_thread_id", "provenance_receipt_refs")
    @classmethod
    def _thread_identity_required(cls, value: str | list[str]) -> str | list[str]:
        values = [value] if isinstance(value, str) else value
        if any(not item.strip() for item in values):
            raise ValueError("thread identity and provenance fields must not be blank")
        return value

    @field_validator("first_occurred_at", "last_occurred_at", "source_available_from", "realizable_from")
    @classmethod
    def _thread_clocks_aware(cls, value: datetime | None) -> datetime | None:
        return _aware(value)

    @model_validator(mode="after")
    def _thread_clock_order(self) -> _ContextThread:
        if (self.first_occurred_at is None) != (self.last_occurred_at is None):
            raise ValueError("thread occurrence bounds must both be exact or both be absent")
        if (
            self.first_occurred_at is not None
            and self.last_occurred_at is not None
            and self.last_occurred_at < self.first_occurred_at
        ):
            raise ValueError("last_occurred_at cannot precede first_occurred_at")
        if (self.source_available_from is None) != (self.realizable_from is None):
            raise ValueError("availability and realizability exact clocks must both be present or absent")
        if (
            self.source_available_from is not None
            and self.realizable_from is not None
            and self.realizable_from < self.source_available_from
        ):
            raise ValueError("realizable_from cannot precede source availability")
        return self


class FirstPartyContextThread(_ContextThread):
    corpus: Literal["first_party"] = "first_party"
    owner_anchor: FirstPartyOwnerAnchor
    relative_date_anchor_ref: str | None = None
    availability_relative_date_anchor_ref: str | None = None
    messages: list[FirstPartyMessageAnchor] = Field(min_length=1)
    source_representations: list[FirstPartySourceRepresentation] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_first_party_thread(self) -> FirstPartyContextThread:
        _validate_thread_members(self.messages, self.source_representations, self.realization_links)
        occurred = [message.occurred_at for message in self.messages]
        if all(value is not None for value in occurred):
            exact = [value for value in occurred if value is not None]
            if self.first_occurred_at != min(exact) or self.last_occurred_at != max(exact):
                raise ValueError("thread occurrence bounds must match its messages")
            if self.relative_date_anchor_ref is not None:
                raise ValueError("exact first-party occurrence clocks cannot use a thread fallback anchor")
        else:
            if self.first_occurred_at is not None or self.last_occurred_at is not None:
                raise ValueError("an incompletely dated thread cannot claim exact occurrence bounds")
            if self.relative_date_anchor_ref is None:
                raise ValueError("incompletely dated first-party thread requires a relative-date anchor")
        if self.relative_date_anchor_ref is not None and not self.relative_date_anchor_ref.strip():
            raise ValueError("relative_date_anchor_ref must not be blank")
        required_messages = [message for message in self.messages if message.required_for_horizon]
        if not required_messages:
            raise ValueError("first-party thread requires at least one horizon-required message")
        if any(message.occurred_at is None for message in required_messages):
            if self.source_available_from is not None or self.realizable_from is not None:
                raise ValueError("relative required occurrence prevents an exact first-party thread horizon")
            if self.availability_relative_date_anchor_ref is None:
                raise ValueError("relative required occurrence requires a thread availability anchor ref")
        else:
            required_available = max(
                message.occurred_at for message in required_messages if message.occurred_at is not None
            )
            if self.source_available_from != required_available or self.realizable_from != required_available:
                raise ValueError("first-party horizon must equal greatest required message availability")
            if self.availability_relative_date_anchor_ref is not None:
                raise ValueError("exact first-party horizon cannot use an availability fallback anchor")
        if (
            self.availability_relative_date_anchor_ref is not None
            and not self.availability_relative_date_anchor_ref.strip()
        ):
            raise ValueError("availability_relative_date_anchor_ref must not be blank")
        _validate_first_party_realization_links(self.realization_links, self.messages, self.source_representations)
        return self


class ThirdPartyContextThread(_ContextThread):
    corpus: Literal["acquired_third_party"] = "acquired_third_party"
    acquisition_anchor: ThirdPartyAcquisitionAnchor
    approval_anchor: ThirdPartyApprovalAnchor
    occurrence_relative_date_anchor_ref: str | None = None
    availability_relative_date_anchor_ref: str | None = None
    messages: list[ThirdPartyMessageAnchor] = Field(min_length=1)
    source_representations: list[ThirdPartySourceRepresentation] = Field(min_length=1)

    @model_validator(mode="after")
    def _validate_third_party_thread(self) -> ThirdPartyContextThread:
        _validate_thread_members(self.messages, self.source_representations, self.realization_links)
        representations_by_id = {
            representation.representation_id: representation for representation in self.source_representations
        }
        summarized_representation = representations_by_id.get(self.acquisition_anchor.representation_id)
        if summarized_representation is None:
            raise ValueError("thread acquisition anchor must name an included representation")
        if (
            summarized_representation.acquired_at != self.acquisition_anchor.acquired_at
            or summarized_representation.acquisition_receipt_ref != self.acquisition_anchor.acquisition_receipt_ref
        ):
            raise ValueError("thread acquisition anchor must match its representation acquisition lineage")
        occurred = [message.occurred_at for message in self.messages]
        if all(value is not None for value in occurred):
            exact = [value for value in occurred if value is not None]
            if self.first_occurred_at != min(exact) or self.last_occurred_at != max(exact):
                raise ValueError("thread occurrence bounds must match its messages")
        elif self.first_occurred_at is not None or self.last_occurred_at is not None:
            raise ValueError("an incompletely dated thread cannot claim exact occurrence bounds")
        elif self.occurrence_relative_date_anchor_ref is None:
            raise ValueError("incompletely dated third-party thread requires a relative-date anchor ref")
        if (
            self.occurrence_relative_date_anchor_ref is not None
            and not self.occurrence_relative_date_anchor_ref.strip()
        ):
            raise ValueError("occurrence_relative_date_anchor_ref must not be blank")
        required_representations = [
            representation for representation in self.source_representations if representation.required_for_horizon
        ]
        if not required_representations:
            raise ValueError("third-party thread requires at least one horizon-required source representation")
        exact_representation_acquisitions = [
            representation.acquired_at
            for representation in required_representations
            if representation.acquired_at is not None
        ]
        all_exact_acquisitions = [
            representation.acquired_at
            for representation in self.source_representations
            if representation.acquired_at is not None
        ]
        if len(all_exact_acquisitions) == len(self.source_representations) and (
            self.acquisition_anchor.acquired_at != min(all_exact_acquisitions)
        ):
            raise ValueError("thread acquisition anchor must equal first per-representation acquisition")
        if any(representation.acquired_at is None for representation in required_representations):
            if self.source_available_from is not None or self.realizable_from is not None:
                raise ValueError("relative required acquisition prevents an exact third-party thread horizon")
            if self.availability_relative_date_anchor_ref is None:
                raise ValueError("relative required acquisition requires a thread availability anchor ref")
        else:
            required_available = max(exact_representation_acquisitions)
            if self.source_available_from != required_available or self.realizable_from != required_available:
                raise ValueError("third-party horizon must equal greatest required custody-backed availability")
            if self.availability_relative_date_anchor_ref is not None:
                raise ValueError("exact third-party horizon cannot use an availability fallback anchor")
            if self.approval_anchor.approved_at < required_available:
                raise ValueError("third-party approval cannot predate full required-source availability")
        if (
            self.availability_relative_date_anchor_ref is not None
            and not self.availability_relative_date_anchor_ref.strip()
        ):
            raise ValueError("availability_relative_date_anchor_ref must not be blank")
        if self.approval_anchor.approved_at < self.acquisition_anchor.acquired_at:
            raise ValueError("third-party approval cannot predate acquisition")
        _validate_third_party_realization_links(self.realization_links, self.messages, self.source_representations)
        return self


def _validate_thread_members(
    messages: Sequence[_MessageAnchor],
    representations: Sequence[_SourceRepresentation],
    realization_links: Sequence[ReviewedRealizationLink],
) -> None:
    representation_ids = [item.representation_id for item in representations]
    if len(representation_ids) != len(set(representation_ids)):
        raise ValueError("representation ids must be unique; identical source hashes remain allowed")
    message_ids = [item.message_anchor_id for item in messages]
    if len(message_ids) != len(set(message_ids)):
        raise ValueError("message anchor ids must be unique")
    thread_orders = [item.thread_order for item in messages]
    if len(thread_orders) != len(set(thread_orders)):
        raise ValueError("thread order must be unique and is distinct from source order")
    known_representations = set(representation_ids)
    for message in messages:
        if not set(message.source_representation_ids) <= known_representations:
            raise ValueError("message anchor references an unknown source representation")
    known_messages = set(message_ids)
    for link in realization_links:
        if not set(link.required_message_anchor_ids) <= known_messages:
            raise ValueError("realization link references an unknown message anchor")
        if not set(link.required_source_representation_ids) <= known_representations:
            raise ValueError("realization link references an unknown source representation")


def _validate_first_party_realization_links(
    links: Sequence[ReviewedRealizationLink],
    messages: Sequence[FirstPartyMessageAnchor],
    representations: Sequence[FirstPartySourceRepresentation],
) -> None:
    messages_by_id = {message.message_anchor_id: message for message in messages}
    representation_ids = {representation.representation_id for representation in representations}
    for link in links:
        if not link.required_message_anchor_ids:
            raise ValueError("first-party realization requires one or more required messages")
        if not set(link.required_source_representation_ids) <= representation_ids:
            raise ValueError("first-party realization references an unknown source representation")
        required = [messages_by_id[message_id] for message_id in link.required_message_anchor_ids]
        if any(message.occurred_at is None for message in required):
            if link.required_source_available_from is not None or link.relative_date_anchor_ref is None:
                raise ValueError("relative first-party realization membership requires an anchor ref")
        else:
            available = max(message.occurred_at for message in required if message.occurred_at is not None)
            if link.required_source_available_from != available or link.relative_date_anchor_ref is not None:
                raise ValueError("first-party realization availability must equal greatest required message clock")


def _validate_third_party_realization_links(
    links: Sequence[ReviewedRealizationLink],
    messages: Sequence[ThirdPartyMessageAnchor],
    representations: Sequence[ThirdPartySourceRepresentation],
) -> None:
    messages_by_id = {message.message_anchor_id: message for message in messages}
    representations_by_id = {representation.representation_id: representation for representation in representations}
    for link in links:
        if not link.required_source_representation_ids:
            raise ValueError("third-party realization requires one or more required source representations")
        covered_representation_ids = set(link.required_source_representation_ids)
        for message_id in link.required_message_anchor_ids:
            if not set(messages_by_id[message_id].source_representation_ids) <= covered_representation_ids:
                raise ValueError("third-party realization messages require their backing source representations")
        required = [
            representations_by_id[representation_id] for representation_id in link.required_source_representation_ids
        ]
        if any(representation.acquired_at is None for representation in required):
            if link.required_source_available_from is not None or link.relative_date_anchor_ref is None:
                raise ValueError("relative third-party realization membership requires an anchor ref")
        else:
            available = max(
                representation.acquired_at for representation in required if representation.acquired_at is not None
            )
            if link.required_source_available_from != available or link.relative_date_anchor_ref is not None:
                raise ValueError("third-party realization availability must equal greatest required acquisition")
