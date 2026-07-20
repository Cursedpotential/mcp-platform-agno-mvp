"""
evidence/workflows.py — named, custody-gated workflows on native agno.workflow.

A workflow = ordered capability steps (custody -> parse -> normalize+store ->
knowledge). Each parse step resolves the best-fit atomic tool from the
registry; if the preferred tool rejects the input (wrong format), the executor
tries the next same-capability candidate automatically and reports every
attempt — the substitution mechanic the mesh is built around.

Workflows registered here:
  chat-transcript : AI-chat exports (ChatGPT / claude.ai / Claude Code JSONL /
                    markdown) -> custody -> parse -> analysis.normalized_record
                    -> knowledge engine (domain-tagged). THE BOOTSTRAP VERTICAL.

  sms-xml         : "SMS Backup & Restore" XML (sms/mms/call) -> custody ->
                    parse.sms-xml (SBV PRIMARY, sms_xml.py FALLBACK via registry
                    substitution) -> analysis.normalized_record -> knowledge.
                    Workflow A (the SBV vertical). Mirrors chat-transcript.

Both runners accept an optional `run_id` (C0 operator-console run ledger,
server/evidence/run_ledger.py): when set, every step is wrapped so
analysis.workflow_run_stage rows land AS STAGES EXECUTE instead of only in
the end-of-run summary dict. run_id=None (the CLI's path) is unchanged.
"""
# Byline: Claude Code · Sonnet (agent) · 2026-07-20 (C0 run-ledger instrumentation added)

from __future__ import annotations

import functools
import inspect
import json
from pathlib import Path
from typing import Any, cast

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from server.evidence.custody import ArtifactRef, ingest_artifact
from server.contracts.records import NormalizedRecord, finalize
from server.tools.registry import load_builtin_tools, registry
from server.evidence.store import ingest_into_knowledge, record_counts, store_records

# ---------------------------------------------------------------------------
# C0 operator-console run ledger — optional, additive instrumentation.
#
# Runners accept `run_id: str | None = None`. When it's set, every step
# executor is wrapped (stage_start before / stage_finish after) so
# analysis.workflow_run_stage fills in AS STAGES EXECUTE instead of only at
# the end (the old black-box summary dict). When run_id is None (the CLI's
# default path, unchanged), none of this runs — zero behavior change.
# ---------------------------------------------------------------------------


def _ledger_stage_output(name: str | None, ctx: dict[str, Any]) -> dict[str, Any] | None:
    """Typed per-stage JSON captured from the shared workflow ctx right after
    that stage's executor returns. Mirrors the ACTUAL ctx keys each step sets
    (see custody_step/parse_step/store_step/knowledge_step below)."""
    if name == "custody":
        artifact: ArtifactRef | None = ctx.get("artifact")
        if artifact is None:
            return None
        return {
            "sha256": artifact.sha256,
            "artifact_id": artifact.artifact_id,
            "duplicate": artifact.duplicate,
            "blob_key": artifact.blob_key,
        }
    if name == "parse":
        raw = ctx.get("raw_records") or []
        return {
            "parser_id": ctx.get("parser_id"),
            "attempts": ctx.get("attempts", []),
            "schema_recognized": ctx.get("parser_id") is not None,
            "record_count": len(raw),
            "parse_stats": ctx.get("parse_stats", {}),
            # chat-transcript's ctx never sets alt_parse (no fallback lane) —
            # default False so the shape is uniform across both workflows.
            "alt_parse": ctx.get("alt_parse", False),
            "sample_records": [json.dumps(r, default=str)[:500] for r in raw[:3]],
        }
    if name == "store":
        return {"rows_stored": ctx.get("stored"), "table": "analysis.normalized_record"}
    if name == "knowledge":
        return {
            "docs_ingested": ctx.get("knowledge_docs", 0),
            "domain": ctx.get("domain"),
            "skipped": ctx.get("knowledge_skipped", True),
        }
    return None


