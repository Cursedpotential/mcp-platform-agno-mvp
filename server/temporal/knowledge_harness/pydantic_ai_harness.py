"""
Bake side B — PydanticAI.

Same contract as ``agno_harness``: ``run_knowledge_step(records_ref, lane,
run_meta) -> KnowledgeResult``, same governed door underneath
(``workflows.py::_knowledge_step_impl``, :483). What differs is the SHAPE: an
``Agent`` with a deps-injected engine handle and ONE typed tool, where the tool
is the only thing allowed to touch the pipeline and the agent's typed output is
the contract the caller sees.

Read ``BAKE.md`` for what is actually being scored. The short version: side A
adapts an existing step; side B wraps that same step in a typed agent boundary.
If the boundary does not buy something concrete — clearer failure behavior, a
contract that catches a class of bug side A cannot — it loses and gets deleted.

DEPENDENCY: ``pydantic-ai`` is NOT a base dependency. It ships as the optional
``temporal-bake`` extra and is imported lazily inside the function, so importing
this module (or the whole ``server.temporal`` package) never requires it.

Byline: Claude Code · Opus 5 · 2026-08-23
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from server.temporal.knowledge_harness import KnowledgeResult, RecordsRef

if TYPE_CHECKING:  # type-only; the runtime import stays lazy in _import_agent()
    from pydantic_ai import RunContext

logger = logging.getLogger("evidence.runs")

HARNESS_NAME = "pydantic_ai"

_INSTALL_HINT = (
    "pydantic-ai is not installed — the PydanticAI side of the knowledge bake "
    "requires it. Install the optional extra: uv pip install -e '.[temporal-bake]'"
)

# The bake's agent needs a model to drive its single tool call. There is no
# default: an unset value is a configuration error, not a reason to silently
# pick a model and spend tokens. Set KNOWLEDGE_BAKE_MODEL to a pydantic-ai
# model id when running side B.
_MODEL_ENV = "KNOWLEDGE_BAKE_MODEL"

_INSTRUCTIONS = (
    "You project already-stored evidence records into the knowledge lane. "
    "Call project_records exactly once with no arguments, then return its result "
    "unchanged. You must not summarize, re-order, filter, or describe the records: "
    "the tool is the only thing permitted to touch the pipeline, and its return "
    "value is the answer."
)


@dataclass
class KnowledgeDeps:
    """Deps injected into the agent's tool — the engine handle is passed in
    rather than reached for, so the tool has exactly one way to see Postgres."""

    records_ref: RecordsRef
    lane: str
    run_meta: dict[str, Any]
    engine: Any


def _import_agent() -> Any:
    """Import pydantic-ai's ``Agent`` or raise the install-extra error.

    Separated so the failure is identical whether it is hit through the harness
    selector or asserted directly in a test."""
    try:
        from pydantic_ai import Agent
    except ImportError as exc:  # pragma: no cover - exercised when the extra is absent
        raise RuntimeError(_INSTALL_HINT) from exc
    return Agent


async def run_knowledge_step(
    records_ref: RecordsRef,
    lane: str,
    run_meta: dict[str, Any],
) -> KnowledgeResult:
    """Project one artifact's stored records through a typed PydanticAI tool."""
    Agent = _import_agent()

    model = (os.getenv(_MODEL_ENV) or "").strip()
    if not model:
        raise RuntimeError(
            f"{HARNESS_NAME} harness requires {_MODEL_ENV} (a pydantic-ai model id); refusing to pick one implicitly"
        )

    from sqlalchemy import create_engine, text

    from server.core.url import db_url

    agent = Agent(
        model,
        deps_type=KnowledgeDeps,
        output_type=KnowledgeResult,
        instructions=_INSTRUCTIONS,
    )

    @agent.tool
    async def project_records(ctx: RunContext[KnowledgeDeps]) -> KnowledgeResult:
        """Run the platform's knowledge projection for the deps' artifact.

        This is the governed door and the ONLY pipeline access the agent has.
        It calls the same ``_knowledge_step_impl`` the live agno workflow calls,
        over the same ``load_records_for_artifact`` rows — side B differs from
        side A in framing, never in what touches the data.
        """
        from server.analysis.context_chat_ingest import create_lane_knowledge
        from server.evidence.store import load_artifact_ref, load_records_for_artifact
        from server.evidence.workflows import _knowledge_step_impl

        deps = ctx.deps
        # The injected engine's one job: prove the rows exist before the
        # projection is attempted, so "0 docs" can never be reported as a
        # success without a reason (the workflows.py:36-44 failure mode).
        with deps.engine.connect() as conn:
            available = conn.execute(
                # Binding shape matches store.py:593-598's own read of this
                # table (plain :param, no cast).
                text("SELECT count(*) FROM working.normalized_record WHERE artifact_id = :artifact_id"),
                {"artifact_id": deps.records_ref.artifact_id},
            ).scalar_one()

        records = load_records_for_artifact(deps.records_ref.artifact_id)
        if deps.records_ref.record_ids:
            wanted = set(deps.records_ref.record_ids)
            records = [r for r in records if str(r.attrs.get("_normalized_record_id") or "") in wanted]

        step_ctx: dict[str, Any] = {
            "domain": deps.lane,
            "records": records,
            "artifact": load_artifact_ref(deps.records_ref.artifact_id),
            "dedupe_noop": bool(deps.run_meta.get("dedupe_noop")),
            "native_evidence_required": bool(deps.run_meta.get("native_evidence_required")),
        }
        knowledge = create_lane_knowledge(deps.lane) if records else None
        output = await _knowledge_step_impl(step_ctx, knowledge)
        if not getattr(output, "success", True):
            raise RuntimeError(str(getattr(output, "content", "knowledge step failed")))

        detail = str(getattr(output, "content", ""))
        return KnowledgeResult(
            docs_ingested=int(step_ctx.get("knowledge_docs") or 0),
            skipped=bool(step_ctx.get("knowledge_skipped")),
            detail=f"{detail} [rows_available={available}]",
            harness=HARNESS_NAME,
            lane=deps.lane,
            attempts=list(step_ctx.get("knowledge_attempts") or []),
        )

    deps = KnowledgeDeps(
        records_ref=records_ref,
        lane=lane,
        run_meta=dict(run_meta),
        engine=create_engine(db_url, pool_pre_ping=True),
    )
    try:
        run = await agent.run(
            f"Project artifact {records_ref.artifact_id} into lane {lane}.",
            deps=deps,
        )
    finally:
        deps.engine.dispose()

    result = run.output
    logger.info(
        "knowledge harness=%s artifact=%s lane=%s docs=%s skipped=%s",
        HARNESS_NAME,
        records_ref.artifact_id,
        lane,
        result.docs_ingested,
        result.skipped,
    )
    return result
