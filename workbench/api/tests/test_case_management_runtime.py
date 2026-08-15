"""HTTP boundary coverage for Matter source resolution and promotion.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.repo.spine_client import SpineError
from app.runtime import case_management as runtime

MATTER_ID = "11111111-1111-4111-8111-111111111111"
COURT_CASE_ID = "22222222-2222-4222-8222-222222222222"
ARTIFACT_ID = "33333333-3333-4333-8333-333333333333"
RECORD_ID = "44444444-4444-4444-8444-444444444444"
HASH_ID = "55555555-5555-4555-8555-555555555555"
SOURCE_ID = "66666666-6666-4666-8666-666666666666"
PROMOTION_ID = "77777777-7777-4777-8777-777777777777"
ITEM_ID = "88888888-8888-4888-8888-888888888888"
TASK_ID = "99999999-9999-4999-8999-999999999999"
DECISION_ID = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
SHA256 = "a" * 64
NOW = "2026-08-15T12:00:00Z"


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(runtime.router)
    return TestClient(app)


def test_resolve_requires_custody_coordinates():
    response = _client().post(
        f"/api/matters/{MATTER_ID}/knowledge/resolve",
        json={"lane": "evidence", "partition_key": "primary"},
    )
    assert response.status_code == 422


def test_resolve_returns_exact_candidates(monkeypatch):
    candidate = {
        "normalized_record_id": RECORD_ID,
        "artifact_id": ARTIFACT_ID,
        "evidence_hash_id": HASH_ID,
        "source_id": SOURCE_ID,
        "sha256": SHA256,
        "record_type": "message",
        "role": "sender",
        "content": "exact record",
        "disclosure_tier": "contemporaneous",
        "review_status": "unreviewed",
    }
    monkeypatch.setattr(
        runtime.service,
        "resolve_knowledge_source",
        lambda matter_id, payload: {"matter_id": str(matter_id), "candidates": [candidate]},
    )

    response = _client().post(
        f"/api/matters/{MATTER_ID}/knowledge/resolve",
        json={
            "lane": "evidence",
            "partition_key": "primary",
            "artifact_id": ARTIFACT_ID,
            "sha256": SHA256,
            "retrieval_ref": "hit-1",
        },
    )

    assert response.status_code == 200
    assert response.json()["candidates"][0]["normalized_record_id"] == RECORD_ID


def test_promoted_item_is_explicitly_unsafe_and_unreviewed(monkeypatch):
    item = {
        "id": ITEM_ID,
        "matter_id": MATTER_ID,
        "court_case_id": COURT_CASE_ID,
        "title": "Draft message",
        "evidence_type": "communication",
        "normalized_record_id": RECORD_ID,
        "evidence_hash_id": HASH_ID,
        "source_id": SOURCE_ID,
        "review_status": "unreviewed",
        "hitl_required": True,
        "safe_for_legal_use": False,
        "is_authenticated": False,
        "created_by": "owner",
        "created_at": NOW,
    }
    monkeypatch.setattr(
        runtime.service,
        "create_evidence_item",
        lambda matter_id, payload: {
            "item": item,
            "promotion_id": PROMOTION_ID,
            "created": True,
        },
    )
    response = _client().post(
        f"/api/matters/{MATTER_ID}/evidence-items",
        json={
            "court_case_id": COURT_CASE_ID,
            "source": {
                "lane": "evidence",
                "partition_key": "primary",
                "artifact_id": ARTIFACT_ID,
                "sha256": SHA256,
                "retrieval_ref": "hit-1",
                "normalized_record_id": RECORD_ID,
            },
            "title": "Draft message",
        },
    )

    assert response.status_code == 201
    assert response.json()["item"]["review_status"] == "unreviewed"
    assert response.json()["item"]["hitl_required"] is True
    assert response.json()["item"]["safe_for_legal_use"] is False


def test_idempotent_retry_accepts_existing_reviewed_unsafe_item(monkeypatch):
    item = {
        "id": ITEM_ID,
        "matter_id": MATTER_ID,
        "court_case_id": COURT_CASE_ID,
        "title": "Reviewed existing item",
        "evidence_type": "communication",
        "normalized_record_id": RECORD_ID,
        "evidence_hash_id": HASH_ID,
        "source_id": SOURCE_ID,
        "review_status": "approved",
        "hitl_required": False,
        "safe_for_legal_use": False,
        "is_authenticated": False,
        "created_by": "owner",
        "created_at": NOW,
    }
    monkeypatch.setattr(
        runtime.service,
        "create_evidence_item",
        lambda matter_id, payload: {
            "item": item,
            "promotion_id": PROMOTION_ID,
            "created": False,
        },
    )
    response = _client().post(
        f"/api/matters/{MATTER_ID}/evidence-items",
        json={
            "court_case_id": COURT_CASE_ID,
            "source": {
                "lane": "evidence",
                "partition_key": "primary",
                "artifact_id": ARTIFACT_ID,
                "sha256": SHA256,
                "retrieval_ref": "hit-1",
                "normalized_record_id": RECORD_ID,
            },
            "title": "Reviewed existing item",
        },
    )

    assert response.status_code == 201
    assert response.json()["created"] is False
    assert response.json()["item"]["review_status"] == "approved"


def test_workbench_rejects_spoofed_actor_fields():
    response = _client().post(
        "/api/matters",
        json={"title": "Spoof attempt", "partition_key": "primary", "created_by": "attacker"},
    )
    assert response.status_code == 422


def test_spine_cross_matter_denial_is_preserved(monkeypatch):
    monkeypatch.setattr(
        runtime.service,
        "get_matter",
        lambda matter_id: (_ for _ in ()).throw(SpineError("matter not found", 404)),
    )
    response = _client().get(f"/api/matters/{MATTER_ID}")
    assert response.status_code == 404
    assert response.json()["detail"] == "matter not found"


def test_review_approval_remains_unauthenticated_and_legally_unsafe(monkeypatch):
    item = {
        "id": ITEM_ID,
        "matter_id": MATTER_ID,
        "court_case_id": COURT_CASE_ID,
        "title": "Reviewed message",
        "evidence_type": "communication",
        "normalized_record_id": RECORD_ID,
        "evidence_hash_id": HASH_ID,
        "source_id": SOURCE_ID,
        "review_status": "approved",
        "hitl_required": False,
        "safe_for_legal_use": False,
        "is_authenticated": False,
        "created_by": "owner",
        "created_at": NOW,
    }
    monkeypatch.setattr(
        runtime.service,
        "review_evidence_item",
        lambda matter_id, item_id, payload: {
            "item": item,
            "task_id": TASK_ID,
            "decision_id": DECISION_ID,
            "decision": "approved",
            "court_readiness": "review_passed",
        },
    )

    response = _client().post(
        f"/api/matters/{MATTER_ID}/evidence-items/{ITEM_ID}/reviews",
        json={"decision": "approved", "rationale": "Reviewed exact record."},
    )

    assert response.status_code == 200
    assert response.json()["item"]["review_status"] == "approved"
    assert response.json()["item"]["safe_for_legal_use"] is False
    assert response.json()["item"]["is_authenticated"] is False


def test_review_rejects_blank_rationale():
    response = _client().post(
        f"/api/matters/{MATTER_ID}/evidence-items/{ITEM_ID}/reviews",
        json={"decision": "approved", "rationale": "   "},
    )
    assert response.status_code == 422


def test_review_history_exposes_reviewer_rationale_and_time(monkeypatch):
    monkeypatch.setattr(
        runtime.service,
        "list_evidence_reviews",
        lambda matter_id, item_id: {
            "data": [
                {
                    "decision_id": DECISION_ID,
                    "task_id": TASK_ID,
                    "evidence_item_id": str(item_id),
                    "reviewer": "owner",
                    "decision": "needs_context",
                    "court_readiness": "draft",
                    "rationale": "Compare this record with the complete thread.",
                    "decided_at": NOW,
                }
            ],
            "total": 1,
        },
    )

    response = _client().get(f"/api/matters/{MATTER_ID}/evidence-items/{ITEM_ID}/reviews")

    assert response.status_code == 200
    assert response.json()["total"] == 1
    assert response.json()["data"][0] == {
        "decision_id": DECISION_ID,
        "task_id": TASK_ID,
        "evidence_item_id": ITEM_ID,
        "reviewer": "owner",
        "decision": "needs_context",
        "court_readiness": "draft",
        "rationale": "Compare this record with the complete thread.",
        "decided_at": NOW,
    }
