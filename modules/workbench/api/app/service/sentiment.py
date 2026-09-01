"""Sentiment analysis service for workbench API."""

from __future__ import annotations

import asyncio
import time

from app.service.model_providers import build_provider, run_sentiment
from app.types.classification import (
    BatchSentimentRequest,
    BatchSentimentResponse,
    ProviderName,
    SentimentLabel,
    SentimentRequest,
    SentimentResponse,
)


class SentimentService:
    """Service for running sentiment analysis with various providers."""

    async def analyze(self, request: SentimentRequest) -> SentimentResponse:
        """Analyze sentiment of a single text."""
        provider = build_provider(request.provider, request.model_id)

        start = time.perf_counter()
        sentiment, score, emotions, reasoning, raw = await run_sentiment(
            provider=provider,
            text=request.text,
            system_prompt=None,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
            include_emotions=request.include_emotions,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        return SentimentResponse(
            sentiment=SentimentLabel(sentiment),
            score=score,
            emotions=emotions if request.include_emotions else {},
            reasoning=reasoning,
            raw_response=raw,
            provider=request.provider,
            model_id=_model_id(request.provider, request.model_id),
            latency_ms=latency_ms,
        )

    async def analyze_batch(self, request: BatchSentimentRequest) -> BatchSentimentResponse:
        """Analyze sentiment of multiple texts in parallel."""
        provider = build_provider(request.provider, request.model_id)

        start = time.perf_counter()

        semaphore = asyncio.Semaphore(5)

        async def analyze_one(text: str) -> SentimentResponse:
            async with semaphore:
                sentiment, score, emotions, reasoning, raw = await run_sentiment(
                    provider=provider,
                    text=text,
                    system_prompt=None,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                    include_emotions=request.include_emotions,
                )
                return SentimentResponse(
                    sentiment=SentimentLabel(sentiment),
                    score=score,
                    emotions=emotions if request.include_emotions else {},
                    reasoning=reasoning,
                    raw_response=raw,
                    provider=request.provider,
                    model_id=_model_id(request.provider, request.model_id),
                    latency_ms=0,
                )

        results = await asyncio.gather(*[analyze_one(t) for t in request.texts])
        total_latency_ms = int((time.perf_counter() - start) * 1000)

        return BatchSentimentResponse(
            results=results,
            total_latency_ms=total_latency_ms,
            provider=request.provider,
            model_id=_model_id(request.provider, request.model_id),
        )


def _model_id(provider: ProviderName, model_id: str | None) -> str:
    """Get resolved model ID."""
    if model_id:
        return model_id
    from app.service.model_providers import _model_id as _resolve_model_id

    return _resolve_model_id(provider, model_id)


# Singleton instance
sentiment_service = SentimentService()
