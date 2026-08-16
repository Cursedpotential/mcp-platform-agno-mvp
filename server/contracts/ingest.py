"""Framework-neutral contracts for canonical file ingestion.

These models deliberately import no workflow, agent, vector, graph, or database
framework. HTTP and in-process callers share the same request and receipt shape.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class IngestLane(str, Enum):
    platform = "platform"
    legal = "legal"
    personal_history = "personal_history"
    context = "context"
    evidence = "evidence"


class IngestRequest(BaseModel):
    """One staged file and the routing context required to ingest it."""

    staged_path: str
    source_identity: dict[str, Any] = Field(default_factory=dict)
    coverage_hint: str | None = None
    lane: IngestLane = IngestLane.platform
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


class IngestRejection(BaseModel):
    code: str
    detail: str


class ProjectionResult(BaseModel):
    sink: str
    status: Literal["completed", "skipped", "failed"]
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
    parser_engine: Literal["go", "python", "none"] = "none"
    chunker_id: str
    record_count: int = 0
    chunk_count: int = 0
    rejections: list[IngestRejection] = Field(default_factory=list)
    attempts: list[dict[str, Any]] = Field(default_factory=list)
    projections: list[ProjectionResult] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime
