from __future__ import annotations

from fastapi import APIRouter

from .. import db, probes
from ..probes import PROBE_CATALOG
from ..schemas import RunPlaygroundRequest, RunProbeRequest

router = APIRouter(tags=["probe"])


@router.get("/probes")
async def list_probe_defs():
    """The canned, scored probes (liveness/tool_use/summarization/instruction_following)
    and the exact prompt each one sends — reference for the playground UI."""
    return PROBE_CATALOG


@router.post("/probe/run")
async def run_probe(req: RunProbeRequest):
    result = await probes.run_named_probe(
        req.provider, req.model, req.probe,
        max_tokens=req.max_tokens, temperature=req.temperature, reasoning_effort=req.reasoning_effort,
    )
    if req.persist:
        run_id = await db.insert_probe_run(
            f"adhoc_{req.probe}",
            req.run_note or f"ad-hoc rerun via llm_probe API (max_tokens={req.max_tokens}, reasoning_effort={req.reasoning_effort})",
        )
        detail = {k: v for k, v in result.items() if k not in ("probe", "ok", "latency_s")}
        await db.insert_probe_result(run_id, req.provider, req.model, req.probe, result["ok"],
                                      None, result.get("latency_s"), detail)
        result["run_id"] = run_id
    return result


@router.post("/playground/run")
async def run_playground(req: RunPlaygroundRequest):
    result = await probes.run_custom_prompt(
        req.provider, req.model, req.prompt,
        max_tokens=req.max_tokens, temperature=req.temperature, reasoning_effort=req.reasoning_effort,
    )
    if req.persist:
        await db.insert_playground_run(
            provider=req.provider, model=req.model, prompt=req.prompt,
            max_tokens=req.max_tokens, temperature=req.temperature, reasoning_effort=req.reasoning_effort,
            ok=result["http_ok"], http_status=result["status"], latency_s=result["latency_s"],
            content=result["content"], reasoning_overhead_tokens=result.get("reasoning_overhead_tokens"),
            usage=result.get("usage"), error=result.get("error"), label=req.label,
        )
    return result


@router.get("/playground/history")
async def playground_history(provider: str | None = None, model: str | None = None, limit: int = 200):
    return await db.fetch_playground_history(provider, model, limit)
