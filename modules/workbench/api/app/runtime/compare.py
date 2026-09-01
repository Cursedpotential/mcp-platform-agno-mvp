# Byline: Codex · GPT-5 · 2026-08-15 (OpenAPI endpoint documentation)
"""Comparison runtime router for workbench API."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
import io
import json
import csv

from app.service.comparison import comparison_service
from app.types.classification import (
    ComparisonRequest,
    ComparisonResponse,
    ExportRequest,
    ProvidersListResponse,
)

router = APIRouter(prefix="/api/comparison", tags=["comparison"])


@router.post(
    "/run",
    response_model=ComparisonResponse,
    summary="Run multi-provider comparison",
    description="""
Run classification and/or sentiment comparison across multiple providers simultaneously.

This is the core endpoint for comparing how different LLMs classify and analyze the same texts.

**Features:**
- Test multiple providers in one request (max 5)
- Each provider can have different model/temperature settings
- Optional sentiment analysis included
- Returns detailed per-text per-provider results
- Calculates agreement rates across providers

**Providers**: ollama, nvidia, openrouter, anthropic, openai, google, groq, portkey

**Example categories**: ["legal", "platform", "personal_history", "context"]
    """,
    response_description="Comparison results with per-provider breakdown and agreement summary",
)
async def run_comparison(request: ComparisonRequest) -> ComparisonResponse:
    """Run classification and/or sentiment comparison across multiple providers."""
    try:
        return await comparison_service.compare(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


@router.get(
    "/providers",
    response_model=ProvidersListResponse,
    summary="List available providers with models",
    description="""
Returns all supported providers with availability, default models, and model lists.

Use this to discover which providers are configured and what models they support.
    """,
    response_description="List of providers with availability and models",
)
async def list_providers(
    refresh: bool = Query(default=False, description="Bypass the five-minute model catalog cache"),
) -> ProvidersListResponse:
    """List available providers with their models and availability."""
    from app.service.model_catalog import model_catalog_service

    return await model_catalog_service.list(refresh=refresh)


@router.post(
    "/export",
    summary="Export comparison results",
    description="""
Export cached comparison results as JSON or CSV.

**Formats:**
- `json`: Full or sanitized (without raw responses) JSON
- `csv`: Spreadsheet-ready CSV with one row per text-provider combination

**Parameters:**
- `format`: "json" or "csv" (query param)
- `comparison_id`: Specific run ID (optional, uses latest)
- `include_raw`: Include raw model responses (query param)
    """,
    response_description="File download (JSON or CSV)",
)
async def export_results(request: ExportRequest, format: str = Query("json", pattern="^(json|csv)$")):
    """Export comparison results as JSON or CSV."""
    # For now, export the last run or a specific run
    cached_ids = comparison_service.list_cached()
    if not cached_ids:
        raise HTTPException(status_code=404, detail="No comparison results to export")

    run_id = request.comparison_id or cached_ids[-1]
    result = comparison_service.get_cached(run_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Comparison run {run_id} not found")

    if format == "json":
        if request.include_raw:
            content = result.model_dump_json(indent=2)
        else:
            # Export without raw responses
            export_data = result.model_dump(
                exclude={
                    "results": {
                        "__all__": {"classification": {"raw_response": True}, "sentiment": {"raw_response": True}}
                    }
                }
            )
            content = json.dumps(export_data, indent=2, default=str)

        return StreamingResponse(
            io.BytesIO(content.encode()),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename=comparison_{run_id}.json"},
        )

    # CSV export
    output = io.StringIO()
    writer = csv.writer(output)

    # Headers
    headers = [
        "text_index",
        "text_preview",
        "provider",
        "model_id",
        "category",
        "confidence",
        "classification_reasoning",
        "sentiment",
        "sentiment_score",
        "sentiment_reasoning",
        "latency_ms",
    ]
    writer.writerow(headers)

    for r in result.results:
        row = [
            r.text_index,
            r.text_preview,
            r.provider.value,
            r.model_id,
            r.classification.category if r.classification else "",
            r.classification.confidence if r.classification else "",
            r.classification.reasoning if r.classification else "",
            r.sentiment.sentiment.value if r.sentiment else "",
            r.sentiment.score if r.sentiment else "",
            r.sentiment.reasoning if r.sentiment else "",
            r.latency_ms,
        ]
        writer.writerow(row)

    content = output.getvalue()
    return StreamingResponse(
        io.BytesIO(content.encode()),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename=comparison_{run_id}.csv"},
    )


@router.get(
    "/runs",
    summary="List cached comparison runs",
    description="Returns list of cached comparison run IDs available for export or retrieval.",
    response_description="List of run IDs",
)
async def list_runs() -> dict:
    """List cached comparison runs."""
    return {"runs": comparison_service.list_cached()}


@router.get(
    "/runs/{run_id}",
    response_model=ComparisonResponse,
    summary="Get a specific comparison run",
    description="Retrieve a specific cached comparison run by ID.",
    response_description="Full comparison response",
)
async def get_run(run_id: str) -> ComparisonResponse:
    """Get a specific comparison run."""
    result = comparison_service.get_cached(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result
