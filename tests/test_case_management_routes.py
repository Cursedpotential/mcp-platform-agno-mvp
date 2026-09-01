"""Focused contracts for the Matter and Knowledge-to-Evidence spine API.

Byline: Codex · GPT-5 · 2026-08-15
Byline amendment: Codex · GPT-5 · 2026-08-18 (third-party acquisition read-model coverage)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from uuid import UUID

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api.case_management_routes import register_case_management_routes
from server.case_management import repository
from server.contracts.case_management import (
    CourtCase,
    EvidenceItemCreate,
    EvidenceItemDetail,
    EvidenceReviewCreate,
    EvidenceReviewResult,
    KnowledgeSourceResolveRequest,
    Matter,
    MatterCreate,
    MatterList,
    ConversationContext,
    OriginalSourceContent,
)

MATTER_ID = UUID("11111111-1111-1111-1111-111111111111")
CASE_ID = UUID("22222222-2222-2222-2222-222222222222")
RECORD_ID = UUID("33333333-3333-3333-3333-333333333333")
HASH_ID = UUID("44444444-4444-4444-4444-444444444444")
SOURCE_ID = UUID("55555555-5555-5555-5555-555555555555")
PROMOTION_ID = UUID("66666666-6666-6666-6666-666666666666")
RUN_ID = UUID("77777777-7777-7777-7777-777777777777")
FILE_NODE_ID = UUID("12121212-1212-1212-1212-121212121212")
TASK_ID = UUID("99999999-9999-9999-9999-999999999999")
DECISION_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
CONVERSATION_ID = UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb")
ACQUISITION_ID = UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
REALIZATION_ID = UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")
NOW = datetime(2026, 8, 15, tzinfo=UTC)
SHA256 = "ab" * 32


def _matter() -> Matter:
    return Matter(
        id=MATTER_ID,
        title="Primary matter",
        description=None,
        status="active",
        partition_keys=["primary"],
        created_at=NOW,
        updated_at=NOW,
    )


def _court_case() -> CourtCase:
    return CourtCase(
        id=CASE_ID,
        matter_id=MATTER_ID,
        caption="Salem v Salem",
        court_name="Family Division",
        docket_number="2026-1",
        jurisdiction="Michigan",
        case_type="custody",
        status="active",
        filed_on=date(2026, 1, 1),
        closed_on=None,
        is_primary=True,
        created_at=NOW,
        updated_at=NOW,
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    app = FastAPI()
    register_case_management_routes(app)
    monkeypatch.setattr(
        "server.case_management.service.list_matters",
        lambda **kwargs: MatterList(data=[_matter()], total=1, limit=kwargs["limit"], offset=kwargs["offset"]),
    )
    monkeypatch.setattr("server.case_management.service.create_matter", lambda body: _matter())
    monkeypatch.setattr("server.case_management.service.create_court_case", lambda matter_id, body: _court_case())
    return TestClient(app)


def test_routes_list_and_create_framework_neutral_matters(client: TestClient) -> None:
    listed = client.get("/v1/matters", params={"limit": 10, "offset": 0})
    assert listed.status_code == 200
    assert listed.json()["data"][0]["title"] == "Primary matter"
    assert listed.json()["data"][0]["partition_keys"] == ["primary"]

    created = client.post("/v1/matters", json={"title": "Primary matter", "partition_key": "primary"})
    assert created.status_code == 201
    assert "knowledge_id" not in created.json()


def test_route_uses_caption_and_expanded_court_case_contract(client: TestClient) -> None:
    response = client.post(
        f"/v1/matters/{MATTER_ID}/court-cases",
        json={
            "caption": "Salem v Salem",
            "status": "active",
            "jurisdiction": "Michigan",
            "filed_on": "2026-01-01",
            "is_primary": True,
        },
    )
    assert response.status_code == 201
    assert response.json()["caption"] == "Salem v Salem"
    assert response.json()["jurisdiction"] == "Michigan"


def test_route_translates_cross_matter_denial(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(*args, **kwargs):
        raise repository.CaseRepositoryError("court case is not part of this matter", 403)

    monkeypatch.setattr("server.case_management.service.promote_evidence", denied)
    response = client.post(
        f"/v1/matters/{MATTER_ID}/evidence-items",
        json=_promotion_payload(),
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "court case is not part of this matter"


def test_route_records_review_without_claiming_legal_safety(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    reviewed = {**_item_row(), "review_status": "approved", "hitl_required": False}
    monkeypatch.setattr(
        "server.case_management.service.review_evidence",
        lambda matter_id, evidence_item_id, body: EvidenceReviewResult(
            item=reviewed,
            task_id=TASK_ID,
            decision_id=DECISION_ID,
            decision="approved",
            court_readiness="review_passed",
        ),
    )
    response = client.post(
        f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}/reviews",
        json={"decision": "approved", "rationale": "Reviewed exact record."},
    )
    assert response.status_code == 200
    assert response.json()["item"]["review_status"] == "approved"
    assert response.json()["item"]["safe_for_legal_use"] is False
    assert response.json()["item"]["is_authenticated"] is False


def test_route_lists_append_only_review_history(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "server.case_management.service.list_evidence_reviews",
        lambda matter_id, evidence_item_id: {
            "data": [
                {
                    "decision_id": str(DECISION_ID),
                    "task_id": str(TASK_ID),
                    "evidence_item_id": str(evidence_item_id),
                    "reviewer": "owner",
                    "decision": "approved",
                    "court_readiness": "review_passed",
                    "rationale": "Reviewed exact record.",
                    "decided_at": NOW,
                }
            ],
            "total": 1,
        },
    )
    response = client.get(f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}/reviews")
    assert response.status_code == 200
    assert response.json()["data"][0]["rationale"] == "Reviewed exact record."


def test_route_returns_nested_public_custody_detail(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "server.case_management.service.get_evidence_detail",
        lambda matter_id, evidence_item_id: repository._evidence_detail_from_row(_detail_row()),
    )

    response = client.get(f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["item"]["id"] == str(_item_row()["id"])
    assert payload["promotion"]["partition_key"] == "primary"
    assert set(payload["promotion"]["source_pointer"]) == {
        "matter_id",
        "court_case_id",
        "partition_key",
        "lane",
        "normalized_record_id",
        "evidence_hash_id",
        "source_id",
        "sha256",
        "conversation_id",
        "retrieval_ref",
        "content_ref",
        "chunk_ref",
        "quote",
    }
    assert payload["record"]["id"] == str(RECORD_ID)
    assert payload["record"]["review_status"] == "needs_more_evidence"
    assert payload["custody_hash"]["digest_sha256"] == SHA256
    assert payload["source"]["original_filename"] == "export.json"
    assert payload["file_node"] is None
    serialized = response.text
    for private_field in (
        "local_path",
        "private_metadata",
        "r2_bucket",
        "r2_key",
        "original_metadata",
        "derived_metadata",
    ):
        assert private_field not in serialized


def test_routes_bound_pagination_and_validate_uuid(client: TestClient) -> None:
    assert client.get("/v1/matters", params={"limit": 201}).status_code == 422
    assert client.get("/v1/matters/not-a-uuid").status_code == 422


def test_public_actor_fields_cannot_spoof_owner(client: TestClient) -> None:
    matter = client.post(
        "/v1/matters",
        json={"title": "Spoof attempt", "partition_key": "primary", "created_by": "attacker"},
    )
    assert matter.status_code == 422

    review = client.post(
        f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}/reviews",
        json={"decision": "approved", "rationale": "spoof", "reviewer": "attacker"},
    )
    assert review.status_code == 422


class _FakeResult:
    def __init__(self, value):
        self.value = value

    def mappings(self):
        return self

    def first(self):
        return self.value

    def all(self):
        return self.value

    def one(self):
        return self.value

    def scalar(self):
        return self.value

    def scalar_one(self):
        return self.value


class _FakeConnection:
    def __init__(self, engine: "_FakeEngine") -> None:
        self.engine = engine

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, statement, params=None):
        self.engine.calls.append((str(statement), params))
        return _FakeResult(self.engine.next_value())


class _FakeEngine:
    def __init__(self, values: list[object]) -> None:
        self.values = values
        self.index = 0
        self.calls: list[tuple[str, object]] = []

    def next_value(self):
        value = self.values[self.index]
        self.index += 1
        return value

    def connect(self):
        return _FakeConnection(self)

    def begin(self):
        return _FakeConnection(self)


def _source_row() -> dict:
    return {
        "normalized_record_id": RECORD_ID,
        "artifact_id": HASH_ID,
        "conversation_id": "conversation-1",
        "record_type": "message",
        "role": "owner",
        "content": "Exact source sentence with surrounding context.",
        "occurred_at": NOW,
        "disclosure_tier": "contemporaneous",
        "review_status": "unreviewed",
        "source_run_id": RUN_ID,
        "evidence_hash_id": HASH_ID,
        "source_id": SOURCE_ID,
        "file_node_id": None,
        "sha256": SHA256,
    }


def _item_row() -> dict:
    return {
        "id": UUID("88888888-8888-8888-8888-888888888888"),
        "matter_id": MATTER_ID,
        "court_case_id": CASE_ID,
        "title": "Exact source sentence",
        "description": None,
        "quote": "Exact source sentence",
        "evidence_type": "communication",
        "evidence_date": NOW,
        "normalized_record_id": RECORD_ID,
        "evidence_hash_id": HASH_ID,
        "source_id": SOURCE_ID,
        "file_node_id": None,
        "source_run_id": RUN_ID,
        "review_status": "unreviewed",
        "hitl_required": True,
        "safe_for_legal_use": False,
        "is_authenticated": False,
        "created_by": "owner",
        "created_at": NOW,
    }


def _detail_row() -> dict:
    return {
        **_item_row(),
        "promotion_id": PROMOTION_ID,
        "promotion_partition_key": "primary",
        "promotion_knowledge_lane": "evidence",
        "promotion_retrieval_item_ref": "retrieval-1",
        "promotion_content_ref": "content-1",
        "promotion_chunk_ref": "chunk-1",
        "promotion_source_pointer": {
            "matter_id": str(MATTER_ID),
            "court_case_id": str(CASE_ID),
            "partition_key": "primary",
            "lane": "evidence",
            "normalized_record_id": str(RECORD_ID),
            "evidence_hash_id": str(HASH_ID),
            "source_id": str(SOURCE_ID),
            "sha256": SHA256,
            "conversation_id": "conversation-1",
            "retrieval_ref": "retrieval-1",
            "content_ref": "content-1",
            "chunk_ref": "chunk-1",
            "quote": "Exact source sentence",
            "local_path": "C:/private/evidence/export.json",
            "private_metadata": {"secret": True},
        },
        "promotion_promoted_by": "owner",
        "promotion_promoted_at": NOW,
        "record_id": RECORD_ID,
        "record_type": "message",
        "record_source": "sbv",
        "record_conversation_id": "conversation-1",
        "record_role": "sender",
        "record_content": "Exact source sentence with surrounding context.",
        "record_occurred_at": NOW,
        "record_acquired_at": NOW,
        "record_ingested_at": NOW,
        "record_realized_at": None,
        "record_disclosure_tier": "contemporaneous",
        "record_review_status": "needs_more_evidence",
        "record_case_id": "primary",
        "custody_hash_id": HASH_ID,
        "custody_hash_source_ref": "source/export.json",
        "custody_hash_algo": "sha256",
        "custody_hash_digest_sha256": SHA256,
        "custody_hash_level": "H1",
        "custody_hash_canon_version": "h1-rawbytes-v1",
        "custody_hash_hashed_at": NOW,
        "custody_hash_computed_by": "sbv",
        "custody_source_id": SOURCE_ID,
        "custody_source_sha256": "ef" * 32,
        "custody_source_byte_size": 1024,
        "custody_source_mime_type": "application/json",
        "custody_source_original_filename": "export.json",
        "custody_source_type": "chat_export",
        "custody_source_platform": "iMessage",
        "custody_source_acquisition_source": "sbv",
        "custody_source_acquisition_method": "manual_export",
        "custody_source_acquired_at_utc": NOW,
        "custody_source_acquired_certainty": "exact",
        "custody_source_provenance_tier": "r2_canonical",
        "custody_source_hash_canon_version": "source-container-v2",
        "custody_source_custody_status": "verified",
        "custody_source_review_status": "reviewed",
        "custody_source_verified_by": "owner",
        "custody_source_verified_at": NOW,
        "detail_file_node_id": None,
        "file_node_kind": None,
        "file_node_path": None,
        "file_node_ordinal": None,
        "file_node_sha256": None,
        "file_node_byte_span_start": None,
        "file_node_byte_span_end": None,
        "file_node_locator": None,
        "file_node_mime_type": None,
    }


def _readiness_row() -> dict:
    return {
        "id": _item_row()["id"],
        "matter_id": MATTER_ID,
        "review_status": "approved",
        "hitl_required": False,
        "safe_for_legal_use": True,
        "is_hypothesis": False,
        "is_authenticated": True,
        "authentication_method": "hash_chain_of_custody",
        "confidence": 0.8,
        "confidence_tier": "high",
        "privacy_sensitivity": "none",
        "redaction_status": "none",
        "sensitivity_tier": "restricted",
        "source_custody_status": "verified",
        "source_review_status": "reviewed",
        "source_verified_by": "owner",
        "source_verified_at": NOW,
        "source_privacy_sensitivity": "none",
        "source_sensitivity_tier": "restricted",
        "content_review_decision_id": DECISION_ID,
        "content_review_approved": True,
        "h1_valid": True,
        "event_chain_valid": True,
        "verified_event_present": True,
        "court_export_view_member": True,
    }


def _resolve_payload() -> dict:
    return {
        "lane": "evidence",
        "partition_key": "primary",
        "artifact_id": str(HASH_ID),
        "sha256": SHA256,
        "conversation_id": "conversation-1",
        "quote": "Exact source sentence",
        "retrieval_ref": "retrieval-1",
        "content_ref": "content-1",
        "chunk_ref": "chunk-1",
    }


def _promotion_payload() -> dict:
    return {
        "court_case_id": str(CASE_ID),
        "source": {**_resolve_payload(), "normalized_record_id": str(RECORD_ID)},
        "title": "Exact source sentence",
        "quote": "Exact source sentence",
        "evidence_type": "communication",
        "created_by": "owner",
    }


def test_resolve_source_requires_custody_and_exact_quote(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _FakeEngine([(1,), (1,), [_source_row()]])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)
    body = KnowledgeSourceResolveRequest.model_validate(_resolve_payload())

    result = repository.resolve_source(MATTER_ID, body)

    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.normalized_record_id == RECORD_ID
    assert candidate.evidence_hash_id == HASH_ID
    assert candidate.source_run_id == RUN_ID
    source_sql = engine.calls[-1][0]
    assert "JOIN evidence.evidence_hash" in source_sql
    assert "nr.case_id = :partition_key" in source_sql
    assert "eh.algo = 'sha256'" in source_sql
    assert "eh.canon_version = 'h1-rawbytes-v1'" in source_sql
    assert "encode(eh.digest, 'hex') = :sha256" in source_sql
    assert "position(:quote in nr.content) > 0" in source_sql
    assert engine.calls[-1][1]["quote"] == "Exact source sentence"


def test_resolve_source_fails_closed_outside_evidence_lane() -> None:
    payload = {**_resolve_payload(), "lane": "legal"}
    with pytest.raises(repository.CaseRepositoryError, match="custody-backed evidence-lane"):
        repository.resolve_source(MATTER_ID, KnowledgeSourceResolveRequest.model_validate(payload))


def test_create_matter_atomically_creates_default_case_and_partition(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    matter_row = {
        "id": MATTER_ID,
        "title": "New matter",
        "description": None,
        "status": "active",
        "created_at": NOW,
        "updated_at": NOW,
    }
    engine = _FakeEngine([matter_row, CASE_ID, None])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.create_matter(
        MatterCreate(title="New matter", partition_key="new-partition", created_by="owner")
    )

    assert result.partition_keys == ["new-partition"]
    court_insert = engine.calls[1]
    assert "INSERT INTO registry.court_case" in court_insert[0]
    assert court_insert[1]["caption"] == "New matter"
    bridge_insert = engine.calls[2]
    assert bridge_insert[1]["default_case_id"] == CASE_ID


def test_promotion_identity_ignores_reindex_generated_refs() -> None:
    first = EvidenceItemCreate.model_validate(_promotion_payload())
    second_payload = _promotion_payload()
    second_payload["source"] = {
        **second_payload["source"],
        "retrieval_ref": "retrieval-after-reindex",
        "content_ref": "new-content-ref",
        "chunk_ref": "new-chunk-ref",
    }
    second = EvidenceItemCreate.model_validate(second_payload)

    first_key, first_pointer_hash, _ = repository._promotion_identity(MATTER_ID, first, _source_row())
    second_key, second_pointer_hash, _ = repository._promotion_identity(MATTER_ID, second, _source_row())

    assert second_key == first_key
    assert second_pointer_hash == first_pointer_hash


def test_promote_is_unsafe_audited_and_idempotent_by_pointer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _FakeEngine(
        [
            (1,),
            (1,),
            (1,),
            _source_row(),
            SHA256,
            None,
            None,
            _item_row(),
            PROMOTION_ID,
            None,
        ]
    )
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)
    audit_calls: list[dict] = []

    def fake_audit(*args, **kwargs):
        audit_calls.append({"args": args, "kwargs": kwargs})
        return 1

    monkeypatch.setattr("server.core.audit.record", fake_audit)
    body = EvidenceItemCreate.model_validate(_promotion_payload())

    result = repository.promote_evidence(MATTER_ID, body)

    assert result.created is True
    assert result.item.review_status == "unreviewed"
    assert result.item.hitl_required is True
    assert result.item.safe_for_legal_use is False
    assert result.item.is_authenticated is False
    assert audit_calls[0]["kwargs"]["connection"] is not None
    insert_sql = next(sql for sql, _ in engine.calls if "INSERT INTO analysis.evidence_item" in sql)
    assert "case_id, matter_id, court_case_id" in insert_sql
    assert "source_run_id" in insert_sql
    promotion_sql = next(sql for sql, _ in engine.calls if "INSERT INTO analysis.knowledge_evidence_promotion" in sql)
    assert "source_pointer_hash" in promotion_sql


def test_promote_retry_returns_existing_without_second_insert(monkeypatch: pytest.MonkeyPatch) -> None:
    existing = {**_item_row(), "promotion_id": PROMOTION_ID}
    engine = _FakeEngine([(1,), (1,), (1,), _source_row(), SHA256, None, existing])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.promote_evidence(MATTER_ID, EvidenceItemCreate.model_validate(_promotion_payload()))

    assert result.created is False
    assert result.promotion_id == PROMOTION_ID
    assert not any("INSERT INTO analysis.evidence_item" in sql for sql, _ in engine.calls)


def test_review_records_append_only_decision_but_keeps_item_legally_unsafe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reviewed_row = {**_item_row(), "review_status": "approved", "hitl_required": False}
    engine = _FakeEngine([_item_row(), TASK_ID, DECISION_ID, reviewed_row, None])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)
    audit_calls: list[dict] = []

    def fake_audit(*args, **kwargs):
        audit_calls.append({"args": args, "kwargs": kwargs})
        return 1

    monkeypatch.setattr("server.core.audit.record", fake_audit)
    result = repository.review_evidence(
        MATTER_ID,
        _item_row()["id"],
        EvidenceReviewCreate(
            decision="approved",
            rationale="Reviewed the exact normalized record.",
        ),
    )

    assert result.item.review_status == "approved"
    assert result.item.hitl_required is False
    assert result.item.safe_for_legal_use is False
    assert result.item.is_authenticated is False
    assert result.court_readiness == "review_passed"
    decision_sql = next(sql for sql, _ in engine.calls if "INSERT INTO analysis.review_decision" in sql)
    assert "court_readiness" in decision_sql
    update_sql = next(sql for sql, _ in engine.calls if "UPDATE analysis.evidence_item" in sql)
    assert "safe_for_legal_use = false" in update_sql
    assert audit_calls[0]["kwargs"]["object_schema"] == "analysis.review_decision"


def test_review_rejects_second_terminal_decision(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _FakeEngine([_item_row(), None])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    with pytest.raises(repository.CaseRepositoryError, match="already resolved") as exc:
        repository.review_evidence(
            MATTER_ID,
            _item_row()["id"],
            EvidenceReviewCreate(decision="rejected", rationale="Duplicate terminal review."),
        )

    assert exc.value.status_code == 409
    assert not any("INSERT INTO analysis.review_decision" in sql for sql, _ in engine.calls)


def test_review_history_is_matter_scoped_and_ordered(monkeypatch: pytest.MonkeyPatch) -> None:
    review_row = {
        "decision_id": DECISION_ID,
        "task_id": TASK_ID,
        "evidence_item_id": _item_row()["id"],
        "reviewer": "owner",
        "decision": "approved",
        "court_readiness": "review_passed",
        "rationale": "Reviewed exact normalized record.",
        "decided_at": NOW,
    }
    engine = _FakeEngine([(1,), [review_row]])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.list_evidence_reviews(MATTER_ID, _item_row()["id"])

    assert result.total == 1
    assert result.data[0].decision_id == DECISION_ID
    assert result.data[0].rationale == "Reviewed exact normalized record."
    assert "item.matter_id = :matter_id" in engine.calls[0][0]
    assert "ORDER BY decided_at, decision_id" in engine.calls[1][0]


def test_court_readiness_route_returns_nested_gates_without_private_fields(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    readiness = repository._court_readiness_from_row(_readiness_row())
    monkeypatch.setattr("server.case_management.service.get_court_readiness", lambda *_args: readiness)

    response = client.get(f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}/court-readiness")

    assert response.status_code == 200
    payload = response.json()
    assert payload["readiness_passed"] is True
    assert payload["blockers"] == []
    assert payload["gates"]["content_review"]["decision_id"] == str(DECISION_ID)
    assert payload["gates"]["assertion"] == {"not_hypothesis": True}
    assert payload["gates"]["court_export"] == {"view_member": True}
    serialized = response.text
    assert "local_path" not in serialized
    assert "r2_key" not in serialized
    assert "private_metadata" not in serialized


@pytest.mark.parametrize(
    ("changes", "blocker"),
    [
        ({"content_review_approved": False}, "CONTENT_REVIEW_REQUIRED"),
        ({"source_custody_status": "collected"}, "CUSTODY_NOT_VERIFIED"),
        ({"source_review_status": "flagged"}, "CUSTODY_NOT_VERIFIED"),
        ({"source_verified_by": None}, "CUSTODY_NOT_VERIFIED"),
        ({"source_verified_at": None}, "CUSTODY_NOT_VERIFIED"),
        ({"verified_event_present": False}, "CUSTODY_NOT_VERIFIED"),
        ({"h1_valid": False}, "CUSTODY_CHAIN_INVALID"),
        ({"event_chain_valid": False}, "CUSTODY_CHAIN_INVALID"),
        ({"is_authenticated": False}, "AUTHENTICATION_REQUIRED"),
        ({"authentication_method": None}, "AUTHENTICATION_REQUIRED"),
        ({"confidence_tier": "low"}, "CONFIDENCE_NOT_EXPORTABLE"),
        ({"is_hypothesis": True}, "HYPOTHESIS_NOT_EXPORTABLE"),
        ({"redaction_status": "required"}, "REDACTION_REQUIRED"),
        ({"privacy_sensitivity": "minor"}, "REDACTION_REQUIRED"),
        ({"source_privacy_sensitivity": "pii"}, "REDACTION_REQUIRED"),
        ({"sensitivity_tier": "sealed"}, "SENSITIVITY_SEALED"),
        ({"source_sensitivity_tier": "sealed"}, "SENSITIVITY_SEALED"),
        ({"safe_for_legal_use": False}, "NOT_RELEASED"),
    ],
)
def test_court_readiness_reports_each_fail_closed_blocker(changes: dict, blocker: str) -> None:
    row = {**_readiness_row(), **changes, "court_export_view_member": False}

    result = repository._court_readiness_from_row(row)

    assert result.readiness_passed is False
    assert blocker in result.blockers


def test_court_readiness_requires_actual_export_view_membership() -> None:
    row = {**_readiness_row(), "court_export_view_member": False}

    result = repository._court_readiness_from_row(row)

    assert result.readiness_passed is False
    assert result.blockers == ["NOT_RELEASED"]
    assert result.gates.court_export.view_member is False


def test_court_readiness_repository_fails_404_on_exact_provenance_mismatch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _FakeEngine([None])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    with pytest.raises(repository.CaseRepositoryError, match="not found in this matter") as exc:
        repository.get_court_readiness(MATTER_ID, _item_row()["id"])

    assert exc.value.status_code == 404


def test_court_readiness_sql_uses_authoritative_view_latest_review_and_custody_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _FakeEngine([_readiness_row()])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.get_court_readiness(MATTER_ID, _item_row()["id"])

    assert result.readiness_passed is True
    sql, params = engine.calls[0]
    normalized = " ".join(sql.split())
    assert "analysis.vw_court_export" in normalized
    assert "analysis.knowledge_evidence_pointer_hash" in normalized
    assert "working.normalized_record" in normalized
    assert "promotion.file_node_id IS NOT DISTINCT FROM ei.file_node_id" in normalized
    assert "task.trigger_code = 'knowledge_evidence_promotion'" in normalized
    assert "ORDER BY decision.decided_at DESC, decision.decision_id DESC" in normalized
    assert "lag(event.event_digest) OVER (ORDER BY event.seq)" in normalized
    assert "generate_series(-720, 840, 15)" in normalized
    assert "chained.event_digest_matches_legacy_trigger" in normalized
    assert "chained.evidence_hash_id = exact_item.evidence_hash_id" in normalized
    assert "chained.file_node_id IS NOT DISTINCT FROM exact_item.file_node_id" in normalized
    assert params == {"matter_id": MATTER_ID, "evidence_item_id": _item_row()["id"]}


def test_promote_denies_foreign_court_case_before_source_write(monkeypatch: pytest.MonkeyPatch) -> None:
    engine = _FakeEngine([(1,), (1,), None])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    with pytest.raises(repository.CaseRepositoryError, match="not part of this matter") as exc:
        repository.promote_evidence(MATTER_ID, EvidenceItemCreate.model_validate(_promotion_payload()))

    assert exc.value.status_code == 403
    assert not any(sql.lstrip().startswith("INSERT") for sql, _ in engine.calls)


def test_evidence_detail_uses_exact_matter_scoped_public_custody_join(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _FakeEngine([_detail_row(), {"ready": False}, {"ready": False}])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.get_evidence_detail(MATTER_ID, _item_row()["id"])

    assert isinstance(result, EvidenceItemDetail)
    assert result.promotion.id == PROMOTION_ID
    assert result.record.content == "Exact source sentence with surrounding context."
    assert result.record.source_kind == "unclassified"
    assert result.record.source_available_from is None
    assert result.record.realization_events == []
    assert result.custody_hash.digest_sha256 == SHA256
    assert result.source.sha256 == "ef" * 32
    assert result.source.hash_canon_version == "source-container-v2"
    assert result.file_node is None
    sql = engine.calls[0][0]
    assert "promotion.matter_id = ei.matter_id" in sql
    assert "record.case_id = promotion.partition_key" in sql
    assert "custody_hash.source_id = promotion.source_id" in sql
    assert "custody_source.sha256 = custody_hash.digest" not in sql
    assert "custody_source.hash_canon_version = custody_hash.canon_version" not in sql
    assert "analysis.knowledge_evidence_pointer_hash" in sql
    assert "record.realized_at" not in sql
    assert "record.acquired_at" not in sql
    for private_column in ("local_path", "r2_bucket", "r2_key", "original_metadata", "derived_metadata"):
        assert private_column not in sql


def test_evidence_detail_returns_404_for_cross_matter_or_broken_provenance(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    engine = _FakeEngine([None])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    with pytest.raises(repository.CaseRepositoryError, match="not found in this matter") as exc:
        repository.get_evidence_detail(MATTER_ID, _item_row()["id"])

    assert exc.value.status_code == 404


def test_evidence_detail_exposes_optional_file_node_without_private_attrs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    row = {
        **_detail_row(),
        "file_node_id": FILE_NODE_ID,
        "detail_file_node_id": FILE_NODE_ID,
        "file_node_kind": "message_unit",
        "file_node_path": "messages.42",
        "file_node_ordinal": 42,
        "file_node_sha256": "cd" * 32,
        "file_node_byte_span_start": 100,
        "file_node_byte_span_end": 200,
        "file_node_locator": {"message_index": 42},
        "file_node_mime_type": "text/plain",
    }
    engine = _FakeEngine([row, {"ready": False}, {"ready": False}])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.get_evidence_detail(MATTER_ID, _item_row()["id"])

    assert result.file_node is not None
    assert result.file_node.node_path == "messages.42"
    assert result.file_node.locator == {"message_index": 42}


def test_evidence_detail_exposes_approved_third_party_context_and_plural_realizations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    projection_row = {
        "projection_kind": "acquired_third_party",
        "source_available_from": NOW,
        "conversation_id": CONVERSATION_ID,
        "external_thread_key": "friend-thread-1",
        "platform": "iMessage",
        "title": "Actual third-party thread",
        "acquisition_id": ACQUISITION_ID,
        "acquired_at": NOW,
        "actual_sender": "Her friend",
        "actual_recipients": ["Her"],
        "actual_participants": ["Her friend", "Her"],
    }
    realization_rows = [
        {
            "id": REALIZATION_ID,
            "kind": "betrayal",
            "realized_at": NOW,
            "approval_state": "approved",
            "trigger_record_id": RECORD_ID,
            "evidence_pointer": {"record_id": str(RECORD_ID)},
            "proposer": "owner",
            "proposed_at": NOW,
            "approved_at": NOW,
            "approved_by": "owner",
            "notes": "Later understood in context.",
        }
    ]
    engine = _FakeEngine(
        [
            _detail_row(),
            {"ready": True},
            projection_row,
            {"ready": True},
            realization_rows,
        ]
    )
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.get_evidence_detail(MATTER_ID, _item_row()["id"])

    assert result.record.source_kind == "third_party_acquired"
    assert result.record.projection_kind == "derived_third_party"
    assert result.record.source_available_from == NOW
    assert result.record.third_party_conversation is not None
    assert result.record.third_party_conversation.actual_sender == "Her friend"
    assert result.record.third_party_conversation.actual_recipients == ["Her"]
    assert "owner" not in result.record.third_party_conversation.actual_participants
    assert [event.id for event in result.record.realization_events] == [REALIZATION_ID]


def test_route_returns_custody_resolved_original_source_content(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = OriginalSourceContent(
        matter_id=MATTER_ID,
        evidence_item_id=_item_row()["id"],
        normalized_record_id=RECORD_ID,
        source_id=SOURCE_ID,
        file_node_id=None,
        evidence_hash_id=HASH_ID,
        sha256=SHA256,
        byte_size=23,
        content_byte_size=23,
        mime_type="text/plain",
        original_filename="messages.txt",
        content="Original source text.",
        encoding="utf-8",
        source_pointer={"source_id": str(SOURCE_ID), "evidence_hash_id": str(HASH_ID)},
        provenance={"source_id": str(SOURCE_ID)},
        h1=SHA256,
        h2=None,
        h3=None,
    )
    monkeypatch.setattr("server.case_management.service.get_original_source_content", lambda *_: source)

    response = client.get(f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}/source-content")

    assert response.status_code == 200
    assert response.json()["content"] == "Original source text."
    assert response.json()["source_id"] == str(SOURCE_ID)


def test_route_returns_bounded_deterministic_conversation_context(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = ConversationContext(
        matter_id=MATTER_ID,
        evidence_item_id=_item_row()["id"],
        selected_normalized_record_id=RECORD_ID,
        messages=[
            {
                "id": RECORD_ID,
                "normalized_record_id": RECORD_ID,
                "content": "First source message.",
                "sender": "Other party",
                "recipients": ["Owner"],
                "occurred_at": NOW,
                "source_kind": "first_party",
                "projection_kind": "authored_normalized",
                "source_available_from": NOW,
                "source_pointer": {"normalized_record_id": str(RECORD_ID)},
            }
        ],
        before=0,
        after=0,
        total=1,
    )
    captured: dict[str, object] = {}

    def fake_context(matter_id, evidence_item_id, *, before, after):
        captured.update(before=before, after=after)
        return context

    monkeypatch.setattr("server.case_management.service.get_conversation_context", fake_context)
    response = client.get(
        f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}/conversation-context",
        params={"before": 2, "after": 3},
    )

    assert response.status_code == 200
    assert captured == {"before": 2, "after": 3}
    assert response.json()["messages"][0]["sender"] == "Other party"
    assert response.json()["messages"][0]["recipients"] == ["Owner"]


def test_context_query_bounds_are_enforced(client: TestClient) -> None:
    response = client.get(
        f"/v1/matters/{MATTER_ID}/evidence-items/{_item_row()['id']}/conversation-context",
        params={"before": 101},
    )
    assert response.status_code == 422


def test_original_source_allows_container_sha_to_differ_from_raw_h1(monkeypatch: pytest.MonkeyPatch) -> None:
    detail = repository._evidence_detail_from_row(_detail_row())
    assert detail.source.sha256 != detail.custody_hash.digest_sha256
    monkeypatch.setattr(repository, "get_evidence_detail", lambda *_: detail)
    monkeypatch.setattr(repository, "_get_engine", lambda: _FakeEngine([]))
    monkeypatch.setattr(
        repository,
        "_custody_blob_row",
        lambda *_: {"blob_key": "aa/raw.txt", "h1": SHA256, "h2": None, "h3": None},
    )
    monkeypatch.setattr(repository, "_safe_custody_path", lambda _: Path("raw.txt"))
    monkeypatch.setattr(repository, "_read_original_text", lambda *args, **kwargs: (b"raw source", 9))

    result = repository.get_original_source_content(MATTER_ID, _item_row()["id"])

    assert result.content == "raw source"
    assert result.h1 == SHA256


def test_context_pre_0026_schema_returns_selected_record_without_invented_parties(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    detail_row = _detail_row()
    detail_row["record_conversation_id"] = "conversation-1"
    detail = repository._evidence_detail_from_row(detail_row)
    monkeypatch.setattr(repository, "get_evidence_detail", lambda *_: detail)
    engine = _FakeEngine([{"ready": False}])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)
    monkeypatch.setattr(repository, "_projection_context_available", lambda *_: False)

    result = repository.get_conversation_context(MATTER_ID, _item_row()["id"], before=25, after=25)

    assert result.context_available is False
    assert result.context_complete is False
    assert result.messages[0].content == detail.record.content
    assert result.messages[0].sender is None
    assert result.messages[0].recipients == []
