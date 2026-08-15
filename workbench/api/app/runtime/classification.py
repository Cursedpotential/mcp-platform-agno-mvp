"""Classification runtime router for workbench API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from app.service.classification import classification_service
from app.types.classification import (
    BatchClassificationRequest,
    BatchClassificationResponse,
    ClassificationRequest,
    ClassificationResponse,
    ProviderName,
)

router = APIRouter(prefix="/classification", tags=["classification"])


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
    summary="List available providers",
    description="""
Returns all supported providers with their availability status and default models.

Availability is determined by checking if required API keys/hosts are configured.
    """,
    response_description="List of providers with availability and default models",
)
async def list_providers() -> dict[str, list[str]]:
    """List available providers and their default models."""
    from app.service.model_providers import _PINNED_MODELS, list_available_providers

    available = list_available_providers()
    return {
        "providers": [
            {
                "name": p.value,
                "available": available.get(p, False),
                "default_model": _PINNED_MODELS.get(p, "unknown"),
            }
            for p in ProviderName
        ]
    }
