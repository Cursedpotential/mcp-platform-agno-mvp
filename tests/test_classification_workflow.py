"""Contract + state-machine tests for ClassificationBatchPipeline (GAP-031).

Byline: Claude Code · Sonnet 5 · 2026-08-26

These run with NO Temporal server, NO worker and NO database — same doctrine as
tests/test_temporal_skeleton.py. The workflow class is instantiated directly and its
signal/query methods (and the pure helpers ``_item_key``/``_resolve_gate``) are called
as plain Python; none of that path touches ``workflow.execute_activity`` or
``workflow.wait_condition``, so it needs no workflow-context sandbox. ``workflow.logger``
IS touched by the signal handler's reject branches, so it is monkeypatched to a stdlib
logger, exactly like the existing ChatTranscriptIngest gate test.

Coverage maps directly to the GAP-031 acceptance gate
(docs/reviews/2026-08-25-schema-audit/AUDIT-GAP-REGISTER.md row 41):
  1. exact normalized signal enum allowlist (action + per-item decision)
  2. item-level decisions record decision_id, actor, decision, reason, source
  3. only individually approved/corrected items become accepted
  4. untouched items remain pending (never silently added)
  5. invalid / mixed / partial / replayed signal cases produce no unintended
     persistence payload and are deterministic on resume (idempotent replay,
     rejected conflicting resubmission)
"""

from __future__ import annotations

import dataclasses
import logging

import pytest

from server.temporal import classification_workflow as cw


def _wf() -> cw.ClassificationBatchPipeline:
    return cw.ClassificationBatchPipeline()


def _open_gate(wf: cw.ClassificationBatchPipeline, items: list[dict]) -> None:
    """Mirror what run() does when opening a review gate, without the activity calls."""
    wf._stage = "gate:1/1"
    wf._gate_abort = False
    wf._gate_closed = False
    wf._gate_items = {wf._item_key(it, idx): it for idx, it in enumerate(items)}
    wf._decisions = {}
    wf._corrections = {}


def _decision(**kwargs) -> cw.ItemAdjudication:
    base = dict(
        decision_id="d-1",
        item_key="c-1",
        actor="reviewer@example.test",
        decision=cw.ITEM_DECISION_APPROVE,
        reason="looks correct",
        source="workbench-ui",
    )
    base.update(kwargs)
    return cw.ItemAdjudication(**base)


# ---------------------------------------------------------------------------
# 1. Workflow/registration contract
# ---------------------------------------------------------------------------


def test_workflow_is_a_workflow_defn_named_classification_batch_pipeline():
    from temporalio.workflow import _Definition

    defn = _Definition.from_class(cw.ClassificationBatchPipeline)
    assert defn is not None
    assert defn.name == "ClassificationBatchPipeline"
    assert defn.run_fn is not None


def test_workflow_exposes_submit_signal_and_status_queries():
    from temporalio.workflow import _Definition

    defn = _Definition.from_class(cw.ClassificationBatchPipeline)
    assert "submit_review_decisions" in defn.signals
    assert "status" in defn.queries
    assert "pending_items" in defn.queries


def test_the_old_free_text_gate_decision_signal_is_gone():
    # GAP-031: the vulnerable free-text signal must not remain reachable alongside
    # the new structured one — that would leave the fail-open hole in place.
    from temporalio.workflow import _Definition

    defn = _Definition.from_class(cw.ClassificationBatchPipeline)
    assert "gate_decision" not in defn.signals
    assert not hasattr(cw.ClassificationBatchPipeline, "gate_decision")


# ---------------------------------------------------------------------------
# 2. Exact normalized enum allowlist — gate-level action
# ---------------------------------------------------------------------------


def test_unknown_gate_action_is_rejected_and_does_not_release_the_gate(monkeypatch):
    monkeypatch.setattr(cw.workflow, "logger", logging.getLogger("test.gap031.action"))
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}])
    wf.submit_review_decisions(cw.ReviewGateSubmission(action="APPROVE"))  # wrong case
    assert wf._gate_abort is False
    assert wf._gate_closed is False
    wf.submit_review_decisions(cw.ReviewGateSubmission(action=""))
    assert wf._gate_abort is False
    assert wf._gate_closed is False
    wf.submit_review_decisions(cw.ReviewGateSubmission(action="approve-all"))
    assert wf._gate_abort is False
    assert wf._gate_closed is False


def test_abort_action_sets_gate_abort():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}])
    wf.submit_review_decisions(cw.ReviewGateSubmission(action=cw.GATE_ACTION_ABORT))
    assert wf._gate_abort is True
    assert wf._gate_closed is False


def test_close_batch_action_closes_without_deciding_items():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}, {"chunk_id": "c-2"}])
    wf.submit_review_decisions(cw.ReviewGateSubmission(action=cw.GATE_ACTION_CLOSE_BATCH))
    assert wf._gate_closed is True
    assert wf._gate_abort is False
    accepted, rejected, pending, _ = wf._resolve_gate()
    assert accepted == []
    assert rejected == 0
    assert pending == 2


