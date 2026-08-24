"""
Bake side A — Agno-as-library.

Implements ``run_knowledge_step`` by REUSING the live knowledge step verbatim:
records come back out of Postgres exactly the way ``run_knowledge_from_store``
(``server/evidence/workflows.py:1024``) reads them, and the projection itself is
``workflows.py::_knowledge_step_impl`` (:483) — the same function the agno
``Workflow`` calls today. Nothing is reimplemented; this module only assembles
the ctx that function already reads and translates its ``StepOutput`` into the
shared ``KnowledgeResult``.

Why that matters for the bake: side A's honest line count is the cost of
*adapting* an existing, working step — not the cost of writing a knowledge
pipeline. Side B (``pydantic_ai_harness``) is measured against the same door.

Every import is inside the function (the ``run_ledger.py:31`` pattern): this
module is reachable from ``activities.py``'s import graph, and
``server.core.session`` reads env at module scope (:94-118, :214-233).

Byline: Claude Code · Opus 5 · 2026-08-23
"""

from __future__ import annotations

import logging
from typing import Any

from server.temporal.knowledge_harness import KnowledgeResult, RecordsRef

logger = logging.getLogger("evidence.runs")

HARNESS_NAME = "agno"


async def run_knowledge_step(
    records_ref: RecordsRef,
    lane: str,
    run_meta: dict[str, Any],
) -> KnowledgeResult:
    """Project one artifact's stored records into the lane's knowledge handle.

    The branch structure below is NOT a decision this module makes — it is the
    ctx that ``_knowledge_step_impl`` inspects:

    - ``records`` empty      -> that function reports a skip and why
      (``workflows.py:591-600`` equivalent branch at :594).
    - ``knowledge`` is a ``NativeEvidenceProjector`` -> it drains the durable
      outbox and raises if any chunk failed (:509-521).
    - otherwise (the CONTEXT lane's Agno ``Knowledge`` handle) -> it renders
      per-conversation markdown and ``ainsert``s with the domain tag (:527).

    The handle itself comes from the governed door
    ``server/analysis/context_chat_ingest.py::create_lane_knowledge`` (:64),
    which maps lane -> Weaviate collection and calls
    ``server/core/session.py::create_knowledge`` (:361). A worker process has no
    FastAPI app state to inherit a handle from, so it builds one through the same
    door the CLI-side context ingest uses rather than inventing a second
    construction path.
    """
    from server.analysis.context_chat_ingest import create_lane_knowledge
    from server.evidence.store import load_artifact_ref, load_records_for_artifact
    from server.evidence.workflows import _knowledge_step_impl

    records = load_records_for_artifact(records_ref.artifact_id)
    if records_ref.record_ids:
        wanted = set(records_ref.record_ids)
        records = [r for r in records if str(r.attrs.get("_normalized_record_id") or "") in wanted]

    ctx: dict[str, Any] = {
        "domain": lane,
        "records": records,
        "artifact": load_artifact_ref(records_ref.artifact_id),
        "dedupe_noop": bool(run_meta.get("dedupe_noop")),
        "native_evidence_required": bool(run_meta.get("native_evidence_required")),
    }
    knowledge = create_lane_knowledge(lane) if records else None
    if knowledge is None and records:
        # create_lane_knowledge never returns None; this guard exists so a
        # future handle-resolution change cannot silently degrade into the
        # "no engine handle passed" skip branch and report a false success.
        raise RuntimeError(f"knowledge harness {HARNESS_NAME}: no engine handle for lane {lane!r}")

    output = await _knowledge_step_impl(ctx, knowledge)
    if not getattr(output, "success", True):
        raise RuntimeError(str(getattr(output, "content", "knowledge step failed")))

    result = KnowledgeResult(
        docs_ingested=int(ctx.get("knowledge_docs") or 0),
        skipped=bool(ctx.get("knowledge_skipped")),
        detail=str(getattr(output, "content", "")),
        harness=HARNESS_NAME,
        lane=lane,
        attempts=list(ctx.get("knowledge_attempts") or []),
    )
    logger.info(
        "knowledge harness=%s artifact=%s lane=%s docs=%s skipped=%s",
        HARNESS_NAME,
        records_ref.artifact_id,
        lane,
        result.docs_ingested,
        result.skipped,
    )
    return result
