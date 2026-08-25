"""server/temporal/classification_workflow.py — ClassificationBatchPipeline (Stage 5, D-068).

Byline: Claude Code · Fable 5 · 2026-08-24

The durable spine for the composed n8n bodies (docs/research/integration-audit-2026-08-24/
composed/): per small batch — classify (n8n) → judge (n8n) → [HITL Signal gate iff anything
needs review] → persist accepted (n8n). Every stage is one activity per the wrap=activity
ruling; the workflow owns sequence/retries/history and NOTHING else.

Owner rules encoded here:
  * SMALL BATCHES — the workflow processes the batches it is given, sequentially; callers
    keep batch sizes small (default 10) and start few. Review cadence lives BETWEEN runs.
  * ANTI-OVER-FLAGGING — judge routes low-confidence to needs_review; nothing is "flagged".
  * DRAFTS BY DESIGN — classifier_version rides every payload; persist stamps it.
  * HITL — needs_review items pause the run on a Signal (approve/abort), notify-don't-abort:
    a log line every _GATE_NOTIFY_AFTER while waiting, forever (same doctrine as
    ChatTranscriptIngest).

Import rule: temporalio + stdlib + our activity dataclasses only; deterministic; no env/net.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timedelta
from typing import Any

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from server.temporal.n8n_activities import N8nCallParams, N8nCallResult

_RETRY = RetryPolicy(
    initial_interval=timedelta(seconds=2),
    backoff_coefficient=4.0,
    maximum_interval=timedelta(minutes=2),
    maximum_attempts=4,
)
_GATE_NOTIFY_AFTER = timedelta(days=7)

CLASSIFY_PATH = "webhook/classify-batch"
JUDGE_PATH = "webhook/judge-gate"
PERSIST_PATH = "webhook/persist-results"


@dataclass
class ClassificationBatchInput:
    """One pipeline run over pre-chunked records (chunking stays platform-side).

    batches: list of batches; each batch is a list of chunk dicts that MUST carry
             record_id, text, occurred_at (temporal mandate) — produced upstream by the
             platform chunker, never by n8n.
    classifier_version: stamps every draft label (versioned-drafts rule).
    run_key: idempotency key derived from the source object keys.
    supervised: when True (default), needs_review items gate on a human Signal.
    """

    batches: list[list[dict[str, Any]]] = field(default_factory=list)
    classifier_version: str = "clf-v0"
    run_key: str = ""
    supervised: bool = True


@dataclass
class ClassificationBatchOutput:
    status: str = "completed"
    batches_processed: int = 0
    accepted: int = 0
    needs_review: int = 0
    persisted: int = 0
    step_log: list[str] = field(default_factory=list)


@workflow.defn(name="ClassificationBatchPipeline")
class ClassificationBatchPipeline:
    def __init__(self) -> None:
        self._gate_decision: str | None = None
        self._stage = "pending"

    @workflow.signal
    def gate_decision(self, decision: str) -> None:
        """'approve' releases a paused review gate; 'abort' ends the run at the gate."""
        self._gate_decision = decision

    @workflow.query
    def status(self) -> str:
        return self._stage

    async def _call(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        result: N8nCallResult = await workflow.execute_activity(
            "n8n_webhook_activity",
            N8nCallParams(webhook_path=path, payload=payload),
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=_RETRY,
        )
        return result.body

    @workflow.run
    async def run(self, params: ClassificationBatchInput) -> ClassificationBatchOutput:
        out = ClassificationBatchOutput()
        for i, batch in enumerate(params.batches):
            self._stage = f"classify:{i + 1}/{len(params.batches)}"
            classified = await self._call(
                CLASSIFY_PATH,
                {
                    "run_key": params.run_key,
                    "batch_index": i,
                    "classifier_version": params.classifier_version,
                    "items": batch,
                },
            )
            self._stage = f"judge:{i + 1}/{len(params.batches)}"
            judged = await self._call(
                JUDGE_PATH,
                {
                    "run_key": params.run_key,
                    "batch_index": i,
                    "classifier_version": params.classifier_version,
                    "items": classified.get("items", []),
                },
            )
            accepted = judged.get("accepted", [])
            review = judged.get("needs_review", [])
            out.accepted += len(accepted)
            out.needs_review += len(review)
            out.step_log.append(
                f"batch {i + 1}: {len(accepted)} accepted, {len(review)} needs_review"
            )

            if review and params.supervised:
                # HITL: pause on the Signal; notify forever, never abort on silence.
                self._stage = f"gate:{i + 1}/{len(params.batches)}"
                self._gate_decision = None
                while self._gate_decision is None:
                    try:
                        await workflow.wait_condition(
                            lambda: self._gate_decision is not None,
                            timeout=_GATE_NOTIFY_AFTER,
                        )
                    except TimeoutError:
                        workflow.logger.info(
                            "review gate still waiting (batch %d, %d items)",
                            i + 1,
                            len(review),
                        )
                if self._gate_decision == "abort":
                    out.status = "aborted_at_gate"
                    out.batches_processed = i + 1
                    self._stage = "aborted"
                    return out
                # 'approve' means: reviewed items were adjudicated in the workbench/n8n
                # surface; the persist body receives accepted + approved-review items.
                accepted = accepted + review

            if accepted:
                self._stage = f"persist:{i + 1}/{len(params.batches)}"
                persisted = await self._call(
                    PERSIST_PATH,
                    {
                        "run_key": params.run_key,
                        "batch_index": i,
                        "classifier_version": params.classifier_version,
                        "items": accepted,
                    },
                )
                out.persisted += int(persisted.get("persisted", len(accepted)))
            out.batches_processed = i + 1

        self._stage = "completed"
        return out
