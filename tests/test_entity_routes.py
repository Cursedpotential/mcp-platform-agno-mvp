"""Governed entity HTTP and normalization contracts.

Byline: Codex · GPT-5 · 2026-08-18
"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.api import entity_routes


def _client() -> TestClient:
    app = FastAPI()
    entity_routes.register_entity_routes(app)
    return TestClient(app)


def test_entity_search_is_bounded_and_shaped(monkeypatch) -> None:
    captured = {}

    def fake_list(*, query, limit):
        captured.update(query=query, limit=limit)
        return [{"id": "entity-1", "display_name": "Alex", "entity_type": "person"}]

    monkeypatch.setattr(entity_routes, "list_entities", fake_list)
    response = _client().get("/v1/entities", params={"q": "Alex", "limit": 7})

    assert response.status_code == 200
    assert captured == {"query": "Alex", "limit": 7}
    assert response.json()["entities"][0]["id"] == "entity-1"


def test_entity_create_accepts_no_spoofed_actor(monkeypatch) -> None:
    captured = {}

    def fake_create(body):
        captured.update(body.model_dump())
        return {"id": "entity-2", **body.model_dump(), "review_status": "approved", "safe_for_legal_use": False}

    monkeypatch.setattr(entity_routes, "create_entity", fake_create)
    response = _client().post(
        "/v1/entities",
        json={"display_name": "Alex Example", "entity_type": "person", "actor": "spoofed"},
    )
    assert response.status_code == 422

    response = _client().post("/v1/entities", json={"display_name": " Alex Example ", "entity_type": "person"})
    assert response.status_code == 201
    assert captured == {"display_name": "Alex Example", "entity_type": "person"}
    assert response.json()["review_status"] == "approved"


def test_entity_type_is_closed() -> None:
    response = _client().post("/v1/entities", json={"display_name": "Alex", "entity_type": "made_up"})
    assert response.status_code == 422
