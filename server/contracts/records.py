"""contracts/records.py — the canonical record schemas.

Two record families:

1. **NormalizedRecord** — the ORIGINAL evidence-type contract (calls, events,
   media). Carries bitemporal substrate: occurred_at / knowledge_time /
   disclosure_tier. Parsers for non-chat formats still emit these.

2. **ChatMessage** / **ChatConversation** — horizon-neutral AI-chat landing
   records. Chunking, classification, and review are separate downstream
   contracts because one chunk may route to several knowledge lanes.

Home (ADR-0035, Option A): import-light, no heavy deps, facade-safe.
"""

# Byline amendment: Codex · GPT-5 · 2026-08-18 (source-party and chunk lineage)

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
import json
from typing import Any, Iterable, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Evidence-type records (calls, events, media) — kept for non-chat parsers
# ---------------------------------------------------------------------------


class DisclosureTier(str, Enum):
    contemporaneous = "contemporaneous"  # knowable at the moment it happened
    hindsight = "hindsight"  # assembled later by connecting records
    discovered = "discovered"  # hidden fact surfaced after the fact


class RecordType(str, Enum):
    message = "message"
    call = "call"
    event = "event"
    media = "media"


class MessageCorpus(str, Enum):
    """Mutually exclusive communication projections for evidence messages."""

    first_party = "first_party"
    acquired_third_party = "acquired_third_party"


class MessageParticipant(BaseModel):
    """One actual sender/recipient coordinate, without case-owner inference."""

    identity: str
    role: str

    @field_validator("identity")
    @classmethod
    def _identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("participant identity must not be blank")
        return value

    @field_validator("role")
    @classmethod
    def _known_role(cls, value: str) -> str:
        if value not in {"from", "to", "cc", "bcc", "group"}:
            raise ValueError("participant role must be from, to, cc, bcc, or group")
        return value


class NormalizedRecord(BaseModel):
    """Canonical record for evidence-type data. Parsers for non-chat formats
    emit these; store.py persists them to working.normalized_record."""

    record_type: RecordType = RecordType.message
    source: str  # parser/source key e.g. 'chatgpt-export'
    conversation_id: str | None = None
    role: str | None = None  # sender / author role
    participants: list[str] = Field(default_factory=list)
    sender: str | None = None
    recipients: list[MessageParticipant] = Field(default_factory=list)
    message_corpus: MessageCorpus | None = None
    content: str = ""
    occurred_at: datetime | None = None  # valid time
    knowledge_time: datetime | None = None  # filled at normalize time if unset
    disclosure_tier: DisclosureTier = DisclosureTier.contemporaneous
    attrs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("occurred_at", "knowledge_time")
    @classmethod
    def _tz_aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class NormalizedRecordChunk(BaseModel):
    """Rebuildable child text for retrieval; never an authored spine record."""

    source_record_index: int = Field(ge=0)
    chunk_index: int = Field(ge=0)
    chunker_id: str
    content: str
    content_sha256: str
    source_content_sha256: str
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    token_count: int | None = Field(default=None, ge=0)
    attrs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("chunker_id", "content_sha256", "source_content_sha256")
    @classmethod
    def _chunk_identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("chunk identity fields must not be blank")
        return value


class _StrictChunkContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class SourceByteRange(_StrictChunkContract):
    """One half-open byte range in an immutable source version.

    Character offsets are deliberately absent: byte coordinates can be checked
    against the stored source bytes without depending on Unicode normalization.
    """

    coordinate_system: Literal["utf8_bytes"] = "utf8_bytes"
    offset: int = Field(ge=0)
    length: int = Field(gt=0)

    @property
    def end_offset(self) -> int:
        """Exclusive end of the range."""
        return self.offset + self.length


