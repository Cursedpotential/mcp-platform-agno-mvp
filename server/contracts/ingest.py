"""Framework-neutral contracts for canonical file ingestion.

These models deliberately import no workflow, agent, vector, graph, or database
framework. HTTP and in-process callers share the same request and receipt shape.

Byline: Codex · GPT-5 · 2026-08-16
"""

# Byline amendment: Codex · GPT-5 · 2026-08-18 (typed acquisition/source class)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (human authority category + named asserter)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (pending native projection receipt state)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (authenticated first-party ownership assertion)

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from server.contracts.records import ChunkCompletenessResult


class IngestLane(str, Enum):
    platform = "platform"
    legal = "legal"
    personal_history = "personal_history"
    context = "context"
    evidence = "evidence"


class AcquisitionAssertion(BaseModel):
    """Human-asserted acquisition event; distinct from file ingest time."""

    acquired_at: datetime
    method: Literal[
        "own_device",
        "household_device",
        "voluntary_third_party",
        "legal_process",
        "public_source",
        "unknown",
    ] = "unknown"
    authority: Literal[
        "device_owner",
        "parent_guardian",
        "account_holder",
        "consent_given",
        "court_order",
        "unclear",
    ] = "unclear"
    source_device: str | None = None
    device_custodian: str | None = None
    notes: str | None = None
    asserted_by_category: Literal["human"] = "human"
    asserted_by: str = "owner"

    @field_validator("asserted_by")
    @classmethod
    def _asserter_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("asserted_by identity must not be blank")
        return value

    @field_validator("acquired_at")
    @classmethod
    def _acquisition_clock_must_be_aware(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("acquired_at requires an explicit timezone")
        return value


class IngestRequest(BaseModel):
    """One staged file and the routing context required to ingest it."""

    staged_path: str
    source_identity: dict[str, Any] = Field(default_factory=dict)
    message_corpus: Literal["first_party", "acquired_third_party"] | None = None
    source_principal: str | None = None
    caller_owns_conversation: bool = False
    acquisition: AcquisitionAssertion | None = None
    coverage_hint: str | None = None
    lane: Literal[IngestLane.context] = IngestLane.context
    classification_target: Literal["context"] = "context"
    matter_id: str = "primary"
    engine: Literal["auto", "go", "python"] = "auto"
    allow_fallback: bool = False
    custody_tier: Literal["full", "light"] = "light"

    @field_validator("staged_path", "matter_id")
    @classmethod
    def _required_text(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be blank")
        return value

    @field_validator("source_principal")
    @classmethod
    def _optional_nonblank(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("source_principal must not be blank")
        return value

    def model_post_init(self, __context: Any) -> None:
        if self.message_corpus == "first_party" and not self.caller_owns_conversation:
            raise ValueError(
                "first_party ingestion requires an explicit authenticated caller_owns_conversation assertion"
            )
        if self.message_corpus == "first_party" and self.source_principal is None:
            raise ValueError("first_party ingestion requires the caller's source_principal identity")
        if self.message_corpus == "acquired_third_party":
            if self.acquisition is None:
                raise ValueError("acquired_third_party ingestion requires an acquisition assertion")
            if self.source_principal is None:
                raise ValueError("acquired_third_party ingestion requires the source account/device principal")


class IngestRejection(BaseModel):
    code: str
    detail: str


class ProjectionResult(BaseModel):
    sink: str
    status: Literal["completed", "pending", "skipped", "failed"]
    detail: str | None = None


class IngestReceipt(BaseModel):
    """Durable result returned by both HTTP and in-process ingestion."""

    receipt_id: str
    status: Literal["completed", "failed"]
    lane: IngestLane
    matter_id: str
    source_name: str
    source_path: str
    source_sha256: str | None = None
    artifact_id: str | None = None
    duplicate: bool = False
    parser_id: str | None = None
    parser_version: str | None = None
    parser_engine: Literal["go", "python", "none"] = "none"
    chunker_id: str
    chunk_generation_id: str | None = None
    chunk_schema_id: str | None = None
    chunk_schema_version: str | None = None
    locator_contract_version: str | None = None
    chunk_completeness_status: Literal["pass", "fail", "not_run"] = "not_run"
    chunk_completeness_result: ChunkCompletenessResult | None = None
    chunk_completeness_receipt_id: str | None = None
    chunk_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    chunk_locator_set_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    record_count: int = 0
    chunk_count: int = 0
    rejections: list[IngestRejection] = Field(default_factory=list)
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    projections: list[ProjectionResult] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime

    @model_validator(mode="after")
    def _completeness_fields_agree(self) -> IngestReceipt:
        has_chunk_output = self.chunk_count > 0 or self.chunk_generation_id is not None
        if self.status == "completed" and not self.duplicate and has_chunk_output:
            if self.chunk_count <= 0 or self.chunk_generation_id is None:
                raise ValueError("completed chunked ingest requires both generation id and positive chunk count")
            if self.chunk_completeness_status != "pass":
                raise ValueError("completed non-duplicate chunked ingest requires passing completeness proof")
        if self.chunk_completeness_status == "not_run":
            if (
                self.chunk_completeness_result is not None
                or self.chunk_completeness_receipt_id is not None
                or self.chunk_manifest_sha256 is not None
                or self.chunk_locator_set_sha256 is not None
            ):
                raise ValueError("not_run receipt cannot claim a chunk completeness result")
            return self
        if self.chunk_completeness_result is None or self.chunk_completeness_receipt_id is None:
            raise ValueError("pass/fail receipt requires completeness result and receipt id")
        if self.chunk_completeness_result.status != self.chunk_completeness_status:
            raise ValueError("receipt completeness status must match its typed result")
        if self.chunk_generation_id != self.chunk_completeness_result.chunk_generation_id:
            raise ValueError("receipt and completeness result must reference the same chunk generation")
        if self.chunk_completeness_receipt_id != self.chunk_completeness_result.receipt_ref:
            raise ValueError("receipt completeness id must match the typed result receipt reference")
        if self.source_sha256 != self.chunk_completeness_result.source_sha256:
            raise ValueError("receipt source fingerprint must match completeness source hash")
        if self.chunk_count != self.chunk_completeness_result.chunk_count:
            raise ValueError("receipt chunk count must match completeness proof")
        if self.chunk_manifest_sha256 != self.chunk_completeness_result.chunk_manifest_sha256:
            raise ValueError("receipt chunk manifest hash must match completeness proof")
        if self.chunk_locator_set_sha256 != self.chunk_completeness_result.locator_set_sha256:
            raise ValueError("receipt locator-set hash must match completeness proof")
        return self
