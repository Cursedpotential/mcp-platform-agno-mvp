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
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from server.evidence.custody import ArtifactRef, ingest_artifact
from server.evidence.normalize import NormalizedRecord, finalize
from server.evidence.registry import load_builtin_tools, registry
from server.evidence.store import ingest_into_knowledge, record_counts, store_records


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
            return StepOutput(content="knowledge: no engine handle passed — skipped (CLI --no-knowledge)", success=True)
        if not ctx.get("records"):
            return StepOutput(content="knowledge: no new records — skipped", success=True)
        n = await ingest_into_knowledge(knowledge, ctx["records"], ctx["artifact"], ctx["domain"])
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
            return StepOutput(content="knowledge: no engine handle passed — skipped (CLI --no-knowledge)", success=True)
        if not ctx.get("records"):
            return StepOutput(content="knowledge: no new records — skipped", success=True)
        n = await ingest_into_knowledge(knowledge, ctx["records"], ctx["artifact"], ctx["domain"])
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
) -> dict[str, Any]:
    """Run the SMS-XML vertical (Workflow A) end-to-end; return a verifiable summary.

    allow_fallback=False (default): primary-parser failure PAUSES the run with
    options (fix primary / allow fallback / abort). allow_fallback=True:
    substitution may proceed, but the summary and every stored record carry
    alt_parse=True + the primary's failure detail."""
    wf, ctx = build_sms_xml_workflow(path, source_meta, domain, knowledge, allow_fallback=allow_fallback)
    ctx["allow_fallback"] = allow_fallback
    result = await wf.arun(input=f"ingest sms-xml: {path}")
    artifact: ArtifactRef | None = ctx.get("artifact")
    return {
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


NAMED_WORKFLOWS: dict[str, str] = {
    "chat-transcript": "AI-chat exports -> custody -> parse -> analysis + knowledge (bootstrap vertical)",
    "sms-xml": "SMS Backup & Restore XML (SBV primary / custom fallback) -> custody -> parse -> analysis + knowledge (Workflow A)",
}


async def run_chat_transcript(
    path: str,
    source_meta: dict[str, Any] | None = None,
    domain: str = "platform_design",
    knowledge=None,
) -> dict[str, Any]:
    """Run the chat-transcript vertical end-to-end; return a verifiable summary."""
    wf, ctx = build_chat_transcript_workflow(path, source_meta, domain, knowledge)
    result = await wf.arun(input=f"ingest transcript: {path}")
    artifact: ArtifactRef | None = ctx.get("artifact")
    return {
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
