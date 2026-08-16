"""Classification runtime router for workbench API.

Byline: Codex · GPT-5 · 2026-08-16
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.service.classification import classification_service
from app.types.classification import (
    BatchClassificationRequest,
    BatchClassificationResponse,
    ClassificationRequest,
    ClassificationResponse,
    ProvidersListResponse,
)

router = APIRouter(prefix="/api/classification", tags=["classification"])


@router.post(
    "/classify",
    response_model=ClassificationResponse,
    summary="Classify a single text",
    description="""
Classify a single text into one of the provided categories.

Returns the category, confidence score, reasoning, and raw model response.

**Providers**: ollama, nvidia, openrouter, anthropic, openai, google, groq, portkey

**Example categories**: ["legal", "platform", "personal_history", "context"]
    """,
    response_description="Classification result with category, confidence, and reasoning",
)
async def classify(request: ClassificationRequest) -> ClassificationResponse:
    """Classify a single text into categories."""
    try:
        return await classification_service.classify(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {e}")


@router.post(
    "/batch",
    response_model=BatchClassificationResponse,
    summary="Classify multiple texts in batch",
    description="""
Classify multiple texts in parallel (max 100 texts per request).

Uses semaphore to limit concurrency to 5 parallel requests.

Returns list of classification results with total latency.
    """,
    response_description="Batch classification results with total latency",
)
async def classify_batch(request: BatchClassificationRequest) -> BatchClassificationResponse:
    """Classify multiple texts in batch."""
    try:
        return await classification_service.classify_batch(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch classification failed: {e}")


@router.get(
    "/categories",
    summary="Get default classification categories",
    description="Returns the default set of categories used for classification.",
    response_description="List of default category names",
)
async def get_default_categories() -> dict[str, list[str]]:
    """Get default classification categories."""
    return {
        "categories": [
            "platform",
            "legal",
            "personal_history",
            "context",
        ]
    }


@router.get(
    "/providers",
    response_model=ProvidersListResponse,
    summary="List available providers",
    description="""
Returns all supported providers with their availability status and available models.

Availability is determined by checking if required API keys/hosts are configured.
Each provider includes its full list of available models for dynamic frontend population.
    """,
    response_description="List of providers with availability, default model, and available models",
)
async def list_providers(
    refresh: bool = Query(default=False, description="Bypass the five-minute model catalog cache"),
) -> ProvidersListResponse:
    """List available providers and their models."""
    from app.service.model_catalog import model_catalog_service

    return await model_catalog_service.list(refresh=refresh)
