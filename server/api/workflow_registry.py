"""Register the evidence workflows with AgentOS so they are actually reachable.

WHY THIS EXISTS (2026-08-01)
============================
`server/evidence/workflows.py` builds real `agno.workflow.Workflow` objects —
custody -> parse -> store -> knowledge, with `on_error=OnError.fail` on every
Step and a supervised HITL gate that pauses the run after each non-final stage.
All of that was written, tested, and then **never handed to AgentOS**.

`AgentOS.__init__` accepts `workflows: Optional[List[Workflow | RemoteWorkflow |
WorkflowFactory]]` (verified against the pinned agno 2.8.0). `main.py` never
passed it. Net effect, measured live: `GET /workflows` returns `[]`, the Studio
Workflows panel is empty, and `POST /workflows/{id}/runs` does not exist — so
the only way to run an ingest was a CLI/script call. The workflows existed but
were unreachable from the platform itself.

WHY A FACTORY AND NOT A PLAIN Workflow
--------------------------------------
`build_chat_transcript_workflow(path=...)` closes over a specific file path:
every Step executor reads from a `ctx` dict created at build time. That makes it
inherently per-request — there is no meaningful "static" instance to register.

agno's answer is `WorkflowFactory`, whose own docstring reads: "A factory that
produces a Workflow per request. Factories live alongside workflows in
``AgentOS(workflows=[...])``. On each request, AgentOS invokes the factory with
a RequestContext and uses the returned Workflow for that request."

So the factory receives the caller's validated input (`RequestContext.input`,
shaped by `input_schema`) and builds a correctly-scoped Workflow per run. That
is exactly the shape these builders already wanted.

WHAT THIS DELIBERATELY DOES NOT DO
----------------------------------
It does not change any Step, executor, or the custody/HITL semantics. It is a
registration layer only: same workflows, now reachable over the API and visible
in the UI, with `mode` exposed so a caller can ask for the existing supervised
gate.
"""
# Byline amendment: Codex · GPT-5 · 2026-08-18 (native evidence projector composition)

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Literal, TypeVar

from agno.utils.log import log_info, log_warning
from agno.workflow.factory import WorkflowFactory
from pydantic import BaseModel, Field


class ChatTranscriptInput(BaseModel):
    """Caller-supplied input for the chat-transcript ingest workflow."""

    path: str = Field(..., description="Absolute path to the transcript file to ingest.")
    domain: str = Field("platform_design", description="Knowledge domain tag for the ingested records.")
    custody_tier: str = Field(
        "full",
        description="Custody depth: 'full' (default) or 'light'. Chat uploads via /v1/runs use 'light'.",
    )
    mode: str = Field(
        "auto",
        description="'auto' runs straight through; 'supervised' pauses after each non-final stage for approval.",
    )


class SmsXmlInput(BaseModel):
    """Caller-supplied input for the SMS-XML ingest workflow."""

    path: str = Field(..., description="Absolute path to the SMS Backup & Restore XML file.")
    source_principal: str = Field(..., min_length=1, description="Owner account/device identity in the export.")
    caller_owns_conversation: Literal[True] = Field(
        ..., description="Authenticated owner assertion required for first-party classification."
    )
    domain: str = Field("evidence", description="Knowledge domain tag for the ingested records.")
    custody_tier: str = Field("full", description="Custody depth: 'full' (default) or 'light'.")
    mode: str = Field("auto", description="'auto' or 'supervised' (pause for approval between stages).")


_InputModel = TypeVar("_InputModel", bound=BaseModel)


def _input_of(ctx: Any, schema: type[_InputModel]) -> _InputModel:
    """Coerce ``RequestContext.input`` to the declared schema.

    Generic on the schema so callers get the concrete model back: annotating
    the return as plain ``BaseModel`` loses the field types, and every
    ``args.path`` / ``args.domain`` access in the factories below then fails
    type-checking with "BaseModel has no attribute ...".

    agno validates against ``input_schema`` and normally hands back a model
    instance, but it passes a plain dict through when no schema applied. Accept
    both so a caller posting raw JSON does not 500 inside the factory.
    """
    data = getattr(ctx, "input", None)
    if isinstance(data, schema):
        return data
    if isinstance(data, BaseModel):
        return schema.model_validate(data.model_dump())
    return schema.model_validate(data or {})


