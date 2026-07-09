"""
evidence/normalize.py — the canonical record schema every parser emits into.

One shape for everything (message / call / event / media) so storage, analysis,
and export never care which parser produced a record. Carries the BITEMPORAL
substrate Part 2 replays over:

  occurred_at     — VALID TIME: when the thing actually happened
  knowledge_time  — when the owner/platform learned it (default: ingestion)
  disclosure_tier — contemporaneous | hindsight | discovered

The Pass-1-vs-final-pass delta (the abuse made legible) filters on these.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Iterable

from pydantic import BaseModel, Field, field_validator


class DisclosureTier(str, Enum):
    contemporaneous = "contemporaneous"  # knowable at the moment it happened
    hindsight = "hindsight"  # assembled later by connecting records
    discovered = "discovered"  # hidden fact surfaced after the fact


class RecordType(str, Enum):
    message = "message"
    call = "call"
    event = "event"
    media = "media"


class NormalizedRecord(BaseModel):
    """Canonical record. Parsers produce these; store.py persists them."""

    record_type: RecordType = RecordType.message
    source: str  # parser/source key e.g. 'chatgpt-export'
    conversation_id: str | None = None
    role: str | None = None  # sender / author role
    participants: list[str] = Field(default_factory=list)
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


def finalize(records: Iterable[NormalizedRecord]) -> list[NormalizedRecord]:
    """Apply normalize-time defaults: knowledge_time = now for anything unset.

    (Re-processing historical material later with a different knowledge_time is
    a deliberate Part-2 operation, not a default.)
    """
    now = datetime.now(timezone.utc)
    out: list[NormalizedRecord] = []
    for rec in records:
        if rec.knowledge_time is None:
            rec = rec.model_copy(update={"knowledge_time": now})
        out.append(rec)
    return out
