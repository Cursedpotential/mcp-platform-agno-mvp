"""Typed boundary models for the Universal Import Workflow starter.

Byline: Codex · GPT-5 · 2026-08-28.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints


NonBlank = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class UIWStartRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request_id: NonBlank
    matter_id: UUID
    court_case_id: UUID
    source_ref: NonBlank
    declared_format: NonBlank
    parser_options_ref: NonBlank


class UIWStartResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    workflow_id: NonBlank
    run_id: NonBlank


class UIWDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str = ""
    decider: NonBlank


class UIWDecisionResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: NonBlank


class UIWPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    phase: NonBlank
    # Empty before parser selection is valid while a workflow is starting.
    select_ref: str = ""
    reason: str = ""
