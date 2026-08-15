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
    ProviderName,
)

router = APIRouter(prefix="/comparison", tags=["comparison"])


@router.post("/run", response_model=ComparisonResponse)
async def run_comparison(request: ComparisonRequest) -> ComparisonResponse:
    """Run classification and/or sentiment comparison across multiple providers."""
    try:
        return await comparison_service.compare(request)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Comparison failed: {e}")


@router.get("/providers")
async def list_providers() -> dict:
    """List available providers with their models and availability."""
    from app.service.model_providers import _PINNED_MODELS, list_available_providers

    available = list_available_providers()
    providers_info = []

    for p in ProviderName:
        providers_info.append(
            {
                "provider": p.value,
                "available": available.get(p, False),
                "default_model": _PINNED_MODELS.get(p, "unknown"),
                "models": [_PINNED_MODELS.get(p, "unknown")],  # Could be extended with model catalog
            }
        )

    return {"providers": providers_info}


@router.post("/export")
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


@router.get("/runs")
async def list_runs() -> dict:
    """List cached comparison runs."""
    return {"runs": comparison_service.list_cached()}


@router.get("/runs/{run_id}")
async def get_run(run_id: str) -> ComparisonResponse:
    """Get a specific comparison run."""
    result = comparison_service.get_cached(run_id)
    if not result:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return result