def _wrap_step_for_ledger(step: Step, seq: int, run_id: str, ctx: dict[str, Any]) -> None:
    """Mutate one Step in place: stage_start before the executor runs,
    stage_finish after (status from StepOutput.success; content from
    .content; typed output from `_ledger_stage_output`). A step exception is
    recorded as a failed stage, then re-raised unchanged.

    functools.wraps preserves the original callable's signature so agno's
    Step._function_has_run_context_param/_function_has_session_state_param
    (which `inspect.signature()` the executor) keep seeing the real function
    — this wrapper adds no new params of its own.
    """
    from server.evidence.run_ledger import stage_finish, stage_start

    original = step.executor
    # Every Step here is built as Step(name=..., executor=<our own function>)
    # a few lines above in build_*_workflow — executor is never None or an
    # agent/team in this file (agno's Step type is a broad union to also
    # support agent/team/generator executors, none of which we use).
    assert original is not None, "C0 ledger wrapping requires a function executor"
    name = step.name
    is_async_original = inspect.iscoroutinefunction(original)

    @functools.wraps(original)
    async def _ledger_wrapped(step_input: StepInput, **kwargs: Any) -> StepOutput:
        stage_start(run_id, seq)
        try:
            result = (
                await original(step_input, **kwargs)  # type: ignore[misc]
                if is_async_original
                else original(step_input, **kwargs)
            )
        except Exception as exc:
            stage_finish(run_id, seq, "failed", content=str(exc), output=None)
            raise
        content = getattr(result, "content", None)
        status = "success" if getattr(result, "success", True) else "failed"
        stage_finish(
            run_id,
            seq,
            status,
            content=str(content) if content is not None else None,
            output=_ledger_stage_output(name, ctx),
        )
        return result  # type: ignore[return-value]

    step.executor = _ledger_wrapped
    step.active_executor = _ledger_wrapped  # type: ignore[assignment]  # agno's own step.py does the same (see _set_active_executor)


# agno.run.base.RunStatus values ('PENDING'/'RUNNING'/'COMPLETED'/'PAUSED'/
# 'CANCELLED'/'ERROR') -> analysis.workflow_run.status CHECK set ('running'/
# 'paused'/'completed'/'failed'). NOTE: none of agno's failure statuses
# actually contain the substring "FAIL" (it's 'ERROR'/'CANCELLED') — mapping
# by table, not by substring match.
_RUN_STATUS_MAP: dict[str, str] = {
    "completed": "completed",
    "paused": "paused",
    "pending": "running",
    "running": "running",
    "error": "failed",
    "cancelled": "failed",
}


def _terminal_status(ctx: dict[str, Any], result: Any) -> str:
    """Map a finished (or aborted) run onto workflow_run.status.

    Two things make this less trivial than `str(result.status)`:

    1. agno's RunStatus does NOT override __str__, so a real enum member
       stringifies to 'RunStatus.completed', not 'completed' — take the
       segment after the last '.' before mapping (a bare '' has no '.',
       rsplit leaves it as-is, falling through to the 'failed' default).
    2. agno's workflow loop sets status=RunStatus.completed as soon as it
       finishes iterating steps WITHOUT AN EXCEPTION — a step returning
       StepOutput(success=False, stop=True) (our parse-step's "no tool
       accepted this file" / "all candidates failed" paths) just halts later
       steps; it does NOT flip the run to an error status. So 'completed' is
       only trusted here once every executed step ALSO reports success=True;
       otherwise this maps to 'failed' regardless of what agno itself says.
    """
    if ctx.get("paused_decision"):  # sms-xml no-silent-substitution pause
        return "paused"
    if result is None:
        return "failed"
    raw = str(getattr(result, "status", "")).rsplit(".", 1)[-1].lower()
    mapped = _RUN_STATUS_MAP.get(raw, "failed")
    if mapped == "completed":
        step_results = getattr(result, "step_results", None) or []
        if any(getattr(s, "success", True) is False for s in step_results):
            return "failed"
    return mapped


