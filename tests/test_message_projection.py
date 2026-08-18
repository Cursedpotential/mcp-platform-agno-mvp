"""Governed message projection writer tests.

Byline: Codex · GPT-5 · 2026-08-18
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from server.contracts.ingest import AcquisitionAssertion, IngestRequest
from server.contracts.records import MessageCorpus, MessageParticipant, NormalizedRecord
from server.evidence.message_projection import (
    _validate_entity_resolutions,
    approve_third_party_conversation,
    build_projection_plan,
    link_duplicate_acquisition,
    write_message_projections,
)
from server.evidence.store import store_record_batch


@dataclass
class _Artifact:
    artifact_id: str = "11111111-1111-1111-1111-111111111111"
    acquisition_id: str | None = "22222222-2222-2222-2222-222222222222"


class _Result:
    def __init__(self, value: str):
        self.value = value

    def scalar_one(self) -> str:
        return self.value

    def all(self):
        return [self.value]


class _Connection:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict]] = []

    def execute(self, statement, params=None):
        rendered = str(statement)
        self.calls.append((rendered, params or {}))
        return _Result("33333333-3333-3333-3333-333333333333")


def _request(kind: str, principal: str = "device-account") -> IngestRequest:
    return IngestRequest(
        staged_path="fixture.json",
        message_corpus=kind,
        source_principal=principal,
        caller_owns_conversation=kind == "first_party",
        acquisition=(
            AcquisitionAssertion(acquired_at=datetime(2025, 1, 2, tzinfo=timezone.utc))
            if kind == "acquired_third_party"
            else None
        ),
    )


def test_projection_plan_uses_actual_source_principal_and_never_owner() -> None:
    record = NormalizedRecord(
        source="fixture",
        sender="device-account",
        recipients=[MessageParticipant(identity="friend", role="to")],
        message_corpus=MessageCorpus.acquired_third_party,
        attrs={"direction": "outbound"},
    )
    plan = build_projection_plan(record, "record-id", "artifact-id", _request("acquired_third_party"))
    assert plan is not None
    assert plan.sender == "device-account"
    assert plan.recipients == (("friend", "to"),)
    assert plan.direction == "outbound"
    assert "owner" not in {plan.sender, *(identity for identity, _role in plan.recipients)}


def test_review_marker_must_be_absent_not_merely_false() -> None:
    record = NormalizedRecord(
        source="fixture",
        sender="device-account",
        recipients=[MessageParticipant(identity="friend", role="to")],
        message_corpus=MessageCorpus.first_party,
        attrs={"source_party_review_required": False},
    )
    plan = build_projection_plan(record, "record-id", "artifact-id", _request("first_party"))
    assert plan is not None and plan.review_required is True


def test_store_rejects_unclassified_or_unrouted_messages_before_db_access() -> None:
    message = NormalizedRecord(source="fixture", conversation_id="thread", participants=["alex", "jordan"])
    with pytest.raises(ValueError, match="explicit first_party or acquired_third_party"):
        store_record_batch([message], [], _Artifact())
    with pytest.raises(ValueError, match="projection_request"):
        store_record_batch(
            [message.model_copy(update={"message_corpus": MessageCorpus.first_party})],
            [],
            _Artifact(),
        )
    with pytest.raises(ValueError, match="must match every classified message"):
        store_record_batch(
            [message.model_copy(update={"message_corpus": MessageCorpus.first_party})],
            [],
            _Artifact(),
            projection_request=_request("acquired_third_party"),
        )


def test_store_rejects_unresolved_first_party_parties_before_db_access() -> None:
    unresolved = NormalizedRecord(
        source="fixture",
        sender="owner-device",
        message_corpus=MessageCorpus.first_party,
    )
    with pytest.raises(ValueError, match="sender and at least one counterparty"):
        store_record_batch(
            [unresolved],
            [],
            _Artifact(),
            projection_request=_request("first_party", principal="owner-device"),
        )


def test_third_party_writer_proposes_route_and_links_authoritative_acquisition() -> None:
    conn = _Connection()
    record = NormalizedRecord(
        source="fixture",
        conversation_id="thread-1",
        sender="alex",
        recipients=[MessageParticipant(identity="jordan", role="to")],
        message_corpus=MessageCorpus.acquired_third_party,
        content="source text",
    )
    written = write_message_projections(
        conn,
        [record],
        ["44444444-4444-4444-4444-444444444444"],
        _Artifact(),
        _request("acquired_third_party", principal="alex"),
    )
    statements = "\n".join(statement for statement, _params in conn.calls)
    route_params = next(params for statement, params in conn.calls if "message_projection_route" in statement)
    assert written == 1
    assert route_params["state"] == "proposed"
    assert "working.third_party_message " in statements
    assert "working.third_party_conversation_acquisition" in statements
    assert "INSERT INTO working.message " not in statements


def test_unresolved_third_party_stays_proposed_and_retains_review_row() -> None:
    conn = _Connection()
    record = NormalizedRecord(
        source="fixture",
        message_corpus=MessageCorpus.acquired_third_party,
        attrs={"source_party_review_required": True},
    )
    write_message_projections(
        conn,
        [record],
        ["44444444-4444-4444-4444-444444444444"],
        _Artifact(),
        _request("acquired_third_party"),
    )
    route_params = next(params for statement, params in conn.calls if "message_projection_route" in statement)
    message_params = next(params for statement, params in conn.calls if "third_party_message " in statement)
    assert route_params["state"] == "proposed"
    assert message_params["sender"] is None


def test_first_party_with_explicit_parties_is_approved_projection() -> None:
    conn = _Connection()
    record = NormalizedRecord(
        source="fixture",
        sender="device-account",
        recipients=[MessageParticipant(identity="friend", role="to")],
        message_corpus=MessageCorpus.first_party,
    )
    write_message_projections(
        conn,
        [record],
        ["44444444-4444-4444-4444-444444444444"],
        _Artifact(acquisition_id=None),
        _request("first_party"),
    )
    statements = "\n".join(statement for statement, _params in conn.calls)
    route_params = next(params for statement, params in conn.calls if "message_projection_route" in statement)
    assert route_params["state"] == "approved"
    assert "INSERT INTO working.message " in statements
    assert "third_party_message" not in statements


def test_resolution_validation_excludes_owner_and_requires_sender_match() -> None:
    rows = [
        {
            "message_id": "message-1",
            "participant_id": "party-from",
            "sender_raw": "alex",
            "participant_raw": "alex",
            "role": "from",
        },
        {
            "message_id": "message-1",
            "participant_id": "party-to",
            "sender_raw": "alex",
            "participant_raw": "jordan",
            "role": "to",
        },
    ]
    with pytest.raises(ValueError, match="owner cannot participate"):
        _validate_entity_resolutions(
            rows,
            {"message-1": "owner-id"},
            {"party-from": "owner-id", "party-to": "jordan-id"},
            "owner-id",
        )
    with pytest.raises(ValueError, match="from-participant"):
        _validate_entity_resolutions(
            rows,
            {"message-1": "alex-id"},
            {"party-from": "wrong-id", "party-to": "jordan-id"},
            "owner-id",
        )


def test_duplicate_acquisition_links_without_rewriting_records() -> None:
    conn = _Connection()
    assert (
        link_duplicate_acquisition(
            conn,
            artifact_id="11111111-1111-1111-1111-111111111111",
            acquisition_id="22222222-2222-2222-2222-222222222222",
            asserted_by="owner",
        )
        == 1
    )
    statement = conn.calls[0][0]
    assert "third_party_conversation_acquisition" in statement
    assert "third_party_conversation tc" in statement
    assert "normalized_record" not in statement


class _Mappings:
    def __init__(self, rows):
        self.rows = rows

    def first(self):
        return self.rows[0] if self.rows else None

    def __iter__(self):
        return iter(self.rows)


class _Scalars:
    def __init__(self, values):
        self.values = values

    def all(self):
        return self.values

    def __iter__(self):
        return iter(self.values)


class _ApprovalResult:
    def __init__(self, *, rows=None, values=None, scalar=None):
        self.rows = rows or []
        self.values = values or []
        self.scalar_value = scalar

    def mappings(self):
        return _Mappings(self.rows)

    def scalars(self):
        return _Scalars(self.values)

    def scalar_one(self):
        return self.scalar_value


class _ApprovalConnection:
    def execute(self, statement, params=None):
        rendered = str(statement)
        if "FROM working.third_party_conversation " in rendered and "FOR UPDATE" in rendered:
            return _ApprovalResult(
                rows=[
                    {
                        "id": "conversation-id",
                        "source_artifact_id": "artifact-id",
                        "case_id": "primary",
                        "review_status": "pending",
                    }
                ]
            )
        if "FROM working.person" in rendered:
            return _ApprovalResult(values=["owner-id"])
        if "FROM working.third_party_message tm" in rendered:
            return _ApprovalResult(
                rows=[
                    {
                        "message_id": "message-id",
                        "normalized_record_id": "record-id",
                        "sender_raw": "alex",
                        "participant_id": "from-id",
                        "participant_raw": "alex",
                        "role": "from",
                    },
                    {
                        "message_id": "message-id",
                        "normalized_record_id": "record-id",
                        "sender_raw": "alex",
                        "participant_id": "to-id",
                        "participant_raw": "jordan",
                        "role": "to",
                    },
                ]
            )
        if "FROM working.entity" in rendered:
            return _ApprovalResult(values=["alex-id", "jordan-id"])
        if "SELECT count(*)" in rendered:
            return _ApprovalResult(scalar=1)
        if "working.source_available_from" in rendered:
            return _ApprovalResult(
                rows=[{"id": "record-id", "source_available_from": datetime(2025, 1, 2, tzinfo=timezone.utc)}]
            )
        return _ApprovalResult()


class _ApprovalEngine:
    class _Context:
        def __enter__(self):
            return _ApprovalConnection()

        def __exit__(self, exc_type, exc, tb):
            return False

    def begin(self):
        return self._Context()


def test_approval_returns_audited_vector_handoff(monkeypatch) -> None:
    monkeypatch.setattr("server.core.audit.record", lambda *args, **kwargs: 99)
    result = approve_third_party_conversation(
        "conversation-id",
        sender_entity_ids={"message-id": "alex-id"},
        participant_entity_ids={"from-id": "alex-id", "to-id": "jordan-id"},
        actor="owner",
        reason="resolved against contact identities",
        engine=_ApprovalEngine(),
    )
    assert result.audit_ledger_id == 99
    assert result.approved_record_count == 1
    assert result.vector_reprojection.normalized_record_ids == ("record-id",)
    assert result.vector_reprojection.source_available_from["record-id"].year == 2025


def test_approved_handoff_is_the_only_vector_replay_authority(monkeypatch) -> None:
    from server.evidence import workflows
    from server.evidence.vector_projection import NativeEvidenceProjector

    acquired = datetime(2025, 1, 2, tzinfo=timezone.utc)
    handoff = SimpleNamespace(
        conversation_id="conversation-id",
        artifact_id="artifact-id",
        normalized_record_ids=("record-id",),
        source_available_from={"record-id": acquired},
    )
    projector = NativeEvidenceProjector.__new__(NativeEvidenceProjector)
    captured = {}
    projector.enqueue = lambda record_ids, reason: (
        captured.update(  # type: ignore[method-assign]
            {"record_ids": tuple(record_ids), "reason": reason}
        )
        or 1
    )
    projector.drain = lambda: SimpleNamespace(completed=1, failed=0)  # type: ignore[method-assign]

    assert asyncio.run(workflows.reproject_approved_third_party(handoff, projector)) == 1
    assert captured["record_ids"] == ("record-id",)
    assert captured["reason"].startswith("approved_third_party:")


def test_sql_contract_keeps_review_reachable_and_owner_drift_deferred() -> None:
    root = Path(__file__).resolve().parents[1]
    migration = (root / "sql/0026_realization_event.sql").read_text(encoding="utf-8")
    grants = (root / "sql/0029_pass_grants.sql").read_text(encoding="utf-8")
    assert "source_party_review_resolved" in migration
    assert "ARRAY['normalized_record','message_projection_route','message','person'" in migration
    assert "working.third_party_message_participant" in grants
    assert "ops.audit_ledger TO horizon_reviewer" in grants
