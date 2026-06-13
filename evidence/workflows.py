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

  (P4 adds sms-xml via SBV as Workflow A.)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agno.workflow import Step, Workflow
from agno.workflow.types import StepInput, StepOutput

from evidence.custody import ArtifactRef, ingest_artifact
from evidence.normalize import NormalizedRecord, finalize
from evidence.registry import load_builtin_tools, registry
from evidence.store import ingest_into_knowledge, record_counts, store_records


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
        ctx["records"] = records
        ctx["stored"] = store_records(records, artifact)
        return StepOutput(content=f"store: {ctx['stored']} rows -> analysis.normalized_record", success=True)

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


NAMED_WORKFLOWS: dict[str, str] = {
    "chat-transcript": "AI-chat exports -> custody -> parse -> analysis + knowledge (bootstrap vertical)",
    # "sms-xml": arrives in P4 as Workflow A (SBV custody-gated vertical)
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