class ContentChunk(_StrictChunkContract):
    """Format-neutral derived text with byte-verifiable source lineage."""

    contract_version: Literal["content-chunk-v1"] = "content-chunk-v1"
    chunk_id: str
    chunk_generation_id: str
    source_version_ref: str
    chunk_index: int = Field(ge=0)
    derivation_mode: Literal["verbatim_span", "composed", "unverified_derived"]
    content_bytes: bytes
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_byte_length: int | None = Field(default=None, ge=0)
    source_ranges: list[SourceByteRange] = Field(default_factory=list)
    chunker_id: str
    chunk_policy_version: str
    chunk_schema_version: str
    implementation_version: str
    token_count: int | None = Field(default=None, ge=0)
    attrs: dict[str, Any] = Field(default_factory=dict)

    @field_validator(
        "chunk_id",
        "chunk_generation_id",
        "source_version_ref",
        "chunker_id",
        "chunk_policy_version",
        "chunk_schema_version",
        "implementation_version",
    )
    @classmethod
    def _content_chunk_identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("content chunk identity and version fields must not be blank")
        return value

    @model_validator(mode="after")
    def _verify_content_and_locator_contract(self) -> ContentChunk:
        if sha256(self.content_bytes).hexdigest() != self.content_sha256:
            raise ValueError("content_sha256 must match content_bytes exactly")
        if self.derivation_mode == "verbatim_span" and len(self.source_ranges) != 1:
            raise ValueError("verbatim_span requires exactly one source byte range")
        if self.derivation_mode == "verbatim_span" and self.source_ranges[0].length != len(self.content_bytes):
            raise ValueError("verbatim source byte-range length must equal UTF-8 content byte length")
        if self.derivation_mode == "composed" and not self.source_ranges:
            raise ValueError("composed chunks require one or more ordered source byte ranges")
        if self.derivation_mode == "composed":
            for previous, current in zip(self.source_ranges, self.source_ranges[1:], strict=False):
                if current.offset < previous.end_offset:
                    raise ValueError("composed source ranges must be ordered and nonoverlapping")
        if self.derivation_mode == "unverified_derived" and self.source_ranges:
            raise ValueError("unverified_derived chunks cannot claim verified source byte ranges")
        if self.source_byte_length is not None and any(
            source_range.end_offset > self.source_byte_length for source_range in self.source_ranges
        ):
            raise ValueError("source byte range exceeds immutable source byte length")
        return self


