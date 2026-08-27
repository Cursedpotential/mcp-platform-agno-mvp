from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


class RunProbeRequest(BaseModel):
    provider: str
    model: str
    probe: Literal["liveness", "tool_use", "summarization", "instruction_following"]
    max_tokens: int = 500
    temperature: float = 0
    reasoning_effort: Optional[Literal["none", "low", "medium", "high"]] = None
    persist: bool = True
    run_note: Optional[str] = None


class RunPlaygroundRequest(BaseModel):
    provider: str
    model: str
    prompt: str = Field(min_length=1)
    max_tokens: int = 500
    temperature: float = 0
    reasoning_effort: Optional[Literal["none", "low", "medium", "high"]] = None
    label: Optional[str] = None
    persist: bool = True


class ProbeResultOut(BaseModel):
    probe: str
    ok: bool
    latency_s: Optional[float]
    detail: dict[str, Any]
    reasoning_overhead_tokens: Optional[int] = None


class PlaygroundResultOut(BaseModel):
    provider: str
    model: str
    ok: bool
    status: Optional[int]
    latency_s: float
    content: Optional[str]
    tool_calls: Optional[list[dict[str, Any]]] = None
    usage: Optional[dict[str, Any]]
    reasoning_overhead_tokens: Optional[int]
    error: Optional[str]