def build_workflow_factories(db: Any, knowledge: Any, native_projector: Any | None = None) -> List[WorkflowFactory]:
    """Build the WorkflowFactory list for ``AgentOS(workflows=...)``.

    ``db`` is the operational store (**PostgresDb** since the 2026-08-04
    flatten, ADR-0043 decision 3; was ~~SurrealDb~~) — the same db the agents
    use, so workflow runs land beside agent sessions rather than in the admin
    plane.
    ``knowledge`` is the one-time boot snapshot from ``_knowledge_handle``; it
    may be None, in which case the knowledge Step self-skips (it already handles
    a None engine by design).

    Import of the builders is deferred to call time: `server/evidence/` pulls in
    the custody/parse/store chain, and a module-scope import here would put that
    on the critical boot path for an import that is only needed once at assembly.
    """
    from server.evidence.workflows import (
        build_chat_transcript_workflow,
        build_sms_xml_workflow,
    )

    def _ledgered(workflow_id: str, args: Any, wf: Any, wf_ctx: dict[str, Any]) -> Any:
        """Give an AgentOS-launched workflow the SAME ledger + controls as
        ``/v1/runs`` (Codex C-03, fixed 2026-08-04).

        These factories used to return the bare workflow: no
        ``ops.workflow_run`` row, so a Studio-launched ingest was invisible to
        the operator console and could not be aborted/continued/retried; and
        the parsed ``mode`` was discarded, so ``mode='supervised'`` validated
        fine and then ran straight through without ever pausing for approval —
        a HITL gate that silently was not one.

        Ledger creation must never block the ingest: if Postgres is
        unreachable the workflow still runs, unledgered, with a loud warning —
        same rule that keeps ``registered_workflows`` from crash-looping boot.
        """
        from server.evidence.workflows import attach_ledger

        try:
            from server.evidence.run_ledger import create_run

            run_id = create_run(
                workflow=workflow_id,
                mode=args.mode,
                source_name=Path(args.path).name,
                source_path=args.path,
                domain=args.domain,
                custody_tier=args.custody_tier,
            )
            attach_ledger(wf, wf_ctx, run_id, args.mode)
            log_info(f"workflow {workflow_id}: ledger run {run_id} (mode={args.mode})")
        except Exception as exc:  # noqa: BLE001 — never block the ingest
            log_warning(
                f"workflow {workflow_id}: could not create a ledger run ({exc!r}); "
                "running WITHOUT ledger or supervised gates"
            )
        return wf

    def _chat_factory(ctx: Any):
        args = _input_of(ctx, ChatTranscriptInput)
        wf, wf_ctx = build_chat_transcript_workflow(
            path=args.path,
            domain=args.domain,
            knowledge=knowledge,
            custody_tier=args.custody_tier,
        )
        return _ledgered("chat-transcript", args, wf, wf_ctx)

    def _sms_factory(ctx: Any):
        args = _input_of(ctx, SmsXmlInput)
        wf, wf_ctx = build_sms_xml_workflow(
            path=args.path,
            source_meta={
                "message_corpus": "first_party",
                "source_principal": args.source_principal,
                "caller_owns_conversation": args.caller_owns_conversation,
            },
            domain=args.domain,
            knowledge=native_projector,
            custody_tier=args.custody_tier,
        )
        return _ledgered("sms-xml", args, wf, wf_ctx)

    return [
        WorkflowFactory(
            id="chat-transcript",
            db=db,
            factory=_chat_factory,
            name="Chat Transcript Ingestion",
            description="custody -> parse -> store -> knowledge for an AI-chat or messaging transcript.",
            input_schema=ChatTranscriptInput,
        ),
        WorkflowFactory(
            id="sms-xml",
            db=db,
            factory=_sms_factory,
            name="SMS XML Ingestion",
            description="custody -> parse -> store -> knowledge for an SMS Backup & Restore XML export.",
            input_schema=SmsXmlInput,
        ),
    ]


def registered_workflows(db: Any, knowledge: Any, native_projector: Any | None = None) -> List[WorkflowFactory]:
    """Same as :func:`build_workflow_factories`, but never fatal at boot.

    Registration is a convenience surface, not the evidence spine — the CLI and
    `/v1/runs` paths keep working regardless. A failure here must not take the
    whole API down (the platform crash-looped once today already from a boot-path
    error), so this logs loudly and returns an empty list instead of raising.
    """
    try:
        factories = build_workflow_factories(db, knowledge, native_projector)
        log_info(f"registered {len(factories)} workflow factories: {[f.id for f in factories]}")
        return factories
    except Exception as exc:  # noqa: BLE001 - boot resilience is the whole point
        log_warning(f"workflow registration failed, continuing without it: {type(exc).__name__}: {exc}")
        return []
