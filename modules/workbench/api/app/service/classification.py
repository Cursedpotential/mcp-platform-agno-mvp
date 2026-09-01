"""Classification service for workbench API."""

from __future__ import annotations

import asyncio
import time

from app.service.model_providers import build_provider, run_classification
from app.types.classification import (
    BatchClassificationRequest,
    BatchClassificationResponse,
    ClassificationRequest,
    ClassificationResponse,
    ProviderName,
)


class ClassificationService:
    """Service for running classification with various providers."""

    async def classify(self, request: ClassificationRequest) -> ClassificationResponse:
        """Classify a single text."""
        provider = build_provider(request.provider, request.model_id)

        start = time.perf_counter()
        category, confidence, reasoning, raw = await run_classification(
            provider=provider,
            text=request.text,
            categories=request.categories,
            system_prompt=request.system_prompt,
            temperature=request.temperature,
            max_tokens=request.max_tokens,
        )
        latency_ms = int((time.perf_counter() - start) * 1000)

        return ClassificationResponse(
            category=category,
            confidence=confidence,
            reasoning=reasoning,
            raw_response=raw,
            provider=request.provider,
            model_id=_model_id(request.provider, request.model_id),
            latency_ms=latency_ms,
        )

    async def classify_batch(self, request: BatchClassificationRequest) -> BatchClassificationResponse:
        """Classify multiple texts in parallel."""
        provider = build_provider(request.provider, request.model_id)

        start = time.perf_counter()

        # Run classifications in parallel with semaphore to limit concurrency
        semaphore = asyncio.Semaphore(5)

        async def classify_one(text: str) -> ClassificationResponse:
            async with semaphore:
                category, confidence, reasoning, raw = await run_classification(
                    provider=provider,
                    text=text,
                    categories=request.categories,
                    system_prompt=request.system_prompt,
                    temperature=request.temperature,
                    max_tokens=request.max_tokens,
                )
                return ClassificationResponse(
                    category=category,
                    confidence=confidence,
                    reasoning=reasoning,
                    raw_response=raw,
                    provider=request.provider,
                    model_id=_model_id(request.provider, request.model_id),
                    latency_ms=0,  # Will be set per-item if needed
                )

        results = await asyncio.gather(*[classify_one(t) for t in request.texts])
        total_latency_ms = int((time.perf_counter() - start) * 1000)

        return BatchClassificationResponse(
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
classification_service = ClassificationService()
