"""Focused contracts for the Matter and Knowledge-to-Evidence spine API.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from datetime import UTC, date, datetime
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
    assert "INSERT INTO analysis.court_case" in court_insert[0]
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
    engine = _FakeEngine([_detail_row()])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.get_evidence_detail(MATTER_ID, _item_row()["id"])

    assert isinstance(result, EvidenceItemDetail)
    assert result.promotion.id == PROMOTION_ID
    assert result.record.content == "Exact source sentence with surrounding context."
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
    engine = _FakeEngine([row])
    monkeypatch.setattr(repository, "_get_engine", lambda: engine)

    result = repository.get_evidence_detail(MATTER_ID, _item_row()["id"])

    assert result.file_node is not None
    assert result.file_node.node_path == "messages.42"
    assert result.file_node.locator == {"message_index": 42}