def build_chat_transcript_workflow(
    path: str,
    source_meta: dict[str, Any] | None = None,
    domain: str = "platform_design",
    knowledge=None,
) -> tuple[Workflow, dict[str, Any]]:
    """Build the chat-transcript workflow. Steps share `ctx` (closure state);
    each StepOutput carries a human-readable status line for the run log."""
    load_builtin_tools()
    ctx: dict[str, Any] = {
        "path": path,
        "source_meta": source_meta or {},
        "domain": domain,
        "attempts": [],
    }

    def custody_step(step_input: StepInput) -> StepOutput:
        artifact = ingest_artifact(ctx["path"], {**ctx["source_meta"], "workflow": "chat-transcript"})
        ctx["artifact"] = artifact
        note = "duplicate — already in custody" if artifact.duplicate else "new artifact"
        return StepOutput(
            content=f"custody: {artifact.sha256[:12]} ({note}, blob={artifact.blob_key})",
            success=True,
        )

    def parse_step(step_input: StepInput) -> StepOutput:
        p = Path(ctx["path"])
        candidates = registry.resolve("parse.transcript", media_hint=p.name.lower(), size_bytes=p.stat().st_size)
        if not candidates:
            return StepOutput(content=f"parse: NO tool accepts {p.name}", success=False, stop=True)
        last_err: Exception | None = None
        for tool in candidates:
            try:
                result = tool.run({"path": str(p), "source_meta": ctx["source_meta"]})
                ctx["attempts"].append({"tool": tool.id, "ok": True})
                ctx["raw_records"] = result["records"]
                ctx["parse_stats"] = result.get("stats", {})
                ctx["parser_id"] = tool.id
                return StepOutput(
                    content=f"parse: {tool.id} -> {len(result['records'])} records "
                    f"(tried: {[a['tool'] for a in ctx['attempts']]})",
                    success=True,
                )
            except Exception as exc:  # wrong format -> try next same-capability tool
                ctx["attempts"].append({"tool": tool.id, "ok": False, "error": str(exc)})
                last_err = exc
        return StepOutput(
            content=f"parse: ALL candidates failed for {p.name}: {ctx['attempts']} (last: {last_err})",
            success=False,
            stop=True,
        )

    def store_step(step_input: StepInput) -> StepOutput:
        artifact: ArtifactRef = ctx["artifact"]
        if artifact.duplicate and record_counts(artifact.artifact_id)["records"] > 0:
            ctx["stored"] = 0
            ctx["records"] = []
            return StepOutput(
                content="store: duplicate artifact already has records — skipped re-store",
                success=True,
            )
        records = finalize([NormalizedRecord.model_validate(r) for r in ctx["raw_records"]])
        # provenance stamp: which tool parsed, and whether an alternate (backup)
        # parser produced it — a backup parse must never be indistinguishable
        # from the primary
        for rec in records:
            rec.attrs.setdefault("parser_tool", ctx.get("parser_id"))
            if ctx.get("alt_parse"):
                rec.attrs["alt_parse"] = True
                rec.attrs["alt_parse_detail"] = ctx.get("alt_parse_detail")
        ctx["records"] = records
        ctx["stored"] = store_records(records, artifact)
        note = " [ALT-PARSE — primary unavailable, see alt_parse_detail]" if ctx.get("alt_parse") else ""
        return StepOutput(content=f"store: {ctx['stored']} rows -> analysis.normalized_record{note}", success=True)

    async def knowledge_step(step_input: StepInput) -> StepOutput:
        if knowledge is None:
            ctx["knowledge_skipped"] = True
            ctx["knowledge_docs"] = 0
            return StepOutput(content="knowledge: no engine handle passed — skipped (CLI --no-knowledge)", success=True)
        if not ctx.get("records"):
            ctx["knowledge_skipped"] = True
            ctx["knowledge_docs"] = 0
            return StepOutput(content="knowledge: no new records — skipped", success=True)
        n = await ingest_into_knowledge(knowledge, ctx["records"], ctx["artifact"], ctx["domain"])
        ctx["knowledge_skipped"] = False
        ctx["knowledge_docs"] = n
        return StepOutput(content=f"knowledge: {n} conversation doc(s) -> domain={ctx['domain']}", success=True)

    wf = Workflow(
        name="chat-transcript",
        description="AI-chat transcript ingestion: custody -> parse -> store -> knowledge",
        steps=[
            Step(name="custody", executor=custody_step),
            Step(name="parse", executor=parse_step),
            Step(name="store", executor=store_step),
            Step(name="knowledge", executor=knowledge_step),
        ],
    )
    return wf, ctx


