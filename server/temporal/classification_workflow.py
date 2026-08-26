"""server/temporal/classification_workflow.py — ClassificationBatchPipeline (Stage 5, D-068).

Byline: Claude Code · Sonnet 5 · 2026-08-26 (GAP-031: item-level HITL adjudication —
see docs/reviews/2026-08-25-schema-audit/GAP-031-IMPLEMENTATION-STATUS.md)

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

GAP-031 (fail-closed item-level adjudication, 2026-08-26): the review gate no longer accepts
free text. ``submit_review_decisions`` takes a ``ReviewGateSubmission`` whose ``action`` MUST
be an exact member of ``_VALID_GATE_ACTIONS`` and whose per-item ``ItemAdjudication``s MUST
carry a decision_id, actor, an exact ``_VALID_ITEM_DECISIONS`` member, a reason and a source.
Only items with a recorded approve/correct decision are added to the persist payload; rejected
and untouched (still-pending) items are excluded — never silently appended. Bad input to the
signal is logged and dropped, never raised (a raising signal handler fails the whole workflow
task) and never defaults to acceptance. This REPLACES the prior free-text ``gate_decision``
signal, which is a breaking change to the Signal contract — see the status doc for the
runbook/doc follow-ups this leaves open.

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

# --- GAP-031: exact normalized signal enum allowlists (fail-closed) --------------------

GATE_ACTION_ABORT = "abort"
GATE_ACTION_SUBMIT_DECISIONS = "submit_decisions"
GATE_ACTION_CLOSE_BATCH = "close_batch"
_VALID_GATE_ACTIONS = frozenset({GATE_ACTION_ABORT, GATE_ACTION_SUBMIT_DECISIONS, GATE_ACTION_CLOSE_BATCH})

ITEM_DECISION_APPROVE = "approve"
ITEM_DECISION_CORRECT = "correct"
ITEM_DECISION_REJECT = "reject"
_VALID_ITEM_DECISIONS = frozenset({ITEM_DECISION_APPROVE, ITEM_DECISION_CORRECT, ITEM_DECISION_REJECT})
# Only these decisions can ever add an item to the persist payload.
_ACCEPTING_DECISIONS = frozenset({ITEM_DECISION_APPROVE, ITEM_DECISION_CORRECT})


@dataclass
class ItemAdjudication:
    """One reviewer's decision on ONE needs_review item.

    decision_id: caller-minted idempotency key for THIS decision. A resubmission of
                 the same decision_id for the same item_key is a no-op (safe retry of
                 an uncertain-delivery signal call). A DIFFERENT decision_id for an
                 item that already has a decision is rejected, not overwritten — one
                 item gets exactly one applied decision per gate.
    item_key:    must match an item in the CURRENT gate's needs_review set (derived by
                 the workflow — see ``ClassificationBatchPipeline._item_key``); a
                 mismatched key is rejected, not silently dropped into the next batch.
    actor:       reviewer identity. Required, non-empty.
    decision:    exact member of ``_VALID_ITEM_DECISIONS``. Anything else is rejected.
    reason:      rationale. Required, non-empty — fail closed on a missing reason.
    source:      origin surface (e.g. "workbench-ui", "temporal-cli"). Required.
    corrected_fields: replacement payload fields, applied over the original item when
                 decision == "correct". Ignored (harmlessly) for approve/reject.
    """

    decision_id: str = ""
    item_key: str = ""
    actor: str = ""
    decision: str = ""
    reason: str = ""
    source: str = ""
    corrected_fields: dict[str, Any] | None = None


@dataclass
class ReviewGateSubmission:
    """The payload of the ``submit_review_decisions`` signal.

    action: exact member of ``_VALID_GATE_ACTIONS`` — anything else is rejected (logged,
            ignored) and NEVER releases the gate. "abort" ends the run at the gate.
            "submit_decisions" applies each ``decisions`` entry independently.
            "close_batch" ends the wait without requiring every item to be decided —
            undecided items remain pending (excluded from persistence, reported in the
            batch's still_pending count for a follow-up gate/run).
    decisions: item-level adjudications for a "submit_decisions" action; ignored for
               "abort"/"close_batch".
    """

    action: str = ""
    decisions: list[ItemAdjudication] = field(default_factory=list)


@dataclass
class ItemDecisionRecord:
    """Durable (in-memory, per-gate) record of one APPLIED item decision."""

    decision_id: str
    item_key: str
    actor: str
    decision: str
    reason: str
    source: str


@dataclass
class ClassificationBatchInput:
    """One pipeline run over pre-chunked records (chunking stays platform-side).

    batches: list of batches; each batch is a list of chunk dicts that MUST carry
             record_id, text, occurred_at (temporal mandate) — produced upstream by the
             platform chunker, never by n8n.
    classifier_version: stamps every draft label (versioned-drafts rule).
    run_key: idempotency key derived from the source object keys.
    supervised: when True (default), needs_review items gate on item-level HITL decisions.
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
    rejected: int = 0
    still_pending: int = 0
    step_log: list[str] = field(default_factory=list)
    adjudications: list[dict[str, Any]] = field(default_factory=list)


@workflow.defn(name="ClassificationBatchPipeline")
class ClassificationBatchPipeline:
    def __init__(self) -> None:
        self._stage = "pending"
        # Per-gate state; reset each time a batch opens a review gate.
        self._gate_abort = False
        self._gate_closed = False
        self._gate_items: dict[str, dict[str, Any]] = {}
        self._decisions: dict[str, ItemDecisionRecord] = {}
        self._corrections: dict[str, dict[str, Any]] = {}

    # -- Signal: the ONLY way to affect a paused review gate ------------------------

    @workflow.signal
    def submit_review_decisions(self, submission: ReviewGateSubmission) -> None:
        """Fail-closed, item-level HITL signal (GAP-031).

        Never raises — a raising signal handler fails the whole workflow task, so every
        validation failure here is logged and the input is dropped, not escalated.
        Nothing here can release the gate except an exact enum match, and nothing here
        can add an item to acceptance except an exact per-item approve/correct decision
        that passes every field check.
        """
        if submission.action not in _VALID_GATE_ACTIONS:
            workflow.logger.warning(
                "review gate: rejected unknown action %r (not in allowlist)",
                submission.action,
            )
            return
        if submission.action == GATE_ACTION_ABORT:
            self._gate_abort = True
            return
        if submission.action == GATE_ACTION_CLOSE_BATCH:
            self._gate_closed = True
            return
        # GATE_ACTION_SUBMIT_DECISIONS
        for decision in submission.decisions:
            self._apply_item_decision(decision)
        # Auto-close once every item currently in the gate has a recorded decision —
        # deterministic given the applied-decisions history, no wall-clock involved.
        if self._gate_items and set(self._gate_items) <= set(self._decisions):
            self._gate_closed = True

    def _apply_item_decision(self, decision: ItemAdjudication) -> None:
        if decision.decision not in _VALID_ITEM_DECISIONS:
            workflow.logger.warning(
                "review gate: rejected decision %r for item %r (not in allowlist)",
                decision.decision,
                decision.item_key,
            )
            return
        if not (decision.decision_id and decision.actor and decision.reason and decision.source):
            workflow.logger.warning(
                "review gate: rejected decision for item %r (decision_id/actor/reason/source must all be non-empty)",
                decision.item_key,
            )
            return
        if decision.item_key not in self._gate_items:
            workflow.logger.warning(
                "review gate: rejected decision for item_key %r (not in the current gate)",
                decision.item_key,
            )
            return
        existing = self._decisions.get(decision.item_key)
        if existing is not None:
            if existing.decision_id == decision.decision_id:
                return  # idempotent replay of the same decision — no-op
            workflow.logger.warning(
                "review gate: item %r already decided (decision_id=%s); "
                "ignoring conflicting resubmission decision_id=%s",
                decision.item_key,
                existing.decision_id,
                decision.decision_id,
            )
            return
        self._decisions[decision.item_key] = ItemDecisionRecord(
            decision_id=decision.decision_id,
            item_key=decision.item_key,
            actor=decision.actor,
            decision=decision.decision,
            reason=decision.reason,
            source=decision.source,
        )
        if decision.decision == ITEM_DECISION_CORRECT and decision.corrected_fields:
            self._corrections[decision.item_key] = dict(decision.corrected_fields)

    @workflow.query
    def status(self) -> str:
        return self._stage

    @workflow.query
    def pending_items(self) -> list[str]:
        """item_keys in the CURRENT gate that have no recorded decision yet."""
        return [k for k in self._gate_items if k not in self._decisions]

    # -- Pure helpers (no temporalio workflow-context calls; unit-testable directly) --

    @staticmethod
    def _item_key(item: dict[str, Any], index: int) -> str:
        """Stable identifier for one item within a batch's review gate.

        Prefers chunk_id (the persist-body primary-key component), then record_id,
        then record_ref. An item carrying none of these is malformed upstream input;
        it still gets a deterministic positional key so it CAN be adjudicated, but
        that key is not stable across a differently-ordered resubmission of the same
        batch — upstream classifiers should always supply a real id.
        """
        for field_name in ("chunk_id", "record_id", "record_ref"):
            val = item.get(field_name)
            if val:
                return str(val)
        return f"__idx_{index}"

    def _resolve_gate(self) -> tuple[list[dict[str, Any]], int, int, list[dict[str, Any]]]:
        """Turn applied per-item decisions into the persist payload.

        Returns (accepted_items, rejected_count, still_pending_count, adjudication_records).
        Only items with a recorded approve/correct decision appear in accepted_items;
        rejected and untouched items are excluded — this is the GAP-031 fail-closed rule
        made concrete. Pure function of self._gate_items/_decisions/_corrections, so it
        needs no workflow-context APIs and can be exercised directly in unit tests.
        """
        accepted_items: list[dict[str, Any]] = []
        rejected = 0
        adjudications: list[dict[str, Any]] = []
        for key, item in self._gate_items.items():
            record = self._decisions.get(key)
            if record is None:
                continue  # still pending — excluded, never silently added
            adjudications.append(
                {
                    "item_key": record.item_key,
                    "decision_id": record.decision_id,
                    "actor": record.actor,
                    "decision": record.decision,
                    "reason": record.reason,
                    "source": record.source,
                }
            )
            if record.decision == ITEM_DECISION_REJECT:
                rejected += 1
                continue
            if record.decision not in _ACCEPTING_DECISIONS:
                continue  # defensive; _VALID_ITEM_DECISIONS already excludes this path
            payload = dict(item)
            if record.decision == ITEM_DECISION_CORRECT and key in self._corrections:
                payload.update(self._corrections[key])
            payload["gate_outcome"] = "accepted"
            payload["adjudication"] = {
                "decision_id": record.decision_id,
                "actor": record.actor,
                "decision": record.decision,
                "reason": record.reason,
                "source": record.source,
            }
            accepted_items.append(payload)
        still_pending = sum(1 for k in self._gate_items if k not in self._decisions)
        return accepted_items, rejected, still_pending, adjudications

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
            out.step_log.append(f"batch {i + 1}: {len(accepted)} accepted, {len(review)} needs_review")

            if review and params.supervised:
                # GAP-031 HITL: pause on item-level decisions; notify forever, never
                # abort on silence, never auto-accept an undecided item.
                self._stage = f"gate:{i + 1}/{len(params.batches)}"
                self._gate_abort = False
                self._gate_closed = False
                self._gate_items = {self._item_key(it, idx): it for idx, it in enumerate(review)}
                self._decisions = {}
                self._corrections = {}
                while not self._gate_abort and not self._gate_closed:
                    try:
                        await workflow.wait_condition(
                            lambda: self._gate_abort or self._gate_closed,
                            timeout=_GATE_NOTIFY_AFTER,
                        )
                    except TimeoutError:
                        pending = len(self._gate_items) - len(self._decisions)
                        workflow.logger.info(
                            "review gate still waiting (batch %d, %d/%d items pending)",
                            i + 1,
                            pending,
                            len(self._gate_items),
                        )
                if self._gate_abort:
                    out.status = "aborted_at_gate"
                    out.batches_processed = i + 1
                    self._stage = "aborted"
                    return out

                adjudicated_accept, batch_rejected, batch_pending, adjudications = self._resolve_gate()
                out.rejected += batch_rejected
                out.still_pending += batch_pending
                out.adjudications.extend(adjudications)
                out.step_log.append(
                    f"batch {i + 1} gate: {len(adjudicated_accept)} adjudicated-accepted, "
                    f"{batch_rejected} rejected, {batch_pending} still pending"
                )
                accepted = accepted + adjudicated_accept

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
