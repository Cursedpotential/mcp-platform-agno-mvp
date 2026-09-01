# Byline: Codex · GPT-5 · 2026-08-16 (Data Explorer HTTP boundary coverage)
# Byline amendment: Codex · GPT-5 · 2026-08-18 (third-party review HTTP proxy coverage)
# Byline: Codex · GPT-5 · 2026-08-18 (authenticated review and entity routes)
"""HTTP contract coverage for bounded Data Explorer detail routes."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.runtime import inspect as runtime

_CONVERSATION_ID = "11111111-1111-1111-1111-111111111111"
_MESSAGE_ID = "22222222-2222-2222-2222-222222222222"
_PARTICIPANT_ID = "33333333-3333-3333-3333-333333333333"
_SENDER_ENTITY_ID = "44444444-4444-4444-4444-444444444444"
_RECIPIENT_ENTITY_ID = "55555555-5555-5555-5555-555555555555"


def _client() -> TestClient:
    app = FastAPI()

    @app.middleware("http")
    async def authenticated_owner(request, call_next):
        request.state.principal = "owner"
        return await call_next(request)

    app.include_router(runtime.router)
    return TestClient(app)


def test_table_detail_forwards_bounded_request(monkeypatch):
    captured = {}

    def fake_detail(schema, table_name, **kwargs):
        captured.update(schema=schema, table_name=table_name, **kwargs)
        return {"schema": schema, "table": table_name, "rows": []}

    monkeypatch.setattr(runtime.inspect_service, "get_table_detail", fake_detail)
    response = _client().get("/api/schemas/postgresql/working/normalized_record", params={"limit": 8})

    assert response.status_code == 200
    assert captured == {"schema": "working", "table_name": "normalized_record", "limit": 8}


def test_vector_detail_forwards_bounded_request(monkeypatch):
    captured = {}

    def fake_detail(collection_name, **kwargs):
        captured.update(collection_name=collection_name, **kwargs)
        return {"collection": collection_name, "objects": []}

    monkeypatch.setattr(runtime.inspect_service, "get_vector_detail", fake_detail)
    response = _client().get("/api/schemas/weaviate/Platform_knowledge", params={"limit": 4})

    assert response.status_code == 200
    assert captured == {"collection_name": "Platform_knowledge", "limit": 4}


def test_data_explorer_limits_fail_closed_before_spine():
    client = _client()
    assert client.get("/api/schemas/postgresql/working/normalized_record", params={"limit": 26}).status_code == 422
    assert client.get("/api/schemas/weaviate/Platform_knowledge", params={"limit": 11}).status_code == 422


def test_third_party_approval_forwards_required_review(monkeypatch):
    captured = {}

    def fake_approve(conversation_id, review):
        captured.update(conversation_id=conversation_id, review=review)
        return {"reprojection": {"status": "completed", "record_count": 1}}

    monkeypatch.setattr(runtime.inspect_service, "approve_third_party_conversation", fake_approve)
    payload = {
        "sender_entity_ids": {_MESSAGE_ID: _SENDER_ENTITY_ID},
        "participant_entity_ids": {_PARTICIPANT_ID: _RECIPIENT_ENTITY_ID},
        "reason": "manual comparison",
    }
    response = _client().post(f"/api/third-party-conversations/{_CONVERSATION_ID}/approve", json=payload)

    assert response.status_code == 200
    assert captured == {"conversation_id": _CONVERSATION_ID, "review": payload}


def test_third_party_approval_requires_actor_and_reason():
    response = _client().post(
        f"/api/third-party-conversations/{_CONVERSATION_ID}/approve",
        json={"sender_entity_ids": {}, "participant_entity_ids": {}},
    )
    assert response.status_code == 422


def test_third_party_approval_rejects_caller_actor(monkeypatch):
    captured = {}
    monkeypatch.setattr(
        runtime.inspect_service, "approve_third_party_conversation", lambda _, review: captured.update(review) or {}
    )
    response = _client().post(
        f"/api/third-party-conversations/{_CONVERSATION_ID}/approve",
        json={"sender_entity_ids": {}, "participant_entity_ids": {}, "reason": "checked", "actor": "intruder"},
    )
    assert response.status_code == 422
    assert captured == {}


def test_entity_search_and_create_use_governed_proxy(monkeypatch):
    monkeypatch.setattr(runtime.inspect_service, "list_entities", lambda **kwargs: {"entities": [{"id": "e1"}]})
    monkeypatch.setattr(runtime.inspect_service, "create_entity", lambda payload: {"id": "e2", **payload})
    assert _client().get("/api/entities", params={"q": "Alex"}).json()["entities"][0]["id"] == "e1"
    created = _client().post("/api/entities", json={"display_name": "Alex", "entity_type": "person"})
    assert created.status_code == 201
    assert created.json()["id"] == "e2"