def build_sms_xml_workflow(
    path: str,
    source_meta: dict[str, Any] | None = None,
    domain: str = "timeline_relationship",
    knowledge=None,
    allow_fallback: bool = False,
) -> tuple[Workflow, dict[str, Any]]:
    """Workflow A — the SBV SMS-XML vertical. Same custody->parse->store->knowledge
    spine as chat-transcript, but resolves capability `parse.sms-xml`: the
    registry returns SBV first (messages.sms-xml-sbv) and the pure-Python parser
    (messages.sms-xml) as fallback.

    NO SILENT SUBSTITUTION (owner mandate 2026-07-02): if the PRIMARY tool fails,
    the workflow STOPS by default and says exactly what failed. Passing
    allow_fallback=True permits the substitution loop to continue autonomously,
    but the run and every stored record are flagged as an ALTERNATE-PARSER parse
    with the primary's failure recorded — a backup parse must never be
    indistinguishable from the primary."""
    load_builtin_tools()
    ctx: dict[str, Any] = {
        "path": path,
        "source_meta": source_meta or {},
        "domain": domain,
        "attempts": [],
        "alt_parse": False,
        "alt_parse_detail": None,
    }

    def custody_step(step_input: StepInput) -> StepOutput:
        artifact = ingest_artifact(ctx["path"], {**ctx["source_meta"], "workflow": "sms-xml"})
        ctx["artifact"] = artifact
        note = "duplicate — already in custody" if artifact.duplicate else "new artifact"
        return StepOutput(
            content=f"custody: {artifact.sha256[:12]} ({note}, blob={artifact.blob_key})",
            success=True,
        )

    def parse_step(step_input: StepInput) -> StepOutput:
        p = Path(ctx["path"])
        candidates = registry.resolve("parse.sms-xml", media_hint=p.name.lower(), size_bytes=p.stat().st_size)
        if not candidates:
            return StepOutput(content=f"parse: NO tool accepts {p.name}", success=False, stop=True)
        primary = candidates[0]
        last_err: Exception | None = None
        for tool in candidates:
            try:
                result = tool.run({"path": str(p), "source_meta": ctx["source_meta"]})
                ctx["attempts"].append({"tool": tool.id, "ok": True})
                ctx["raw_records"] = result["records"]
                ctx["parse_stats"] = result.get("stats", {})
                ctx["parser_id"] = tool.id
                if tool.id != primary.id:
                    # substitution happened — only reachable with allow_fallback=True
                    ctx["alt_parse"] = True
                    ctx["alt_parse_detail"] = {
                        "primary": primary.id,
                        "primary_error": next((a["error"] for a in ctx["attempts"] if a["tool"] == primary.id), None),
                        "used": tool.id,
                    }
                    return StepOutput(
                        content=f"parse: ALTERNATE PARSER — primary {primary.id} unavailable "
                        f"({ctx['alt_parse_detail']['primary_error']}); backup {tool.id} parsed "
                        f"{len(result['records'])} records (allow_fallback=True). "
                        f"Attempts: {ctx['attempts']}",
                        success=True,
                    )
                return StepOutput(
                    content=f"parse: {tool.id} (primary) -> {len(result['records'])} records",
                    success=True,
                )
            except Exception as exc:
                ctx["attempts"].append({"tool": tool.id, "ok": False, "error": str(exc)})
                last_err = exc
                if tool.id == primary.id and not ctx.get("allow_fallback"):
                    # PAUSE, don't fail: surface the decision with its options.
                    # Interactive: pick an option and rerun. Autonomous lane: queue
                    # this verbatim to APPROVALS.md and work on something else.
                    ctx["paused_decision"] = {
                        "reason": f"primary parser {primary.id} failed",
                        "error": str(exc),
                        "options": {
                            "a": f"fix/restore the primary ({primary.id}) and rerun",
                            "b": f"rerun with allow_fallback=True -> use {[c.id for c in candidates[1:]]} "
                            f"(run + records flagged alt_parse)",
                            "c": "abort this file (leave for a later batch)",
                        },
                    }
                    return StepOutput(
                        content=f"parse: PAUSED awaiting decision — primary {primary.id} FAILED for "
                        f"{p.name}: {exc}. Options: (a) fix primary; (b) allow_fallback=True, "
                        f"flagged alt_parse; (c) abort. No silent substitution.",
                        success=False,
                        stop=True,
                    )
        return StepOutput(
            content=f"parse: ALL candidates failed for {p.name}: {ctx['attempts']} (last: {last_err})",
            success=False,
            stop=True,
        )

    def store_step(step_input: StepInput) -> StepOutput:
        artifact: ArtifactRef = ctx["artifact"]
        if artifact.duplicate and record_counts(artifact.artifact_id)["records"] > 0:
            ctx["stored"] = 0
            ctx["records"] = []
            return StepOutput(
                content="store: duplicate artifact already has records — skipped re-store",
                success=True,
            )
        records = finalize([NormalizedRecord.model_validate(r) for r in ctx["raw_records"]])
        # provenance stamp: which tool parsed, and whether an alternate (backup)
        # parser produced it — a backup parse must never be indistinguishable
        # from the primary
        for rec in records:
            rec.attrs.setdefault("parser_tool", ctx.get("parser_id"))
            if ctx.get("alt_parse"):
                rec.attrs["alt_parse"] = True
                rec.attrs["alt_parse_detail"] = ctx.get("alt_parse_detail")
        ctx["records"] = records
        ctx["stored"] = store_records(records, artifact)
        note = " [ALT-PARSE — primary unavailable, see alt_parse_detail]" if ctx.get("alt_parse") else ""
        return StepOutput(content=f"store: {ctx['stored']} rows -> analysis.normalized_record{note}", success=True)

    async def knowledge_step(step_input: StepInput) -> StepOutput:
        if knowledge is None:
            ctx["knowledge_skipped"] = True
            ctx["knowledge_docs"] = 0
            return StepOutput(content="knowledge: no engine handle passed — skipped (CLI --no-knowledge)", success=True)
        if not ctx.get("records"):
            ctx["knowledge_skipped"] = True
            ctx["knowledge_docs"] = 0
            return StepOutput(content="knowledge: no new records — skipped", success=True)
        n = await ingest_into_knowledge(knowledge, ctx["records"], ctx["artifact"], ctx["domain"])
        ctx["knowledge_skipped"] = False
        ctx["knowledge_docs"] = n
        return StepOutput(content=f"knowledge: {n} conversation doc(s) -> domain={ctx['domain']}", success=True)

    wf = Workflow(
        name="sms-xml",
        description="SMS-XML ingestion (SBV primary / custom fallback): custody -> parse -> store -> knowledge",
        steps=[
            Step(name="custody", executor=custody_step),
            Step(name="parse", executor=parse_step),
            Step(name="store", executor=store_step),
            Step(name="knowledge", executor=knowledge_step),
        ],
    )
    return wf, ctx


