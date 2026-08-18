# Byline: Codex · GPT-5 · 2026-08-15 (Knowledge runtime boundary coverage)
# Byline: Codex · GPT-5 · 2026-08-16 (canonical item detail boundary coverage)
# Byline: Codex · GPT-5 · 2026-08-18 (native evidence horizon proxy coverage)
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
    assert captured == {
        "query": "custody",
        "case_id": "primary",
        "lane": "evidence",
        "limit": 5,
        "horizon": None,
    }


def test_search_parses_and_forwards_horizon(monkeypatch):
    captured = {}

    def fake_search(query, **kwargs):
        captured.update(query=query, **kwargs)
        return {"data": [], "meta": {"total_count": 0}}

    monkeypatch.setattr(runtime.knowledge_service, "search", fake_search)
    response = _client().get(
        "/api/knowledge/search",
        params={"q": "what was visible", "lane": "evidence", "horizon": "2025-06-01T12:30:00Z"},
    )

    assert response.status_code == 200
    assert captured["horizon"] == "2025-06-01T12:30:00+00:00"


def test_contents_requires_case_and_lane():
    response = _client().get("/api/knowledge/contents")
    assert response.status_code == 422


def test_contents_forwards_case_lane_and_pagination(monkeypatch):
    captured = {}

    def fake_list_contents(**kwargs):
        captured.update(kwargs)
        return {"data": [], "meta": {"total_count": 0}}

    monkeypatch.setattr(runtime.knowledge_service, "list_contents", fake_list_contents)
    response = _client().get(
        "/api/knowledge/contents",
        params={"case_id": "matter-7", "lane": "evidence", "limit": 10, "offset": 20},
    )

    assert response.status_code == 200
    assert captured == {"case_id": "matter-7", "lane": "evidence", "limit": 10, "offset": 20}


def test_content_detail_forwards_artifact_and_case(monkeypatch):
    captured = {}

    def fake_get_content(artifact_id, **kwargs):
        captured.update(artifact_id=artifact_id, **kwargs)
        return {"artifact_id": artifact_id, "records": []}

    monkeypatch.setattr(runtime.knowledge_service, "get_content", fake_get_content)
    response = _client().get(
        "/api/knowledge/contents/artifact-1",
        params={"case_id": "matter-9"},
    )

    assert response.status_code == 200
    assert captured == {"artifact_id": "artifact-1", "case_id": "matter-9"}


def test_content_detail_preserves_spine_not_found(monkeypatch):
    def fake_get_content(*args, **kwargs):
        raise runtime.SpineError("knowledge item not found", 404)

    monkeypatch.setattr(runtime.knowledge_service, "get_content", fake_get_content)
    response = _client().get(
        "/api/knowledge/contents/missing",
        params={"case_id": "primary"},
    )

    assert response.status_code == 404
    assert response.json()["detail"] == "knowledge item not found"


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
