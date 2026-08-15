# Byline: Codex · GPT-5 · 2026-08-15 (Knowledge runtime boundary coverage)
"""HTTP contract tests for bounded Knowledge and Graphiti query parameters."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.runtime import knowledge as runtime


def _client() -> TestClient:
    app = FastAPI()
    app.include_router(runtime.router)
    return TestClient(app)


def test_search_forwards_case_and_lane(monkeypatch):
    captured = {}

    def fake_search(query, **kwargs):
        captured.update(query=query, **kwargs)
        return {"data": [], "meta": {"total_count": 0}}

    monkeypatch.setattr(runtime.knowledge_service, "search", fake_search)
    response = _client().get(
        "/api/knowledge/search",
        params={"q": "custody", "case_id": "primary", "lane": "evidence", "limit": 5},
    )

    assert response.status_code == 200
    assert captured == {"query": "custody", "case_id": "primary", "lane": "evidence", "limit": 5}


def test_contents_requires_case_and_lane():
    response = _client().get("/api/knowledge/contents")
    assert response.status_code == 422


def test_search_rejects_unknown_lane_and_unbounded_limit():
    client = _client()
    assert client.get("/api/knowledge/search", params={"q": "x", "lane": "unknown"}).status_code == 422
    assert client.get("/api/knowledge/search", params={"q": "x", "limit": 101}).status_code == 422


def test_graphiti_rejects_unknown_kind():
    response = _client().get("/api/graphiti/search", params={"q": "x", "kind": "episodes"})
    assert response.status_code == 422


def test_graphiti_denied_group_becomes_403(monkeypatch):
    monkeypatch.setattr(
        runtime.graphiti_service,
        "search_facts",
        lambda *args, **kwargs: (_ for _ in ()).throw(ValueError("Graphiti group is not authorized")),
    )
    response = _client().get(
        "/api/graphiti/search",
        params={"q": "x", "group_id": "guessed-case"},
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Graphiti group is not authorized"