class ChunkGeneration(_StrictChunkContract):
    """Immutable manifest for one version-pinned chunk derivation run."""

    contract_version: Literal["chunk-generation-v1"] = "chunk-generation-v1"
    chunk_generation_id: str
    source_version_ref: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_byte_length: int = Field(ge=0)
    chunker_id: str
    chunk_policy_version: str
    chunk_schema_version: str
    implementation_version: str
    chunks: list[ContentChunk] = Field(default_factory=list)
    chunk_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    locator_set_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    receipt_ref: str
    activity_ref: str
    created_at: datetime

    @field_validator(
        "chunk_generation_id",
        "source_version_ref",
        "chunker_id",
        "chunk_policy_version",
        "chunk_schema_version",
        "implementation_version",
        "receipt_ref",
        "activity_ref",
    )
    @classmethod
    def _generation_identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("chunk generation identity, version, and receipt fields must not be blank")
        return value

    @model_validator(mode="after")
    def _manifest_matches_children(self) -> ChunkGeneration:
        indexes = [chunk.chunk_index for chunk in self.chunks]
        ids = [chunk.chunk_id for chunk in self.chunks]
        if len(indexes) != len(set(indexes)) or len(ids) != len(set(ids)):
            raise ValueError("chunk ids and indexes must be unique within a generation")
        for chunk in self.chunks:
            if chunk.chunk_generation_id != self.chunk_generation_id:
                raise ValueError("chunk generation id does not match its manifest")
            if chunk.source_version_ref != self.source_version_ref:
                raise ValueError("chunk source version does not match its manifest")
            if chunk.source_sha256 != self.source_sha256:
                raise ValueError("chunk source hash does not match its manifest")
            if chunk.source_byte_length is not None and chunk.source_byte_length != self.source_byte_length:
                raise ValueError("chunk source byte length does not match its manifest")
            if any(source_range.end_offset > self.source_byte_length for source_range in chunk.source_ranges):
                raise ValueError("generation chunk locator exceeds immutable source byte length")
            pins = (
                (chunk.chunker_id, self.chunker_id),
                (chunk.chunk_policy_version, self.chunk_policy_version),
                (chunk.chunk_schema_version, self.chunk_schema_version),
                (chunk.implementation_version, self.implementation_version),
            )
            if any(child != manifest for child, manifest in pins):
                raise ValueError("chunk implementation pins do not match its manifest")
        locator_payload = [
            {
                "chunk_id": chunk.chunk_id,
                "chunk_index": chunk.chunk_index,
                "ranges": [source_range.model_dump(mode="json") for source_range in chunk.source_ranges],
            }
            for chunk in sorted(self.chunks, key=lambda item: item.chunk_index)
        ]
        calculated_locator_hash = sha256(
            json.dumps(locator_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        manifest_payload = {
            "chunk_generation_id": self.chunk_generation_id,
            "source_version_ref": self.source_version_ref,
            "source_sha256": self.source_sha256,
            "source_byte_length": self.source_byte_length,
            "chunker_id": self.chunker_id,
            "chunk_policy_version": self.chunk_policy_version,
            "chunk_schema_version": self.chunk_schema_version,
            "implementation_version": self.implementation_version,
            "locator_set_sha256": calculated_locator_hash,
            "chunks": [
                {
                    "chunk_id": chunk.chunk_id,
                    "chunk_index": chunk.chunk_index,
                    "content_sha256": chunk.content_sha256,
                    "derivation_mode": chunk.derivation_mode,
                }
                for chunk in sorted(self.chunks, key=lambda item: item.chunk_index)
            ],
        }
        calculated_manifest_hash = sha256(
            json.dumps(manifest_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        if self.locator_set_sha256 not in {None, calculated_locator_hash}:
            raise ValueError("locator_set_sha256 must bind the actual generation chunk locator set")
        if self.chunk_manifest_sha256 not in {None, calculated_manifest_hash}:
            raise ValueError("chunk_manifest_sha256 must bind the immutable generation manifest")
        object.__setattr__(self, "locator_set_sha256", calculated_locator_hash)
        object.__setattr__(self, "chunk_manifest_sha256", calculated_manifest_hash)
        return self


class ChunkCompletenessResult(_StrictChunkContract):
    """Fail-closed proof that a generation covers and reassembles its source."""

    contract_version: Literal["chunk-completeness-v1"] = "chunk-completeness-v1"
    status: Literal["pass", "fail", "not_run"]
    chunk_generation_id: str
    source_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    reassembled_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    source_byte_length: int | None = Field(default=None, ge=0)
    covered_byte_length: int | None = Field(default=None, ge=0)
    covered_ranges: list[SourceByteRange] = Field(default_factory=list)
    exact_range_coverage: bool | None = None
    chunk_count: int | None = Field(default=None, ge=0)
    chunk_manifest_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    locator_set_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    receipt_ref: str | None = None
    activity_ref: str | None = None
    detail: str | None = None

    @field_validator("chunk_generation_id")
    @classmethod
    def _completeness_generation_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("chunk_generation_id must not be blank")
        return value

    @model_validator(mode="after")
    def _validate_completeness_proof(self) -> ChunkCompletenessResult:
        proof_fields = (
            self.source_sha256,
            self.reassembled_sha256,
            self.source_byte_length,
            self.covered_byte_length,
            self.exact_range_coverage,
            self.chunk_count,
            self.chunk_manifest_sha256,
            self.locator_set_sha256,
            self.receipt_ref,
            self.activity_ref,
        )
        if self.status == "not_run":
            if any(value is not None for value in proof_fields) or self.covered_ranges:
                raise ValueError("not_run cannot carry an unperformed completeness proof")
            return self
        if any(value is None for value in proof_fields):
            raise ValueError("pass/fail completeness results require hashes, lengths, coverage, and receipts")
        receipt_ref = self.receipt_ref
        activity_ref = self.activity_ref
        if receipt_ref is None or activity_ref is None:
            raise ValueError("pass/fail completeness results require receipt and activity references")
        if not receipt_ref.strip() or not activity_ref.strip():
            raise ValueError("completeness receipt and activity references must not be blank")
        sorted_ranges = sorted(self.covered_ranges, key=lambda item: item.offset)
        ranges_are_exact = bool(sorted_ranges) or self.source_byte_length == 0
        cursor = 0
        for item in sorted_ranges:
            if item.offset != cursor:
                ranges_are_exact = False
                break
            cursor = item.end_offset
        ranges_are_exact = ranges_are_exact and cursor == self.source_byte_length
        computed_covered = sum(item.length for item in sorted_ranges)
        if computed_covered != self.covered_byte_length:
            raise ValueError("covered_byte_length must equal the declared byte ranges")
        if ranges_are_exact != self.exact_range_coverage:
            raise ValueError("exact_range_coverage does not match the declared ranges")
        proof_passes = (
            self.source_sha256 == self.reassembled_sha256
            and self.source_byte_length == self.covered_byte_length
            and self.exact_range_coverage
        )
        if (self.status == "pass") != proof_passes:
            raise ValueError("completeness status does not match the supplied proof")
        return self


class ChunkGenerationCompletenessBinding(_StrictChunkContract):
    """Binds a completeness proof to the actual immutable generation manifest."""

    generation: ChunkGeneration
    completeness: ChunkCompletenessResult

    @model_validator(mode="after")
    def _proof_matches_generation(self) -> ChunkGenerationCompletenessBinding:
        proof = self.completeness
        generation = self.generation
        if proof.status == "not_run":
            raise ValueError("generation completeness binding cannot use not_run")
        expected_ranges = [
            source_range
            for chunk in sorted(generation.chunks, key=lambda item: item.chunk_index)
            for source_range in chunk.source_ranges
        ]
        comparisons = (
            (proof.chunk_generation_id, generation.chunk_generation_id),
            (proof.source_sha256, generation.source_sha256),
            (proof.source_byte_length, generation.source_byte_length),
            (proof.chunk_count, len(generation.chunks)),
            (proof.chunk_manifest_sha256, generation.chunk_manifest_sha256),
            (proof.locator_set_sha256, generation.locator_set_sha256),
            (proof.covered_ranges, expected_ranges),
        )
        if any(actual != expected for actual, expected in comparisons):
            raise ValueError("completeness proof must bind the actual generation manifest and locator set")
        return self


class TimelineEventCandidateProvenance(_StrictChunkContract):
    """Exact source lineage for an independently extracted event candidate."""

    contract_version: Literal["timeline-event-source-locator-v1"] = "timeline-event-source-locator-v1"
    derivation_pass: Literal["timeline_event_extraction"] = "timeline_event_extraction"
    event_candidate_ref: str
    extraction_generation_id: str
    source_version_ref: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_ranges: list[SourceByteRange] = Field(min_length=1)
    extractor_id: str
    extraction_policy_version: str
    implementation_version: str
    receipt_ref: str
    activity_ref: str
    review_case_refs: list[str] = Field(default_factory=list)
    active_event_candidate_assertion_refs: list[str] = Field(default_factory=list)

    @field_validator(
        "event_candidate_ref",
        "extraction_generation_id",
        "source_version_ref",
        "extractor_id",
        "extraction_policy_version",
        "implementation_version",
        "receipt_ref",
        "activity_ref",
    )
    @classmethod
    def _event_provenance_identity_required(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("timeline extraction provenance fields must not be blank")
        return value


class SourceDerivationManifest(_StrictChunkContract):
    """Sibling derivation generations authorized from one source version.

    This records coordination only. An extraction generation never replaces,
    shortens, or satisfies the independent whole-source chunking proof.
    """

    contract_version: Literal["source-derivations-v1"] = "source-derivations-v1"
    source_version_ref: str
    source_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    chunk_generation_ids: list[str] = Field(default_factory=list)
    timeline_extraction_generation_ids: list[str] = Field(default_factory=list)

    @field_validator("source_version_ref", "chunk_generation_ids", "timeline_extraction_generation_ids")
    @classmethod
    def _derivation_manifest_fields_required(cls, value: str | list[str]) -> str | list[str]:
        values = [value] if isinstance(value, str) else value
        if any(not item.strip() for item in values):
            raise ValueError("source derivation references must not be blank")
        if not isinstance(value, str) and len(value) != len(set(value)):
            raise ValueError("derivation generation references must be unique")
        return value

    @model_validator(mode="after")
    def _sibling_generation_namespaces_are_distinct(self) -> SourceDerivationManifest:
        if set(self.chunk_generation_ids) & set(self.timeline_extraction_generation_ids):
            raise ValueError("chunk and timeline extraction generations are independent siblings")
        return self


def finalize(records: Iterable[NormalizedRecord]) -> list[NormalizedRecord]:
    """Apply normalize-time defaults: knowledge_time = now for anything unset.

    NOTE 2026-08-14 (ADR-0045 §A, SUPERSEDED 0008:247): ``knowledge_time`` is
    AUDIT ONLY — it records the row-write time and is never a horizon input.
    It is stamped here for backward compatibility only. The horizon clock is
    ``working.visible_from(record_id)`` (COALESCE of the earliest APPROVED
    realization_event.realized_at with occurred_at); see
    ``server/evidence/store.horizon_axes`` for the Weaviate projection. No
    behavior change in this function — it still stamps the audit field.
    """
    now = datetime.now(timezone.utc)
    out: list[NormalizedRecord] = []
    for rec in records:
        if rec.knowledge_time is None:
            rec = rec.model_copy(update={"knowledge_time": now})
        out.append(rec)
    return out


# ---------------------------------------------------------------------------
# AI Chat records — the RIGHT schema for chat data
# ---------------------------------------------------------------------------


class ChatLane(str, Enum):
    """The five global knowledge lanes.

    AI-chat classifiers may emit only the first four. ``evidence`` is reserved
    for custody-approved source material and cannot be inferred from chat text.
    """

    platform = "platform"
    legal = "legal"
    personal_history = "personal_history"
    context = "context"
    evidence = "evidence"


class ChatMessage(BaseModel):
    """One message in an AI chat. Maps 1:1 to working.chat_message columns.

    Parsers for chat formats (ChatGPT, Gemini, Claude, etc.) emit these.
    Unlike NormalizedRecord, this carries:
      - message_index: ordering within conversation (timestamps often missing)
      - thinking: chain-of-thought (o1, Claude thinking blocks)
      - attachments: files, URLs, links the user referenced
    """

    source: str  # parser key: chatgpt-official, gemini-md, etc.
    conversation_id: str  # external ID from the export
    message_index: int  # 0-based ordering within conversation
    role: str  # user | assistant | system | tool
    content: str = ""
    timestamp: datetime | None = None  # nullable — many .md exports have none
    thinking: str | None = None  # chain-of-thought
    attachments: list[str] = Field(default_factory=list)  # files, URLs, links
    attrs: dict[str, Any] = Field(default_factory=dict)

    @field_validator("timestamp")
    @classmethod
    def _tz_aware(cls, v: datetime | None) -> datetime | None:
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=timezone.utc)
        return v


class ChatConversation(BaseModel):
    """Conversation-level metadata. Maps 1:1 to working.chat_conversation columns.

    One ChatConversation groups many ChatMessages. Carries the title, source,
    file_path, and denormalized message_count / first_message_at / last_message_at.
    """

    source: str  # parser key
    conversation_id: str  # external ID from the export
    title: str | None = None
    created_at: datetime | None = None
    file_path: str | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)


def finalize_chat(messages: list[ChatMessage]) -> list[ChatMessage]:
    """Return horizon-neutral chat messages unchanged."""
    return messages


class ChatChunk(BaseModel):
    """One canonical, message-boundary-preserving chunk stored once in PG."""

    conversation_id: str
    chunk_index: int
    content: str
    content_hash: str
    message_indexes: list[int]
    chunker_id: str
    token_count: int | None = None
    char_start: int | None = None
    char_end: int | None = None
    attrs: dict[str, Any] = Field(default_factory=dict)


class LaneClassification(BaseModel):
    """One lane assignment; several assignments may describe one chunk."""

    lane: ChatLane
    confidence: float = Field(ge=0.0, le=1.0)
    review_status: str
    rationale: str | None = None

    @field_validator("lane")
    @classmethod
    def _chat_never_routes_to_evidence(cls, value: ChatLane) -> ChatLane:
        if value is ChatLane.evidence:
            raise ValueError("AI chat cannot be routed to the evidence lane")
        return value
