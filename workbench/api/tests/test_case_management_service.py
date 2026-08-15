"""Contract tests for the Workbench-to-spine Matter adapter.

Byline: Codex · GPT-5 · 2026-08-15
"""

from __future__ import annotations

from uuid import UUID

from app.service import case_management
from app.types.case_management import (
    EvidenceItemCreate,
    EvidenceReviewCreate,
    EvidenceSourcePointer,
    KnowledgeSourceRef,
)

MATTER_ID = UUID("11111111-1111-4111-8111-111111111111")
COURT_CASE_ID = UUID("22222222-2222-4222-8222-222222222222")
ARTIFACT_ID = UUID("33333333-3333-4333-8333-333333333333")
RECORD_ID = UUID("44444444-4444-4444-8444-444444444444")
SHA256 = "a" * 64


def test_resolve_forwards_only_platform_source_coordinates(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {"matter_id": str(MATTER_ID), "candidates": []}

    monkeypatch.setattr(case_management, "spine_json", fake_spine_json)
    payload = KnowledgeSourceRef(
        lane="evidence",
        partition_key="primary",
        artifact_id=ARTIFACT_ID,
        sha256=SHA256.upper(),
        quote="exact quote",
        retrieval_ref="hit-1",
        content_ref="content-1",
    )

    case_management.resolve_knowledge_source(MATTER_ID, payload)

    assert captured == {
        "method": "POST",
        "path": f"/v1/matters/{MATTER_ID}/knowledge/resolve",
        "kwargs": {
            "json": {
                "lane": "evidence",
                "partition_key": "primary",
                "artifact_id": str(ARTIFACT_ID),
                "sha256": SHA256,
                "quote": "exact quote",
                "retrieval_ref": "hit-1",
                "content_ref": "content-1",
            }
        },
    }


def test_promote_forwards_explicit_court_case_and_selected_record(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {}

    monkeypatch.setattr(case_management, "spine_json", fake_spine_json)
    source = EvidenceSourcePointer(
        lane="evidence",
        partition_key="primary",
        artifact_id=ARTIFACT_ID,
        sha256=SHA256,
        normalized_record_id=RECORD_ID,
        retrieval_ref="hit-1",
    )
    payload = EvidenceItemCreate(
        court_case_id=COURT_CASE_ID,
        source=source,
        title="Draft text message",
        quote="exact quote",
    )

    case_management.create_evidence_item(MATTER_ID, payload)

    assert captured["method"] == "POST"
    assert captured["path"] == f"/v1/matters/{MATTER_ID}/evidence-items"
    assert captured["kwargs"]["json"]["court_case_id"] == str(COURT_CASE_ID)
    assert captured["kwargs"]["json"]["source"]["normalized_record_id"] == str(RECORD_ID)
    assert captured["kwargs"]["json"]["source"]["partition_key"] == "primary"


def test_lists_are_bounded_and_matter_scoped(monkeypatch):
    calls = []
    monkeypatch.setattr(
        case_management,
        "spine_json",
        lambda method, path, **kwargs: calls.append((method, path, kwargs)) or {},
    )

    case_management.list_matters(limit=10, offset=2)
    case_management.list_evidence_items(MATTER_ID, limit=7, offset=3)

    assert calls == [
        ("GET", "/v1/matters", {"params": {"limit": 10, "offset": 2}}),
        (
            "GET",
            f"/v1/matters/{MATTER_ID}/evidence-items",
            {"params": {"limit": 7, "offset": 3}},
        ),
    ]


def test_review_forwards_human_decision_to_exact_matter_item(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {}

    monkeypatch.setattr(case_management, "spine_json", fake_spine_json)
    item_id = UUID("88888888-8888-4888-8888-888888888888")
    payload = EvidenceReviewCreate(
        decision="needs_changes",
        rationale="The record needs a narrower quote span.",
    )

    case_management.review_evidence_item(MATTER_ID, item_id, payload)

    assert captured == {
        "method": "POST",
        "path": f"/v1/matters/{MATTER_ID}/evidence-items/{item_id}/reviews",
        "kwargs": {
            "json": {
                "decision": "needs_changes",
                "rationale": "The record needs a narrower quote span.",
                "reviewer": "owner",
            }
        },
    }


def test_review_history_forwards_exact_matter_item_scope(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {"data": [], "total": 0}

    monkeypatch.setattr(case_management, "spine_json", fake_spine_json)
    item_id = UUID("88888888-8888-4888-8888-888888888888")

    result = case_management.list_evidence_reviews(MATTER_ID, item_id)

    assert result == {"data": [], "total": 0}
    assert captured == {
        "method": "GET",
        "path": f"/v1/matters/{MATTER_ID}/evidence-items/{item_id}/reviews",
        "kwargs": {},
    }


def test_evidence_detail_forwards_exact_matter_item_scope(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {}

    monkeypatch.setattr(case_management, "spine_json", fake_spine_json)
    item_id = UUID("88888888-8888-4888-8888-888888888888")

    case_management.get_evidence_detail(MATTER_ID, item_id)

    assert captured == {
        "method": "GET",
        "path": f"/v1/matters/{MATTER_ID}/evidence-items/{item_id}",
        "kwargs": {},
    }


def test_court_readiness_forwards_exact_matter_item_scope(monkeypatch):
    captured = {}

    def fake_spine_json(method, path, **kwargs):
        captured.update(method=method, path=path, kwargs=kwargs)
        return {}

    monkeypatch.setattr(case_management, "spine_json", fake_spine_json)
    item_id = UUID("88888888-8888-4888-8888-888888888888")

    case_management.get_court_readiness(MATTER_ID, item_id)

    assert captured == {
        "method": "GET",
        "path": f"/v1/matters/{MATTER_ID}/evidence-items/{item_id}/court-readiness",
        "kwargs": {},
    }
