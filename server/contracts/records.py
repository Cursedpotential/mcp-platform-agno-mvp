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
from typing import Any, Iterable

from pydantic import BaseModel, Field, field_validator


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