async def run_sms_xml(
    path: str,
    source_meta: dict[str, Any] | None = None,
    domain: str = "timeline_relationship",
    knowledge=None,
    allow_fallback: bool = False,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run the SMS-XML vertical (Workflow A) end-to-end; return a verifiable summary.

    allow_fallback=False (default): primary-parser failure PAUSES the run with
    options (fix primary / allow fallback / abort). allow_fallback=True:
    substitution may proceed, but the summary and every stored record carry
    alt_parse=True + the primary's failure detail.

    run_id (C0 ledger, optional): see module docstring block above
    `_ledger_stage_output` — None (default) is a strict no-op."""
    wf, ctx = build_sms_xml_workflow(path, source_meta, domain, knowledge, allow_fallback=allow_fallback)
    ctx["allow_fallback"] = allow_fallback
    if run_id is not None:
        # wf.steps is always the plain list[Step] we just built above (agno's
        # own declared type is a broad union that also covers Loop/Parallel/
        # Router/Workflow-as-step, none of which build_*_workflow() uses).
        for seq, step in enumerate(cast("list[Step]", wf.steps), start=1):
            _wrap_step_for_ledger(step, seq, run_id, ctx)

    summary: dict[str, Any] | None = None
    result: Any = None
    exc_message: str | None = None
    try:
        result = await wf.arun(input=f"ingest sms-xml: {path}")
        artifact: ArtifactRef | None = ctx.get("artifact")
        summary = {
            "workflow": "sms-xml",
            "status": str(getattr(result, "status", "unknown")),
            "artifact_id": artifact.artifact_id if artifact else None,
            "sha256": artifact.sha256 if artifact else None,
            "duplicate": artifact.duplicate if artifact else None,
            "parser": ctx.get("parser_id"),
            "alt_parse": ctx.get("alt_parse", False),
            "alt_parse_detail": ctx.get("alt_parse_detail"),
            "parse_attempts": ctx.get("attempts", []),
            "parse_stats": ctx.get("parse_stats", {}),
            "records_stored": ctx.get("stored", 0),
            "step_log": [s.content for s in getattr(result, "step_results", []) if getattr(s, "content", None)],
        }
        return summary
    except Exception as exc:
        exc_message = str(exc)
        raise
    finally:
        if run_id is not None:
            from server.evidence.run_ledger import finish_run

            artifact = ctx.get("artifact")
            finish_run(
                run_id,
                _terminal_status(ctx, result),
                summary=summary,
                error=exc_message,
                sha256=artifact.sha256 if artifact else None,
                artifact_id=artifact.artifact_id if artifact else None,
            )


NAMED_WORKFLOWS: dict[str, str] = {
    "chat-transcript": "AI-chat exports -> custody -> parse -> analysis + knowledge (bootstrap vertical)",
    "sms-xml": "SMS Backup & Restore XML (SBV primary / custom fallback) -> custody -> parse -> analysis + knowledge (Workflow A)",
}

# C0 operator console: seed order for analysis.workflow_run_stage per named
# workflow (both build_* functions above wire identical Step name/order —
# custody -> parse -> store -> knowledge). Keep in lockstep with the two
# build_*_workflow functions if their Step lists ever diverge.
WORKFLOW_STAGE_NAMES: dict[str, list[str]] = {
    "chat-transcript": ["custody", "parse", "store", "knowledge"],
    "sms-xml": ["custody", "parse", "store", "knowledge"],
}


async def run_chat_transcript(
    path: str,
    source_meta: dict[str, Any] | None = None,
    domain: str = "platform_design",
    knowledge=None,
    run_id: str | None = None,
) -> dict[str, Any]:
    """Run the chat-transcript vertical end-to-end; return a verifiable summary.

    run_id (C0 ledger, optional): see module docstring block above
    `_ledger_stage_output` — None (default) is a strict no-op."""
    wf, ctx = build_chat_transcript_workflow(path, source_meta, domain, knowledge)
    if run_id is not None:
        # wf.steps is always the plain list[Step] we just built above (agno's
        # own declared type is a broad union that also covers Loop/Parallel/
        # Router/Workflow-as-step, none of which build_*_workflow() uses).
        for seq, step in enumerate(cast("list[Step]", wf.steps), start=1):
            _wrap_step_for_ledger(step, seq, run_id, ctx)

    summary: dict[str, Any] | None = None
    result: Any = None
    exc_message: str | None = None
    try:
        result = await wf.arun(input=f"ingest transcript: {path}")
        artifact: ArtifactRef | None = ctx.get("artifact")
        summary = {
            "workflow": "chat-transcript",
            "status": str(getattr(result, "status", "unknown")),
            "artifact_id": artifact.artifact_id if artifact else None,
            "sha256": artifact.sha256 if artifact else None,
            "duplicate": artifact.duplicate if artifact else None,
            "parser": ctx.get("parser_id"),
            "parse_attempts": ctx.get("attempts", []),
            "records_stored": ctx.get("stored", 0),
            "step_log": [s.content for s in getattr(result, "step_results", []) if getattr(s, "content", None)],
        }
        return summary
    except Exception as exc:
        exc_message = str(exc)
        raise
    finally:
        if run_id is not None:
            from server.evidence.run_ledger import finish_run

            artifact = ctx.get("artifact")
            finish_run(
                run_id,
                _terminal_status(ctx, result),
                summary=summary,
                error=exc_message,
                sha256=artifact.sha256 if artifact else None,
                artifact_id=artifact.artifact_id if artifact else None,
            )
