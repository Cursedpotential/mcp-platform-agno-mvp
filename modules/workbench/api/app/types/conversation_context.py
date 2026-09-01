"""Conversation-context response contracts for the Matter API.

Byline: Codex · GPT-5.6-Sol · 2026-08-30
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.types.case_management import RecordProjectionKind, RecordSourceKind


class ConversationMessage(BaseModel):
    id: UUID
    normalized_record_id: UUID
    content: str
    sender: str | None = None
    recipients: list[str] = Field(default_factory=list)
    occurred_at: datetime | None = None
    source_kind: RecordSourceKind = "unclassified"
    projection_kind: RecordProjectionKind = "authored_normalized"
    source_available_from: datetime | None = None
    source_pointer: dict[str, object] = Field(default_factory=dict)


class ConversationContext(BaseModel):
    matter_id: UUID
    evidence_item_id: UUID
    selected_normalized_record_id: UUID
    messages: list[ConversationMessage]
    before: int = Field(ge=0)
    after: int = Field(ge=0)
    total: int = Field(ge=0)
    context_available: bool = True
    context_complete: bool = True
    availability_reason: str | None = None
