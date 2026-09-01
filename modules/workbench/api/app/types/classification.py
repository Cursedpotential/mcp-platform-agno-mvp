"""Type definitions for classification and sentiment analysis.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class ProviderName(str, Enum):
    """Supported model providers."""

    OLLAMA = "ollama"
    NVIDIA = "nvidia"
    OPENROUTER = "openrouter"
    ANTHROPIC = "anthropic"
    OPENAI = "openai"
    GOOGLE = "google"
    GROQ = "groq"
    PORTKEY = "portkey"


class SentimentLabel(str, Enum):
    """Sentiment classification labels."""

    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"


class ClassificationRequest(BaseModel):
    """Request for single text classification."""

    text: str = Field(..., min_length=1, max_length=100000)
    categories: list[str] = Field(..., min_length=1, max_length=20)
    provider: ProviderName = ProviderName.OLLAMA
    model_id: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    system_prompt: str | None = None


class ClassificationResponse(BaseModel):
    """Response for single text classification."""

    category: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    raw_response: str
    provider: ProviderName
    model_id: str
    latency_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchClassificationRequest(BaseModel):
    """Request for batch classification."""

    texts: list[str] = Field(..., min_length=1, max_length=100)
    categories: list[str] = Field(..., min_length=1, max_length=20)
    provider: ProviderName = ProviderName.OLLAMA
    model_id: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    system_prompt: str | None = None


class BatchClassificationResponse(BaseModel):
    """Response for batch classification."""

    results: list[ClassificationResponse]
    total_latency_ms: int
    provider: ProviderName
    model_id: str


class SentimentRequest(BaseModel):
    """Request for single text sentiment analysis."""

    text: str = Field(..., min_length=1, max_length=100000)
    provider: ProviderName = ProviderName.OLLAMA
    model_id: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    include_emotions: bool = True


class SentimentResponse(BaseModel):
    """Response for single text sentiment analysis."""

    sentiment: SentimentLabel
    score: float = Field(ge=-1.0, le=1.0)
    emotions: dict[str, float] = Field(default_factory=dict)
    reasoning: str
    raw_response: str
    provider: ProviderName
    model_id: str
    latency_ms: int
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class BatchSentimentRequest(BaseModel):
    """Request for batch sentiment analysis."""

    texts: list[str] = Field(..., min_length=1, max_length=100)
    provider: ProviderName = ProviderName.OLLAMA
    model_id: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)
    include_emotions: bool = True


class BatchSentimentResponse(BaseModel):
    """Response for batch sentiment analysis."""

    results: list[SentimentResponse]
    total_latency_ms: int
    provider: ProviderName
    model_id: str


class ProviderConfig(BaseModel):
    """Configuration for a single provider in comparison."""

    provider: ProviderName
    model_id: str | None = None
    temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    max_tokens: int = Field(default=1024, ge=1, le=8192)


class ComparisonRequest(BaseModel):
    """Request for multi-provider comparison."""

    texts: list[str] = Field(..., min_length=1, max_length=50)
    categories: list[str] = Field(..., min_length=1, max_length=20)
    providers: list[ProviderConfig] = Field(..., min_length=1, max_length=5)
    include_sentiment: bool = True
    system_prompt: str | None = None


class ComparisonResult(BaseModel):
    """Single result in a comparison."""

    text_index: int
    text_preview: str  # First 100 chars
    provider: ProviderName
    model_id: str
    classification: ClassificationResponse | None = None
    sentiment: SentimentResponse | None = None
    latency_ms: int


class ComparisonSummary(BaseModel):
    """Summary statistics for a comparison run."""

    total_texts: int
    total_providers: int
    avg_latency_ms: float
    category_agreement_rate: float  # % of texts where all providers agree on top category
    sentiment_agreement_rate: float  # % of texts where all providers agree on sentiment


class ComparisonResponse(BaseModel):
    """Response for multi-provider comparison."""

    results: list[ComparisonResult]
    summary: ComparisonSummary
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ProviderInfo(BaseModel):
    """Information about an available provider/model."""

    provider: ProviderName
    models: list[str]
    default_model: str
    available: bool
    source: str
    error: str | None = None


class ProvidersListResponse(BaseModel):
    """Response listing available providers and models."""

    providers: list[ProviderInfo]
    refreshed_at: datetime
    cache_hit: bool = False


class ExportRequest(BaseModel):
    """Request to export comparison results."""

    comparison_id: str | None = None
    format: Literal["json", "csv"] = "json"
    include_raw: bool = False


class HealthCheckResponse(BaseModel):
    """Health check for a provider."""

    provider: ProviderName
    model_id: str | None
    status: Literal["healthy", "degraded", "unhealthy"]
    latency_ms: int | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