# ---------------------------------------------------------------------------
# 3. Exact normalized enum allowlist — item-level decision
# ---------------------------------------------------------------------------


def test_item_decision_with_invalid_enum_is_rejected(monkeypatch):
    monkeypatch.setattr(cw.workflow, "logger", logging.getLogger("test.gap031.item"))
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[_decision(decision="mostly_approve")],
        )
    )
    assert wf._decisions == {}


@pytest.mark.parametrize("missing_field", ["decision_id", "actor", "reason", "source"])
def test_item_decision_missing_a_required_field_is_rejected(monkeypatch, missing_field):
    monkeypatch.setattr(cw.workflow, "logger", logging.getLogger("test.gap031.missing"))
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[_decision(**{missing_field: ""})],
        )
    )
    assert wf._decisions == {}


def test_item_decision_with_unknown_item_key_is_rejected(monkeypatch):
    monkeypatch.setattr(cw.workflow, "logger", logging.getLogger("test.gap031.unknown"))
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[_decision(item_key="c-does-not-exist")],
        )
    )
    assert wf._decisions == {}


# ---------------------------------------------------------------------------
# 4. Item-level decisions record decision_id/actor/decision/reason/source
# ---------------------------------------------------------------------------


def test_valid_approve_decision_is_recorded_with_full_provenance():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1", "summary": "x"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[_decision()],
        )
    )
    record = wf._decisions["c-1"]
    assert record.decision_id == "d-1"
    assert record.actor == "reviewer@example.test"
    assert record.decision == cw.ITEM_DECISION_APPROVE
    assert record.reason == "looks correct"
    assert record.source == "workbench-ui"


def test_valid_correct_decision_stores_corrected_fields():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1", "summary": "wrong"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[
                _decision(
                    decision=cw.ITEM_DECISION_CORRECT,
                    corrected_fields={"summary": "fixed"},
                )
            ],
        )
    )
    assert wf._corrections["c-1"] == {"summary": "fixed"}
    accepted, _, _, _ = wf._resolve_gate()
    assert accepted[0]["summary"] == "fixed"


# ---------------------------------------------------------------------------
# 5. Only approved/corrected items are accepted; rejected/pending are excluded
# ---------------------------------------------------------------------------


def test_resolve_gate_excludes_rejected_and_pending_items():
    wf = _wf()
    _open_gate(
        wf,
        [
            {"chunk_id": "c-approve"},
            {"chunk_id": "c-correct"},
            {"chunk_id": "c-reject"},
            {"chunk_id": "c-untouched"},
        ],
    )
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[
                _decision(item_key="c-approve", decision_id="d-a"),
                _decision(
                    item_key="c-correct",
                    decision_id="d-c",
                    decision=cw.ITEM_DECISION_CORRECT,
                    corrected_fields={"note": "adjusted"},
                ),
                _decision(item_key="c-reject", decision_id="d-r", decision=cw.ITEM_DECISION_REJECT),
            ],
        )
    )
    accepted, rejected, pending, adjudications = wf._resolve_gate()
    accepted_keys = {item["chunk_id"] for item in accepted}
    assert accepted_keys == {"c-approve", "c-correct"}
    assert rejected == 1
    assert pending == 1  # c-untouched
    assert len(adjudications) == 3  # every DECIDED item, not the untouched one
    for item in accepted:
        assert item["gate_outcome"] == "accepted"
        assert item["adjudication"]["actor"] == "reviewer@example.test"
    # c-untouched must not appear anywhere in the accepted payload
    assert "c-untouched" not in accepted_keys


def test_gate_items_not_yet_decided_are_never_silently_added():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}, {"chunk_id": "c-2"}])
    # No decisions submitted at all.
    accepted, rejected, pending, adjudications = wf._resolve_gate()
    assert accepted == []
    assert rejected == 0
    assert pending == 2
    assert adjudications == []


# ---------------------------------------------------------------------------
# 6. Replayed / conflicting signal delivery is deterministic
# ---------------------------------------------------------------------------


def test_replaying_the_same_decision_id_is_an_idempotent_no_op():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}])
    d = _decision()
    wf.submit_review_decisions(cw.ReviewGateSubmission(action=cw.GATE_ACTION_SUBMIT_DECISIONS, decisions=[d]))
    first = wf._decisions["c-1"]
    # Re-deliver the identical signal (e.g. a client retry after an uncertain ack).
    wf.submit_review_decisions(cw.ReviewGateSubmission(action=cw.GATE_ACTION_SUBMIT_DECISIONS, decisions=[d]))
    assert len(wf._decisions) == 1
    assert wf._decisions["c-1"] == first


def test_conflicting_resubmission_with_a_new_decision_id_is_rejected(monkeypatch):
    monkeypatch.setattr(cw.workflow, "logger", logging.getLogger("test.gap031.conflict"))
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[_decision(decision_id="d-first", decision=cw.ITEM_DECISION_APPROVE)],
        )
    )
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[_decision(decision_id="d-second", decision=cw.ITEM_DECISION_REJECT)],
        )
    )
    # The FIRST applied decision wins; the conflicting resubmission never overwrote it.
    assert wf._decisions["c-1"].decision_id == "d-first"
    assert wf._decisions["c-1"].decision == cw.ITEM_DECISION_APPROVE


