"""
server/temporal/workflows.py — ``ChatTranscriptIngest``, the P1 workflow.

INERT: nothing dispatches to this. The live path remains
``server/evidence/workflows.py::run_chat_transcript`` (:940).

IMPORT RULE (plan §4 risk 2): this module imports ONLY ``temporalio`` + stdlib +
the dataclass types from ``server.temporal.activities``. Workflow code is replayed
from history, so it must be deterministic and must not touch env, network or DB —
including at import time. The in-repo precedent for keeping that boundary is
``server/evidence/run_ledger.py:31`` (``db_url`` imported inside ``_get_engine()``
"to avoid import-time env coupling"); the counter-examples that must stay out of a
workflow module's import graph are ``server/core/url.py:27`` (module-level
``build_db_url()`` reading six env vars) and ``server/core/session.py:94-118,
214-233`` (module-level ``getenv`` for SurrealDB / Weaviate / OpenRouter / NVIDIA,
several with hardcoded tailnet IP defaults). ``activities.py`` is import-safe by
construction — every ``server.*`` import lives inside an Activity body — and the
``workflow.unsafe.imports_passed_through()`` block below tells the sandbox to
reuse the host module rather than re-import it under replay.

WHAT THIS ENCODES BEYOND THE CURRENT PIPELINE
---------------------------------------------

1. **Declared retries.** Each stage carries a ``RetryPolicy`` instead of a
   hand-rolled loop. The numbers mirror what ``store.py`` already does
   (``_TRANSIENT_BACKOFFS_S = (2.0, 8.0, 30.0)`` at :89 — four total attempts,
   ~2s/8s/30s), expressed as ``initial_interval=2s, backoff_coefficient=4.0``.

2. **Push HITL, no poll.** ``supervised=True`` gates every non-final stage the way
   ``server/evidence/workflows.py:232 _wrap_step_for_run_control`` does today, but
   waits on a Signal via ``workflow.wait_condition`` instead of the 2s poll loop at
   :297-312. This deletes both the poll and the 24h ``_GATE_POLL_CEILING_S`` fail-
   closed branch (:223). Per plan §4 risk 3 the ceiling is replaced by a NOTIFY
   timer, not by silence: every ``_GATE_NOTIFY_AFTER`` the workflow logs that it is
   still waiting, and keeps waiting. A gate that aborts an operator's run because
   they were in a hearing for two days is the hazard being removed; a run paused
   forever with nobody told is the hazard being avoided.

3. **Immediate abort.** An abort Signal ends the run at the current boundary
   without waiting for a poll tick.

Postgres remains authority throughout: the ledger writes stay in the Activities'
underlying platform functions, and this workflow's output is a summary, not a
report. ``run_report.py:53 build_run_report`` over ``ops.workflow_run*`` is still
the authoritative durable report; Temporal history is diagnostic telemetry
(``run_report.py:154``'s ``"authority": "diagnostic_only"``).

Byline: Claude Code · Opus 5 · 2026-08-23
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from server.temporal.activities import (
        CustodyParams,
        CustodyResult,
        KnowledgeParams,
        KnowledgeResult,
        ParseParams,
        ParseResult,
        StoreParams,
        StoreResult,
        custody_activity,
        knowledge_activity,
        parse_activity,
        store_activity,
    )

__all__ = [
    "ChatTranscriptInput",
    "ChatTranscriptOutput",
    "ChatTranscriptIngest",
    "GATE_APPROVE",
    "GATE_ABORT",
    "TASK_QUEUE",
]

TASK_QUEUE = "evidence-ingest"

GATE_APPROVE = "approve"
GATE_ABORT = "abort"

# Mirrors store.py:89 _TRANSIENT_BACKOFFS_S = (2.0, 8.0, 30.0): first retry after
# ~2s, then ~8s, then ~32s, four attempts total.
_BACKOFF_INITIAL = timedelta(seconds=2)
_BACKOFF_COEFFICIENT = 4.0
_BACKOFF_MAX_INTERVAL = timedelta(seconds=60)

_CUSTODY_RETRY = RetryPolicy(
    initial_interval=_BACKOFF_INITIAL,
    backoff_coefficient=_BACKOFF_COEFFICIENT,
    maximum_interval=_BACKOFF_MAX_INTERVAL,
    maximum_attempts=4,
)
# Parse failure after the whole candidate chain is a real "no tool accepts this"
# verdict, not a transient — retrying it is waiting for nothing.
_PARSE_RETRY = RetryPolicy(
    initial_interval=_BACKOFF_INITIAL,
    backoff_coefficient=_BACKOFF_COEFFICIENT,
    maximum_interval=_BACKOFF_MAX_INTERVAL,
    maximum_attempts=2,
)
_STORE_RETRY = RetryPolicy(
    initial_interval=_BACKOFF_INITIAL,
    backoff_coefficient=_BACKOFF_COEFFICIENT,
    maximum_interval=_BACKOFF_MAX_INTERVAL,
    maximum_attempts=4,
)
# The stage that actually fails in prod (a Weaviate outage — workflows.py:36-44).
# More attempts and a longer ceiling than the rest: it is the one worth waiting on.
_KNOWLEDGE_RETRY = RetryPolicy(
    initial_interval=_BACKOFF_INITIAL,
    backoff_coefficient=_BACKOFF_COEFFICIENT,
    maximum_interval=timedelta(minutes=5),
    maximum_attempts=6,
)

_CUSTODY_TIMEOUT = timedelta(minutes=30)  # sha256 + write-once blob copy of a large export
_PARSE_TIMEOUT = timedelta(minutes=30)
_STORE_TIMEOUT = timedelta(minutes=30)
_KNOWLEDGE_TIMEOUT = timedelta(hours=2)  # render + embed + ainsert every conversation

# Plan §4 risk 3: notify, never abort. The operator is told the run is still
# parked; the run keeps waiting.
_GATE_NOTIFY_AFTER = timedelta(days=7)


@dataclass
class ChatTranscriptInput:
    """Workflow input.

    Defaults follow the live chat-transcript vertical, not the builder's own
    signature: ``run_routes.py:114`` defaults this workflow's domain to
    ``context`` and ``:124`` defaults its custody tier to ``light`` (the AI-chat
    knowledge lane is the owner's story, not evidence)."""

    path: str
    source_meta: dict[str, Any] = field(default_factory=dict)
    lane: str = "context"
    custody_tier: str = "light"
    parent_run_id: str | None = None
    run_id: str | None = None
    supervised: bool = False


@dataclass
class ChatTranscriptOutput:
    """Summary of the run. Deliberately NOT a report — ``ops.workflow_run*`` is."""

    status: str
    artifact_id: str | None = None
    sha256: str | None = None
    duplicate: bool | None = None
    parser_id: str | None = None
    records_parsed: int = 0
    records_stored: int = 0
    docs_ingested: int = 0
    knowledge_harness: str | None = None
    knowledge_skipped: bool | None = None
    aborted_at: str | None = None
    step_log: list[str] = field(default_factory=list)


@workflow.defn(name="ChatTranscriptIngest")
class ChatTranscriptIngest:
    """custody -> parse -> store -> knowledge, durably.

    Stage order and semantics are a 1:1 restatement of
    ``build_chat_transcript_workflow`` (``server/evidence/workflows.py:588``),
    whose four ``Step``s are declared at :673-676 with ``on_error="fail"`` so an
    uncaught exception halts the run instead of cascading into later steps with
    broken ctx. A Temporal Activity that raises past its retries fails the
    workflow, which is the same contract without the agno footgun documented at
    :49-63 (``Step.on_error`` actually defaults to ``skip``)."""

    def __init__(self) -> None:
        self._gate: str | None = None
        self._stage: str = "pending"
        self._aborted_at: str | None = None

    # -- signals / queries --------------------------------------------------

    @workflow.signal(name="gate_decision")
    def gate_decision(self, decision: str) -> None:
        """Operator decision for the stage boundary currently being gated.

        Replaces the ``ops.workflow_run.gate_state`` column write + 2s poll
        (``run_ledger.py:174 set_gate`` / ``:205 read_gate``,
        ``workflows.py:297-312``). P2 re-points the EXISTING endpoints —
        ``run_routes.py:567 continue_run``, ``:587 abort_run``, ``:617 retry_run``
        — at this signal; it does not add a HITL surface. The operator decision
        stays evidentiary and keeps being written to
        ``ops.workflow_run_review_action`` on the platform side (plan §P2).

        An unrecognized value is ignored rather than raising: a signal handler
        that raises fails the whole workflow task, which would turn an operator's
        typo into a dead run."""
        normalized = (decision or "").strip().lower()
        if normalized in (GATE_APPROVE, GATE_ABORT):
            self._gate = normalized
        else:
            workflow.logger.warning("gate_decision: ignoring unrecognized value %r", decision)

    @workflow.query(name="status")
    def status(self) -> dict[str, Any]:
        """Current stage + gate state, for operations. Not a report."""
        return {"stage": self._stage, "gate": self._gate, "aborted_at": self._aborted_at}

    # -- run ----------------------------------------------------------------

    @workflow.run
    async def run(self, params: ChatTranscriptInput) -> ChatTranscriptOutput:
        step_log: list[str] = []

        self._stage = "custody"
        custody: CustodyResult = await workflow.execute_activity(
            custody_activity,
            CustodyParams(
                path=params.path,
                source_meta=params.source_meta,
                custody_tier=params.custody_tier,
            ),
            start_to_close_timeout=_CUSTODY_TIMEOUT,
            retry_policy=_CUSTODY_RETRY,
        )
        step_log.append(
            f"custody: {custody.sha256[:12]} "
            f"({'duplicate — already in custody' if custody.duplicate else 'new artifact'}, "
            f"blob={custody.blob_key})"
        )
        if params.supervised and not await self._gate_open("custody"):
            return self._aborted(step_log, custody=custody)

        self._stage = "parse"
        parse: ParseResult = await workflow.execute_activity(
            parse_activity,
            ParseParams(path=params.path, source_meta=params.source_meta),
            start_to_close_timeout=_PARSE_TIMEOUT,
            retry_policy=_PARSE_RETRY,
        )
        step_log.append(
            f"parse: {parse.parser_id} -> {parse.record_count} records "
            f"(tried: {[a.get('tool') for a in parse.attempts]})"
        )
        if params.supervised and not await self._gate_open("parse"):
            return self._aborted(step_log, custody=custody, parse=parse)

        self._stage = "store"
        store: StoreResult = await workflow.execute_activity(
            store_activity,
            StoreParams(
                artifact_id=custody.artifact_id,
                records=parse.records,
                parser_id=parse.parser_id,
                parent_run_id=params.parent_run_id,
            ),
            start_to_close_timeout=_STORE_TIMEOUT,
            retry_policy=_STORE_RETRY,
        )
        step_log.append(store.detail)
        if params.supervised and not await self._gate_open("store"):
            return self._aborted(step_log, custody=custody, parse=parse, store=store)

        # Final stage — never gated, matching _wrap_step_for_run_control's
        # "pause after every NON-FINAL stage" rule (workflows.py:232).
        self._stage = "knowledge"
        knowledge: KnowledgeResult = await workflow.execute_activity(
            knowledge_activity,
            KnowledgeParams(
                artifact_id=custody.artifact_id,
                lane=params.lane,
                run_meta={
                    "run_id": params.run_id,
                    "parent_run_id": params.parent_run_id,
                    "dedupe_noop": store.dedupe_noop,
                },
            ),
            start_to_close_timeout=_KNOWLEDGE_TIMEOUT,
            retry_policy=_KNOWLEDGE_RETRY,
        )
        step_log.append(knowledge.detail)

        self._stage = "completed"
        return ChatTranscriptOutput(
            status="completed",
            artifact_id=custody.artifact_id,
            sha256=custody.sha256,
            duplicate=custody.duplicate,
            parser_id=parse.parser_id,
            records_parsed=parse.record_count,
            records_stored=store.stored,
            docs_ingested=knowledge.docs_ingested,
            knowledge_harness=knowledge.harness,
            knowledge_skipped=knowledge.skipped,
            step_log=step_log,
        )

    # -- gate ---------------------------------------------------------------

    async def _gate_open(self, stage: str) -> bool:
        """Block until the operator approves or aborts. Returns False on abort.

        No poll, no ceiling. ``wait_condition`` is woken by the signal handler,
        so a decision arriving mid-Activity is not lost — the bonus the current
        boundary-only design cannot give (plan §P2)."""
        self._gate = None
        while self._gate is None:
            try:
                await workflow.wait_condition(
                    lambda: self._gate is not None,
                    timeout=_GATE_NOTIFY_AFTER,
                )
            except asyncio.TimeoutError:
                # NOTIFY, do not abort (plan §4 risk 3). Falls through and waits
                # again; the log line is the operator's nudge.
                workflow.logger.warning(
                    "supervised gate after stage %s has been waiting %s with no decision — "
                    "still waiting (this never fails the run closed)",
                    stage,
                    _GATE_NOTIFY_AFTER,
                )
        if self._gate == GATE_ABORT:
            self._aborted_at = stage
            workflow.logger.info("supervised gate: operator aborted after stage %s", stage)
            return False
        return True

    def _aborted(
        self,
        step_log: list[str],
        *,
        custody: CustodyResult | None = None,
        parse: ParseResult | None = None,
        store: StoreResult | None = None,
    ) -> ChatTranscriptOutput:
        self._stage = "aborted"
        return ChatTranscriptOutput(
            status="aborted",
            artifact_id=custody.artifact_id if custody else None,
            sha256=custody.sha256 if custody else None,
            duplicate=custody.duplicate if custody else None,
            parser_id=parse.parser_id if parse else None,
            records_parsed=parse.record_count if parse else 0,
            records_stored=store.stored if store else 0,
            aborted_at=self._aborted_at,
            step_log=step_log,
        )
