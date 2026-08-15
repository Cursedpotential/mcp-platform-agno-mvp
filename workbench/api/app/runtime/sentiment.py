"""Sentiment analysis runtime router for workbench API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.service.sentiment import sentiment_service
from app.types.classification import (
    BatchSentimentRequest,
    BatchSentimentResponse,
    SentimentRequest,
    SentimentResponse,
)

router = APIRouter(prefix="/sentiment", tags=["sentiment"])


@router.post(
    "/analyze",
    response_model=SentimentResponse,
    summary="Analyze sentiment of a single text",
    description="""
Analyze the sentiment of a single text.

Returns sentiment label (positive/negative/neutral/mixed), score (-1 to 1),
emotion breakdown, reasoning, and raw response.

**Providers**: ollama, nvidia, openrouter, anthropic, openai, google, groq, portkey
    """,
    response_description="Sentiment analysis result with label, score, and emotions",
)
async def analyze_sentiment(request: SentimentRequest) -> SentimentResponse:
    """Analyze sentiment of a single text."""
    try:
        return await sentiment_service.analyze(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Sentiment analysis failed: {e}")


@router.post(
    "/batch",
    response_model=BatchSentimentResponse,
    summary="Analyze sentiment of multiple texts in batch",
    description="""
Analyze sentiment of multiple texts in parallel (max 100 texts per request).

Returns list of sentiment results with total latency.
    """,
    response_description="Batch sentiment analysis results with total latency",
)
async def analyze_batch(request: BatchSentimentRequest) -> BatchSentimentResponse:
    """Analyze sentiment of multiple texts in batch."""
    try:
        return await sentiment_service.analyze_batch(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch sentiment analysis failed: {e}")