# ---------------------------------------------------------------------------
# 7. Mixed and partial submissions
# ---------------------------------------------------------------------------


def test_mixed_submission_applies_valid_entries_and_drops_invalid_ones(monkeypatch):
    monkeypatch.setattr(cw.workflow, "logger", logging.getLogger("test.gap031.mixed"))
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-good"}, {"chunk_id": "c-also-good"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[
                _decision(item_key="c-good", decision_id="d-1"),
                _decision(item_key="c-also-good", decision_id="d-2", decision="not_a_real_decision"),
                _decision(item_key="c-not-in-gate", decision_id="d-3"),
                cw.ItemAdjudication(item_key="c-good", decision_id="d-4"),  # missing everything else
            ],
        )
    )
    assert set(wf._decisions) == {"c-good"}
    assert wf._decisions["c-good"].decision_id == "d-1"


def test_partial_submission_does_not_auto_close_the_gate():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}, {"chunk_id": "c-2"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[_decision(item_key="c-1")],
        )
    )
    assert wf._gate_closed is False
    assert wf.pending_items() == ["c-2"]


def test_full_submission_auto_closes_the_gate():
    wf = _wf()
    _open_gate(wf, [{"chunk_id": "c-1"}, {"chunk_id": "c-2"}])
    wf.submit_review_decisions(
        cw.ReviewGateSubmission(
            action=cw.GATE_ACTION_SUBMIT_DECISIONS,
            decisions=[
                _decision(item_key="c-1", decision_id="d-1"),
                _decision(item_key="c-2", decision_id="d-2", decision=cw.ITEM_DECISION_REJECT),
            ],
        )
    )
    assert wf._gate_closed is True
    assert wf.pending_items() == []


# ---------------------------------------------------------------------------
# 8. _item_key precedence and fallback
# ---------------------------------------------------------------------------


def test_item_key_prefers_chunk_id_then_record_id_then_record_ref():
    wf = _wf()
    assert wf._item_key({"chunk_id": "ch", "record_id": "r", "record_ref": "rr"}, 0) == "ch"
    assert wf._item_key({"record_id": "r", "record_ref": "rr"}, 0) == "r"
    assert wf._item_key({"record_ref": "rr"}, 0) == "rr"


def test_item_key_falls_back_to_a_positional_key_when_no_id_is_present():
    wf = _wf()
    assert wf._item_key({}, 3) == "__idx_3"


# ---------------------------------------------------------------------------
# 9. Payload round-trip through temporalio's default converter
# ---------------------------------------------------------------------------


def _round_trip(value):
    from temporalio.converter import DataConverter

    converter = DataConverter.default.payload_converter
    payloads = converter.to_payloads([value])
    return converter.from_payloads(payloads, [type(value)])[0]


_PAYLOAD_SAMPLES = [
    cw.ClassificationBatchInput(
        batches=[[{"record_id": "r-1", "text": "hi", "occurred_at": "2026-08-26T00:00:00Z"}]],
        classifier_version="clf-v0",
        run_key="run-1",
        supervised=True,
    ),
    cw.ClassificationBatchOutput(
        status="completed",
        batches_processed=1,
        accepted=1,
        needs_review=1,
        persisted=2,
        rejected=1,
        still_pending=1,
        step_log=["batch 1: 1 accepted, 1 needs_review"],
        adjudications=[{"item_key": "c-1", "decision": "approve"}],
    ),
    cw.ItemAdjudication(
        decision_id="d-1",
        item_key="c-1",
        actor="reviewer@example.test",
        decision="approve",
        reason="looks correct",
        source="workbench-ui",
        corrected_fields={"summary": "x"},
    ),
    cw.ReviewGateSubmission(
        action="submit_decisions",
        decisions=[cw.ItemAdjudication(decision_id="d-1", item_key="c-1")],
    ),
    cw.ItemDecisionRecord(
        decision_id="d-1",
        item_key="c-1",
        actor="reviewer@example.test",
        decision="approve",
        reason="looks correct",
        source="workbench-ui",
    ),
]


@pytest.mark.parametrize("value", _PAYLOAD_SAMPLES, ids=lambda v: type(v).__name__)
def test_payload_dataclass_round_trips_through_the_default_converter(value):
    assert _round_trip(value) == value


@pytest.mark.parametrize("value", _PAYLOAD_SAMPLES, ids=lambda v: type(v).__name__)
def test_payload_types_are_dataclasses(value):
    assert dataclasses.is_dataclass(value)


# ---------------------------------------------------------------------------
# 10. Determinism: no env/network import at module load (replay constraint)
# ---------------------------------------------------------------------------


def test_workflow_module_does_not_import_env_reading_modules():
    import subprocess
    import sys

    code = (
        "import sys; import server.temporal.classification_workflow;"
        "bad=[m for m in ('server.core.url','server.core.session') if m in sys.modules];"
        "print(','.join(bad))"
    )
    proc = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "", f"workflow module import pulled in {proc.stdout.strip()}"
