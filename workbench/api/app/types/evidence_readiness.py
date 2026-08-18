"""Court-readiness projections for sanitized evidence detail responses.

Byline: Codex · GPT-5 · 2026-08-18 (extracted from evidence_detail.py)
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

CourtReadinessBlocker = Literal[
    "CONTENT_REVIEW_REQUIRED",
    "PROVENANCE_INVALID",
    "CUSTODY_NOT_VERIFIED",
    "CUSTODY_CHAIN_INVALID",
    "AUTHENTICATION_REQUIRED",
    "CONFIDENCE_NOT_EXPORTABLE",
    "HYPOTHESIS_NOT_EXPORTABLE",
    "REDACTION_REQUIRED",
    "SENSITIVITY_SEALED",
    "NOT_RELEASED",
]


class ContentReviewReadinessGate(BaseModel):
    approved: bool
    decision_id: UUID | None = None


class ProvenanceReadinessGate(BaseModel):
    exact: bool


class CustodyReadinessGate(BaseModel):
    h1_valid: bool
    event_chain_valid: bool
    verified_event_present: bool
    source_status: str = Field(min_length=1, max_length=100)
    source_reviewed: bool
    verified_by: str | None = Field(default=None, max_length=500)
    verified_at: datetime | None = None


class AuthenticationReadinessGate(BaseModel):
    authenticated: bool
    method: str | None = Field(default=None, max_length=200)


class ConfidenceReadinessGate(BaseModel):
    value: float | None = Field(default=None, ge=0, le=1)
    tier: str = Field(min_length=1, max_length=100)
    export_band: bool


class AssertionReadinessGate(BaseModel):
    not_hypothesis: bool


class RedactionReadinessGate(BaseModel):
    privacy_sensitivity: str = Field(min_length=1, max_length=100)
    source_privacy_sensitivity: str = Field(min_length=1, max_length=100)
    status: str = Field(min_length=1, max_length=100)
    clear_for_export: bool


class SensitivityReadinessGate(BaseModel):
    evidence_tier: str = Field(min_length=1, max_length=100)
    source_tier: str = Field(min_length=1, max_length=100)
    sealed: bool


class CourtExportReadinessGate(BaseModel):
    view_member: bool


class CourtReadinessGates(BaseModel):
    content_review: ContentReviewReadinessGate
    provenance: ProvenanceReadinessGate
    custody: CustodyReadinessGate
    authentication: AuthenticationReadinessGate
    confidence: ConfidenceReadinessGate
    assertion: AssertionReadinessGate
    redaction: RedactionReadinessGate
    sensitivity: SensitivityReadinessGate
    court_export: CourtExportReadinessGate


class CourtReadiness(BaseModel):
    """Matter-scoped database gate projection, not a legal conclusion."""

    evidence_item_id: UUID
    matter_id: UUID
    readiness_passed: bool
    blockers: list[CourtReadinessBlocker]
    gates: CourtReadinessGates

    @model_validator(mode="after")
    def require_honest_readiness(self) -> CourtReadiness:
        expected: set[CourtReadinessBlocker] = set()
        if not self.gates.content_review.approved or self.gates.content_review.decision_id is None:
            expected.add("CONTENT_REVIEW_REQUIRED")
        if not self.gates.provenance.exact:
            expected.add("PROVENANCE_INVALID")
        custody = self.gates.custody
        if not (
            custody.verified_event_present
            and custody.source_status.lower() == "verified"
            and custody.source_reviewed
            and custody.verified_by is not None
            and custody.verified_at is not None
        ):
            expected.add("CUSTODY_NOT_VERIFIED")
        if not custody.h1_valid or not custody.event_chain_valid:
            expected.add("CUSTODY_CHAIN_INVALID")
        if not self.gates.authentication.authenticated or self.gates.authentication.method is None:
            expected.add("AUTHENTICATION_REQUIRED")
        if not self.gates.confidence.export_band:
            expected.add("CONFIDENCE_NOT_EXPORTABLE")
        if not self.gates.assertion.not_hypothesis:
            expected.add("HYPOTHESIS_NOT_EXPORTABLE")
        if not self.gates.redaction.clear_for_export:
            expected.add("REDACTION_REQUIRED")
        if self.gates.sensitivity.sealed:
            expected.add("SENSITIVITY_SEALED")
        if not self.gates.court_export.view_member:
            expected.add("NOT_RELEASED")
        if len(self.blockers) != len(set(self.blockers)) or set(self.blockers) != expected:
            raise ValueError("court-export blockers do not match their database gates")
        if self.readiness_passed != (not expected):
            raise ValueError("supplemental readiness result does not match its database gates")
        return self
